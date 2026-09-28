"""What an element declaration says about its own value: a default or fixed text, nillable; and
what a wildcard attribute allows."""

import textwrap

import pytest
import xmlschema

from generate.collector import collect
from generate.emitters.definition import emit_definition

FLAGS = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
      <xs:element name="Root">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="Unit" type="xs:string" default="mm"/>
            <xs:element name="Version" type="xs:string" fixed="2007"/>
            <xs:element name="Comment" type="xs:string" nillable="true"/>
            <xs:element name="Plain" type="xs:string"/>
            <xs:element name="Extensible">
              <xs:complexType>
                <xs:attribute name="name" type="xs:string"/>
                <xs:anyAttribute namespace="##other" processContents="lax"/>
              </xs:complexType>
            </xs:element>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
    </xs:schema>
""")


@pytest.fixture()
def elements(tmp_path):
    (tmp_path / 'flags.xsd').write_text(FLAGS)
    return collect(xmlschema.XMLSchema(str(tmp_path / 'flags.xsd')))


class TestElementValue:
    def test_a_default_text_is_kept(self, elements):
        assert elements['Unit'].text_content.default == 'mm'

    def test_a_fixed_text_is_kept(self, elements):
        assert elements['Version'].text_content.fixed == '2007'

    def test_nillable_is_kept(self, elements):
        assert elements['Comment'].nillable is True
        assert elements['Plain'].nillable is False


class TestWildcardAttribute:
    def test_its_namespace_constraint_is_kept(self, elements):
        assert elements['Extensible'].attr_any is True
        assert elements['Extensible'].attr_any_namespace == ['##other']


class TestEmitted:
    def test_flags_are_written_sparsely(self, elements, tmp_path):
        out = tmp_path / 'definition.generated.ts'
        emit_definition(elements, out)
        content = out.read_text()

        assert "textContent: { default: 'mm'" in content
        assert "textContent: { fixed: '2007'" in content
        assert 'nillable: true,' in content
        assert content.count('nillable') == 1
        assert "any: true,\n\t\t\tanyNamespace: ['##other']," in content
