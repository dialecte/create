"""Read a schema into its element declarations: every global of every document it reaches, and every
local declaration their content models hold - each walked once, so recursive schemas end."""
import warnings
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path

import xmlschema
from xmlschema import XMLSchemaImportWarning, XMLSchemaIncludeWarning
from xmlschema.validators import (
    XsdAnyElement,
    XsdAtomicBuiltin,
    XsdAttribute,
    XsdComplexType,
    XsdComponent,
    XsdElement,
    XsdGroup,
    XsdSimpleType,
)

from generate_next.errors import SchemaNotReadable, SchemaNotRepresentable
from generate_next.model.declarations import (
    AttributeDeclaration,
    ElementDeclaration,
    ElementParticle,
    GroupParticle,
    Namespace,
    Particle,
    Schema,
    TextDeclaration,
    WildcardParticle,
)
from generate_next.model.particles import emptiable, held_leaves
from generate_next.model.wildcards import attribute_wildcard_of, wildcard_of

def read_schema(entry: Path, *, global_attributes: list[tuple[str, str]] | None = None) -> Schema:
    """Every element declaration the schema whose entry document is `entry` makes, and the declarations of the
    global attributes asked for by (namespace, local name), those it declares."""
    schema = _load(entry)
    reader = _Reader(schema)
    # the globals of the schema's own documents - not those of the XML Schema meta-schema, whatever
    # namespace the schema's documents target
    reader.read(
        [element for _, element in sorted(schema.maps.elements.items()) if element.schema.meta_schema is not None]
    )
    return reader.schema_model(global_attributes=global_attributes or [])


def _load(entry: Path) -> xmlschema.XMLSchema:
    """The schema, read from local documents only: a document that cannot be read - out of reach, or
    remote - is an error, never a warning, never a download."""
    with warnings.catch_warnings():
        warnings.simplefilter('error', XMLSchemaImportWarning)
        warnings.simplefilter('error', XMLSchemaIncludeWarning)
        try:
            return xmlschema.XMLSchema(str(entry), allow='local')
        except (XMLSchemaImportWarning, XMLSchemaIncludeWarning) as failure:
            raise SchemaNotReadable(f'{entry}: {failure}') from failure


@dataclass
class _Reader:
    schema: xmlschema.XMLSchema
    # one entry per declaration (keyed by the xmlschema component), in the order first met
    found: dict[int, XsdElement] = field(default_factory=dict)
    parents: dict[int, set[str]] = field(default_factory=dict)
    content_models: dict[int, GroupParticle | None] = field(default_factory=dict)
    # a number per declaration, given when first met - read or named by a particle
    keys: dict[int, int] = field(default_factory=dict)
    type_keys: dict[int, int] = field(default_factory=dict)

    def key_of(self, element: XsdElement) -> int:
        return self.keys.setdefault(id(element), len(self.keys))

    def read(self, roots: list[XsdElement]) -> None:
        """Every declaration reachable from `roots`, depth first, each walked once; no recursion, so a
        schema of any depth is read. An abstract element never appears: its content is not walked."""
        pending: list[tuple[XsdElement, str | None]] = [(root, None) for root in reversed(roots)]
        while pending:
            element, parent_name = pending.pop()
            identity = id(element)
            if parent_name is not None:
                self.parents.setdefault(identity, set()).add(parent_name)
            if identity in self.found:
                continue
            self.found[identity] = element
            self.parents.setdefault(identity, set())
            content_model, declarations = (None, []) if element.abstract else self._content_of(element)
            self.content_models[identity] = content_model
            pending.extend((child, element.local_name) for child in reversed(declarations))

    def schema_model(self, *, global_attributes: list[tuple[str, str]]) -> Schema:
        elements = [element for element in self.found.values() if not element.abstract]
        element_prefixes: dict[str, set[str]] = {}
        for element in elements:
            uri = _namespace_of(element.name)
            element_prefixes.setdefault(_element_prefix(element, uri), set()).add(uri)
        prefixes = _AttributePrefixes(self.schema, element_prefixes=element_prefixes)
        declarations = tuple(
            _declaration(
                prefixes=prefixes,
                key=self.key_of(element),
                type_key=self.type_keys.setdefault(id(element.type), len(self.type_keys)),
                element=element,
                content_model=self.content_models[identity],
                parent_names=tuple(sorted(self.parents[identity])),
            )
            for identity, element in self.found.items()
            if not element.abstract
        )
        # after the elements' attributes, whose prefixes are chosen first; in the order asked
        declared = {(_namespace_of(name), attribute.local_name): attribute for name, attribute in self.schema.maps.attributes.items()}
        attributes = {name: _attribute(prefixes, declared[name]) for name in global_attributes if name in declared}
        return Schema(elements=declarations, global_attributes=attributes)

    def _content_of(self, element: XsdElement) -> tuple[GroupParticle | None, list[XsdElement]]:
        """The particle tree of the element content of `element`, and the declarations it names in
        content order: a reference resolved to its global, a substitution head standing for the choice
        among the elements that may replace it."""
        content = element.type.content if isinstance(element.type, XsdComplexType) else None
        if not isinstance(content, XsdGroup):
            return None, []
        declarations: list[XsdElement] = []

        # groups cannot be circular in XSD (only elements recurse, and `read` walks each once): this
        # recursion is as deep as the groups are nested
        # kept as written, empty groups included: an empty branch is what lets a choice hold nothing; what a
        # particle with maxOccurs 0 holds is written but never walked - no document holds it
        def group_particle(group: XsdGroup, *, held: bool) -> GroupParticle:
            held = held and group.max_occurs != 0
            particles: list[Particle] = []
            for item in group:
                if isinstance(item, XsdGroup):
                    particles.append(group_particle(item, held=held))
                elif isinstance(item, XsdAnyElement):
                    wildcard = wildcard_of(item.elem, target_namespace=item.target_namespace or '')
                    particles.append(
                        WildcardParticle(wildcard=wildcard, min_occurs=item.min_occurs, max_occurs=item.max_occurs)
                    )
                elif isinstance(item, XsdElement):
                    particles.append(element_particle(item, held=held))
                else:
                    raise SchemaNotRepresentable(f'{element.name}: a content particle of an unknown kind: {item!r}')
            return GroupParticle(
                kind=group.model, min_occurs=group.min_occurs, max_occurs=group.max_occurs, particles=tuple(particles)
            )

        def element_particle(item: XsdElement, *, held: bool) -> Particle:
            if not held or item.max_occurs == 0:
                written = item.ref if item.ref is not None else item
                return _element_particle(written, min_occurs=item.min_occurs, max_occurs=item.max_occurs, declaration=None)
            # only a reference to a global can be substituted; a local declaration is itself
            alternatives = self._with_substitutes(item.ref) if item.ref is not None else [item]
            declarations.extend(alternatives)
            if alternatives == [item.ref if item.ref is not None else item]:
                return _element_particle(
                    alternatives[0], min_occurs=item.min_occurs, max_occurs=item.max_occurs, declaration=self.key_of(alternatives[0])
                )
            # a substitution head stands for one of the elements that may replace it, per occurrence; an
            # abstract head nothing replaces is an empty choice, which nothing satisfies
            return GroupParticle(
                kind='choice',
                min_occurs=item.min_occurs,
                max_occurs=item.max_occurs,
                particles=tuple(
                    _element_particle(alternative, min_occurs=1, max_occurs=1, declaration=self.key_of(alternative))
                    for alternative in alternatives
                ),
            )

        model = group_particle(content, held=True)
        # a model that lets no element in and that nothing fails says no more than no model
        if next(held_leaves(model), None) is None and emptiable(model):
            return None, []
        return model, declarations

    def _with_substitutes(self, head: XsdElement) -> list[XsdElement]:
        """`head` (unless abstract), then every element that substitutes for it, directly or not,
        sorted by name, then namespace."""
        members: dict[int, XsdElement] = {}
        pending = list(self.schema.maps.substitution_groups.get(head.name, ()))
        while pending:
            member = pending.pop()
            if id(member) in members:
                continue
            members[id(member)] = member
            pending.extend(self.schema.maps.substitution_groups.get(member.name, ()))
        substitutes = sorted(
            (member for member in members.values() if not member.abstract), key=lambda member: (member.local_name, _namespace_of(member.name))
        )
        return substitutes if head.abstract else [head, *substitutes]


def _declaration(
    *,
    prefixes: '_AttributePrefixes',
    key: int,
    type_key: int,
    element: XsdElement,
    content_model: GroupParticle | None,
    parent_names: tuple[str, ...],
) -> ElementDeclaration:
    # an unqualified local element is in no namespace, whatever the schema targets
    uri = _namespace_of(element.name)
    namespace = Namespace(prefix=_element_prefix(element, uri), uri=uri)
    # read from the type: what the schema library keeps on a substitution member declared without a type
    # of its own is anyType's, not its head's type's
    complex_type = element.type if isinstance(element.type, XsdComplexType) else None
    attributes = tuple(
        sorted(
            (
                _attribute(prefixes, attribute)
                for name, attribute in (complex_type.attributes.items() if complex_type is not None else ())
                if name is not None and attribute.use != 'prohibited'
            ),
            key=lambda attribute: attribute.key,
        )
    )
    try:
        any_attribute = attribute_wildcard_of(complex_type) if complex_type is not None else None
    except SchemaNotRepresentable as failure:
        raise SchemaNotRepresentable(f'{element.name}: {failure}') from failure
    return ElementDeclaration(
        key=key,
        name=element.local_name,
        namespace=namespace,
        is_global=element.is_global(),
        type_name=element.type.name,
        type_key=type_key,
        block=tuple(sorted((element.block or '').split())),
        nillable=element.nillable,
        documentation=_documentation(element),
        attributes=attributes,
        any_attribute=any_attribute,
        content_model=content_model,
        text=_text(element),
        parent_names=parent_names,
    )


def _text(element: XsdElement) -> TextDeclaration | None:
    """The text the element holds: of its simple type, of its simple content, or untyped when its
    content is mixed; none for element-only or empty content. Simple content is typed even in a type
    marked mixed: the mark only matters beside elements."""
    element_type = element.type
    if isinstance(element_type, XsdComplexType):
        if element_type.has_simple_content():
            element_type = element_type.content
        elif element_type.mixed:
            return TextDeclaration(builtin=None, default=element.default, fixed=element.fixed)
        else:
            return None
    return TextDeclaration(builtin=_builtin_of(element_type), default=element.default, fixed=element.fixed)


def _element_particle(
    element: XsdElement, *, min_occurs: int, max_occurs: int | None, declaration: int | None
) -> ElementParticle:
    return ElementParticle(
        name=element.local_name,
        namespace=_namespace_of(element.name),
        min_occurs=min_occurs,
        max_occurs=max_occurs,
        declaration=declaration,
    )


def _attribute(prefixes: '_AttributePrefixes', attribute: XsdAttribute) -> AttributeDeclaration:
    """An attribute in no namespace is keyed by its bare name; any other always `prefix:local`, with
    its namespace - in XML a namespaced attribute is always written with a prefix."""
    uri = _namespace_of(attribute.name)
    local = attribute.local_name
    if not uri:
        key, namespace = local, None
    else:
        declaring = attribute.ref if attribute.ref is not None else attribute
        prefix = prefixes.of(declaring=declaring, uri=uri)
        key, namespace = f'{prefix}:{local}', Namespace(prefix=prefix, uri=uri)
    return AttributeDeclaration(
        key=key,
        namespace=namespace,
        required=attribute.use == 'required',
        default=attribute.default,
        fixed=attribute.fixed,
        builtin=_builtin_of(attribute.type),
    )


def _builtin_of(simple_type: XsdSimpleType | None) -> str | None:
    """The most specific built-in datatype a type derives from; None for a plain string, a list or a union."""
    current = simple_type
    # a list or a union has no base type: the walk ends there, without a built-in
    while current is not None and not isinstance(current, XsdAtomicBuiltin):
        current = current.base_type
    if current is None:
        return None
    return None if current.local_name == 'string' else current.local_name


def _documentation(element: XsdElement) -> str | None:
    """The first non-empty documentation of the declaration, its whole text (markup inside included)."""
    annotation = element.annotation
    for documentation in annotation.documentation if annotation is not None else ():
        text = ''.join(documentation.itertext()).strip()
        if text:
            return text
    return None


def _namespace_of(name: str | None) -> str:
    """The namespace of a Clark name (`{uri}local`), '' for an unqualified one."""
    return name[1 : name.index('}')] if name and name.startswith('{') else ''


def _element_prefix(component: XsdComponent, uri: str) -> str:
    """The prefix the declaring document gives `uri`: '' when it is that document's default namespace
    (or when it binds it to nothing)."""
    namespaces = component.schema.namespaces
    if namespaces.get('') == uri:
        return ''
    return next((prefix for prefix, namespace in namespaces.items() if prefix and namespace == uri), '')


@dataclass
class _AttributePrefixes:
    """A non-empty prefix for each attribute namespace, never one standing for another namespace - of another
    attribute, or of an element: the one the declaring document binds, else one any document of the schema binds
    (the XML namespace is always bound to `xml`), else one made up - `ns1`, `ns2`... in the order first needed,
    none a document binds."""

    schema: xmlschema.XMLSchema
    # the prefixes the elements are written with, and their namespaces
    element_prefixes: dict[str, set[str]]
    chosen: dict[str, str] = field(default_factory=dict)

    def of(self, *, declaring: XsdAttribute, uri: str) -> str:
        if uri not in self.chosen:
            self.chosen[uri] = self._first_free(declaring=declaring, uri=uri)
        return self.chosen[uri]

    def _first_free(self, *, declaring: XsdAttribute, uri: str) -> str:
        def free(prefix: str) -> bool:
            return prefix not in self.chosen.values() and self.element_prefixes.get(prefix, {uri}) <= {uri}

        documents = [declaring.schema, *(document for document in self.schema.maps.iter_schemas() if document is not declaring.schema)]
        for document in documents:
            for prefix, namespace in document.namespaces.items():
                if prefix and namespace == uri and free(prefix):
                    return prefix
        taken = {prefix for document in self.schema.maps.iter_schemas() for prefix in document.namespaces}
        return next(f'ns{number}' for number in count(1) if f'ns{number}' not in taken and free(f'ns{number}'))
