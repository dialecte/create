"""The definition data of a dialecte: the schema's declarations, keyed exactly as `definition.generated.ts`.

A tag declared more than once is the union of its declarations: what a record of that tag may carry
under some parent (an attribute is required only where every declaration requires it). A tag declared
several ways - declarations validation tells apart - also keeps each way, numbered, and every particle
holding it names the one it holds.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generate_next.model.declarations import (
    AtomicType,
    AttributeDeclaration,
    DataType,
    ListType,
    UnionType,
    ElementDeclaration,
    ElementParticle,
    FieldPath,
    GroupParticle,
    IdentityConstraint,
    NameTest,
    Particle,
    SelectorPath,
    TypeDefinition,
    TextDeclaration,
    Wildcard,
    WildcardParticle,
)
from generate_next.definition.sidecars import (
    attach_mapped_attributes,
    attach_mapped_children,
    mapped_attribute_names,
    mapped_parents,
    read_attribute_mapping,
    read_parent_mapping,
)
from generate_next.definition.identity_fields import identity_fields
from generate_next.definition.patterns import pattern_to_js
from generate_next.model.particles import held_leaves
from generate_next.model.read_schema import ANY_TYPE, read_schema
from generate_next.model.wildcards import union, weakest_process_contents


@dataclass(frozen=True)
class Generated:
    """What the generator writes: the definition (tag -> element), and the types elements may take with xsi:type
    (Clark name -> what the type lets an element hold)."""

    definition: dict[str, Any]
    types: dict[str, Any]


def generate_definition(entry: Path) -> Generated:
    """The definition data of the schema whose entry document is `entry`, with what the sidecar files
    beside it add, and its types."""
    attribute_mapping = read_attribute_mapping(entry)
    schema = read_schema(entry, global_attributes=mapped_attribute_names(attribute_mapping))
    declarations = attach_mapped_attributes(schema.elements, attribute_mapping, global_attributes=schema.global_attributes)
    parent_mapping = mapped_parents(read_parent_mapping(entry))
    generated = build_definition(declarations, parent_mapping=parent_mapping, types=schema.types)
    definition = attach_mapped_children(generated.definition, parent_mapping, declarations=declarations)
    return Generated(definition=definition, types=generated.types)


def build_definition(
    declarations: tuple[ElementDeclaration, ...],
    *,
    parent_mapping: dict[str, list[str]] | None = None,
    types: tuple[TypeDefinition, ...] = (),
) -> Generated:
    by_tag: dict[str, list[ElementDeclaration]] = {}
    for declaration in declarations:
        by_tag.setdefault(declaration.name, []).append(declaration)
    ways = {tag: _ways(tag_declarations) for tag, tag_declarations in by_tag.items()}
    # a tag declared several ways: each way numbered; particles and children details name it by its number
    numbers = {
        declaration.key: str(number)
        for tag_ways in ways.values()
        if len(tag_ways) > 1
        for number, way in enumerate(tag_ways, start=1)
        for declaration in way
    }
    identities = identity_fields(declarations, parent_mapping=parent_mapping or {}, types=types)
    variants = {variant.name: variant for variant in types}
    context = _Context(numbers=numbers, identities=identities, variants=variants)
    definition = {tag: _element(tag, by_tag[tag], ways=ways[tag], context=context) for tag in sorted(by_tag)}
    written_types = {
        name: _held([variant], holder=_namespace_of(name), context=context) for name, variant in sorted(variants.items())
    }
    return Generated(definition=definition, types=written_types)


@dataclass(frozen=True)
class _Context:
    # the number of each declaration of a tag declared several ways, by key
    numbers: dict[int, str]
    # the keys of the attributes identifying each declaration, by key
    identities: dict[int, set[str]]
    # the types elements may take with xsi:type, by Clark name
    variants: dict[str, TypeDefinition]


def _namespace_of(clark_name: str) -> str:
    return clark_name[1 : clark_name.index('}')] if clark_name.startswith('{') else ''


def _ways(declarations: list[ElementDeclaration]) -> list[list[ElementDeclaration]]:
    """The declarations of a tag grouped by what validation tells apart - namespace, type, nillable, default and
    fixed text, blocked derivations -, in a canonical order that a change elsewhere in the schema leaves alone."""
    grouped: dict[tuple[Any, ...], list[ElementDeclaration]] = {}
    for declaration in declarations:
        text = declaration.text
        same_way = (
            declaration.namespace.uri,
            declaration.type_key,
            declaration.nillable,
            text.default if text is not None else None,
            text.fixed if text is not None else None,
            declaration.block,
            tuple((constraint.namespace, constraint.name) for constraint in declaration.constraints),
        )
        grouped.setdefault(same_way, []).append(declaration)
    return sorted(grouped.values(), key=_way_order)


def _way_order(way: list[ElementDeclaration]) -> tuple[Any, ...]:
    """A global declaration first, then by namespace, type name (anonymous types last), the parents holding it,
    what else sets it apart, and what it holds; the order the schema was read in only breaks what is left of a
    tie (ways that hold the same)."""
    first = way[0]
    text = first.text

    def optional(value: str | None) -> tuple[bool, str]:
        return (value is not None, value or '')

    return (
        not any(declaration.is_global for declaration in way),
        first.namespace.uri,
        first.type_name is None,
        first.type_name or '',
        tuple(sorted({parent for declaration in way for parent in declaration.parent_names})),
        first.nillable,
        optional(text.default if text is not None else None),
        optional(text.fixed if text is not None else None),
        first.block,
        tuple((constraint.namespace, constraint.name) for constraint in first.constraints),
        tuple(attribute.key for attribute in first.attributes),
        json.dumps(_written_datatype(text.datatype), sort_keys=True) if text is not None and text.datatype is not None else '',
        tuple(leaf.name if isinstance(leaf, ElementParticle) else '*' for leaf in held_leaves(first.content_model)),
        min(declaration.key for declaration in way),
    )


def _element(
    tag: str, declarations: list[ElementDeclaration], *, ways: list[list[ElementDeclaration]], context: _Context
) -> dict[str, Any]:
    """A tag: the union of its declarations; and, when it is declared several ways, each way as it is."""
    # the namespace of the tag: its global declaration's, else the first one met
    canonical = next((declaration for declaration in declarations if declaration.is_global), declarations[0])
    element: dict[str, Any] = {'tag': tag, **_heading(declarations, canonical=canonical, global_known=len(ways) == 1)}
    element['parents'] = sorted({parent for declaration in declarations for parent in declaration.parent_names})
    # the union in the declarations' canonical order: the order the schema was read in changes nothing
    element.update(_content([declaration for way in ways for declaration in way], holder=canonical.namespace.uri, context=context))
    if len(ways) > 1:
        element['declarations'] = {
            str(number): _declaration(way, context=context) for number, way in enumerate(ways, start=1)
        }
    return element


def _declaration(way: list[ElementDeclaration], *, context: _Context) -> dict[str, Any]:
    """One way a tag is declared: the element as those declarations have it."""
    canonical = next((declaration for declaration in way if declaration.is_global), way[0])
    return {
        **_heading(way, canonical=canonical, global_known=True),
        **_content(way, holder=canonical.namespace.uri, context=context),
    }


def _heading(declarations: list[ElementDeclaration], *, canonical: ElementDeclaration, global_known: bool) -> dict[str, Any]:
    heading: dict[str, Any] = {'namespace': {'prefix': canonical.namespace.prefix, 'uri': canonical.namespace.uri}}
    documentation = next((declaration.documentation for declaration in declarations if declaration.documentation), None)
    if documentation is not None:
        heading['documentation'] = documentation
    # what an element a wildcard admits is validated by; said where it is one declaration's, never of a union
    if global_known and canonical.is_global:
        heading['global'] = True
    return heading


def _content(declarations: list[ElementDeclaration], *, holder: str, context: _Context) -> dict[str, Any]:
    """What the declarations let an element hold, as one: what a record may hold under some parent."""
    content: dict[str, Any] = {}
    # nil where one declaration allows it
    if any(declaration.nillable for declaration in declarations):
        content['nillable'] = True
    # an element of anyType holds any element already: its variants' children are not listed again
    variant_types = tuple(
        context.variants[name]
        for name in dict.fromkeys(
            name for declaration in declarations if declaration.type_name != ANY_TYPE for name in declaration.variants
        )
    )
    content.update(_held(declarations, holder=holder, context=context, also=variant_types))
    identifying = sorted({key for declaration in declarations for key in context.identities.get(declaration.key, ())})
    if identifying:
        content['attributes']['identityFields'] = identifying
    # the constraints of a declaration, never of a union: they hold only where it is the one that applies
    constraints = declarations[0].constraints
    if constraints and all(declaration.constraints == constraints for declaration in declarations):
        content['constraints'] = [_written_constraint(constraint) for constraint in constraints]
    # the types an instance may name instead, said where every declaration admits the same
    variants = declarations[0].variants
    if variants and all(declaration.variants == variants for declaration in declarations):
        content['variants'] = list(variants)
    if all(declaration.abstract_type for declaration in declarations):
        content['abstractType'] = True
    return content


def _held(
    parts: list[ElementDeclaration] | list[TypeDefinition],
    *,
    holder: str,
    context: _Context,
    also: tuple[TypeDefinition, ...] = (),
) -> dict[str, Any]:
    """The attributes, children, content model and text the parts - declarations or types - give an element; `also`
    the variant types whose children it may hold too (listed, their content model theirs)."""
    held: dict[str, Any] = {'attributes': _attributes(parts)}
    leaves = [leaf for part in parts for leaf in held_leaves(part.content_model)]
    every_leaf = leaves + [leaf for variant in also for leaf in held_leaves(variant.content_model)]
    # each child once, in content order (the variants' after); a particle no document may hold names no child
    child_names = list(dict.fromkeys(leaf.name for leaf in every_leaf if isinstance(leaf, ElementParticle)))
    children: dict[str, Any] = {'sequence': child_names}
    if any(isinstance(leaf, WildcardParticle) for leaf in every_leaf):
        children['any'] = True
    children['details'] = _child_details(every_leaf, numbers=context.numbers)
    held['children'] = children
    # one content model when every part has the same shape, written relative to the holder's namespace so parts in
    # two namespaces compare as particles; a particle names the declaration it holds only where they all hold the
    # same one
    content_models = [_particle(part.content_model, holder=holder, numbers=context.numbers) for part in parts]
    first = content_models[0]
    if first is not None and all(_shape(model) == _shape(first) for model in content_models):
        held['contentModel'] = _shared(content_models)
    texts = [part.text for part in parts if part.text is not None]
    if texts:
        held['textContent'] = _text_content(texts)
    return held


def _written_constraint(constraint: IdentityConstraint) -> dict[str, Any]:
    written: dict[str, Any] = {'kind': constraint.kind, 'name': constraint.name, 'namespace': constraint.namespace}
    if constraint.refer is not None:
        written['refer'] = {'name': constraint.refer[1], 'namespace': constraint.refer[0]}
    written['selector'] = [_written_path(path) for path in constraint.selector]
    written['fields'] = [[_written_path(path) for path in field] for field in constraint.fields]
    return written


def _written_path(path: SelectorPath | FieldPath) -> dict[str, Any]:
    written: dict[str, Any] = {'deep': True} if path.deep else {}
    written['steps'] = [_written_name_test(step) for step in path.steps]
    if isinstance(path, FieldPath) and path.attribute is not None:
        written['attribute'] = _written_name_test(path.attribute)
    return written


def _written_name_test(test: NameTest) -> dict[str, str]:
    written: dict[str, str] = {}
    if test.name is not None:
        written['name'] = test.name
    if test.namespace is not None:
        written['namespace'] = test.namespace
    return written


def _shape(particle: dict[str, Any] | None) -> Any:
    """A written particle without the declarations it names."""
    if particle is None:
        return None
    shape = {key: value for key, value in particle.items() if key not in ('declaration', 'particles')}
    if 'particles' in particle:
        shape['particles'] = [_shape(nested) for nested in particle['particles']]
    return shape


def _shared(particles: list[dict[str, Any]]) -> dict[str, Any]:
    """Particles of one shape as one: each element particle names a declaration only where all of them do."""
    first = particles[0]
    shared = {key: value for key, value in first.items() if key not in ('declaration', 'particles')}
    if 'declaration' in first and all(particle.get('declaration') == first['declaration'] for particle in particles):
        shared['declaration'] = first['declaration']
    if 'particles' in first:
        shared['particles'] = [_shared(list(nested)) for nested in zip(*(particle['particles'] for particle in particles))]
    return shared


def _child_details(leaves: list[ElementParticle | WildcardParticle], *, numbers: dict[int, str]) -> dict[str, Any]:
    """For each child declared several ways, per namespace it is held in here, the declarations its particles hold:
    one decides it; several leave it to the particle the child matches."""
    named: dict[str, dict[str, set[str]]] = {}
    for leaf in leaves:
        if isinstance(leaf, ElementParticle) and leaf.declaration in numbers:
            named.setdefault(leaf.name, {}).setdefault(leaf.namespace, set()).add(numbers[leaf.declaration])
    return {
        name: {'declarations': {uri: sorted(by_namespace[uri], key=int) for uri in sorted(by_namespace)}}
        for name, by_namespace in named.items()
    }


def _text_content(texts: list[TextDeclaration]) -> dict[str, Any]:
    """The text of a tag, across the declarations that hold text: its type, default or fixed value
    only where they all agree."""
    first = texts[0]
    text: dict[str, Any] = {}
    if first.datatype is not None and all(other.datatype == first.datatype for other in texts):
        text['type'] = _written_datatype(first.datatype)
    for name in ('default', 'fixed'):
        value = getattr(first, name)
        if value is not None and all(getattr(other, name) == value for other in texts):
            text[name] = value
    return text


def _particle(particle: Particle | None, *, holder: str, numbers: dict[int, str]) -> dict[str, Any] | None:
    """A particle as the definition writes it: `minOccurs` only when not 0, `maxOccurs` only when
    bounded; an element's namespace only when it is not the one of the element holding the model; the
    declaration it holds when its tag is declared several ways."""
    if particle is None:
        return None
    match particle:
        case ElementParticle():
            written: dict[str, Any] = {'kind': 'element', 'name': particle.name}
            if particle.namespace != holder:
                written['namespace'] = particle.namespace
        case WildcardParticle():
            written = {'kind': 'any', **_written_wildcard(particle.wildcard)}
        case GroupParticle():
            written = {'kind': particle.kind}
    if particle.min_occurs != 0:
        written['minOccurs'] = particle.min_occurs
    if particle.max_occurs is not None:
        written['maxOccurs'] = particle.max_occurs
    if isinstance(particle, ElementParticle) and particle.declaration in numbers:
        written['declaration'] = numbers[particle.declaration]
    if isinstance(particle, GroupParticle):
        written['particles'] = [_particle(nested, holder=holder, numbers=numbers) for nested in particle.particles]
    return written


def _written_wildcard(wildcard: Wildcard) -> dict[str, Any]:
    admitted = {'namespace': list(wildcard.namespace)} if wildcard.namespace is not None else {}
    excluded = {'notNamespace': list(wildcard.not_namespace)} if wildcard.not_namespace is not None else {}
    return {**admitted, **excluded, 'processContents': wildcard.process_contents}


def _attributes(declarations: list[ElementDeclaration]) -> dict[str, Any]:
    keys = sorted({attribute.key for declaration in declarations for attribute in declaration.attributes})
    details: dict[str, Any] = {}
    for key in keys:
        found = [
            next((attribute for attribute in declaration.attributes if attribute.key == key), None)
            for declaration in declarations
        ]
        # a key names one namespace: each attribute namespace has a prefix of its own
        carried = [attribute for attribute in found if attribute is not None]
        details[key] = _attribute_detail(carried, everywhere=None not in found)
    attributes: dict[str, Any] = {'sequence': keys}
    wildcards = [declaration.any_attribute for declaration in declarations if declaration.any_attribute is not None]
    if wildcards:
        # what a record of the tag may carry under some parent: processed as leniently as any declaration does
        merged = union(wildcards, process_contents=weakest_process_contents(wildcards))
        attributes['any'] = _written_wildcard(merged)
    attributes['details'] = details
    return attributes


def _attribute_detail(attributes: list[AttributeDeclaration], *, everywhere: bool) -> dict[str, Any]:
    """One attribute across the declarations that carry it: required only if every declaration of the
    tag requires it, a default, a fixed value or a type only if they all agree on it."""
    first = attributes[0]
    detail: dict[str, Any] = {}
    if everywhere and all(attribute.required for attribute in attributes):
        detail['required'] = True
    for name in ('default', 'fixed'):
        values = {getattr(attribute, name) for attribute in attributes}
        if len(values) == 1 and getattr(first, name) is not None:
            detail[name] = getattr(first, name)
    if first.namespace is not None:
        detail['namespace'] = {'prefix': first.namespace.prefix, 'uri': first.namespace.uri}
    if first.datatype is not None and all(attribute.datatype == first.datatype for attribute in attributes):
        detail['type'] = _written_datatype(first.datatype)
    return detail


_FACET_KEYS = (
    ('enumeration', 'enumeration'),
    ('pattern', 'pattern'),
    ('length', 'length'),
    ('min_length', 'minLength'),
    ('max_length', 'maxLength'),
    ('min_inclusive', 'minInclusive'),
    ('max_inclusive', 'maxInclusive'),
    ('min_exclusive', 'minExclusive'),
    ('max_exclusive', 'maxExclusive'),
    ('total_digits', 'totalDigits'),
    ('fraction_digits', 'fractionDigits'),
    ('white_space', 'whiteSpace'),
)


def _written_datatype(datatype: DataType) -> dict[str, Any]:
    """A datatype as the definition writes it: `{ builtin | list | union, facets? }`, facets only when a
    restriction adds some."""
    match datatype:
        case AtomicType():
            written: dict[str, Any] = {'builtin': datatype.builtin}
        case ListType():
            written = {'list': _written_datatype(datatype.item)}
        case UnionType():
            written = {'union': [_written_datatype(member) for member in datatype.members]}
    facets = {}
    for field, key in _FACET_KEYS:
        value = getattr(datatype.facets, field)
        if value is not None:
            facets[key] = (
                [[pattern_to_js(pattern) for pattern in level] for level in value]
                if field == 'pattern'
                else list(value) if field == 'enumeration' else value
            )
    if facets:
        written['facets'] = facets
    return written
