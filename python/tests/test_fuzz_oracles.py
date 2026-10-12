"""The fuzzer's tie-breakers, on schemas whose verdict the specification settles: a finding both libraries support
fails, and the specification's own substitution rule reads every block of the chain."""
from pathlib import Path

from proof import fuzz
from proof.corpus import CorpusSchema

HEAD = (
    '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:a="urn:fuzz:a" targetNamespace="urn:fuzz:a" '
    'elementFormDefault="qualified">{body}</xs:schema>'
)


def _schema(tmp_path: Path, body: str) -> CorpusSchema:
    entry = tmp_path / 'a.xsd'
    entry.write_text(HEAD.format(body=body), encoding='utf-8')
    return CorpusSchema(id='case', entry=entry)


def test_a_type_both_libraries_refuse_as_xsi_type_is_a_finding_they_agree_on(tmp_path: Path) -> None:
    schema = _schema(
        tmp_path,
        '<xs:complexType name="T0"/><xs:complexType name="TU"><xs:attribute name="u"/></xs:complexType>'
        '<xs:element name="Root" type="a:T0"/>',
    )
    # an `extra` variant: the definition would list TU, both libraries refuse it (not derived from T0)
    assert fuzz._library_agrees_with_libxml2(schema, 'variants', 'extra/{urn:fuzz:a}Root/{urn:fuzz:a}TU')


def test_an_intermediate_type_blocking_extension_blocks_the_extension_above_it_too(tmp_path: Path) -> None:
    # T2 extends T1 (which blocks extension), T1 restricts T0: every method of the chain meets the union of blocks
    schema = _schema(
        tmp_path,
        '<xs:complexType name="T0"/>'
        '<xs:complexType name="T1" block="extension"><xs:complexContent><xs:restriction base="a:T0"/></xs:complexContent></xs:complexType>'
        '<xs:complexType name="T2"><xs:complexContent><xs:extension base="a:T1"/></xs:complexContent></xs:complexType>'
        '<xs:element name="M0" type="a:T0"/><xs:element name="M1" substitutionGroup="a:M0" type="a:T2"/>',
    )
    library = schema.library
    assert not fuzz._substitutes(library, library.elements['M0'], library.elements['M1'])


def test_an_abstract_head_stands_for_nothing_itself(tmp_path: Path) -> None:
    (tmp_path / 'b.xsd').write_text(
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:b="urn:fuzz:b" targetNamespace="urn:fuzz:b" '
        'elementFormDefault="qualified"><xs:complexType name="T0"/><xs:element name="BHead" type="b:T0" abstract="true"/>'
        '</xs:schema>',
        encoding='utf-8',
    )
    schema = _schema(
        tmp_path,
        '<xs:import namespace="urn:fuzz:b" schemaLocation="b.xsd"/>'
        '<xs:element name="HoldsB" xmlns:b="urn:fuzz:b"><xs:complexType><xs:sequence><xs:element ref="b:BHead" minOccurs="0"/>'
        '</xs:sequence></xs:complexType></xs:element>',
    )
    draw = fuzz.Draw(a='', b='', holders={'HoldsB': ['BHead']})
    # libxml2 refuses <BHead/> (`extra` if a definition held it); the specification refuses it too
    assert fuzz._specification_agrees_with_libxml2(schema, draw, 'extra/HoldsB/BHead')
    assert not fuzz._specification_agrees_with_libxml2(schema, draw, 'missing/HoldsB/BHead')
