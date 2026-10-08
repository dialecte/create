"""The definition data of a dialecte: the schema's declarations, keyed exactly as `definition.generated.ts`.

A tag declared more than once is the union of its declarations: what a record of that tag may carry
under some parent (an attribute is required only where every declaration requires it).
"""
from pathlib import Path
from typing import Any

from generate_next.model.declarations import (
    AttributeDeclaration,
    ElementDeclaration,
    ElementParticle,
    GroupParticle,
    Particle,
    TextDeclaration,
    Wildcard,
    WildcardParticle,
)
from generate_next.definition.sidecars import attach_mapped_children, read_parent_mapping
from generate_next.model.particles import held_leaves
from generate_next.model.read_schema import read_schema
from generate_next.model.wildcards import union, weakest_process_contents


def generate_definition(entry: Path) -> dict[str, Any]:
    """The definition data of the schema whose entry document is `entry`, with what the sidecar files
    beside it add."""
    declarations = read_schema(entry)
    return attach_mapped_children(build_definition(declarations), read_parent_mapping(entry), declarations=declarations)


def build_definition(declarations: tuple[ElementDeclaration, ...]) -> dict[str, Any]:
    by_tag: dict[str, list[ElementDeclaration]] = {}
    for declaration in declarations:
        by_tag.setdefault(declaration.name, []).append(declaration)
    return {tag: _element(tag, by_tag[tag]) for tag in sorted(by_tag)}


def _element(tag: str, declarations: list[ElementDeclaration]) -> dict[str, Any]:
    # the namespace of the tag: its global declaration's, else the first one met
    canonical = next((declaration for declaration in declarations if declaration.is_global), declarations[0])
    element: dict[str, Any] = {
        'tag': tag,
        'namespace': {'prefix': canonical.namespace.prefix, 'uri': canonical.namespace.uri},
    }
    documentation = next((declaration.documentation for declaration in declarations if declaration.documentation), None)
    if documentation is not None:
        element['documentation'] = documentation
    element['parents'] = sorted({parent for declaration in declarations for parent in declaration.parent_names})
    element['attributes'] = _attributes(declarations)
    leaves = [leaf for declaration in declarations for leaf in held_leaves(declaration.content_model)]
    # each child once, in content order; a particle no document may hold names no child
    child_names = list(dict.fromkeys(leaf.name for leaf in leaves if isinstance(leaf, ElementParticle)))
    children: dict[str, Any] = {'sequence': child_names}
    if any(isinstance(leaf, WildcardParticle) for leaf in leaves):
        children['any'] = True
    # an edge gets details once there is something to say about it (its declaration, its constraints)
    children['details'] = {}
    element['children'] = children
    # one content model when every declaration agrees on it; each parent's own comes with its edge
    # written relative to the tag's own namespace, so declarations in two namespaces compare as particles
    content_models = [
        _particle(declaration.content_model, holder=canonical.namespace.uri) for declaration in declarations
    ]
    if content_models[0] is not None and all(model == content_models[0] for model in content_models):
        element['contentModel'] = content_models[0]
    texts = [declaration.text for declaration in declarations if declaration.text is not None]
    if texts:
        element['textContent'] = _text_content(texts)
    return element


def _text_content(texts: list[TextDeclaration]) -> dict[str, Any]:
    """The text of a tag, across the declarations that hold text: its type, default or fixed value
    only where they all agree."""
    first = texts[0]
    text: dict[str, Any] = {}
    if first.builtin is not None and all(other.builtin == first.builtin for other in texts):
        text['type'] = {'builtin': first.builtin}
    for name in ('default', 'fixed'):
        value = getattr(first, name)
        if value is not None and all(getattr(other, name) == value for other in texts):
            text[name] = value
    return text


def _particle(particle: Particle | None, *, holder: str) -> dict[str, Any] | None:
    """A particle as the definition writes it: `minOccurs` only when not 0, `maxOccurs` only when
    bounded; an element's namespace only when it is not the one of the element holding the model."""
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
    if isinstance(particle, GroupParticle):
        written['particles'] = [_particle(nested, holder=holder) for nested in particle.particles]
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
    builtins = {attribute.builtin for attribute in attributes}
    if len(builtins) == 1 and first.builtin is not None:
        detail['type'] = {'builtin': first.builtin}
    return detail
