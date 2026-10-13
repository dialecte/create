"""xsi:type: the named types an element may take instead of its declared one - validly derived, not blocked, not
abstract - listed on its declaration and written once each in TYPES."""
from pathlib import Path

import pytest
import xmlschema
from lxml import etree

from tests.conftest import TARGET, XS, pick, schema

XSI = 'http://www.w3.org/2001/XMLSchema-instance'


def holding(element: str, *, more: str) -> str:
    return schema(f'<xs:element name="Root"><xs:complexType><xs:sequence>{element}</xs:sequence></xs:complexType></xs:element>{more}')


BASE = (
    '<xs:complexType name="tBase"><xs:attribute name="a"/></xs:complexType>'
    '<xs:complexType name="tExt"><xs:complexContent><xs:extension base="tBase"><xs:sequence><xs:element name="Extra" type="xs:string" minOccurs="0"/>'
    '</xs:sequence><xs:attribute name="b"/></xs:extension></xs:complexContent></xs:complexType>'
)


def test_a_type_extending_the_declared_one_is_a_variant_written_once_in_types(generated_of) -> None:
    generated = generated_of(holding('<xs:element name="P" type="tBase"/>', more=BASE))
    assert pick(generated.definition, 'P.variants') == [f'{{{TARGET}}}tExt']
    variant = generated.types[f'{{{TARGET}}}tExt']
    assert variant['attributes']['sequence'] == ['a', 'b']
    assert variant['children']['sequence'] == ['Extra']
    # written relative to the type's namespace, like an element's: Extra is in it
    assert pick(variant, 'contentModel.particles')[0] == {'kind': 'element', 'name': 'Extra', 'maxOccurs': 1}
    # the element a variant only holds is declared, held by the element taking the type
    assert pick(generated.definition, 'Extra.parents') == ['P']


def test_a_declaration_keeps_its_own_attributes_and_lists_every_child_it_may_hold(definition_of) -> None:
    data = definition_of(holding('<xs:element name="P" type="tBase"/>', more=BASE))
    # without xsi:type, only the declared type's: the variants' are in TYPES
    assert pick(data, 'P.attributes.sequence') == ['a']
    assert 'contentModel' not in data['P']
    # every element the tag may hold, its variants' included (the content model says where)
    assert pick(data, 'P.children.sequence') == ['Extra']
    assert 'xsi:type' not in pick(data, 'P.attributes.details')


@pytest.mark.parametrize(
    'blocked',
    [
        pytest.param('<xs:element name="P" type="tBase" block="extension"/>', id='an element blocking extensions -> no variant'),
        pytest.param('<xs:element name="P" type="tBlocked"/>', id='a type blocking extensions -> no variant'),
    ],
)
def test_a_blocked_derivation_is_no_variant(definition_of, blocked: str) -> None:
    more = BASE + (
        '<xs:complexType name="tBlocked" block="extension"><xs:attribute name="a"/></xs:complexType>'
        '<xs:complexType name="tBlockedExt"><xs:complexContent><xs:extension base="tBlocked"><xs:attribute name="b"/>'
        '</xs:extension></xs:complexContent></xs:complexType>'
    )
    assert 'variants' not in definition_of(holding(blocked, more=more))['P']


def test_an_abstract_type_requires_a_variant_and_is_none(definition_of) -> None:
    more = (
        '<xs:complexType name="tShape" abstract="true"><xs:attribute name="id"/></xs:complexType>'
        '<xs:complexType name="tSquare"><xs:complexContent><xs:extension base="tShape"><xs:attribute name="side"/></xs:extension></xs:complexContent></xs:complexType>'
        '<xs:complexType name="tRound" abstract="true"><xs:complexContent><xs:extension base="tShape"/></xs:complexContent></xs:complexType>'
    )
    data = definition_of(holding('<xs:element name="Shape" type="tShape"/>', more=more))
    assert pick(data, 'Shape.abstractType') is True
    assert pick(data, 'Shape.variants') == [f'{{{TARGET}}}tSquare']


def test_a_simple_type_restricting_the_declared_one_is_a_variant_of_its_text(generated_of) -> None:
    more = '<xs:simpleType name="tCode"><xs:restriction base="xs:token"><xs:maxLength value="3"/></xs:restriction></xs:simpleType>'
    generated = generated_of(holding('<xs:element name="P" type="xs:token"/>', more=more))
    assert pick(generated.definition, 'P.variants') == [f'{{{TARGET}}}tCode']
    assert generated.types[f'{{{TARGET}}}tCode']['textContent'] == {'type': {'builtin': 'token', 'facets': {'maxLength': 3}}}


def test_a_type_two_elements_admit_is_written_once(generated_of) -> None:
    generated = generated_of(holding('<xs:element name="P" type="tBase"/><xs:element name="Q" type="tBase"/>', more=BASE))
    assert list(generated.types) == [f'{{{TARGET}}}tExt']
    assert pick(generated.definition, 'Q.variants') == [f'{{{TARGET}}}tExt']


def test_the_variants_are_those_libxml2_lets_an_instance_name(generated_of, tmp_path: Path) -> None:
    more = BASE + (
        '<xs:complexType name="tOther"><xs:attribute name="z"/></xs:complexType>'
        '<xs:complexType name="tRestricted"><xs:complexContent><xs:restriction base="tBase"><xs:attribute name="a" type="xs:token"/>'
        '</xs:restriction></xs:complexContent></xs:complexType>'
        '<xs:complexType name="tDeep"><xs:complexContent><xs:extension base="tExt"/></xs:complexContent></xs:complexType>'
        '<xs:complexType name="tAbstract" abstract="true"><xs:complexContent><xs:extension base="tBase"/></xs:complexContent></xs:complexType>'
    )
    entry = holding('<xs:element name="P" type="tBase" block="restriction"/>', more=more)
    generated = generated_of(entry)
    listed = set(pick(generated.definition, 'P.variants'))
    validator = etree.XMLSchema(etree.parse(str(tmp_path / 'entry.xsd')))
    # what an instance may name: its declared type, or one of the variants
    named = listed | {pick(generated.definition, 'P.type')}
    for name in ('tBase', 'tExt', 'tOther', 'tRestricted', 'tDeep', 'tAbstract'):
        instance = etree.fromstring(f'<t:Root xmlns:t="{TARGET}" xmlns:xsi="{XSI}"><t:P xsi:type="t:{name}"/></t:Root>')
        assert validator.validate(instance) == (f'{{{TARGET}}}{name}' in named), name


@pytest.mark.parametrize(
    ('element', 'declared'),
    [
        pytest.param('<xs:element name="P" type="tBase"/>', f'{{{TARGET}}}tBase', id='a named type -> its Clark name'),
        pytest.param('<xs:element name="P" type="xs:token"/>', f'{{{XS}}}token', id='a built-in type -> its Clark name'),
        pytest.param('<xs:element name="P"/>', f'{{{XS}}}anyType', id='no type -> anyType'),
        pytest.param('<xs:element name="P"><xs:complexType/></xs:element>', None, id='an anonymous type -> none'),
    ],
)
def test_a_declaration_names_its_declared_type(definition_of, element: str, declared: str | None) -> None:
    assert definition_of(holding(element, more=BASE))['P'].get('type') == declared


def test_a_selector_reaches_what_a_variant_holds(definition_of) -> None:
    more = BASE.replace('<xs:element name="Extra" type="xs:string" minOccurs="0"/>',
                        '<xs:element name="Extra" minOccurs="0" maxOccurs="unbounded"><xs:complexType><xs:attribute name="id"/></xs:complexType></xs:element>')
    entry = schema(
        '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="P" type="tBase"/></xs:sequence></xs:complexType>'
        '<xs:unique name="u"><xs:selector xpath="t:P/t:Extra"/><xs:field xpath="@id"/></xs:unique></xs:element>' + more
    )
    assert pick(definition_of(entry), 'Extra.attributes.identityFields') == ['id']


def test_an_element_of_any_type_lists_its_variants_but_no_child_of_theirs(definition_of) -> None:
    # Any already holds any element: what its variants hold is already admitted, not listed again
    data = definition_of(holding('<xs:element name="P" type="tBase"/><xs:element name="Any"/>', more=BASE))
    assert pick(data, 'Any.variants') == [f'{{{TARGET}}}tBase', f'{{{TARGET}}}tExt']
    assert pick(data, 'Any.children') == {'sequence': [], 'any': True, 'details': {}}
    assert pick(data, 'Extra.parents') == ['P']


XML_NAMESPACE_SCHEMA = (
    '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="http://www.w3.org/XML/1998/namespace">'
    '<xs:attribute name="lang" type="xs:language"/></xs:schema>'
)


def test_an_element_of_any_type_lists_no_built_in_type_in_a_schema_importing_the_xml_namespace(definition_of) -> None:
    # importing the XML namespace makes the schema library put its own anySimpleType and anyAtomicType (an XSD 1.1
    # type libxml2 does not even resolve) among the schema's types; built-in types are left to core, which knows
    # their hierarchy
    entry = schema(
        '<xs:import namespace="http://www.w3.org/XML/1998/namespace" schemaLocation="xml.xsd"/>'
        '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="Any"/></xs:sequence>'
        '<xs:attribute ref="xml:lang"/></xs:complexType></xs:element>'
        '<xs:complexType name="tBase"/>'
    )
    data = definition_of(entry, imports={'xml.xsd': XML_NAMESPACE_SCHEMA})
    assert pick(data, 'Any.variants') == [f'{{{TARGET}}}tBase']


def test_a_child_only_an_element_of_any_type_reaches_through_a_variant_has_no_parent(definition_of) -> None:
    # an element of anyType is a wildcard both ways: what it holds through a variant is no child of it, so it is no
    # parent either - the parent and child tables agree, as for any element a wildcard admits
    more = '<xs:complexType name="tHolder"><xs:sequence><xs:element name="Only" type="xs:string"/></xs:sequence></xs:complexType>'
    data = definition_of(holding('<xs:element name="Any"/>', more=more))
    assert pick(data, 'Only.parents') == []
    assert 'Only' not in pick(data, 'Any.children.sequence')


@pytest.mark.parametrize(
    'head',
    [
        pytest.param('<xs:element name="Head" type="tBase"/>', id='a head open to substitution'),
        pytest.param('<xs:element name="Head" type="tBase" block="#all"/>', id='a head blocking substitution'),
        pytest.param(
            '<xs:element name="Head" substitutionGroup="Top"/><xs:element name="Top" type="tBase" block="#all"/>',
            id='a head taking its type from a head blocking substitution',
        ),
    ],
)
def test_a_member_naming_no_type_has_its_heads_type_as_libxml2_reads_it(generated_of, tmp_path: Path, head: str) -> None:
    # Member is read before its head
    source = holding('<xs:element ref="Head"/>', more=BASE + '<xs:element name="Member" substitutionGroup="Head"/>' + head)
    generated = generated_of(source)
    assert pick(generated.definition, 'Member.attributes.sequence') == ['a']
    assert pick(generated.definition, 'Member.variants') == [f'{{{TARGET}}}tExt']
    # libxml2 reads Member with tBase's attribute a and admits tExt
    path = tmp_path / 'member.xsd'
    path.write_text(source, encoding='utf-8')
    validator = etree.XMLSchema(etree.parse(str(path)))
    for instance, valid in [('<Member a="1"/>', True), ('<Member z="1"/>', False), (f'<Member xmlns:xsi="{XSI}" xsi:type="t:tExt" b="1"/>', True)]:
        document = etree.fromstring(instance.replace('<Member', f'<t:Member xmlns:t="{TARGET}"'))
        assert validator.validate(document) is valid, instance


def test_two_elements_of_one_type_admit_what_each_one_blocks_not(definition_of) -> None:
    data = definition_of(holding('<xs:element name="P" type="tBase" block="extension"/><xs:element name="Q" type="tBase"/>', more=BASE))
    assert 'variants' not in data['P']
    assert pick(data, 'Q.variants') == [f'{{{TARGET}}}tExt']


# libxml2 flattens a union's members: it refuses one that is a union itself, which XSD - and the schema library's
# derivation check - admits
LIBXML2_UNION_FAULTS = {('Outer', 'tEither'), ('Outer', 'tNarrow')}


def test_the_simple_type_variants_are_those_libxml2_lets_an_instance_name(generated_of, tmp_path: Path) -> None:
    # a list and a union derive from anySimpleType only; a union's members, theirs, and what derives from them
    # are validly derived from it
    simple_types = {
        'tInt': ('<xs:restriction base="xs:int"/>', '1'),
        'tSmall': ('<xs:restriction base="tInt"><xs:maxInclusive value="5"/></xs:restriction>', '1'),
        'tWord': ('<xs:restriction base="xs:string"/>', 'a'),
        'tInts': ('<xs:list itemType="tInt"/>', '1 2'),
        'tEither': ('<xs:union memberTypes="tInt xs:boolean"/>', '1'),
        'tNarrow': ('<xs:restriction base="tEither"><xs:pattern value="1"/></xs:restriction>', '1'),
        'tOuter': ('<xs:union memberTypes="tEither xs:date"/>', '1'),
        'tMixed': ('<xs:union memberTypes="tInt"><xs:simpleType><xs:restriction base="xs:date"/></xs:simpleType></xs:union>', '1'),
    }
    more = ''.join(f'<xs:simpleType name="{name}">{body}</xs:simpleType>' for name, (body, _) in simple_types.items())
    elements = {'AnySimple': 'xs:anySimpleType', 'Int': 'xs:int', 'Either': 'tEither', 'Ints': 'tInts', 'Outer': 'tOuter', 'Mixed': 'tMixed'}
    entry = holding(''.join(f'<xs:element name="{name}" type="{type_name}"/>' for name, type_name in elements.items()), more=more)
    generated = generated_of(entry)
    validator = etree.XMLSchema(etree.parse(str(tmp_path / 'entry.xsd')))
    library = xmlschema.XMLSchema10(str(tmp_path / 'entry.xsd'))
    declared_types = {declaration.local_name: declaration.type for declaration in library.elements['Root'].type.content}
    for element, declared in elements.items():
        listed = set(generated.definition[element].get('variants', []))
        for name, (_, value) in simple_types.items():
            if name == declared:
                continue
            # the other elements in schema order, with a value of their own type
            children = {other: f'<t:{other}>{simple_types.get(elements[other], (None, "1"))[1]}</t:{other}>' for other in elements}
            children[element] = f'<t:{element} xsi:type="t:{name}">{value}</t:{element}>'
            instance = f'<t:Root xmlns:t="{TARGET}" xmlns:xsi="{XSI}">{"".join(children.values())}</t:Root>'
            admitted = validator.validate(etree.fromstring(instance))
            if (element, name) in LIBXML2_UNION_FAULTS:
                derived = library.maps.get_instance_type(f'{{{TARGET}}}{name}', declared_types[element], {})
                assert not admitted and derived is library.maps.types[f'{{{TARGET}}}{name}'], (element, name)
                admitted = True
            assert admitted == (f'{{{TARGET}}}{name}' in listed), (element, name)
    assert pick(generated.definition, 'AnySimple.variants') == [f'{{{TARGET}}}{name}' for name in sorted(simple_types)]
    # a built-in member is left to the reader, an anonymous one no instance can name
    assert pick(generated.definition, 'Either.variants') == [f'{{{TARGET}}}{name}' for name in ('tInt', 'tNarrow', 'tSmall')]
    assert pick(generated.definition, 'Mixed.variants') == [f'{{{TARGET}}}{name}' for name in ('tInt', 'tSmall')]


def test_an_abstract_element_admits_no_variant_and_holds_nothing_of_theirs(definition_of) -> None:
    # no instance of Head exists: what tExt holds is held by the members only
    more = BASE + '<xs:element name="Head" type="tBase" abstract="true"/><xs:element name="Member" substitutionGroup="Head"/>'
    data = definition_of(holding('<xs:element ref="Head"/>', more=more))
    assert pick(data, 'Extra.parents') == ['Member']


def test_a_tag_declared_two_ways_says_variants_and_abstract_type_on_each_way_only(definition_of) -> None:
    more = BASE + (
        '<xs:complexType name="tShape" abstract="true"/>'
        '<xs:complexType name="tSquare"><xs:complexContent><xs:extension base="tShape"/></xs:complexContent></xs:complexType>'
        '<xs:element name="Box"><xs:complexType><xs:sequence><xs:element name="P" type="tShape"/></xs:sequence></xs:complexType></xs:element>'
    )
    data = definition_of(holding('<xs:element name="P" type="tBase"/><xs:element ref="Box"/>', more=more))
    assert 'variants' not in data['P'] and 'abstractType' not in data['P']
    ways = sorted(data['P']['declarations'].values(), key=lambda way: way['variants'])
    assert [way['variants'] for way in ways] == [[f'{{{TARGET}}}tExt'], [f'{{{TARGET}}}tSquare']]
    assert [way.get('abstractType') for way in ways] == [None, True]


def test_a_tag_declared_two_ways_lists_its_children_in_the_ways_order_not_the_reading_order(definition_of) -> None:
    # the local Zed is read first (Root comes before Zed); the global one is the first way
    more = '<xs:element name="Zed"><xs:complexType><xs:sequence><xs:element name="FromGlobal"/></xs:sequence></xs:complexType></xs:element>'
    local = '<xs:element name="Zed"><xs:complexType><xs:sequence><xs:element name="FromLocal"/></xs:sequence></xs:complexType></xs:element>'
    data = definition_of(holding(local, more=more))
    assert pick(data, 'Zed.children.sequence') == ['FromGlobal', 'FromLocal']


def test_a_member_naming_its_own_type_keeps_it(definition_of) -> None:
    more = BASE + '<xs:element name="Head" type="tBase" block="#all"/><xs:element name="Member" type="tExt" substitutionGroup="Head"/>'
    assert pick(definition_of(holding('<xs:element ref="Head"/>', more=more)), 'Member.attributes.sequence') == ['a', 'b']


CHAIN = BASE + (
    '<xs:complexType name="tRes"><xs:complexContent><xs:restriction base="tExt"><xs:attribute name="b" type="xs:token"/>'
    '</xs:restriction></xs:complexContent></xs:complexType>'
    '<xs:simpleType name="tInt"><xs:restriction base="xs:int"/></xs:simpleType>'
    '<xs:simpleType name="tEither"><xs:union memberTypes="tInt xs:boolean"/></xs:simpleType>'
    '<xs:simpleType name="tNarrow"><xs:restriction base="tEither"><xs:pattern value="1"/></xs:restriction></xs:simpleType>'
    '<xs:complexType name="tIntMeasure"><xs:simpleContent><xs:extension base="tInt"><xs:attribute name="unit"/></xs:extension>'
    '</xs:simpleContent></xs:complexType>'
)
CHAIN_VALUES = {'tBase': '', 'tExt': '', 'tRes': '', 'tInt': '1', 'tEither': '1', 'tNarrow': '1', 'tIntMeasure': '1'}


@pytest.mark.parametrize(
    ('element', 'attributes'),
    [
        pytest.param('<xs:element name="P" block="extension"/>', '', id='an element blocking extensions, anywhere in the chain'),
        pytest.param('<xs:element name="P"/>', 'blockDefault="extension"', id='a schema blocking extensions by default'),
        pytest.param('<xs:element name="P" type="tEither" block="restriction"/>', '', id='a union blocking restrictions, members included'),
        pytest.param('<xs:element name="P" type="tEither" block="extension"/>', '', id='a union blocking extensions'),
        pytest.param('<xs:element name="P" type="tNarrow"/>', '', id='a restriction of a union admitting none of its members'),
    ],
)
def test_every_step_of_a_derivation_is_checked_against_what_is_blocked_as_libxml2_does(
    generated_of, tmp_path: Path, element: str, attributes: str
) -> None:
    body = f'<xs:element name="Root"><xs:complexType><xs:sequence>{element}</xs:sequence></xs:complexType></xs:element>'
    generated = generated_of(schema(body + CHAIN, attributes=attributes))
    validator = etree.XMLSchema(etree.parse(str(tmp_path / 'entry.xsd')))
    listed = set(generated.definition['P'].get('variants', []))
    for name, value in CHAIN_VALUES.items():
        if f'type="{name}"' in element:
            continue
        instance = f'<t:Root xmlns:t="{TARGET}" xmlns:xsi="{XSI}"><t:P xsi:type="t:{name}">{value}</t:P></t:Root>'
        assert validator.validate(etree.fromstring(instance)) == (f'{{{TARGET}}}{name}' in listed), name
