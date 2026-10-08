"""The definition data of a dialecte: the schema's declarations, keyed exactly as `definition.generated.ts`.

A tag declared more than once is the union of its declarations: what a record of that tag may carry
under some parent (an attribute is required only where every declaration requires it).
"""
from pathlib import Path
from typing import Any

from generate_next.errors import SchemaNotRepresentable
from generate_next.model.declarations import AttributeDeclaration, ElementDeclaration
from generate_next.model.read_schema import read_schema


def generate_definition(entry: Path) -> dict[str, Any]:
    """The definition data of the schema whose entry document is `entry`."""
    return build_definition(read_schema(entry))


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
    child_names: list[str] = []
    for declaration in declarations:
        child_names.extend(name for name in declaration.child_names if name not in child_names)
    # an edge gets details once there is something to say about it (its declaration, its constraints)
    element['children'] = {'sequence': child_names, 'details': {}}
    return element


def _attributes(declarations: list[ElementDeclaration]) -> dict[str, Any]:
    keys = sorted({attribute.key for declaration in declarations for attribute in declaration.attributes})
    details: dict[str, Any] = {}
    for key in keys:
        found = [
            next((attribute for attribute in declaration.attributes if attribute.key == key), None)
            for declaration in declarations
        ]
        carried = [attribute for attribute in found if attribute is not None]
        namespaces = {attribute.namespace for attribute in carried}
        if len(namespaces) > 1:
            raise SchemaNotRepresentable(
                f'{declarations[0].name}: the attribute {key} is in a different namespace in each declaration of the tag'
            )
        details[key] = _attribute(carried, everywhere=None not in found)
    attributes: dict[str, Any] = {'sequence': keys}
    wildcards = [declaration.any_attribute for declaration in declarations if declaration.any_attribute is not None]
    if wildcards:
        attributes['any'] = True
        attributes['anyNamespace'] = sorted({namespace for wildcard in wildcards for namespace in wildcard})
    attributes['details'] = details
    return attributes


def _attribute(attributes: list[AttributeDeclaration], *, everywhere: bool) -> dict[str, Any]:
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
