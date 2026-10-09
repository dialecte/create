"""Text content: whether an element holds text, and what that text is."""
from typing import Any

import pytest

from tests.conftest import schema

ABSENT = '(absent)'


def text_of(entry_body: str) -> str:
    return schema(
        '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Probe"/></xs:sequence></xs:complexType></xs:element>'
        + entry_body
    )


CASES: dict[str, tuple[str, Any]] = {
    'an element of a built-in type -> text of that type': (text_of('<xs:element name="Probe" type="xs:int"/>'), {'type': {'builtin': 'int'}}),
    'an element of a plain string -> untyped text': (text_of('<xs:element name="Probe" type="xs:string"/>'), {}),
    'simple content extending a built-in, with an attribute -> text of that type': (
        text_of(
            '<xs:element name="Probe"><xs:complexType><xs:simpleContent><xs:extension base="xs:decimal">'
            '<xs:attribute name="unit" type="xs:token"/></xs:extension></xs:simpleContent></xs:complexType></xs:element>'
        ),
        {'type': {'builtin': 'decimal'}},
    ),
    'mixed content -> untyped text beside the elements': (
        text_of('<xs:element name="Probe"><xs:complexType mixed="true"><xs:sequence><xs:element name="b" minOccurs="0"/></xs:sequence></xs:complexType></xs:element>'),
        {},
    ),
    'simple content in a type also marked mixed -> text of the simple content\'s type': (
        text_of(
            '<xs:element name="Probe"><xs:complexType mixed="true"><xs:simpleContent><xs:extension base="xs:normalizedString">'
            '<xs:attribute name="lang" type="xs:language"/></xs:extension></xs:simpleContent></xs:complexType></xs:element>'
        ),
        {'type': {'builtin': 'normalizedString'}},
    ),
    'mixed content with a default text -> untyped text with its default': (
        text_of('<xs:element name="Probe" default="none"><xs:complexType mixed="true"><xs:sequence><xs:element name="b" minOccurs="0"/></xs:sequence></xs:complexType></xs:element>'),
        {'default': 'none'},
    ),
    'an element declared without a type -> untyped text (anyType is mixed)': (text_of('<xs:element name="Probe"/>'), {}),
    'element-only content -> no text': (
        text_of('<xs:element name="Probe"><xs:complexType><xs:sequence><xs:element name="b"/></xs:sequence></xs:complexType></xs:element>'),
        ABSENT,
    ),
    'an empty complex type -> no text': (text_of('<xs:element name="Probe"><xs:complexType/></xs:element>'), ABSENT),
    'a fixed text value -> kept with the text': (
        text_of('<xs:element name="Probe" type="xs:normalizedString" fixed="R-GOOSE"/>'),
        {'type': {'builtin': 'normalizedString'}, 'fixed': 'R-GOOSE'},
    ),
    'a default text value -> kept with the text': (text_of('<xs:element name="Probe" type="xs:token" default="on"/>'), {'type': {'builtin': 'token'}, 'default': 'on'}),
    'a tag declared under two parents with two fixed texts -> text without a fixed value at the tag level': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="GSEControl"><xs:complexType><xs:sequence><xs:element name="Probe" type="xs:normalizedString" fixed="R-GOOSE"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="SampledValueControl"><xs:complexType><xs:sequence><xs:element name="Probe" type="xs:normalizedString" fixed="R-SV"/></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {'type': {'builtin': 'normalizedString'}},
    ),
    'a tag declared under two parents with two text types -> untyped text at the tag level': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="Probe" type="xs:int"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="Probe" type="xs:token"/></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
    ),
}


@pytest.mark.parametrize(('entry', 'expected'), CASES.values(), ids=CASES.keys())
def test_text_content(definition_of, entry: str, expected: Any) -> None:
    probe = definition_of(entry)['Probe']
    assert probe.get('textContent', ABSENT) == expected
