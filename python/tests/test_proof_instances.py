"""The instance tier's two judges on inline rows: for each document, the structural faults the definition predicts
(their families) are those libxml2 finds - a row with a fault and a row without, for every structural fact the walk reads."""
from pathlib import Path

import pytest
from lxml import etree

from proof.instances import COMPARED, judge, predict
from tests.conftest import TARGET, schema

XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'

# one schema, every structural fact the walk reads: a sequence with occurrences, a choice, an all group, a tag declared two
# ways (by parent and by namespace), element and attribute wildcards, required / fixed attributes, nillable, mixed and
# simple content, xsi:type, a fixed value its pattern constrains too
SCHEMA = schema(
    '<xs:element name="Root"><xs:complexType><xs:sequence>'
    '<xs:element name="A" type="tA" minOccurs="0" maxOccurs="2"/>'
    '<xs:choice minOccurs="0"><xs:element name="C1"/><xs:element name="C2"/></xs:choice>'
    '<xs:element name="All" minOccurs="0"><xs:complexType><xs:all><xs:element name="X"/><xs:element name="Y" minOccurs="0"/></xs:all></xs:complexType></xs:element>'
    '<xs:element name="Left" minOccurs="0"><xs:complexType><xs:sequence><xs:element name="Item"><xs:complexType><xs:attribute name="l" use="required"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="Right" minOccurs="0"><xs:complexType><xs:sequence><xs:element name="Item"><xs:complexType><xs:attribute name="r" use="required"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="Open" minOccurs="0"><xs:complexType><xs:sequence><xs:any namespace="##other" processContents="strict" minOccurs="0"/>'
    '<xs:any namespace="##local" processContents="skip" minOccurs="0"/></xs:sequence><xs:anyAttribute namespace="##other" processContents="lax"/></xs:complexType></xs:element>'
    '<xs:element name="Lax" minOccurs="0"><xs:complexType><xs:sequence><xs:any processContents="lax" minOccurs="0" maxOccurs="unbounded"/></xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="Nil" type="xs:int" nillable="true" minOccurs="0"/>'
    '<xs:element name="Mixed" minOccurs="0"><xs:complexType mixed="true"><xs:sequence><xs:element name="B" minOccurs="0"/></xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="Simple" type="xs:string" minOccurs="0"/>'
    '<xs:element name="P" type="tBase" minOccurs="0"/>'
    '<xs:element name="Abs" type="tAbs" minOccurs="0"/>'
    '<xs:element name="Empty" minOccurs="0"><xs:complexType/></xs:element>'
    '<xs:element name="NilFix" type="xs:string" nillable="true" fixed="f" minOccurs="0"/>'
    '</xs:sequence><xs:attribute name="req" use="required"/><xs:attribute name="fix" fixed="1"/>'
    '<xs:attribute name="fixn" type="xs:normalizedString" fixed="a b"/>'
    '<xs:attribute name="fixp" fixed="ABC"><xs:simpleType><xs:restriction base="xs:string"><xs:pattern value="[A-Z]+"/>'
    '</xs:restriction></xs:simpleType></xs:attribute></xs:complexType></xs:element>'
    '<xs:complexType name="tA"><xs:attribute name="a" type="xs:token" fixed="v"/></xs:complexType>'
    '<xs:complexType name="tBase"><xs:sequence><xs:element name="Base" minOccurs="0"/></xs:sequence></xs:complexType>'
    '<xs:complexType name="tExt"><xs:complexContent><xs:extension base="tBase"><xs:sequence><xs:element name="Extra"/></xs:sequence>'
    '<xs:attribute name="e" use="required"/></xs:extension></xs:complexContent></xs:complexType>'
    '<xs:complexType name="tAbs" abstract="true"><xs:sequence><xs:element name="Need"/></xs:sequence></xs:complexType>'
    '<xs:complexType name="tAbsExt"><xs:complexContent><xs:extension base="tAbs"/></xs:complexContent></xs:complexType>'
    '<xs:element name="Global"/>'
)
OTHER = '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:other" elementFormDefault="qualified"><xs:element name="G"/></xs:schema>'


def document(body: str, *, root_attributes: str = 'req="1"') -> str:
    return (
        f'<Root xmlns="{TARGET}" xmlns:xsi="{XSI_NS}" xmlns:o="urn:other" xmlns:t="{TARGET}" '
        f'xmlns:xs="http://www.w3.org/2001/XMLSchema" {root_attributes}>{body}</Root>'
    )


ROWS = [
    pytest.param(document(''), id='the smallest valid document'),
    pytest.param(document('', root_attributes=''), id='a required attribute missing'),
    pytest.param(document('', root_attributes='req="1" fix="1"'), id='a fixed attribute at its value'),
    pytest.param(document('', root_attributes='req="1" fix="2"'), id='a fixed attribute at another value'),
    pytest.param(document('<A a=" v "/>'), id='a fixed token compared after its whitespace collapses'),
    pytest.param(document('', root_attributes='req="1" fixn="a&#9;b"'), id='a fixed normalizedString: a tab replaced by a space'),
    pytest.param(document('', root_attributes='req="1" fixn="a  b"'), id='a fixed normalizedString: spaces not collapsed'),
    pytest.param(document('', root_attributes='req="1" zz="1"'), id='an undeclared attribute'),
    pytest.param(document('<A/><A/>'), id='a child repeated up to its maximum'),
    pytest.param(document('<A/><A/><A/>'), id='a child repeated past its maximum'),
    pytest.param(document('<C2/>'), id='one branch of a choice'),
    pytest.param(document('<C1/><C2/>'), id='two branches of a choice'),
    pytest.param(document('<All><Y/><X/></All>'), id='an all group in another order'),
    pytest.param(document('<All><Y/></All>'), id='an all group missing a required child'),
    pytest.param(document('<Left><Item l="1"/></Left>'), id='a tag declared two ways, as its parent declares it'),
    pytest.param(document('<Left><Item r="1"/></Left>'), id='a tag declared two ways, with the other way\'s attribute'),
    pytest.param(document('<Open><o:G/></Open>'), id='a strict wildcard admitting a declared foreign element'),
    pytest.param(document('<Open><o:Z/></Open>'), id='a strict wildcard admitting a foreign element with no declaration'),
    pytest.param(document('<Open><Global/></Open>', root_attributes='req="1"'), id='##other refusing the target namespace'),
    pytest.param(document('<Open o:x="1"/>'), id='an attribute wildcard admitting a foreign attribute'),
    pytest.param(document('<Open x="1"/>'), id='an attribute wildcard refusing an attribute in no namespace'),
    pytest.param(document('<Lax><Unknown><Global zz="1"/></Unknown></Lax>'), id='a lax wildcard: an undeclared element, a declared one inside'),
    pytest.param(document('<Lax><Global><Inner/></Global></Lax>'), id='a lax wildcard: a declared element holding what it may not'),
    pytest.param(document('<Lax><Unknown xsi:type="t:tAbsExt"/></Lax>'), id='a lax wildcard: an undeclared element assessed by the type it names'),
    pytest.param(document('<Lax><Unknown xsi:type="xs:int">x</Unknown></Lax>'), id='a lax wildcard: an undeclared element naming a built-in type'),
    pytest.param(document('<Nil xsi:nil="true"/>'), id='a nillable element nil'),
    pytest.param(document('<Nil xsi:nil="true">1</Nil>'), id='a nil element holding text'),
    pytest.param(document('<A xsi:nil="true"/>'), id='nil on an element that is not nillable'),
    pytest.param(document('<A xsi:nil="true"><B/></A>'), id='nil refused: the content is still assessed'),
    pytest.param(document('<NilFix xsi:nil="true"/>'), id='nil on an element with a fixed value'),
    pytest.param(document('<Empty>\n  </Empty>'), id='whitespace in empty content'),
    pytest.param(document('<Empty/>'), id='empty content, empty'),
    pytest.param(document('<Mixed>text<B/>more</Mixed>'), id='text in mixed content'),
    pytest.param(document('text'), id='text in element-only content'),
    pytest.param(document('<Simple><B/></Simple>'), id='a child in simple content'),
    pytest.param(document('<P><Base/></P>'), id='an element as its declared type'),
    pytest.param(document('<P xsi:type="t:tExt" e="1"><Base/><Extra/></P>'), id='an element as the type it names'),
    pytest.param(document('<P xsi:type="t:tExt"><Base/></P>'), id='an element missing what the type it names requires'),
    pytest.param(document('<P xsi:type="t:tBase"><Base/></P>'), id='an element naming its declared type'),
    pytest.param(document('<P xsi:type="xs:string" e="1"><Base/></P>'), id='a built-in type refused: assessed by its declaration'),
    pytest.param(document('<P xsi:type="t:tAbsExt"><Base/><Need/></P>'), id='an unrelated type refused: assessed by its declaration'),
    pytest.param(document('<P xsi:type="u:tExt"><Base/></P>'), id='a type of an unbound prefix refused: assessed by its declaration'),
    pytest.param(document('<Abs xsi:type="t:tBase"/>'), id='an abstract type, the type named refused: its content is not assessed'),
    pytest.param(document('<Abs/>'), id='an abstract type named by no xsi:type: its content is not assessed'),
    pytest.param(document('<Abs xsi:type="t:tAbsExt"/>'), id='an abstract type replaced by the type named: its content is'),
    pytest.param(document('<B/>'), id='a child no particle names'),
    pytest.param(document('<o:A/>'), id='a child in another namespace than its particle'),
    pytest.param(document('<Left><Item/><Item l="1"/></Left>'), id='a child before the first refused one is still assessed'),
]


@pytest.mark.parametrize('instance', ROWS)
def test_the_definition_predicts_the_structural_faults_libxml2_finds(tmp_path: Path, generated_of, instance: str) -> None:
    (tmp_path / 'other.xsd').write_text(OTHER, encoding='utf-8')
    entry = SCHEMA.replace('<xs:element name="Root">', '<xs:import namespace="urn:other" schemaLocation="other.xsd"/><xs:element name="Root">')
    generated = generated_of(entry)
    validator = etree.XMLSchema(etree.parse(str(tmp_path / 'entry.xsd')))
    root = etree.fromstring(instance)
    prediction = predict(definition=generated.definition, types=generated.types, root=root)
    assert prediction.unpredictable == []
    assert prediction.families() & COMPARED == judge(validator, root) & COMPARED, prediction.faults


def test_libxml2_reads_a_memberless_abstract_head_as_empty_and_the_walk_can_read_it_so(tmp_path: Path, generated_of) -> None:
    # a choice holding only an abstract element no member substitutes for admits nothing; libxml2 skips it
    generated = generated_of(
        schema(
            '<xs:element name="Head" abstract="true"/>'
            '<xs:element name="R"><xs:complexType><xs:sequence><xs:element name="A"/>'
            '<xs:choice><xs:element ref="t:Head"/></xs:choice></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="S"><xs:complexType><xs:sequence><xs:element name="A"/></xs:sequence></xs:complexType></xs:element>'
        )
    )
    validator = etree.XMLSchema(etree.parse(str(tmp_path / 'entry.xsd')))
    root = etree.fromstring(f'<R xmlns="{TARGET}"><A/></R>')
    spec, as_libxml2 = (predict(definition=generated.definition, types=generated.types, root=root, as_libxml2=reading) for reading in (False, True))
    assert (spec.families(), spec.read_as_libxml2) == (frozenset({'content'}), False)
    assert (as_libxml2.families(), as_libxml2.read_as_libxml2) == (frozenset(), True)
    assert judge(validator, root) == frozenset()
    # no empty choice in play: the reading changes nothing, so it explains nothing
    plain = etree.fromstring(f'<S xmlns="{TARGET}"><B/></S>')
    assert predict(definition=generated.definition, types=generated.types, root=plain, as_libxml2=True).read_as_libxml2 is False
