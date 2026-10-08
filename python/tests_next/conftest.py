"""Inline schemas for the generator's tests: write them, run the whole generator, read the definition data."""
from pathlib import Path
from typing import Any

import pytest

from generate_next.definition.build import generate_definition

XS = 'http://www.w3.org/2001/XMLSchema'
TARGET = 'urn:dialecte:test'


def schema(body: str, *, target: str = TARGET, prefix: str = 't', attributes: str = '') -> str:
    """A schema document around `body`, its target namespace declared as the default and as `prefix`."""
    return (
        f'<xs:schema xmlns:xs="{XS}" xmlns="{target}" xmlns:{prefix}="{target}" '
        f'targetNamespace="{target}" elementFormDefault="qualified" {attributes}>{body}</xs:schema>'
    )


@pytest.fixture
def definition_of(tmp_path: Path):
    """`definition_of(entry_body, imports={'other.xsd': text})` -> the definition data of the generated dialecte."""

    def build(entry: str, *, imports: dict[str, str] | None = None) -> dict[str, Any]:
        for file_name, text in (imports or {}).items():
            (tmp_path / file_name).write_text(text, encoding='utf-8')
        entry_path = tmp_path / 'entry.xsd'
        entry_path.write_text(entry, encoding='utf-8')
        return generate_definition(entry_path)

    return build


def pick(data: dict[str, Any], path: str) -> Any:
    """The value at a dotted path of the definition data (`'Bay.attributes.details.name'`)."""
    value: Any = data
    for key in path.split('.'):
        value = value[key]
    return value
