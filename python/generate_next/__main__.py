"""`python -m generate_next --entry <schema.xsd> --out-dir <folder>`: write `definition.generated.ts`.

The definition is the generator's only output; the constants and types are derived from it by the
TypeScript side of @dialecte/create.
"""
import argparse
from pathlib import Path

from generate_next.definition.build import generate_definition
from generate_next.emit.ts_literal import definition_source


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(prog='generate_next', description=__doc__)
    parser.add_argument('--entry', required=True, type=Path, help='the entry document of the schema')
    parser.add_argument('--out-dir', required=True, type=Path, help='where definition.generated.ts is written')
    arguments = parser.parse_args(argv)

    generated = generate_definition(arguments.entry)
    arguments.out_dir.mkdir(parents=True, exist_ok=True)
    output = arguments.out_dir / 'definition.generated.ts'
    output.write_text(definition_source(generated.definition, generated.types), encoding='utf-8')
    print(f'{output} - {len(generated.definition)} elements, {len(generated.types)} xsi:type variants')
    return output


if __name__ == '__main__':
    main()
