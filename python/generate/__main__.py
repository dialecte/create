"""CLI entry point: python -m generate --entry <xsd> --out-dir <dir>"""
import argparse
import sys
from pathlib import Path
from typing import Any

import xmlschema

from generate.collector import collect
from generate.deriver import (
    assign_identity_fields,
    derive_graph,
    derive_identity_fields,
    derive_root_element,
    derive_singleton_elements,
    strip_canonical_child_namespaces,
)
from generate.emitters.constants import emit_constants
from generate.emitters.definition import emit_definition
from generate.emitters.types import emit_types
from generate.example import example_facts
from generate.globals import inject_mapped_attributes, load_attr_mapping
from generate.orphans import detect_orphans, inject_orphan_parents, load_parent_mapping
from generate.xsi_type import XsiTypeExpander
def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description='Generate TypeScript definition files from XSD schemas.',
    )
    parser.add_argument(
        '--entry',
        type=Path,
        required=True,
        help='Path to the entry XSD file (e.g. IEC61850-6-100.xsd)',
    )
    parser.add_argument(
        '--out-dir',
        type=Path,
        required=True,
        help='Output directory for generated .ts files',
    )
    parser.add_argument(
        '--root',
        help='The element that starts a document, when more than one could',
    )
    args = parser.parse_args(argv)

    entry: Path = args.entry
    out_dir: Path = args.out_dir

    if not entry.exists():
        print(f'Error: XSD file not found: {entry}', file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Parse
    print(f'Loading schema: {entry}')
    schema = xmlschema.XMLSchema(str(entry))

    # Phase 2: Collect
    print('Collecting elements...')
    expander = XsiTypeExpander(schema)
    elements = collect(schema, expander=expander)
    print(f'  Found {len(elements)} elements')

    # Phase 2b: Orphan injection
    mapping = load_parent_mapping(entry)
    # The root is settled before injection: the orphans the mapping attaches are not candidates,
    # and among the others the choice is never a guess.
    root_element = derive_root_element(elements, override=args.root, exclude=set(mapping))

    orphans_injected = 0
    unmapped_count = 0
    if mapping:
        orphans = detect_orphans(elements, root_element)
        if orphans:
            unmapped = inject_orphan_parents(elements, mapping, root_name=root_element)
            orphans_injected = len(orphans) - len(unmapped)
            unmapped_count = len(unmapped)
            for name in unmapped:
                print(f'  WARNING: unmapped orphan element: {name}', file=sys.stderr)

    # Phase 2b': Homonyms - one name, several declarations. Merged by union, and said out loud.
    # The parents concerned are those holding a declaration of their own, every one of them.
    homonyms = sorted(name for name, e in elements.items() if e.definitions_by_parent)
    for name in homonyms:
        print(
            f"  WARNING: {name!r} is declared with different content under: "
            + ', '.join(sorted(elements[name].definitions_by_parent))
            + ' - its definition is the union of those declarations',
            file=sys.stderr,
        )

    # Phase 2c: Mapped attribute injection (attribute-mapping.json sidecar)
    attr_mapping = load_attr_mapping(entry)
    mapped_attrs_injected = inject_mapped_attributes(schema, elements, attr_mapping)
    if mapped_attrs_injected:
        print(f'  Mapped attributes injected: {mapped_attrs_injected}')

    # Phase 3: Derive
    print('Deriving graphs...')
    strip_canonical_child_namespaces(elements)
    descendants, ancestors = derive_graph(elements)
    singleton_elements = derive_singleton_elements(elements, root_element)
    assign_identity_fields(elements, derive_identity_fields(elements))
    print(f'  Root: {root_element}')
    print(f'  Singletons: {len(singleton_elements)}')

    # Phase 4: Emit
    def_path = out_dir / 'definition.generated.ts'
    const_path = out_dir / 'constants.generated.ts'
    types_path = out_dir / 'types.generated.ts'

    print('Emitting files...')
    emit_definition(elements, def_path)
    emit_constants(elements, descendants, ancestors, root_element, singleton_elements, const_path)
    emit_types(elements, types_path)

    print(f'  {def_path}')
    print(f'  {const_path}')
    print(f'  {types_path}')
    warnings = f', {unmapped_count} unmapped warnings' if unmapped_count else ', 0 unmapped warnings'
    counted_homonyms = f', {len(homonyms)} homonym{"s" if len(homonyms) != 1 else ""}'
    print(f'Done. {len(elements)} elements, {orphans_injected} orphans injected{warnings}{counted_homonyms}, ROOT={root_element}')

    # what a scaffold writes its worked example with
    return example_facts(elements, root_element)
if __name__ == '__main__':
    main()
