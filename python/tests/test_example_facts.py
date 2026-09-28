"""What a scaffolded package's worked example names: the root, its first allowed child, and what that
child requires. The scaffold writes these into the example, so a reader opens real element names."""

import textwrap

import pytest
import xmlschema

from generate.__main__ import main
from generate.collector import collect
from generate.example import example_facts

SCHEMA = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
               targetNamespace="urn:example" xmlns="urn:example" elementFormDefault="qualified">
      <xs:element name="Root">
        <xs:complexType><xs:sequence>
          <xs:element name="Item" maxOccurs="unbounded">
            <xs:complexType>
              <xs:attribute name="fixedOne" type="xs:string" fixed="F" use="required"/>
              <xs:attribute name="kind" use="required">
                <xs:simpleType><xs:restriction base="xs:string">
                  <xs:enumeration value="first"/><xs:enumeration value="second"/>
                </xs:restriction></xs:simpleType>
              </xs:attribute>
              <xs:attribute name="name" type="xs:string" use="required"/>
              <xs:attribute name="optional" type="xs:string"/>
            </xs:complexType>
          </xs:element>
          <xs:element name="Other" minOccurs="0"/>
        </xs:sequence></xs:complexType>
      </xs:element>
    </xs:schema>
""")

EMPTY_ROOT = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
      <xs:element name="Lonely"><xs:complexType/></xs:element>
    </xs:schema>
""")


@pytest.fixture()
def schema_path(tmp_path):
    path = tmp_path / 'example.xsd'
    path.write_text(SCHEMA)
    return path


class TestExampleFacts:
    def test_names_the_root_and_the_first_child_it_allows(self, schema_path):
        facts = example_facts(collect(xmlschema.XMLSchema(str(schema_path))), 'Root')
        assert facts['root']['name'] == 'Root'
        assert facts['child']['name'] == 'Item'

    def test_carries_the_namespace_of_each_for_xpath(self, schema_path):
        facts = example_facts(collect(xmlschema.XMLSchema(str(schema_path))), 'Root')
        assert facts['root']['namespaceUri'] == 'urn:example'
        assert facts['child']['namespaceUri'] == 'urn:example'

    def test_fills_each_required_attribute_with_a_value_the_schema_accepts(self, schema_path):
        facts = example_facts(collect(xmlschema.XMLSchema(str(schema_path))), 'Root')
        # fixed, else the first enumerated value, else a placeholder (XSD allows no default on a
        # required attribute); an optional one is left out
        assert facts['child']['requiredAttributes'] == [
            {'name': 'fixedOne', 'value': 'F'},
            {'name': 'kind', 'value': 'first'},
            {'name': 'name', 'value': 'hello-world'},
        ]

    def test_a_root_that_allows_no_child_has_none(self, tmp_path):
        path = tmp_path / 'lonely.xsd'
        path.write_text(EMPTY_ROOT)
        facts = example_facts(collect(xmlschema.XMLSchema(str(path))), 'Lonely')
        assert facts['root']['name'] == 'Lonely'
        assert facts['child'] is None


class TestMainReturnsThem:
    def test_a_run_hands_the_facts_back_to_its_caller(self, schema_path, tmp_path):
        facts = main(['--entry', str(schema_path), '--out-dir', str(tmp_path / 'out')])
        assert facts['root']['name'] == 'Root'
        assert facts['child']['name'] == 'Item'
