"""Datatypes: what an attribute or a text value IS, beyond the facets that restrict it.

Every simple type bottoms out in an XSD built-in (decimal, boolean, dateTime, ID, ...), possibly
as a list of one or a union of several. A validator, a form or a UI needs that to interpret the
facets and the value at all.
"""

import textwrap

import pytest
import xmlschema

from generate.collector import collect
from generate.emitters.definition import emit_definition
from generate.ir import DataType

TYPED = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
      <xs:simpleType name="tPercent">
        <xs:restriction base="xs:integer">
          <xs:minInclusive value="0"/><xs:maxInclusive value="100"/>
        </xs:restriction>
      </xs:simpleType>
      <xs:simpleType name="tNames"><xs:list itemType="xs:NCName"/></xs:simpleType>
      <xs:simpleType name="tThreeNames">
        <xs:restriction base="tNames"><xs:length value="3"/></xs:restriction>
      </xs:simpleType>
      <xs:simpleType name="tSizeWord">
        <xs:restriction base="xs:token"><xs:enumeration value="small"/><xs:enumeration value="large"/></xs:restriction>
      </xs:simpleType>
      <xs:simpleType name="tSize"><xs:union memberTypes="tSizeWord xs:positiveInteger"/></xs:simpleType>

      <xs:element name="Root">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="Count" type="xs:nonNegativeInteger"/>
            <xs:element name="Plain" type="xs:string"/>
            <xs:element name="Labels" type="tNames"/>
          </xs:sequence>
          <xs:attribute name="name" type="xs:string" use="required"/>
          <xs:attribute name="ratio" type="xs:decimal"/>
          <xs:attribute name="enabled" type="xs:boolean"/>
          <xs:attribute name="when" type="xs:dateTime"/>
          <xs:attribute name="key" type="xs:ID"/>
          <xs:attribute name="percent" type="tPercent"/>
          <xs:attribute name="names" type="tThreeNames"/>
          <xs:attribute name="size" type="tSize"/>
          <xs:attribute name="untyped"/>
        </xs:complexType>
      </xs:element>
    </xs:schema>
""")


@pytest.fixture()
def elements(tmp_path):
    (tmp_path / 'typed.xsd').write_text(TYPED)
    return collect(xmlschema.XMLSchema(str(tmp_path / 'typed.xsd')))


def _type(elements, attribute: str) -> DataType | None:
    return elements['Root'].attributes[attribute].type


class TestAtomic:
    @pytest.mark.parametrize(
        ('attribute', 'builtin'),
        [('ratio', 'decimal'), ('enabled', 'boolean'), ('when', 'dateTime'), ('key', 'ID')],
    )
    def test_a_builtin_is_named(self, elements, attribute, builtin):
        assert _type(elements, attribute) == DataType(kind='atomic', builtin=builtin)

    def test_a_restriction_names_the_most_specific_builtin_it_derives_from(self, elements):
        assert _type(elements, 'percent').builtin == 'integer'

    def test_a_plain_string_has_no_type_to_tell(self, elements):
        assert _type(elements, 'name') is None
        assert _type(elements, 'untyped') is None


class TestListAndUnion:
    def test_a_list_names_its_item_type(self, elements):
        names = _type(elements, 'names')
        assert names.kind == 'list'
        assert names.item == DataType(kind='atomic', builtin='NCName')

    def test_the_facets_of_the_list_itself_stay_with_the_list(self, elements):
        assert _type(elements, 'names').facets.length == 3

    def test_a_union_names_its_members_each_with_its_own_facets(self, elements):
        size = _type(elements, 'size')
        assert size.kind == 'union'
        assert [member.builtin for member in size.members] == ['token', 'positiveInteger']
        assert size.members[0].facets.enumeration == ['small', 'large']
        assert size.members[1].facets is None


class TestTextContent:
    def test_the_text_of_an_element_is_typed_the_same_way(self, elements):
        assert elements['Count'].text_content.type == DataType(kind='atomic', builtin='nonNegativeInteger')
        assert elements['Labels'].text_content.type.kind == 'list'

    def test_a_plain_string_text_has_no_type_to_tell(self, elements):
        assert elements['Plain'].text_content.type is None


class TestEmitted:
    def test_types_are_written_sparsely(self, elements, tmp_path):
        out = tmp_path / 'definition.generated.ts'
        emit_definition(elements, out)
        content = out.read_text()

        # a top-level atomic type names its built-in; a built-in's white space is not repeated
        assert "ratio: { type: { builtin: 'decimal' } }" in content
        # a list keeps the facets of the list itself, apart from those of its items
        assert "type: { list: { builtin: 'NCName' }, facets: { length: 3 } }" in content
        # a union member keeps its own facets, which the flat view merges with the others'; a
        # built-in's own facets (token collapses white space) are what its name says, not repeated
        assert (
            "type: { union: [{ builtin: 'token', facets: { enumeration: ['small', 'large'] } }, { builtin: 'positiveInteger' }] }"
            in content
        )
        # a plain string has no type to tell, and nothing to say about white space
        assert "name: { required: true }" in content
