"""Read a schema into its element declarations: every global of every document it reaches, and every
local declaration their content models hold - each walked once, so recursive schemas end."""
import warnings
from dataclasses import dataclass, field
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
from generate_next.model.declarations import AttributeDeclaration, ElementDeclaration, Namespace

def read_schema(entry: Path) -> tuple[ElementDeclaration, ...]:
    """Every element declaration the schema whose entry document is `entry` makes."""
    schema = _load(entry)
    reader = _Reader(schema)
    # the globals of the schema's own documents - not those of the XML Schema meta-schema, whatever
    # namespace the schema's documents target
    reader.read(
        [element for _, element in sorted(schema.maps.elements.items()) if element.schema.meta_schema is not None]
    )
    return reader.declarations()


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
    children: dict[int, list[str]] = field(default_factory=dict)

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
            content = [] if element.abstract else self._declarations_in_content(element)
            self.children[identity] = [child.local_name for child in content]
            pending.extend((child, element.local_name) for child in reversed(content))

    def declarations(self) -> tuple[ElementDeclaration, ...]:
        return tuple(
            _declaration(
                schema=self.schema,
                element=element,
                child_names=tuple(self.children[identity]),
                parent_names=tuple(sorted(self.parents[identity])),
            )
            for identity, element in self.found.items()
            if not element.abstract
        )

    def _declarations_in_content(self, element: XsdElement) -> list[XsdElement]:
        """The element declarations the content of `element` holds, in content order: a reference
        resolved to its global, with the elements that substitute for that global."""
        content = element.type.content if isinstance(element.type, XsdComplexType) else None
        if not isinstance(content, XsdGroup):
            return []
        found: list[XsdElement] = []

        # groups cannot be circular in XSD: only elements recurse, and `read` walks each once
        def walk(group: XsdGroup) -> None:
            for particle in group:
                if isinstance(particle, XsdGroup):
                    walk(particle)
                elif isinstance(particle, XsdAnyElement):
                    continue  # a wildcard names no element
                elif isinstance(particle, XsdElement):
                    # only a reference to a global can be substituted; a local declaration is itself
                    found.extend(self._with_substitutes(particle.ref) if particle.ref is not None else [particle])
                else:
                    raise SchemaNotRepresentable(f'{element.name}: a content particle of an unknown kind: {particle!r}')

        walk(content)
        return found

    def _with_substitutes(self, head: XsdElement) -> list[XsdElement]:
        """`head` (unless abstract), then every element that substitutes for it, directly or not,
        sorted by name."""
        members: dict[int, XsdElement] = {}
        pending = list(self.schema.maps.substitution_groups.get(head.name, ()))
        while pending:
            member = pending.pop()
            if id(member) in members:
                continue
            members[id(member)] = member
            pending.extend(self.schema.maps.substitution_groups.get(member.name, ()))
        substitutes = sorted(
            (member for member in members.values() if not member.abstract), key=lambda member: member.local_name
        )
        return substitutes if head.abstract else [head, *substitutes]


def _declaration(
    *,
    schema: xmlschema.XMLSchema,
    element: XsdElement,
    child_names: tuple[str, ...],
    parent_names: tuple[str, ...],
) -> ElementDeclaration:
    # an unqualified local element is in no namespace, whatever the schema targets
    uri = _namespace_of(element.name)
    namespace = Namespace(prefix=_element_prefix(element, uri), uri=uri)
    attributes = tuple(
        sorted(
            (
                _attribute(schema, attribute)
                for name, attribute in element.attributes.items()
                if name is not None and attribute.use != 'prohibited'
            ),
            key=lambda attribute: attribute.key,
        )
    )
    # a wildcard that admits no namespace at all (what a restriction leaves of one) is no wildcard
    wildcard = element.attributes.get(None)
    any_attribute = tuple(wildcard.namespace) if wildcard is not None and wildcard.namespace else None
    return ElementDeclaration(
        name=element.local_name,
        namespace=namespace,
        is_global=element.is_global(),
        documentation=_documentation(element),
        attributes=attributes,
        any_attribute=any_attribute,
        child_names=child_names,
        parent_names=parent_names,
    )


def _attribute(schema: xmlschema.XMLSchema, attribute: XsdAttribute) -> AttributeDeclaration:
    """An attribute in no namespace is keyed by its bare name; any other always `prefix:local`, with
    its namespace - in XML a namespaced attribute is always written with a prefix."""
    uri = _namespace_of(attribute.name)
    local = attribute.local_name
    if not uri:
        key, namespace = local, None
    else:
        declaring = attribute.ref if attribute.ref is not None else attribute
        prefix = _attribute_prefix(schema=schema, declaring=declaring, uri=uri)
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
    return None if current.local_name in ('string', 'anySimpleType') else current.local_name


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
    if not uri:
        return ''
    namespaces = component.schema.namespaces
    if namespaces.get('') == uri:
        return ''
    return next((prefix for prefix, namespace in namespaces.items() if prefix and namespace == uri), '')


def _attribute_prefix(*, schema: xmlschema.XMLSchema, declaring: XsdAttribute, uri: str) -> str:
    """A non-empty prefix for an attribute's namespace: the one the declaring document binds, else one
    any document of the schema binds (the XML namespace is always bound to `xml`)."""
    documents = [declaring.schema, *(document for document in schema.maps.iter_schemas() if document is not declaring.schema)]
    for document in documents:
        prefix = next((prefix for prefix, namespace in document.namespaces.items() if prefix and namespace == uri), None)
        if prefix is not None:
            return prefix
    raise SchemaNotRepresentable(f'{declaring.name}: no document of the schema gives its namespace a prefix')
