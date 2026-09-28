"""Homonyms: one local name declared with different content under different parents.

A dialecte knows an element by its tag name, so the declarations are merged. The merge must not
lose anything a valid document may hold (union, everything optional unless required everywhere),
and it must be visible: each declaration is written on the edge from its parent, and the run report
lists the parents concerned.
"""

import textwrap

import pytest
import xmlschema

from generate.collector import collect
from generate.deriver import assign_identity_fields, derive_identity_fields
from generate.emitters.definition import emit_definition

# A cut-down of PLC TC6 and MusicXML: `variable` is a structure under `struct` and a bare string
# under `coil`; `part` and `measure` nest one way in a partwise score, the other way in a timewise one.
HOMONYMS = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
      <xs:element name="struct">
        <xs:complexType><xs:sequence>
          <xs:element name="variable" minOccurs="1" maxOccurs="unbounded">
            <xs:complexType>
              <xs:sequence><xs:element name="type" minOccurs="1"/></xs:sequence>
              <xs:attribute name="name" type="xs:string" use="required"/>
              <xs:attribute name="address" type="xs:string"/>
            </xs:complexType>
          </xs:element>
        </xs:sequence></xs:complexType>
        <xs:unique name="variableName"><xs:selector xpath="variable"/><xs:field xpath="@name"/></xs:unique>
      </xs:element>
      <xs:element name="coil">
        <xs:complexType><xs:sequence>
          <xs:element name="variable" type="xs:string"/>
        </xs:sequence></xs:complexType>
      </xs:element>
      <xs:element name="note"/>
      <xs:element name="score-partwise">
        <xs:complexType><xs:sequence>
          <xs:element name="part"><xs:complexType><xs:sequence>
            <xs:element name="measure" maxOccurs="unbounded"><xs:complexType><xs:sequence>
              <xs:element ref="note" minOccurs="0" maxOccurs="unbounded"/>
            </xs:sequence></xs:complexType></xs:element>
          </xs:sequence></xs:complexType></xs:element>
        </xs:sequence></xs:complexType>
      </xs:element>
      <xs:element name="score-timewise">
        <xs:complexType><xs:sequence>
          <xs:element name="measure"><xs:complexType><xs:sequence>
            <xs:element name="part" maxOccurs="unbounded"><xs:complexType><xs:sequence>
              <xs:element ref="note" minOccurs="0" maxOccurs="unbounded"/>
            </xs:sequence></xs:complexType></xs:element>
          </xs:sequence></xs:complexType></xs:element>
        </xs:sequence></xs:complexType>
      </xs:element>
      <!-- the same named type under two parents: no homonym, nothing to report -->
      <xs:complexType name="tLabel"><xs:attribute name="text" type="xs:string" use="required"/></xs:complexType>
      <xs:element name="a"><xs:complexType><xs:sequence><xs:element name="label" type="tLabel"/></xs:sequence></xs:complexType></xs:element>
      <xs:element name="b"><xs:complexType><xs:sequence><xs:element name="label" type="tLabel"/></xs:sequence></xs:complexType></xs:element>
    </xs:schema>
""")


@pytest.fixture()
def elements(tmp_path):
    (tmp_path / 'homonyms.xsd').write_text(HOMONYMS)
    return collect(xmlschema.XMLSchema(str(tmp_path / 'homonyms.xsd')))


class TestUnion:
    def test_the_children_of_every_declaration_are_kept(self, elements):
        assert elements['part'].child_sequence == ['measure', 'note']
        assert elements['measure'].child_sequence == ['note', 'part']

    def test_a_child_required_under_one_parent_only_is_optional(self, elements):
        # `type` is required in the struct variable and absent from the coil one
        assert elements['variable'].children['type'].required is False
        assert elements['variable'].children['type'].min_occurs == 0

    def test_an_attribute_required_under_one_parent_only_is_optional(self, elements):
        assert elements['variable'].attributes['name'].required is False

    def test_an_attribute_required_everywhere_stays_required(self, elements):
        assert elements['label'].attributes['text'].required is True

    def test_the_largest_occurrence_wins(self, elements):
        # measure: unbounded under part, once under score-timewise
        assert elements['part'].children['measure'].max_occurs is None

    def test_text_content_declared_under_one_parent_is_kept(self, elements):
        assert elements['variable'].text_content is not None

    def test_the_content_models_are_not_merged_but_offered_as_a_choice(self, elements):
        model = elements['part'].content_model
        assert model.kind == 'choice' and model.of_declarations
        assert [[p.name for p in alternative.particles] for alternative in model.particles] == [
            ['measure'],
            ['note'],
        ]


class TestDeclarationsByParent:
    def test_a_homonym_keeps_a_declaration_under_each_of_its_parents(self, elements):
        assert sorted(elements['variable'].definitions_by_parent) == ['coil', 'struct']
        assert sorted(elements['part'].definitions_by_parent) == ['measure', 'score-partwise']

    def test_the_same_named_type_under_two_parents_is_not_a_homonym(self, elements):
        assert elements['label'].definitions_by_parent == {}
        assert elements['note'].definitions_by_parent == {}


class TestDefinitionOnTheEdge:
    """The runtime reads the definition where it lives: on the edge from the parent. It is a full
    element definition, the same shape as the tag-level one, so a reader needs no second type."""

    def test_a_homonym_keeps_each_full_definition_by_parent(self, elements):
        struct = elements['variable'].definitions_by_parent['struct']
        coil = elements['variable'].definitions_by_parent['coil']
        assert struct.tag == coil.tag == 'variable'
        assert struct.parents == ['struct'] and coil.parents == ['coil']
        assert struct.attributes['name'].required is True  # untouched by the union
        assert struct.child_sequence == ['type']
        assert coil.attributes == {} and coil.child_sequence == []
        assert coil.text_content is not None and struct.text_content is None

    def test_an_element_declared_once_has_no_definition_by_parent(self, elements):
        assert elements['label'].definitions_by_parent == {}
        assert elements['note'].definitions_by_parent == {}

    def test_identity_fields_are_those_of_the_definition_they_are_declared_in(self, elements):
        assign_identity_fields(elements, derive_identity_fields(elements))
        assert elements['variable'].identity_fields == ['name']
        assert elements['variable'].definitions_by_parent['struct'].identity_fields == ['name']
        # coil's variable has no `name`: nothing identifies it there
        assert elements['variable'].definitions_by_parent['coil'].identity_fields == []

    def test_the_edge_carries_the_content_declared_under_that_parent(self, elements, tmp_path):
        # The edge is the child's declaration under this parent: its occurrence and namespace were
        # already there; what the declaration holds sits next to them, not in a nested definition.
        assign_identity_fields(elements, derive_identity_fields(elements))
        out = tmp_path / 'definition.generated.ts'
        emit_definition(elements, out)
        content = out.read_text()
        assert 'definition: {' not in content

        coil = content[content.index('\n\tcoil: {'):]
        coil = coil[: coil.index('\n\t},')]
        variable_under_coil = coil[coil.index('\t\t\t\tvariable: {'):]
        assert 'attributes: {' in variable_under_coil and 'children: {' in variable_under_coil
        assert 'textContent: {' in variable_under_coil
        assert 'identityFields' not in variable_under_coil
        # the tag-level fields stay at the tag level
        assert "tag: 'variable'" not in coil and 'parents:' not in variable_under_coil

        struct = content[content.index('\n\tstruct: {'):]
        struct = struct[: struct.index('\n\t},')]
        assert 'name: { required: true' in struct  # as declared under struct
        assert "identityFields: ['name']" in struct
        assert 'contentModel: {' in struct[struct.index('\t\t\t\tvariable: {'):]
        # the parents concerned are the edges carrying content: no second list to keep in sync
        assert 'homonyms' not in content

    def test_an_element_declared_once_keeps_bare_edges(self, elements, tmp_path):
        out = tmp_path / 'definition.generated.ts'
        emit_definition(elements, out)
        content = out.read_text()
        a = content[content.index('\n\ta: {'):]
        a = a[: a.index('\n\t},')]
        label_edge = next(line for line in a.splitlines() if line.strip().startswith('label:'))
        assert label_edge.rstrip().endswith('},')  # one line: occurrence only
        assert 'attributes' not in label_edge
