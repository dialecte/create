"""The content model as the schema wrote it: the particle tree.

The flat children table (names, per-name occurrence) is the ergonomic view and stays. Order,
nesting, choice groups and the occurrence of a GROUP - `(a, b)*` - only survive in the tree, which
is what a validator of child order and counts needs.
"""

import textwrap

import pytest
import xmlschema

from generate.collector import collect
from generate.emitters.definition import emit_definition
from generate.ir import Particle

MODELS = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
      <xs:element name="caption"/><xs:element name="col"/><xs:element name="colgroup"/>
      <xs:element name="tr"/><xs:element name="dt"/><xs:element name="dd"/>
      <xs:element name="title"/><xs:element name="meta"/>

      <!-- XHTML table: optional element, then a repeated choice -->
      <xs:element name="table">
        <xs:complexType>
          <xs:sequence>
            <xs:element ref="caption" minOccurs="0"/>
            <xs:choice minOccurs="0" maxOccurs="unbounded">
              <xs:element ref="col"/>
              <xs:element ref="colgroup"/>
            </xs:choice>
            <xs:element ref="tr" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>

      <!-- a repeated GROUP: (dt+, dd+)* - each name alone says nothing about the pairing -->
      <xs:element name="dl">
        <xs:complexType>
          <xs:sequence minOccurs="0" maxOccurs="unbounded">
            <xs:element ref="dt" maxOccurs="unbounded"/>
            <xs:element ref="dd" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>

      <!-- xs:all: unordered, which the flat table cannot say -->
      <xs:element name="head">
        <xs:complexType>
          <xs:all>
            <xs:element ref="title"/>
            <xs:element ref="meta" minOccurs="0"/>
          </xs:all>
        </xs:complexType>
      </xs:element>

      <!-- a wildcard, with its namespace constraint -->
      <xs:element name="Private">
        <xs:complexType>
          <xs:sequence>
            <xs:any namespace="##other" processContents="lax" minOccurs="0" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>

      <!-- a substitution head in a model: one of its members, with the head's occurrence -->
      <xs:element name="instruction" abstract="true"/>
      <xs:element name="for-each" substitutionGroup="instruction"/>
      <xs:element name="choose" substitutionGroup="instruction"/>
      <xs:element name="template">
        <xs:complexType>
          <xs:sequence>
            <xs:element ref="instruction" minOccurs="0" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>

      <!-- no content model at all -->
      <xs:element name="Empty"><xs:complexType/></xs:element>

      <xs:element name="Root">
        <xs:complexType><xs:sequence>
          <xs:element ref="table"/><xs:element ref="dl"/><xs:element ref="head"/>
          <xs:element ref="Private"/><xs:element ref="template"/><xs:element ref="Empty"/>
        </xs:sequence></xs:complexType>
      </xs:element>
    </xs:schema>
""")


@pytest.fixture()
def elements(tmp_path):
    (tmp_path / 'models.xsd').write_text(MODELS)
    return collect(xmlschema.XMLSchema(str(tmp_path / 'models.xsd')))


def _el(name: str, min_occurs: int = 1, max_occurs: int | None = 1) -> Particle:
    return Particle(kind='element', name=name, min_occurs=min_occurs, max_occurs=max_occurs)


class TestTree:
    def test_a_sequence_keeps_order_optionality_and_nested_choice(self, elements):
        assert elements['table'].content_model == Particle(
            kind='sequence',
            particles=[
                _el('caption', 0, 1),
                Particle(kind='choice', min_occurs=0, max_occurs=None, particles=[_el('col'), _el('colgroup')]),
                _el('tr', 1, None),
            ],
        )

    def test_a_repeated_group_keeps_its_own_occurrence(self, elements):
        model = elements['dl'].content_model
        assert (model.kind, model.min_occurs, model.max_occurs) == ('sequence', 0, None)
        assert [p.name for p in model.particles] == ['dt', 'dd']
        # the flat view still says dt/dd unbounded; only the tree says they come in runs
        assert elements['dl'].children['dt'].max_occurs is None

    def test_all_is_told_apart_from_a_sequence(self, elements):
        assert elements['head'].content_model.kind == 'all'

    def test_a_wildcard_keeps_its_namespace_constraint(self, elements):
        [wildcard] = elements['Private'].content_model.particles
        assert wildcard == Particle(
            kind='any', min_occurs=0, max_occurs=None, namespace=['##other'], process_contents='lax'
        )

    def test_a_substitution_head_is_a_choice_of_its_members(self, elements):
        [slot] = elements['template'].content_model.particles
        assert slot == Particle(
            kind='choice', min_occurs=0, max_occurs=None, particles=[_el('choose'), _el('for-each')]
        )

    def test_an_element_without_content_has_no_model(self, elements):
        assert elements['Empty'].content_model is None

    def test_an_untyped_element_accepts_anything_and_its_model_says_so(self, elements):
        [wildcard] = elements['caption'].content_model.particles
        assert (wildcard.kind, wildcard.namespace) == ('any', ['##any'])


class TestEmitted:
    def test_the_tree_is_written_in_the_occurrence_convention_of_children(self, elements, tmp_path):
        out = tmp_path / 'definition.generated.ts'
        emit_definition(elements, out)
        content = out.read_text()

        # absent minOccurs = 0 and absent maxOccurs = unbounded, as in `children.details`
        assert (
            "contentModel: { kind: 'sequence', minOccurs: 1, maxOccurs: 1, particles: ["
            "{ kind: 'element', name: 'caption', maxOccurs: 1 }, "
            "{ kind: 'choice', particles: [{ kind: 'element', name: 'col', minOccurs: 1, maxOccurs: 1 }, "
            "{ kind: 'element', name: 'colgroup', minOccurs: 1, maxOccurs: 1 }] }, "
            "{ kind: 'element', name: 'tr', minOccurs: 1 }] }"
        ) in content
        assert "{ kind: 'any', namespace: ['##other'], processContents: 'lax' }" in content
        assert "\tEmpty: {" in content and 'Empty' in content
