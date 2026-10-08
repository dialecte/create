"""Sidecar files next to the entry document: what a dialecte knows that its schema cannot say.

`attribute-mapping.json` names, per tag, attributes its wildcard admits that the dialecte types:
`{ "SCL": { "e:version": "namespace" } }`. Each is the schema's global declaration of that attribute, added to every
declaration of the tag under the key the definition writes it with.

`parent-mapping.json` maps an element a wildcard admits to the parents it belongs under:
`{ "ProcessResources": ["Bay", "Function"] }`. The element becomes a child of each parent named - listed
among its children, the parent among its parents - with no particle: a wildcard of the parent admits it, under
every declaration of the parent.
"""
import json
from pathlib import Path
from typing import Any

from generate_next.errors import SidecarMistake
from dataclasses import replace

from generate_next.model.declarations import AttributeDeclaration, ElementDeclaration, WildcardParticle
from generate_next.model.particles import held_leaves
from generate_next.model.wildcards import admits

PARENT_MAPPING = 'parent-mapping.json'
ATTRIBUTE_MAPPING = 'attribute-mapping.json'


def read_parent_mapping(entry: Path) -> Any:
    """The parent mapping beside `entry`, empty when there is none."""
    return _read(entry.parent / PARENT_MAPPING)


def read_attribute_mapping(entry: Path) -> Any:
    """The attribute mapping beside `entry`, empty when there is none."""
    return _read(entry.parent / ATTRIBUTE_MAPPING)


def _read(sidecar: Path) -> Any:
    return json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else {}


def mapped_attribute_names(mapping: Any) -> list[tuple[str, str]]:
    """The (namespace, local name) of each attribute the mapping names, in its order; a mapping of the wrong shape
    is refused."""
    if not isinstance(mapping, dict):
        raise SidecarMistake(f'{ATTRIBUTE_MAPPING}: it must be an object mapping each tag to its attributes')
    names: list[tuple[str, str]] = []
    for tag, attributes in mapping.items():
        if not isinstance(attributes, dict) or not all(isinstance(uri, str) for uri in attributes.values()):
            raise SidecarMistake(f'{ATTRIBUTE_MAPPING}: {tag} must map to an object of attribute keys and namespaces')
        names.extend((uri, key.split(':', 1)[-1]) for key, uri in attributes.items())
    return names


def attach_mapped_attributes(
    declarations: tuple[ElementDeclaration, ...],
    mapping: Any,
    *,
    global_attributes: dict[tuple[str, str], AttributeDeclaration],
) -> tuple[ElementDeclaration, ...]:
    """`declarations` with each mapped attribute added to every declaration of its tag that does not declare it.
    Refused as a mistake: a tag or a global attribute the schema does not declare, a key the definition does not
    write that attribute with, an attribute every declaration of the tag already declares, a declaration lacking
    it whose wildcard does not admit it."""
    mapped_attribute_names(mapping)
    added: dict[str, list[AttributeDeclaration]] = {}
    tags = {declaration.name for declaration in declarations}
    for tag, attributes in mapping.items():
        if tag not in tags:
            raise SidecarMistake(f'{ATTRIBUTE_MAPPING}: the schema declares no element {tag}')
        for key, uri in attributes.items():
            attribute = global_attributes.get((uri, key.split(':', 1)[-1]))
            if attribute is None:
                raise SidecarMistake(f'{ATTRIBUTE_MAPPING}: the schema declares no global attribute {key} in {uri!r}')
            if attribute.key != key:
                raise SidecarMistake(f'{ATTRIBUTE_MAPPING}: {key} is written {attribute.key} in the definition')
            if all(_declares(declaration, attribute) for declaration in declarations if declaration.name == tag):
                raise SidecarMistake(f'{ATTRIBUTE_MAPPING}: {tag} already declares {key}')
            added.setdefault(tag, []).append(attribute)
    return tuple(
        _with_attributes(declaration, added[declaration.name]) if declaration.name in added else declaration
        for declaration in declarations
    )


def _with_attributes(declaration: ElementDeclaration, attributes: list[AttributeDeclaration]) -> ElementDeclaration:
    missing = [attribute for attribute in attributes if not _declares(declaration, attribute)]
    for attribute in missing:
        uri = attribute.namespace.uri if attribute.namespace is not None else ''
        if declaration.any_attribute is None or not admits(declaration.any_attribute, uri):
            raise SidecarMistake(f'{ATTRIBUTE_MAPPING}: a declaration of {declaration.name} admits no attribute {attribute.key}')
    return replace(declaration, attributes=(*declaration.attributes, *missing))


def _declares(declaration: ElementDeclaration, attribute: AttributeDeclaration) -> bool:
    return any(declared.key == attribute.key for declared in declaration.attributes)


def mapped_parents(mapping: Any) -> dict[str, list[str]]:
    """The parent mapping, each element to the parents it is attached under; a mapping of the wrong shape is
    refused."""
    if not isinstance(mapping, dict):
        raise SidecarMistake(f'{PARENT_MAPPING}: it must be an object mapping each element to its parents')
    for child, parents in mapping.items():
        if not isinstance(parents, list) or not all(isinstance(parent, str) for parent in parents):
            raise SidecarMistake(f'{PARENT_MAPPING}: {child} must map to a list of parent names')
    return mapping


def attach_mapped_children(
    definition: dict[str, Any], mapping: Any, *, declarations: tuple[ElementDeclaration, ...]
) -> dict[str, Any]:
    """`definition` with each mapped element listed under the parents the mapping names. Refused as a
    mistake: a name the schema does not declare - element or parent -, a parent named twice or already holding
    the element, a parent one declaration of which admits no such element, a mapping that leaves no root."""
    mapping = mapped_parents(mapping)
    by_tag: dict[str, list[ElementDeclaration]] = {}
    for declaration in declarations:
        by_tag.setdefault(declaration.name, []).append(declaration)
    for child, parents in mapping.items():
        unknown = [name for name in [child, *parents] if name not in definition]
        if unknown:
            raise SidecarMistake(f'{PARENT_MAPPING}: the schema declares no element {", ".join(unknown)}')
        if len(set(parents)) < len(parents):
            raise SidecarMistake(f'{PARENT_MAPPING}: {child} names a parent twice: {", ".join(parents)}')
        uri = definition[child]['namespace']['uri']
        is_global = any(declaration.is_global for declaration in by_tag[child])
        for parent in parents:
            if child in definition[parent]['children']['sequence']:
                raise SidecarMistake(f'{PARENT_MAPPING}: {parent} already holds {child}')
            if not all(_admits(declaration, uri=uri, is_global=is_global) for declaration in by_tag[parent]):
                raise SidecarMistake(
                    f'{PARENT_MAPPING}: the content of {parent} admits no {child} where it is declared '
                    '(no wildcard of its namespace, or only strict ones and no global declaration of it)'
                )
    attached = {tag: dict(element) for tag, element in definition.items()}
    for child in sorted(mapping):
        attached[child]['parents'] = sorted({*attached[child]['parents'], *mapping[child]})
        for parent in mapping[child]:
            # under the tag level, and under each way the parent is declared
            attached[parent] = _holding(attached[parent], child)
            if 'declarations' in attached[parent]:
                attached[parent]['declarations'] = {
                    number: _holding(declared, child) for number, declared in attached[parent]['declarations'].items()
                }
    # a document starts with an element no other holds (itself excepted): a mapping may not take the last
    # one away
    if mapping and not any(set(element['parents']) <= {tag} for tag, element in attached.items()):
        raise SidecarMistake(f'{PARENT_MAPPING}: it leaves no element without a parent, so no document root')
    return attached


def _holding(element: dict[str, Any], child: str) -> dict[str, Any]:
    """`element` with `child` listed last among its children."""
    children = element['children']
    return {**element, 'children': {**children, 'sequence': [*children['sequence'], child]}}


def _admits(parent: ElementDeclaration, *, uri: str, is_global: bool) -> bool:
    """Whether a wildcard a document may hold in the content of `parent` admits an element of `uri`: a strict
    one only an element declared globally, the declaration it asks for."""
    return any(
        admits(leaf.wildcard, uri) and (leaf.wildcard.process_contents != 'strict' or is_global)
        for leaf in held_leaves(parent.content_model)
        if isinstance(leaf, WildcardParticle)
    )
