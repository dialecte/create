"""The entry point end to end, on schemas small enough to read."""

import textwrap

import pytest

from generate.__main__ import main

TWO_ROOTS = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
      <xs:element name="Item"><xs:complexType><xs:attribute name="id" type="xs:string" use="required"/></xs:complexType></xs:element>
      <xs:element name="score-partwise">
        <xs:complexType><xs:sequence><xs:element ref="Item" minOccurs="0" maxOccurs="unbounded"/></xs:sequence></xs:complexType>
      </xs:element>
      <xs:element name="score-timewise">
        <xs:complexType><xs:sequence><xs:element ref="Item" minOccurs="0"/></xs:sequence></xs:complexType>
      </xs:element>
    </xs:schema>
""")

ONE_ROOT_AND_ORPHANS = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
      <xs:element name="Root">
        <xs:complexType><xs:sequence><xs:any processContents="lax" minOccurs="0" maxOccurs="unbounded"/></xs:sequence></xs:complexType>
      </xs:element>
      <!-- reachable through the wildcard only: an orphan, mapped by the sidecar -->
      <xs:element name="Extra"><xs:complexType><xs:attribute name="n" type="xs:string"/></xs:complexType></xs:element>
    </xs:schema>
""")


def _generate(tmp_path, xsd: str, *args: str) -> str:
    entry = tmp_path / 'schema.xsd'
    entry.write_text(xsd)
    out = tmp_path / 'out'
    main(['--entry', str(entry), '--out-dir', str(out), *args])
    return (out / 'constants.generated.ts').read_text()


class TestRootChoice:
    def test_two_candidates_without_a_choice_fail_naming_them(self, tmp_path):
        with pytest.raises(ValueError, match='--root.*score-partwise, score-timewise'):
            _generate(tmp_path, TWO_ROOTS)

    def test_the_chosen_root_is_taken(self, tmp_path):
        constants = _generate(tmp_path, TWO_ROOTS, '--root', 'score-timewise')
        assert "export const ROOT_ELEMENT = 'score-timewise' as const" in constants

    def test_a_choice_that_is_not_a_candidate_fails(self, tmp_path):
        with pytest.raises(ValueError, match="'Item' is not a root candidate"):
            _generate(tmp_path, TWO_ROOTS, '--root', 'Item')

    def test_orphans_mapped_by_the_sidecar_are_not_root_candidates(self, tmp_path):
        (tmp_path / 'parent-mapping.json').write_text('{"Extra": ["Root"]}')
        constants = _generate(tmp_path, ONE_ROOT_AND_ORPHANS)
        assert "export const ROOT_ELEMENT = 'Root' as const" in constants
        assert "Extra: ['Root']" in constants or "\tExtra: ['Root']" in constants


HOMONYM = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
      <xs:element name="Root">
        <xs:complexType><xs:sequence>
          <xs:element name="struct"><xs:complexType><xs:sequence>
            <xs:element name="variable"><xs:complexType><xs:attribute name="name" type="xs:string"/></xs:complexType></xs:element>
          </xs:sequence></xs:complexType></xs:element>
          <xs:element name="coil"><xs:complexType><xs:sequence>
            <xs:element name="variable" type="xs:string"/>
          </xs:sequence></xs:complexType></xs:element>
          <!-- the string declaration again, under a third parent: it differs from struct's too -->
          <xs:element name="contact"><xs:complexType><xs:sequence>
            <xs:element name="variable" type="xs:string"/>
          </xs:sequence></xs:complexType></xs:element>
        </xs:sequence></xs:complexType>
      </xs:element>
    </xs:schema>
""")


class TestHomonymReport:
    def test_a_homonym_is_reported_with_every_parent_it_is_declared_under(self, tmp_path, capsys):
        # coil and contact share one declaration: both are listed, not only the last one seen
        _generate(tmp_path, HOMONYM)

        assert (
            "WARNING: 'variable' is declared with different content under: coil, contact, struct"
            in capsys.readouterr().err
        )

    def test_the_summary_counts_them(self, tmp_path, capsys):
        _generate(tmp_path, HOMONYM)

        assert '1 homonym' in capsys.readouterr().out
