"""The attribute wildcard of a type: what it declares (its own and its attribute groups', intersected),
united with its base type's along an extension, each resolved in the document that writes it. Every
row is checked twice: against the expected wildcard, and against what libxml2 lets an instance carry."""
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from generate_next.errors import SchemaNotRepresentable
from tests_next.conftest import TARGET, pick, schema

EXT = 'urn:dialecte:ext'
# the namespaces an attribute is tried in, '' for none
PROBES = ('', TARGET, EXT, 'urn:a', 'urn:b', 'urn:c')


def root(content: str, *, more: str = '') -> str:
    return schema(f'<xs:element name="Root"><xs:complexType>{content}</xs:complexType></xs:element>{more}')


CASES: dict[str, tuple[str, dict[str, str], dict[str, Any] | None]] = {
    'a wildcard beside an attribute group with one -> what both admit, processed as the type\'s own says': (
        root(
            '<xs:attributeGroup ref="gOpen"/><xs:anyAttribute namespace="urn:a urn:b" processContents="lax"/>',
            more='<xs:attributeGroup name="gOpen"><xs:anyAttribute namespace="urn:b urn:c" processContents="skip"/></xs:attributeGroup>',
        ),
        {},
        {'namespace': ['urn:b'], 'processContents': 'lax'},
    ),
    'only an attribute group admits other attributes -> its wildcard, resolved in its own document': (
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:attributeGroup ref="e:gOpen"/></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}"',
        ),
        {
            'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="{EXT}">'
            '<xs:attributeGroup name="gOpen"><xs:anyAttribute namespace="##other" processContents="lax"/></xs:attributeGroup></xs:schema>'
        },
        {'notNamespace': ['', EXT], 'processContents': 'lax'},
    ),
    'two attribute groups, one admitting all but some, one listing -> the listed ones not excluded': (
        root(
            '<xs:attributeGroup ref="gOther"/><xs:attributeGroup ref="gListed"/>',
            more='<xs:attributeGroup name="gOther"><xs:anyAttribute namespace="##other" processContents="skip"/></xs:attributeGroup>'
            f'<xs:attributeGroup name="gListed"><xs:anyAttribute namespace="urn:a {TARGET}" processContents="lax"/></xs:attributeGroup>',
        ),
        {},
        {'namespace': ['urn:a'], 'processContents': 'skip'},
    ),
    'a wildcard admitting any namespace beside an attribute group admitting other ones -> the other ones': (
        root(
            '<xs:attributeGroup ref="gOther"/><xs:anyAttribute processContents="lax"/>',
            more='<xs:attributeGroup name="gOther"><xs:anyAttribute namespace="##other" processContents="skip"/></xs:attributeGroup>',
        ),
        {},
        {'notNamespace': ['', TARGET], 'processContents': 'lax'},
    ),
    'other namespaces than the target one, and than none (a no-namespace group) -> other than the target one': (
        (
            f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:t="{TARGET}" targetNamespace="{TARGET}" elementFormDefault="qualified">'
            '<xs:import schemaLocation="none.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:attributeGroup ref="gOther"/>'
            '<xs:anyAttribute namespace="##other" processContents="lax"/></xs:complexType></xs:element></xs:schema>'
        ),
        {
            'none.xsd': '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
            '<xs:attributeGroup name="gOther"><xs:anyAttribute namespace="##other" processContents="skip"/></xs:attributeGroup></xs:schema>'
        },
        {'notNamespace': ['', TARGET], 'processContents': 'lax'},
    ),
    'a wildcard and an attribute group admitting nothing in common -> no wildcard': (
        root(
            '<xs:attributeGroup ref="gOpen"/><xs:anyAttribute namespace="urn:a" processContents="lax"/>',
            more='<xs:attributeGroup name="gOpen"><xs:anyAttribute namespace="urn:b" processContents="lax"/></xs:attributeGroup>',
        ),
        {},
        None,
    ),
    'an extension declaring no wildcard, of a base that has one -> the base\'s, inherited': (
        root(
            '<xs:complexContent><xs:extension base="tOpen"/></xs:complexContent>',
            more='<xs:complexType name="tOpen"><xs:anyAttribute namespace="##other" processContents="lax"/></xs:complexType>',
        ),
        {},
        {'notNamespace': ['', TARGET], 'processContents': 'lax'},
    ),
    'a type extending a type of another schema, both admitting other attributes -> any namespace but none': (
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:complexContent><xs:extension base="e:tOpen">'
            '<xs:anyAttribute namespace="##other" processContents="lax"/></xs:extension></xs:complexContent></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}"',
        ),
        {
            'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="{EXT}">'
            '<xs:complexType name="tOpen"><xs:anyAttribute namespace="##other" processContents="lax"/></xs:complexType></xs:schema>'
        },
        {'notNamespace': [''], 'processContents': 'lax'},
    ),
    'an extension listing a namespace over a base admitting any -> any, processed as the extension says': (
        root(
            '<xs:complexContent><xs:extension base="tOpen"><xs:anyAttribute namespace="urn:a" processContents="skip"/></xs:extension></xs:complexContent>',
            more='<xs:complexType name="tOpen"><xs:anyAttribute processContents="lax"/></xs:complexType>',
        ),
        {},
        {'notNamespace': [], 'processContents': 'skip'},
    ),
    'an extension of an extension, each listing one namespace -> all three': (
        root(
            '<xs:complexContent><xs:extension base="tMiddle"><xs:anyAttribute namespace="urn:c" processContents="lax"/></xs:extension></xs:complexContent>',
            more='<xs:complexType name="tBase"><xs:anyAttribute namespace="urn:a" processContents="lax"/></xs:complexType>'
            '<xs:complexType name="tMiddle"><xs:complexContent><xs:extension base="tBase">'
            '<xs:anyAttribute namespace="urn:b" processContents="lax"/></xs:extension></xs:complexContent></xs:complexType>',
        ),
        {},
        {'namespace': ['urn:a', 'urn:b', 'urn:c'], 'processContents': 'lax'},
    ),
    'a simple content extension admitting other attributes -> its wildcard': (
        root(
            '<xs:simpleContent><xs:extension base="xs:token"><xs:anyAttribute namespace="urn:a" processContents="lax"/></xs:extension></xs:simpleContent>'
        ),
        {},
        {'namespace': ['urn:a'], 'processContents': 'lax'},
    ),
    'an attribute group redefined over itself -> its wildcard intersected with the one it redefines': (
        schema(
            '<xs:redefine schemaLocation="base.xsd"><xs:attributeGroup name="gOpen"><xs:attributeGroup ref="gOpen"/>'
            '<xs:anyAttribute namespace="urn:a urn:b" processContents="lax"/></xs:attributeGroup></xs:redefine>'
            '<xs:element name="Root"><xs:complexType><xs:attributeGroup ref="gOpen"/></xs:complexType></xs:element>'
        ),
        {
            'base.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="{TARGET}">'
            '<xs:attributeGroup name="gOpen"><xs:anyAttribute namespace="urn:a urn:c" processContents="skip"/></xs:attributeGroup></xs:schema>'
        },
        {'namespace': ['urn:a'], 'processContents': 'lax'},
    ),
    'a type named as the attribute group it references -> that group, types and groups are named apart': (
        schema(
            '<xs:element name="Root" type="gOpen"/><xs:complexType name="gOpen"><xs:attributeGroup ref="gOpen"/></xs:complexType>'
            '<xs:attributeGroup name="gOpen"><xs:anyAttribute namespace="urn:a" processContents="lax"/></xs:attributeGroup>'
        ),
        {},
        {'namespace': ['urn:a'], 'processContents': 'lax'},
    ),
    'a wildcard that does not say how it is processed -> strictly': (
        root('<xs:anyAttribute namespace="urn:a"/>'),
        {},
        {'namespace': ['urn:a'], 'processContents': 'strict'},
    ),
    'the target namespace and no namespace, listed by keyword -> both, resolved': (
        root('<xs:anyAttribute namespace="##targetNamespace ##local" processContents="lax"/>'),
        {},
        {'namespace': ['', TARGET], 'processContents': 'lax'},
    ),
    'an element declared without a type -> any attribute, laxly': (
        schema('<xs:element name="Root"/>'),
        {},
        {'notNamespace': [], 'processContents': 'lax'},
    ),
}


@pytest.mark.parametrize(('entry', 'imports', 'expected'), CASES.values(), ids=CASES.keys())
def test_attribute_wildcard(definition_of, entry: str, imports: dict[str, str], expected: dict[str, Any] | None) -> None:
    assert pick(definition_of(entry, imports=imports), 'Root.attributes').get('any') == expected


@pytest.mark.parametrize(('entry', 'imports', 'expected'), CASES.values(), ids=CASES.keys())
def test_attribute_wildcard_admits_what_libxml2_admits(
    definition_of, tmp_path: Path, entry: str, imports: dict[str, str], expected: dict[str, Any] | None
) -> None:
    definition_of(entry, imports=imports)
    validator = etree.XMLSchema(etree.parse(str(tmp_path / 'entry.xsd')))
    admitted = [namespace for namespace in PROBES if _libxml2_admits(validator, namespace)]
    assert admitted == [namespace for namespace in PROBES if _admits(expected, namespace)]


def _libxml2_admits(validator: etree.XMLSchema, namespace: str) -> bool:
    """Whether an instance root may carry an undeclared attribute of `namespace`: a strict wildcard that
    admits it still asks for its declaration, so that complaint counts as admitted."""
    attribute = 'p:probe="x" xmlns:p="{}"'.format(namespace) if namespace else 'probe="x"'
    instance = etree.fromstring(f'<Root xmlns="{TARGET}" {attribute}/>')
    if validator.validate(instance):
        return True
    return all('demanded by the strict wildcard' in error.message for error in validator.error_log)


def _admits(wildcard: dict[str, Any] | None, namespace: str) -> bool:
    if wildcard is None:
        return False
    if 'namespace' in wildcard:
        return namespace in wildcard['namespace']
    return namespace not in wildcard['notNamespace']


def test_two_wildcards_excluding_different_namespaces_cannot_be_intersected(definition_of, tmp_path: Path) -> None:
    # XSD 1.0 cannot express what two negations of different namespaces both admit: the schema is in error
    entry = schema(
        f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
        '<xs:element name="Root"><xs:complexType><xs:attributeGroup ref="e:gOther"/>'
        '<xs:anyAttribute namespace="##other" processContents="lax"/></xs:complexType></xs:element>',
        attributes=f'xmlns:e="{EXT}"',
    )
    ext = (
        f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="{EXT}">'
        '<xs:attributeGroup name="gOther"><xs:anyAttribute namespace="##other" processContents="lax"/></xs:attributeGroup></xs:schema>'
    )
    with pytest.raises(SchemaNotRepresentable, match='Root'):
        definition_of(entry, imports={'ext.xsd': ext})
    with pytest.raises(etree.XMLSchemaParseError):
        etree.XMLSchema(etree.parse(str(tmp_path / 'entry.xsd')))
