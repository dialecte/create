"""`python -m generate --entry <schema.xsd> --out-dir <folder>`: write `definition.generated.ts`.

The definition is the generator's only output; the constants and types are derived from it by the
TypeScript side of @dialecte/create, which calls `generate` and writes every file itself.
"""
import argparse
from pathlib import Path
from typing import Any

from generate.definition.build import generate_definition
from generate.emit.ts_literal import definition_source


def generate(entry: Path) -> dict[str, Any]:
    """The definition of the schema whose entry document is `entry`: its data, its types and its TypeScript source."""
    generated = generate_definition(entry)
    return {
        'definition': generated.definition,
        'types': generated.types,
        'source': definition_source(generated.definition, generated.types),
    }


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(prog='generate', description=__doc__)
    parser.add_argument('--entry', required=True, type=Path, help='the entry document of the schema')
    parser.add_argument('--out-dir', required=True, type=Path, help='where definition.generated.ts is written')
    arguments = parser.parse_args(argv)

    generated = generate(arguments.entry)
    arguments.out_dir.mkdir(parents=True, exist_ok=True)
    output = arguments.out_dir / 'definition.generated.ts'
    output.write_text(generated['source'], encoding='utf-8')
    print(f'{output} - {len(generated["definition"])} elements, {len(generated["types"])} xsi:type variants')
    return output


if __name__ == '__main__':
    main()
