"""CLI entry point: python -m generate --entry <xsd> --out-dir <dir>"""
import argparse
import sys
from pathlib import Path

import xmlschema

from generate.collector import collect
from generate.deriver import derive_graph, derive_identity_fields, derive_root_element, derive_singleton_elements
from generate.emitters.constants import emit_constants
from generate.emitters.definition import emit_definition
from generate.emitters.types import emit_types
from generate.globals import inject_mapped_attributes, load_attr_mapping
from generate.orphans import detect_orphans, inject_orphan_parents, load_parent_mapping
from generate.xsi_type import XsiTypeExpander
def main(argv: list[str] | None = None) -> None:
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
    # Determine root before injection so orphans don't compete
    roots = sorted(n for n, e in elements.items() if not e.parents)
    root_candidate = max(roots, key=lambda n: len(elements[n].children)) if roots else None

    orphans_injected = 0
    unmapped_count = 0
    if mapping:
        orphans = detect_orphans(elements, root_candidate or '')
        if orphans:
            unmapped = inject_orphan_parents(elements, mapping, root_name=root_candidate or '')
            orphans_injected = len(orphans) - len(unmapped)
            unmapped_count = len(unmapped)
            for name in unmapped:
                print(f'  WARNING: unmapped orphan element: {name}', file=sys.stderr)

    # Phase 2c: Mapped attribute injection (attribute-mapping.json sidecar)
    attr_mapping = load_attr_mapping(entry)
    mapped_attrs_injected = inject_mapped_attributes(schema, elements, attr_mapping)
    if mapped_attrs_injected:
        print(f'  Mapped attributes injected: {mapped_attrs_injected}')

    # Phase 3: Derive
    print('Deriving graphs...')
    descendants, ancestors = derive_graph(elements)
    root_element = derive_root_element(elements, override=root_candidate)
    singleton_elements = derive_singleton_elements(elements, root_element)
    identity_fields = derive_identity_fields(elements)
    for name, fields in identity_fields.items():
        elements[name].identity_fields = fields
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
    print(f'Done. {len(elements)} elements, {orphans_injected} orphans injected{warnings}, ROOT={root_element}')
if __name__ == '__main__':
    main()
