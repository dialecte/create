"""The attributes of a child as declared under each parent: `ATTRIBUTES.byParent`.

One constant, two axes: `byTag` is the table every consumer had, `byParent` has one entry per edge,
the tag-level object for an element declared once, the declaration's own where a homonym differs.
Both carry attribute skeletons: one key per attribute name, typed; details live in `DEFINITION`.
"""

import textwrap

import pytest
import xmlschema

from generate.collector import collect
from generate.emitters.constants import emit_constants
from generate.emitters.types import emit_types

SCHEMA = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
      <xs:element name="Bay">
        <xs:complexType><xs:attribute name="name" type="xs:string" use="required"/></xs:complexType>
      </xs:element>
      <xs:element name="Address">
        <xs:complexType><xs:sequence>
          <xs:element name="P" maxOccurs="unbounded"><xs:complexType><xs:simpleContent><xs:extension base="xs:string">
            <xs:attribute name="type" use="required"><xs:simpleType><xs:restriction base="xs:string">
              <xs:enumeration value="IP"/><xs:enumeration value="VLAN-ID"/>
            </xs:restriction></xs:simpleType></xs:attribute>
          </xs:extension></xs:simpleContent></xs:complexType></xs:element>
        </xs:sequence></xs:complexType>
      </xs:element>
      <xs:element name="PhysConn">
        <xs:complexType><xs:sequence>
          <xs:element name="P" maxOccurs="unbounded"><xs:complexType><xs:simpleContent><xs:extension base="xs:string">
            <xs:attribute name="type" use="required"><xs:simpleType><xs:restriction base="xs:string">
              <xs:enumeration value="Plug"/><xs:enumeration value="Cable"/>
            </xs:restriction></xs:simpleType></xs:attribute>
          </xs:extension></xs:simpleContent></xs:complexType></xs:element>
        </xs:sequence></xs:complexType>
      </xs:element>
      <xs:element name="Root">
        <xs:complexType><xs:sequence>
          <xs:element ref="Bay" maxOccurs="unbounded"/>
          <xs:element ref="Address"/>
          <xs:element ref="PhysConn"/>
          <xs:element name="Sub"><xs:complexType><xs:sequence>
            <xs:element ref="Bay" maxOccurs="unbounded"/>
          </xs:sequence></xs:complexType></xs:element>
        </xs:sequence></xs:complexType>
      </xs:element>
    </xs:schema>
""")


@pytest.fixture()
def elements(tmp_path):
    (tmp_path / 'edges.xsd').write_text(SCHEMA)
    return collect(xmlschema.XMLSchema(str(tmp_path / 'edges.xsd')))


@pytest.fixture()
def emitted(elements, tmp_path):
    constants = tmp_path / 'constants.generated.ts'
    types = tmp_path / 'types.generated.ts'
    emit_constants(
        elements,
        descendants={n: [] for n in elements},
        ancestors={n: [] for n in elements},
        root_element='Root',
        singleton_elements=['Root'],
        out=constants,
    )
    emit_types(elements, types)
    return constants.read_text(), types.read_text()


class TestCollectedDefinitions:
    def test_a_homonym_keeps_the_attributes_of_each_definition_by_parent(self, elements):
        by_parent = elements['P'].definitions_by_parent
        assert set(by_parent) == {'Address', 'PhysConn'}
        assert by_parent['Address'].attributes['type'].facets.enumeration == ['IP', 'VLAN-ID']
        assert by_parent['PhysConn'].attributes['type'].facets.enumeration == ['Plug', 'Cable']

    def test_an_element_declared_once_keeps_nothing_by_parent(self, elements):
        assert elements['Bay'].definitions_by_parent == {}


class TestAttributesConstant:
    def test_by_tag_is_the_table_every_consumer_had(self, emitted):
        constants, _ = emitted
        assert "const ATTRIBUTES_BY_TAG = {\n\tAddress: {} as AttributesOf<'Address'>," in constants
        assert "\tBay: {\n\t\tname: '' as string,\n\t} as AttributesOf<'Bay'>," in constants
        assert "export const ATTRIBUTES = {\n\tbyTag: ATTRIBUTES_BY_TAG,\n\tbyParent: {\n" in constants

    def test_by_parent_refers_to_the_tag_object_for_an_element_declared_once(self, emitted):
        constants, _ = emitted
        assert (
            "\t\tRoot: {\n\t\t\tBay: ATTRIBUTES_BY_TAG.Bay,\n\t\t\tAddress: ATTRIBUTES_BY_TAG.Address,\n"
            "\t\t\tPhysConn: ATTRIBUTES_BY_TAG.PhysConn,\n\t\t\tSub: ATTRIBUTES_BY_TAG.Sub,\n\t\t},"
        ) in constants
        assert "\t\tSub: {\n\t\t\tBay: ATTRIBUTES_BY_TAG.Bay,\n\t\t}," in constants

    def test_by_parent_holds_the_declaration_of_a_homonym_under_each_parent(self, emitted):
        constants, _ = emitted
        assert "\t\tAddress: {\n\t\t\tP: { type: '' as string } as AttributesPInAddress,\n\t\t}," in constants
        assert "\t\tPhysConn: {\n\t\t\tP: { type: '' as string } as AttributesPInPhysConn,\n\t\t}," in constants
        assert "import type { AvailableElement, AttributesOf, AttributesByParent, AttributesPInAddress, AttributesPInPhysConn } from './types.generated'" in constants

    def test_by_parent_is_checked_against_the_type_map_and_nothing_else_changes(self, emitted):
        constants, _ = emitted
        assert "\t} satisfies AttributesByParent,\n} as const" in constants
        assert 'attributesByParent' not in constants and "'#document'" not in constants
        assert "\tRoot: [],\n" in constants
        assert "\tBay: ['Root', 'Sub'],\n" in constants


class TestAttributesByParent:
    def test_one_entry_per_edge_with_the_tag_level_type_for_an_element_declared_once(self, emitted):
        _, types = emitted
        assert "export type AttributesByParent = {" in types
        assert "\tRoot: {\n\t\tBay: AttributesBay\n\t\tAddress: AttributesAddress\n\t\tPhysConn: AttributesPhysConn\n\t\tSub: AttributesSub\n\t}" in types
        assert types.count("Bay: AttributesBay") == 3  # AttributesMap, under Root, under Sub

    def test_a_homonym_has_the_type_of_its_declaration_under_each_parent(self, emitted):
        _, types = emitted
        assert "\tAddress: {\n\t\tP: AttributesPInAddress\n\t}" in types
        assert "\tPhysConn: {\n\t\tP: AttributesPInPhysConn\n\t}" in types

    def test_an_element_without_children_has_no_row(self, emitted):
        _, types = emitted
        assert "\tBay: {\n" not in types.split("export type AttributesByParent")[1]


class TestPerParentTypes:
    def test_a_homonym_gets_one_type_per_declaration(self, emitted):
        _, types = emitted
        assert "export type AttributesPInAddress = {\n\ttype: 'IP' | 'VLAN-ID' | (string & {})\n}" in types
        assert "export type AttributesPInPhysConn = {\n\ttype: 'Plug' | 'Cable' | (string & {})\n}" in types

    def test_the_by_tag_type_stays_the_merged_view(self, emitted):
        _, types = emitted
        assert "export type AttributesP = {\n\ttype: 'IP' | 'VLAN-ID' | 'Plug' | 'Cable' | (string & {})\n}" in types
