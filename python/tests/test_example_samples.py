"""The values a scaffolded package's worked example gives a required attribute of a built-in type (BUILTIN_SAMPLES in
src/derive/example-facts.ts) are values of that type: libxml2 accepts each one."""
import re
from pathlib import Path

import pytest
from lxml import etree

SOURCE = Path(__file__).resolve().parents[2] / 'src' / 'derive' / 'example-facts.ts'
XS = 'http://www.w3.org/2001/XMLSchema'

# a mutant copy of the engine holds python/ only: the TypeScript side is judged beside it, not there
pytestmark = pytest.mark.skipif(not SOURCE.exists(), reason="needs create's src/derive")


def samples() -> dict[str, str]:
    if not SOURCE.exists():
        return {}
    text = SOURCE.read_text(encoding='utf-8')
    table = text[text.index('const BUILTIN_SAMPLES'):]
    table = table[:table.index('\n}')]
    return dict(re.findall(r"^\t(\w+): '([^']*)',$", table, flags=re.M))


def test_the_table_is_read() -> None:
    assert len(samples()) >= 30


@pytest.mark.parametrize(('builtin', 'value'), sorted(samples().items()))
def test_each_sample_is_a_value_of_its_built_in_type(builtin: str, value: str) -> None:
    schema = etree.XMLSchema(etree.fromstring(
        f'<xs:schema xmlns:xs="{XS}"><xs:element name="E"><xs:complexType>'
        f'<xs:attribute name="a" type="xs:{builtin}" use="required"/></xs:complexType></xs:element></xs:schema>'
    ))
    instance = etree.fromstring(f'<E a="{value}"/>')
    assert schema.validate(instance), [error.message for error in schema.error_log]
