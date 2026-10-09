"""Datatypes: what a simple value is - a built-in, a list of one, a union of several - with the facets each
restriction adds, kept where they apply (D1); values as written (GD2); a built-in's own facets never written."""
from typing import Any

import pytest

from tests_next.conftest import TARGET, pick, schema


def typed(simple_type: str, *, more: str = '') -> str:
    """Root carrying an attribute `a` of the anonymous simple type `simple_type` (the body of an xs:simpleType)."""
    return schema(
        f'<xs:element name="Root"><xs:complexType><xs:attribute name="a"><xs:simpleType>{simple_type}</xs:simpleType>'
        f'</xs:attribute></xs:complexType></xs:element>{more}'
    )


CASES: dict[str, tuple[str, Any]] = {
    'a restriction of a built-in -> the built-in with the facets the restriction adds': (
        typed('<xs:restriction base="xs:token"><xs:maxLength value="10"/></xs:restriction>'),
        {'builtin': 'token', 'facets': {'maxLength': 10}},
    ),
    'a built-in derived from another -> that built-in, none of its own facets': (
        typed('<xs:restriction base="xs:byte"/>'),
        {'builtin': 'byte'},
    ),
    'patterns on two levels -> one list per level: each level must match, one pattern of a level is enough': (
        typed('<xs:restriction base="tA"><xs:pattern value="a.*"/></xs:restriction>',
              more='<xs:simpleType name="tA"><xs:restriction base="xs:token"><xs:pattern value="[a-z]+"/><xs:pattern value="[0-9]+"/></xs:restriction></xs:simpleType>'),
        {'builtin': 'token', 'facets': {'pattern': [['[a-z]+', '[0-9]+'], ['a[^\\n\\r]*']]}},
    ),
    'a pattern with XSD escapes -> written as a JS source with XSD\'s meaning': (
        typed('<xs:restriction base="xs:token"><xs:pattern value="\\d+\\.\\s"/></xs:restriction>'),
        {'builtin': 'token', 'facets': {'pattern': [['\\p{Nd}+\\.[\\t\\n\\r ]']]}},
    ),
    'an enumeration restricting another -> only the derived one, it replaces the base': (
        typed('<xs:restriction base="tColors"><xs:enumeration value="red"/></xs:restriction>',
              more='<xs:simpleType name="tColors"><xs:restriction base="xs:token"><xs:enumeration value="red"/><xs:enumeration value="blue"/></xs:restriction></xs:simpleType>'),
        {'builtin': 'token', 'facets': {'enumeration': ['red']}},
    ),
    'lengths on two levels -> the most derived one of each': (
        typed('<xs:restriction base="tA"><xs:minLength value="2"/></xs:restriction>',
              more='<xs:simpleType name="tA"><xs:restriction base="xs:string"><xs:minLength value="1"/><xs:maxLength value="9"/></xs:restriction></xs:simpleType>'),
        {'builtin': 'string', 'facets': {'minLength': 2, 'maxLength': 9}},
    ),
    'ranges and digits -> the range values as written, the digits as numbers': (
        typed('<xs:restriction base="xs:decimal"><xs:minInclusive value="-1.50"/><xs:maxExclusive value="99999999999999999999"/>'
              '<xs:totalDigits value="22"/><xs:fractionDigits value="2"/></xs:restriction>'),
        {'builtin': 'decimal', 'facets': {'minInclusive': '-1.50', 'maxExclusive': '99999999999999999999', 'totalDigits': 22, 'fractionDigits': 2}},
    ),
    'a range of dates -> the date as written': (
        typed('<xs:restriction base="xs:date"><xs:minInclusive value="2001-01-01"/></xs:restriction>'),
        {'builtin': 'date', 'facets': {'minInclusive': '2001-01-01'}},
    ),
    'a list -> the item type, the list\'s own length a number of items': (
        typed('<xs:restriction base="tList"><xs:maxLength value="3"/></xs:restriction>',
              more='<xs:simpleType name="tList"><xs:list><xs:simpleType><xs:restriction base="xs:token"><xs:maxLength value="5"/></xs:restriction></xs:simpleType></xs:list></xs:simpleType>'),
        {'list': {'builtin': 'token', 'facets': {'maxLength': 5}}, 'facets': {'maxLength': 3}},
    ),
    'a list of plain strings -> the string item kept': (
        typed('<xs:list itemType="xs:string"/>'),
        {'list': {'builtin': 'string'}},
    ),
    'a union -> each member with its own facets, none of them at the union': (
        typed('<xs:union memberTypes="xs:int tColor"/>',
              more='<xs:simpleType name="tColor"><xs:restriction base="xs:token"><xs:enumeration value="red"/></xs:restriction></xs:simpleType>'),
        {'union': [{'builtin': 'int'}, {'builtin': 'token', 'facets': {'enumeration': ['red']}}]},
    ),
    'a restriction of a union -> its own facets on the union, values as written': (
        typed('<xs:restriction base="tU"><xs:enumeration value="01"/><xs:enumeration value="red"/></xs:restriction>',
              more='<xs:simpleType name="tU"><xs:union memberTypes="xs:int xs:token"/></xs:simpleType>'),
        {'union': [{'builtin': 'int'}, {'builtin': 'token'}], 'facets': {'enumeration': ['01', 'red']}},
    ),
    'a string whose white space a restriction collapses -> said, it is not the built-in\'s': (
        typed('<xs:restriction base="xs:string"><xs:whiteSpace value="collapse"/></xs:restriction>'),
        {'builtin': 'string', 'facets': {'whiteSpace': 'collapse'}},
    ),
    'a token restricted with the white space it already collapses -> not said': (
        typed('<xs:restriction base="xs:token"><xs:whiteSpace value="collapse"/><xs:length value="2"/></xs:restriction>'),
        {'builtin': 'token', 'facets': {'length': 2}},
    ),
    'a list of a union -> the union inside the list': (
        typed('<xs:list><xs:simpleType><xs:union memberTypes="xs:int xs:boolean"/></xs:simpleType></xs:list>'),
        {'list': {'union': [{'builtin': 'int'}, {'builtin': 'boolean'}]}},
    ),
    'a union of a list and a nested union -> each member as it is, in order': (
        typed('<xs:union memberTypes="tInts tEither"/>',
              more='<xs:simpleType name="tInts"><xs:list itemType="xs:int"/></xs:simpleType>'
                   '<xs:simpleType name="tEither"><xs:union memberTypes="xs:date xs:token"/></xs:simpleType>'),
        {'union': [{'list': {'builtin': 'int'}}, {'union': [{'builtin': 'date'}, {'builtin': 'token'}]}]},
    ),
    'a union naming members and holding others -> the named ones first, as the union orders them': (
        typed('<xs:union memberTypes="xs:decimal"><xs:simpleType><xs:restriction base="xs:token"/></xs:simpleType></xs:union>'),
        {'union': [{'builtin': 'decimal'}, {'builtin': 'token'}]},
    ),
    'an enumeration of qualified names in the xml namespace -> its prefix always bound': (
        typed('<xs:restriction base="xs:QName"><xs:enumeration value="xml:lang"/></xs:restriction>'),
        {'builtin': 'QName', 'facets': {'enumeration': ['{http://www.w3.org/XML/1998/namespace}lang']}},
    ),
    'a restriction of an inline base -> both levels\' facets, from each its own restriction': (
        typed('<xs:restriction><xs:simpleType><xs:restriction base="xs:token"><xs:maxLength value="9"/><xs:pattern value="a.*"/></xs:restriction>'
              '</xs:simpleType><xs:minLength value="2"/><xs:pattern value=".*z"/></xs:restriction>'),
        {'builtin': 'token', 'facets': {'pattern': [['a[^\\n\\r]*'], ['[^\\n\\r]*z']], 'minLength': 2, 'maxLength': 9}},
    ),
    'a restriction with an annotation and a fixed facet -> the facets only, fixed or not': (
        typed('<xs:restriction base="xs:token"><xs:annotation><xs:documentation>no facet</xs:documentation></xs:annotation>'
              '<xs:maxLength value="4" fixed="true"/></xs:restriction>'),
        {'builtin': 'token', 'facets': {'maxLength': 4}},
    ),
    'an enumeration of a collapsing type written with spaces -> the values compared, collapsed': (
        typed('<xs:restriction base="xs:token"><xs:enumeration value="  two   words "/></xs:restriction>'),
        {'builtin': 'token', 'facets': {'enumeration': ['two words']}},
    ),
    'an enumeration of qualified names -> each by namespace and local name, unprefixed in the default namespace': (
        typed('<xs:restriction base="xs:QName"><xs:enumeration value="e:there"/><xs:enumeration value="here"/></xs:restriction>')
        .replace('<xs:schema ', '<xs:schema xmlns:e="urn:e" '),
        {'builtin': 'QName', 'facets': {'enumeration': ['{urn:e}there', f'{{{TARGET}}}here']}},
    ),
}


@pytest.mark.parametrize(('entry', 'expected'), CASES.values(), ids=CASES.keys())
def test_datatypes(definition_of, entry: str, expected: Any) -> None:
    assert pick(definition_of(entry), 'Root.attributes.details.a')['type'] == expected


def test_a_plain_string_says_nothing(definition_of) -> None:
    assert 'type' not in pick(definition_of(typed('<xs:restriction base="xs:string"/>')), 'Root.attributes.details.a')


def test_an_attribute_carries_no_facets_of_its_own_any_more(definition_of) -> None:
    detail = pick(definition_of(typed('<xs:restriction base="xs:token"><xs:maxLength value="10"/></xs:restriction>')), 'Root.attributes.details.a')
    assert 'facets' not in detail


def test_simple_content_text_is_typed_the_same_way(definition_of) -> None:
    entry = schema(
        '<xs:element name="Root"><xs:complexType><xs:simpleContent><xs:restriction base="tText"><xs:maxLength value="4"/></xs:restriction>'
        '</xs:simpleContent></xs:complexType></xs:element>'
        '<xs:complexType name="tText"><xs:simpleContent><xs:extension base="xs:token"/></xs:simpleContent></xs:complexType>'
    )
    assert pick(definition_of(entry), 'Root.textContent.type') == {'builtin': 'token', 'facets': {'maxLength': 4}}


def test_a_restriction_of_untyped_simple_content_adding_no_facet_says_nothing(definition_of) -> None:
    entry = schema(
        '<xs:element name="Root"><xs:complexType><xs:simpleContent><xs:restriction base="tAny"/>'
        '</xs:simpleContent></xs:complexType></xs:element>'
        '<xs:complexType name="tAny"><xs:simpleContent><xs:extension base="xs:anySimpleType"/></xs:simpleContent></xs:complexType>'
    )
    assert pick(definition_of(entry), 'Root.textContent') == {}


def test_a_redefined_simple_type_adds_its_facets_to_the_one_it_redefines(definition_of) -> None:
    entry = schema(
        '<xs:redefine schemaLocation="base.xsd"><xs:simpleType name="tCode"><xs:restriction base="tCode"><xs:maxLength value="3"/>'
        '</xs:restriction></xs:simpleType></xs:redefine>'
        '<xs:element name="Root"><xs:complexType><xs:attribute name="a" type="tCode"/></xs:complexType></xs:element>'
    )
    base = (
        f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="{TARGET}">'
        '<xs:simpleType name="tCode"><xs:restriction base="xs:token"><xs:minLength value="1"/></xs:restriction></xs:simpleType></xs:schema>'
    )
    assert pick(definition_of(entry, imports={'base.xsd': base}), 'Root.attributes.details.a.type') == {
        'builtin': 'token', 'facets': {'minLength': 1, 'maxLength': 3},
    }
