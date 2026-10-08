"""Sidecar files next to the entry document: what a dialecte knows that its schema cannot say.

`parent-mapping.json` maps an element a wildcard admits to the parents it belongs under:
`{ "ProcessResources": ["Bay", "Function"] }`. The element becomes a child of each parent named - listed
among its children, the parent among its parents - with no particle: a wildcard of the parent admits it, under
every declaration of the parent.
"""
import json
from pathlib import Path
from typing import Any

from generate_next.errors import SidecarMistake
from generate_next.model.declarations import ElementDeclaration, WildcardParticle
from generate_next.model.particles import held_leaves
from generate_next.model.wildcards import admits

PARENT_MAPPING = 'parent-mapping.json'


def read_parent_mapping(entry: Path) -> dict[str, list[str]]:
    """The parent mapping beside `entry`, empty when there is none."""
    mapping_file = entry.parent / PARENT_MAPPING
    if not mapping_file.exists():
        return {}
    return json.loads(mapping_file.read_text(encoding='utf-8'))


def attach_mapped_children(
    definition: dict[str, Any], mapping: Any, *, declarations: tuple[ElementDeclaration, ...]
) -> dict[str, Any]:
    """`definition` with each mapped element listed under the parents the mapping names. Refused as a
    mistake: a name the schema does not declare - element or parent -, a parent named twice or already holding
    the element, a parent one declaration of which admits no such element, a mapping that leaves no root."""
    if not isinstance(mapping, dict):
        raise SidecarMistake(f'{PARENT_MAPPING}: it must be an object mapping each element to its parents')
    by_tag: dict[str, list[ElementDeclaration]] = {}
    for declaration in declarations:
        by_tag.setdefault(declaration.name, []).append(declaration)
    for child, parents in mapping.items():
        if not isinstance(parents, list) or not all(isinstance(parent, str) for parent in parents):
            raise SidecarMistake(f'{PARENT_MAPPING}: {child} must map to a list of parent names')
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
    attached = {tag: {**element, 'children': {**element['children']}} for tag, element in definition.items()}
    for child in sorted(mapping):
        attached[child]['parents'] = sorted({*attached[child]['parents'], *mapping[child]})
        for parent in mapping[child]:
            attached[parent]['children']['sequence'] = [*attached[parent]['children']['sequence'], child]
    # a document starts with an element no other holds (itself excepted): a mapping may not take the last
    # one away
    if mapping and not any(set(element['parents']) <= {tag} for tag, element in attached.items()):
        raise SidecarMistake(f'{PARENT_MAPPING}: it leaves no element without a parent, so no document root')
    return attached


def _admits(parent: ElementDeclaration, *, uri: str, is_global: bool) -> bool:
    """Whether a wildcard a document may hold in the content of `parent` admits an element of `uri`: a strict
    one only an element declared globally, the declaration it asks for."""
    return any(
        admits(leaf.wildcard, uri) and (leaf.wildcard.process_contents != 'strict' or is_global)
        for leaf in held_leaves(parent.content_model)
        if isinstance(leaf, WildcardParticle)
    )
