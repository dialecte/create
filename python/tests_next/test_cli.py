"""The command line: one schema in, `definition.generated.ts` out."""
from pathlib import Path

from generate_next.__main__ import main
from tests_next.conftest import schema


def test_a_schema_given_on_the_command_line_writes_its_definition(tmp_path: Path) -> None:
    entry = tmp_path / 'entry.xsd'
    entry.write_text(schema('<xs:element name="Root"/>'), encoding='utf-8')
    output = main(['--entry', str(entry), '--out-dir', str(tmp_path / 'out')])
    assert output == tmp_path / 'out' / 'definition.generated.ts'
    assert "\tRoot: {\n\t\ttag: 'Root'," in output.read_text(encoding='utf-8')
