"""The command line: one schema in, `definition.generated.ts` out; `generate` hands the same to the TypeScript side."""
from pathlib import Path

import pytest

from generate.__main__ import generate, main
from tests.conftest import schema


def test_a_schema_given_on_the_command_line_writes_its_definition(tmp_path: Path) -> None:
    entry = tmp_path / 'entry.xsd'
    entry.write_text(schema('<xs:element name="Root"/>'), encoding='utf-8')
    output = main(['--entry', str(entry), '--out-dir', str(tmp_path / 'out')])
    assert output == tmp_path / 'out' / 'definition.generated.ts'
    assert "\tRoot: {\n\t\ttag: 'Root'," in output.read_text(encoding='utf-8')


def test_generate_returns_the_data_and_the_source_and_writes_nothing(tmp_path: Path) -> None:
    entry = tmp_path / 'entry.xsd'
    entry.write_text(schema('<xs:element name="Root"/>'), encoding='utf-8')
    generated = generate(entry)
    assert list(generated['definition']) == ['Root']
    assert generated['types'] == {}
    assert "\tRoot: {\n\t\ttag: 'Root'," in generated['source']
    assert sorted(path.name for path in tmp_path.iterdir()) == ['entry.xsd']


@pytest.mark.parametrize('missing', ['--entry', '--out-dir'])
def test_the_entry_and_the_output_folder_are_required(tmp_path: Path, missing: str) -> None:
    given = {'--entry': str(tmp_path / 'entry.xsd'), '--out-dir': str(tmp_path / 'out')}
    del given[missing]
    with pytest.raises(SystemExit):
        main([item for pair in given.items() for item in pair])


def test_the_output_folder_is_made_with_its_parents_and_may_already_exist(tmp_path: Path) -> None:
    entry = tmp_path / 'entry.xsd'
    entry.write_text(schema('<xs:element name="Root"/>'), encoding='utf-8')
    out = tmp_path / 'deep' / 'er' / 'out'
    main(['--entry', str(entry), '--out-dir', str(out)])
    assert main(['--entry', str(entry), '--out-dir', str(out)]) == out / 'definition.generated.ts'
