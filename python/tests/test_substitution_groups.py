"""Element substitution: a member of a substitution group may appear wherever its head may.

The collector must therefore see the members under every parent that names the head, must not
turn an abstract head into an element of the dialecte, and must not take the members - global
elements nobody references by name - for roots.
"""

import textwrap

import pytest
import xmlschema

from generate.collector import collect
from generate.deriver import derive_root_element, find_root_candidates
from generate.ir import ElementDef, Namespace

# A cut-down of the XSLT 2.0 schema: an abstract head with concrete members, one of which heads a
# group of its own, and a concrete head that is itself an element.
XSLT_LIKE = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
               xmlns="urn:xslt-like" targetNamespace="urn:xslt-like"
               elementFormDefault="qualified">

      <xs:element name="instruction" abstract="true"/>
      <xs:element name="for-each" substitutionGroup="instruction">
        <xs:complexType>
          <xs:sequence>
            <xs:element ref="instruction" minOccurs="0" maxOccurs="unbounded"/>
          </xs:sequence>
          <xs:attribute name="select" type="xs:string" use="required"/>
        </xs:complexType>
      </xs:element>
      <xs:element name="choose" substitutionGroup="instruction"/>
      <!-- a member that heads a group of its own: its members substitute the top head too -->
      <xs:element name="value-of" substitutionGroup="instruction"/>
      <xs:element name="copy-of" substitutionGroup="value-of"/>

      <!-- a CONCRETE head: it is an element in its own right, and its members may replace it -->
      <xs:element name="template">
        <xs:complexType>
          <xs:sequence>
            <xs:element ref="instruction" minOccurs="0" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
      <xs:element name="named-template" substitutionGroup="template"/>

      <xs:element name="stylesheet">
        <xs:complexType>
          <xs:sequence>
            <xs:element ref="template" minOccurs="0" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
    </xs:schema>
""")


@pytest.fixture()
def elements(tmp_path):
    (tmp_path / 'xslt-like.xsd').write_text(XSLT_LIKE)
    return collect(xmlschema.XMLSchema(str(tmp_path / 'xslt-like.xsd')))


class TestMembersReplaceTheirHead:
    def test_the_members_are_children_wherever_the_head_is_named(self, elements):
        # members by name: the schema keeps them as a set, and the output must not move between runs
        assert elements['template'].child_sequence == ['choose', 'copy-of', 'for-each', 'value-of']

    def test_a_member_of_a_member_substitutes_the_top_head_too(self, elements):
        assert 'copy-of' in elements['for-each'].child_sequence

    def test_the_members_inherit_the_occurrence_of_the_head_particle(self, elements):
        child = elements['template'].children['for-each']
        assert (child.min_occurs, child.max_occurs) == (0, None)

    def test_the_members_know_their_parents(self, elements):
        # named-template declares no type: it takes its head's, so it holds instructions too
        assert elements['choose'].parents == ['for-each', 'template', 'named-template']

    def test_an_abstract_head_is_not_an_element_of_the_dialecte(self, elements):
        assert 'instruction' not in elements

    def test_a_concrete_head_stays_an_element_and_its_members_join_it(self, elements):
        assert elements['stylesheet'].child_sequence == ['template', 'named-template']
        assert elements['named-template'].parents == ['stylesheet']


class TestRoots:
    def test_members_are_not_roots_the_one_unreferenced_element_is(self, elements):
        assert find_root_candidates(elements) == ['stylesheet']
        assert derive_root_element(elements) == 'stylesheet'

    def test_several_candidates_are_refused_and_named(self):
        two_roots = {
            name: ElementDef(tag=name, namespace=Namespace('', ''))
            for name in ('score-partwise', 'score-timewise')
        }
        with pytest.raises(ValueError, match='score-partwise.*score-timewise'):
            derive_root_element(two_roots)

    def test_a_chosen_root_must_be_a_candidate(self, elements):
        with pytest.raises(ValueError, match='not a root candidate'):
            derive_root_element(elements, override='template')
