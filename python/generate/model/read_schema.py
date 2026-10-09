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
    XsdIdentity,
    XsdKey,
    XsdKeyref,
    XsdSimpleType,
    XsdUnique,
)
from xmlschema.validators.xsdbase import XsdType

from generate.errors import SchemaNotReadable, SchemaNotRepresentable
from generate.model.declarations import (
    AttributeDeclaration,
    ElementDeclaration,
    ElementParticle,
    GroupParticle,
    IdentityConstraint,
    Namespace,
    Particle,
    Schema,
    TextDeclaration,
    TypeDefinition,
    Wildcard,
    WildcardParticle,
)
from generate.model.datatypes import datatype_of
from generate.model.identity_paths import parse_field, parse_selector
from generate.model.particles import emptiable, held_leaves
from generate.model.wildcards import attribute_wildcard_of, wildcard_of
from generate.model.names import sorted_names

ANY_TYPE = '{http://www.w3.org/2001/XMLSchema}anyType'
ANY_SIMPLE_TYPE = '{http://www.w3.org/2001/XMLSchema}anySimpleType'
# built-in types the schema library makes inside a schema it loads (one importing the XML namespace) rather than
# leaving them to its meta-schema: built-ins all the same, never a schema's own type
_MADE_BY_THE_LIBRARY = frozenset({ANY_SIMPLE_TYPE, '{http://www.w3.org/2001/XMLSchema}anyAtomicType'})


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
            schema = xmlschema.XMLSchema(str(entry), allow='local')
        except (XMLSchemaImportWarning, XMLSchemaIncludeWarning) as failure:
            raise SchemaNotReadable(f'{entry}: {failure}') from failure
    _give_members_their_head_type(schema)
    return schema


def _give_members_their_head_type(schema: xmlschema.XMLSchema) -> None:
    """A global element that names no type and declares none has its substitution group head's type. The schema
    library gives it anyType when the head blocks substitution; libxml2, like the specification, the head's."""
    resolved: set[int] = set()

    def resolve(element: XsdElement) -> None:
        if id(element) in resolved:
            return
        resolved.add(id(element))
        head_name = element.elem.get('substitutionGroup')
        if head_name is None:
            return
        head = schema.maps.elements[element.schema.resolve_qname(head_name)]
        resolve(head)
        # in a valid schema a member has anyType, where its head has another type, only when it names none
        if element.type.name == ANY_TYPE:
            element.type = head.type

    # the meta-schema's elements are shared by every schema read: left as they are
    for element in list(schema.maps.elements.values()):
        if element.schema.meta_schema is not None:
            resolve(element)


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
    # per declaration, the types it admits with xsi:type; each type once, with its particle tree and declarations
    variants: dict[int, list[XsdType]] = field(default_factory=dict)
    type_contents: dict[int, tuple[GroupParticle | None, list[XsdElement]]] = field(default_factory=dict)
    variant_types: dict[int, XsdType] = field(default_factory=dict)
    _admitted: dict[tuple[int, frozenset[str]], list[XsdType]] = field(default_factory=dict)
    _derived_from: dict[int | str, list[XsdType]] | None = None
    # the global elements naming each head (Clark name) in their substitutionGroup, read from the documents: the
    # schema library forgets the affiliation of a member whose head blocks substitution
    _members_of: dict[str, list[XsdElement]] | None = None
    # the elements of anyType through whose variants a declaration is reached: its parents when it has no other
    through_any_type: dict[int, set[str]] = field(default_factory=dict)

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
            content_model, declarations = (None, []) if element.abstract else self._content_of(element.type, owner=element.name)
            self.content_models[identity] = content_model
            held = [(child, element.local_name) for child in declarations]
            # what the element may hold with xsi:type naming another type is walked too; an element of anyType holds
            # any element already, so its variants give it no child of their own - only a parent to a declaration
            # nothing else holds
            variants = [] if element.abstract else self._variants_of(element)
            of_any_type = element.type.name == ANY_TYPE
            for variant in variants:
                if id(variant) not in self.type_contents:
                    self.type_contents[id(variant)] = self._content_of(variant, owner=variant.name)
                    self.variant_types[id(variant)] = variant
                for child in self.type_contents[id(variant)][1]:
                    if of_any_type:
                        self.through_any_type.setdefault(id(child), set()).add(element.local_name)
                    held.append((child, None if of_any_type else element.local_name))
            self.variants[identity] = variants
            pending.extend(reversed(held))

    def _variants_of(self, element: XsdElement) -> list[XsdType]:
        """The named types of the schema an instance of `element` may name with xsi:type instead of its declared
        type: validly derived from it by no step the element or the type blocks (the schema's blockDefault
        included), not abstract - as libxml2 reads xsi:type. Built-in types are left out (a reader knows their
        hierarchy)."""
        declared = element.type
        blocked = _derivations(element.block) | _derivations(getattr(declared, 'block', ''))
        cache_key = (id(declared), blocked)
        if cache_key not in self._admitted:
            admitted = [
                candidate
                for candidate in self._candidates(declared)
                if not candidate.abstract and self._validly_derived(candidate, declared, blocked=blocked)
            ]
            self._admitted[cache_key] = sorted(admitted, key=lambda variant: variant.name)
        return self._admitted[cache_key]

    def _validly_derived(self, derived: XsdType, base: XsdType, *, blocked: frozenset[str]) -> bool:
        """XSD's type derivation rule: `derived` is `base`, or each step up to it is a derivation not blocked - a
        simple type's always a restriction -, a simple type derived from a member counting as derived from the
        union."""
        if _base_key(derived) == _base_key(base):
            return True
        if _method_of(derived) in blocked:
            return False
        step = self._base_of(derived)
        if step is not None and self._validly_derived(step, base, blocked=blocked):
            return True
        return isinstance(derived, XsdSimpleType) and any(
            self._validly_derived(derived, member, blocked=blocked) for member in _union_members(base)
        )

    def _candidates(self, declared: XsdType) -> list[XsdType]:
        """The named types that may derive from `declared`: those with it among their bases - a list or a union
        derives from anySimpleType, never from its item or members (libxml2 refuses a list of A for an A, the
        schema library takes it) -, and, for a union, its members, theirs, and what derives from them. The bases
        are indexed once; what blocks a step is checked after."""
        if self._derived_from is None:
            self._derived_from = {}
            for candidate in self.schema.maps.types.values():
                if _built_in(candidate):
                    continue
                base = self._base_of(candidate)
                while base is not None:
                    self._derived_from.setdefault(_base_key(base), []).append(candidate)
                    base = self._base_of(base)
        candidates = list(self._derived_from.get(_base_key(declared), []))
        pending = list(_union_members(declared))
        while pending:
            member = pending.pop()
            if member.name is not None and not _built_in(member):
                candidates.append(member)
            candidates.extend(self._derived_from.get(_base_key(member), []))
            pending.extend(_union_members(member))
        return list(dict.fromkeys(candidates))

    def _base_of(self, xsd_type: XsdType) -> XsdType | None:
        """The type `xsd_type` derives from; none for anyType. The schema library gives a list, a union and a
        primitive built-in no base - each derives from anySimpleType -, nor a complex type deriving from nothing
        it names - which restricts anyType."""
        if xsd_type.base_type is not None and xsd_type.base_type is not xsd_type:
            return xsd_type.base_type
        if _base_key(xsd_type) == ANY_TYPE:
            return None
        if isinstance(xsd_type, XsdSimpleType) and _base_key(xsd_type) != ANY_SIMPLE_TYPE:
            return self.schema.maps.types[ANY_SIMPLE_TYPE]
        return self.schema.maps.types[ANY_TYPE]

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
                parent_names=sorted_names(self.parents[identity] or self.through_any_type.get(identity, ())),
                variants=tuple(variant.name for variant in self.variants[identity]),
            )
            for identity, element in self.found.items()
            if not element.abstract
        )
        # after the elements' attributes, whose prefixes are chosen first; in the order asked
        declared = {(_namespace_of(name), attribute.local_name): attribute for name, attribute in self.schema.maps.attributes.items()}
        attributes = {name: _attribute(prefixes, declared[name]) for name in global_attributes if name in declared}
        types = tuple(
            _type_definition(prefixes=prefixes, xsd_type=variant, content_model=self.type_contents[identity][0])
            for identity, variant in sorted(self.variant_types.items(), key=lambda item: item[1].name)
        )
        return Schema(elements=declarations, global_attributes=attributes, types=types)

    def _content_of(self, xsd_type: XsdType, *, owner: str) -> tuple[GroupParticle | None, list[XsdElement]]:
        """The particle tree of the element content a type gives, and the declarations it names in content
        order: a reference resolved to its global, a substitution head standing for the choice among the
        elements that may replace it."""
        content = xsd_type.content if isinstance(xsd_type, XsdComplexType) else None
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
                    raise SchemaNotRepresentable(f'{owner}: a content particle of an unknown kind: {item!r}')
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
        """`head` (unless abstract), then every element that substitutes for it, directly or not, sorted by name,
        then namespace (Substitution Group OK (Transitive)). Only the head's element-level blocking counts: no member
        when it blocks substitution, and a member blocking substitution itself still has its own members stand for
        the head. A member's type must derive from the head's by no method the head blocks (its `block`, the
        schema's blockDefault included), the head's type blocks, or a type between them blocks - every step checked
        (libxml2 misses an extension step below a restriction step)."""
        if 'substitution' in (head.block or '').split():
            return [] if head.abstract else [head]
        blocked = _derivations(head.block) | _derivations(getattr(head.type, 'block', ''))
        # an element names one head and the library refuses a circular group: the members form a tree, each met once
        members: list[XsdElement] = []
        pending = list(self._members_named(head))
        while pending:
            member = pending.pop()
            members.append(member)
            pending.extend(self._members_named(member))
        substitutes = sorted(
            (
                member
                for member in members
                if not member.abstract
                and self._validly_derived(member.type, head.type, blocked=blocked | self._blocked_between(member.type, head.type))
            ),
            key=lambda member: (member.local_name, _namespace_of(member.name)),
        )
        return substitutes if head.abstract else [head, *substitutes]

    def _blocked_between(self, derived: XsdType, base: XsdType) -> frozenset[str]:
        """What the types strictly between `derived` and `base` on its derivation chain block: a member's type may not
        derive through them by those methods (Substitution Group OK (Transitive), clause 2.3)."""
        blocked: set[str] = set()
        step = self._base_of(derived)
        while step is not None and _base_key(step) != _base_key(base):
            blocked |= _derivations(getattr(step, 'block', ''))
            step = self._base_of(step)
        return frozenset(blocked)

    def _members_named(self, head: XsdElement) -> list[XsdElement]:
        """The global elements whose substitutionGroup names `head`, as their documents write it."""
        if self._members_of is None:
            self._members_of = {}
            for element in self.schema.maps.elements.values():
                affiliation = element.elem.get('substitutionGroup') if element.schema.meta_schema is not None else None
                if affiliation is not None:
                    self._members_of.setdefault(element.schema.resolve_qname(affiliation), []).append(element)
        return self._members_of.get(head.name, [])


def _base_key(xsd_type: XsdType) -> int | str:
    """How a type is found among bases: a built-in by its name (the schema library keeps several of each, an
    untyped element its own anyType), any other by identity."""
    return xsd_type.name if (xsd_type.name or '').startswith('{http://www.w3.org/2001/XMLSchema}') else id(xsd_type)


def _union_members(xsd_type: XsdType) -> tuple[XsdType, ...]:
    """The member types of a union. A restriction of one has none of its own: an instance may not name a member
    and leave the restriction's facets behind (libxml2 and the schema library refuse)."""
    return tuple(getattr(xsd_type, 'member_types', None) or ())


def _built_in(xsd_type: XsdType) -> bool:
    """A type of the meta-schema, or one the library makes inside the schema it loads: left to core, which knows
    the built-ins' hierarchy."""
    return xsd_type.schema.meta_schema is None or xsd_type.name in _MADE_BY_THE_LIBRARY


def _derivations(block: str | None) -> frozenset[str]:
    """The derivation methods a block value names (the schema library writes #all out)."""
    return frozenset((block or '').split()) & {'extension', 'restriction'}


def _method_of(xsd_type: XsdType) -> str:
    """How a type derives from its base: a complex type as it says (restriction when it says nothing - of anyType),
    a simple type always by restriction (a list and a union included)."""
    return (getattr(xsd_type, 'derivation', None) or 'restriction') if isinstance(xsd_type, XsdComplexType) else 'restriction'


def _declaration(
    *,
    prefixes: '_AttributePrefixes',
    key: int,
    type_key: int,
    element: XsdElement,
    content_model: GroupParticle | None,
    parent_names: tuple[str, ...],
    variants: tuple[str, ...],
) -> ElementDeclaration:
    # an unqualified local element is in no namespace, whatever the schema targets
    uri = _namespace_of(element.name)
    namespace = Namespace(prefix=_element_prefix(element, uri), uri=uri)
    attributes, any_attribute = _attributes_of(prefixes, element.type, owner=element.name)
    return ElementDeclaration(
        key=key,
        name=element.local_name,
        namespace=namespace,
        is_global=element.is_global(),
        type_name=element.type.name,
        type_key=type_key,
        block=sorted_names((element.block or '').split()),
        nillable=element.nillable,
        documentation=_documentation(element),
        attributes=attributes,
        any_attribute=any_attribute,
        content_model=content_model,
        text=_text(element),
        parent_names=parent_names,
        constraints=tuple(_constraint(identity) for identity in element.identities),
        variants=variants,
        abstract_type=element.type.abstract,
    )


def _type_definition(
    *, prefixes: '_AttributePrefixes', xsd_type: XsdType, content_model: GroupParticle | None
) -> TypeDefinition:
    attributes, any_attribute = _attributes_of(prefixes, xsd_type, owner=xsd_type.name)
    return TypeDefinition(
        name=xsd_type.name,
        attributes=attributes,
        any_attribute=any_attribute,
        content_model=content_model,
        text=_text_of(xsd_type, default=None, fixed=None),
    )


def _attributes_of(
    prefixes: '_AttributePrefixes', xsd_type: XsdType, *, owner: str
) -> tuple[tuple[AttributeDeclaration, ...], Wildcard | None]:
    """The attributes a type gives an element, sorted by key, and its attribute wildcard."""
    complex_type = xsd_type if isinstance(xsd_type, XsdComplexType) else None
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
        raise SchemaNotRepresentable(f'{owner}: {failure}') from failure
    return attributes, any_attribute


def _constraint(identity: XsdIdentity) -> IdentityConstraint:
    """An identity constraint as written, its paths parsed with the namespaces in scope where it is written."""
    if isinstance(identity, XsdKeyref):
        kind = 'keyref'
        refer = identity.refer if isinstance(identity.refer, str) else identity.refer.name
    elif isinstance(identity, XsdKey | XsdUnique):
        kind, refer = ('key' if isinstance(identity, XsdKey) else 'unique'), None
    else:
        raise SchemaNotRepresentable(f'{identity.name}: an identity constraint of an unknown kind')
    return IdentityConstraint(
        kind=kind,
        name=identity.local_name,
        namespace=_namespace_of(identity.name),
        refer=(_namespace_of(refer), refer[refer.index('}') + 1 :] if refer.startswith('{') else refer) if refer else None,
        selector=parse_selector(identity.selector.path, namespaces=_in_scope(identity.selector)),
        fields=tuple(parse_field(field.path, namespaces=_in_scope(field)) for field in identity.fields),
    )


def _in_scope(component: XsdComponent) -> dict[str, str]:
    """The prefixes bound where the component is written - on it or on an element around it - and `xml`, always
    bound. Not the document's: a prefix may be bound again closer to a constraint."""
    return {**(component.schema.source.get_nsmap(component.elem) or {}), 'xml': 'http://www.w3.org/XML/1998/namespace'}


def _text(element: XsdElement) -> TextDeclaration | None:
    return _text_of(element.type, default=element.default, fixed=element.fixed)


def _text_of(xsd_type: XsdType, *, default: str | None, fixed: str | None) -> TextDeclaration | None:
    """The text a type lets an element hold: of its simple type, of its simple content, or untyped when its
    content is mixed; none for element-only or empty content. Simple content is typed even in a type
    marked mixed: the mark only matters beside elements."""
    if isinstance(xsd_type, XsdComplexType):
        if xsd_type.has_simple_content():
            xsd_type = xsd_type.content
        elif xsd_type.mixed:
            return TextDeclaration(datatype=None, default=default, fixed=fixed)
        else:
            return None
    return TextDeclaration(datatype=datatype_of(xsd_type), default=default, fixed=fixed)


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
        datatype=datatype_of(attribute.type),
    )


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
