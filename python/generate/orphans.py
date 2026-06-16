"""Orphan element detection and parent injection from a JSON sidecar mapping.

Inserted between Collect and Derive phases. Handles XSD global elements that
are children-via-xs:any wildcards (e.g. IEC 61850-6-100 extension elements)
whose parent-child relationships are domain knowledge, not XSD-declared.
"""
import json
from pathlib import Path

from generate.ir import ChildDef, ElementDef


def load_parent_mapping(entry_path: Path) -> dict[str, list[str]]:
    """Read parent-mapping.json from the same directory as the entry XSD.

    Returns empty dict if the file does not exist.
    """
    mapping_file = entry_path.parent / 'parent-mapping.json'
    if not mapping_file.exists():
        return {}
    with open(mapping_file) as f:
        return json.load(f)


def detect_orphans(elements: dict[str, ElementDef], root_name: str) -> list[str]:
    """Return parentless element names, excluding the root element."""
    return sorted(
        name for name, e in elements.items()
        if not e.parents and name != root_name
    )


def inject_orphan_parents(
    elements: dict[str, ElementDef],
    mapping: dict[str, list[str]],
    root_name: str = '',
) -> list[str]:
    """Inject parent-child links from the sidecar mapping.

    For each mapped orphan:
      - Sets element.parents to the mapped parent list
      - Adds element to each parent's children dict and child_sequence

    *root_name* is excluded from orphan detection.
    Returns names of orphan elements NOT covered by the mapping (for warnings).
    """
    orphan_names = {name for name, e in elements.items() if not e.parents and name != root_name}
    mapped_orphans = orphan_names & mapping.keys()
    unmapped = sorted(orphan_names - mapping.keys())

    for name in sorted(mapped_orphans):
        parents = mapping[name]

        elem = elements[name]
        valid_parents = [p for p in parents if p in elements]
        elem.parents = valid_parents

        for parent_name in valid_parents:
            parent = elements[parent_name]
            if name not in parent.children:
                parent.children[name] = ChildDef(
                    required=False,
                    min_occurs=0,
                    max_occurs=None,
                )
            if name not in parent.child_sequence:
                parent.child_sequence.append(name)

    return unmapped
