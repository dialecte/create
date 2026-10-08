"""Attributes: the keys, what each one is, across the declarations of a tag."""
from typing import Any

import pytest

from tests_next.conftest import TARGET, pick, schema

EXT = 'urn:dialecte:ext'
XML = 'http://www.w3.org/XML/1998/namespace'


def root(attributes: str, *, more: str = '') -> str:
    return schema(f'<xs:element name="Root"><xs:complexType>{attributes}</xs:complexType></xs:element>{more}')


CASES: dict[str, tuple[str, dict[str, str], str, Any]] = {
    'a required, an optional, a defaulted and a fixed attribute -> sorted keys, each with what it is': (
        root(
            '<xs:attribute name="version" type="xs:token" use="required"/>'
            '<xs:attribute name="desc" type="xs:string"/>'
            '<xs:attribute name="kind" type="xs:token" default="primary"/>'
            '<xs:attribute name="unit" type="xs:token" fixed="V"/>'
        ),
        {},
        'Root.attributes',
        {
            'sequence': ['desc', 'kind', 'unit', 'version'],
            'details': {
                'desc': {},
                'kind': {'default': 'primary', 'type': {'builtin': 'token'}},
                'unit': {'fixed': 'V', 'type': {'builtin': 'token'}},
                'version': {'required': True, 'type': {'builtin': 'token'}},
            },
        },
    ),
    'an attribute typed by a restriction of a built-in -> the built-in it derives from': (
        root(
            '<xs:attribute name="name" type="tName"/>',
            more='<xs:simpleType name="tName"><xs:restriction base="xs:Name"><xs:maxLength value="32"/></xs:restriction></xs:simpleType>',
        ),
        {},
        'Root.attributes.details.name',
        {'type': {'builtin': 'Name'}},
    ),
    'a plain string, a list and a union -> no built-in type yet': (
        root(
            '<xs:attribute name="text" type="xs:string"/>'
            '<xs:attribute name="items" type="xs:NMTOKENS"/>'
            '<xs:attribute name="either"><xs:simpleType><xs:union memberTypes="xs:int xs:boolean"/></xs:simpleType></xs:attribute>'
        ),
        {},
        'Root.attributes.details',
        {'either': {}, 'items': {}, 'text': {}},
    ),
    'an attribute a restriction prohibits -> absent': (
        root(
            '<xs:complexContent><xs:restriction base="tBase"><xs:attribute name="legacy" use="prohibited"/></xs:restriction></xs:complexContent>',
            more='<xs:complexType name="tBase"><xs:attribute name="legacy" type="xs:string"/><xs:attribute name="kept" type="xs:string"/></xs:complexType>',
        ),
        {},
        'Root.attributes.sequence',
        ['kept'],
    ),
    'an attribute of another namespace -> keyed prefix:local, with its namespace': (
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:attribute name="version" type="xs:token"/>'
            '<xs:attribute ref="e:version"/></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}"',
        ),
        {
            'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:e="{EXT}" targetNamespace="{EXT}">'
            '<xs:attribute name="version" type="xs:token"/></xs:schema>'
        },
        'Root.attributes',
        {
            'sequence': ['e:version', 'version'],
            'details': {
                'e:version': {'namespace': {'prefix': 'e', 'uri': EXT}, 'type': {'builtin': 'token'}},
                'version': {'type': {'builtin': 'token'}},
            },
        },
    ),
    'a foreign attribute referenced from a document whose default namespace is the foreign one -> prefix:local with its namespace': (
        (
            f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{EXT}" xmlns:t="{TARGET}" '
            f'targetNamespace="{TARGET}" elementFormDefault="qualified">'
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:attribute name="version" type="xs:int"/>'
            '<xs:attribute ref="version"/></xs:complexType></xs:element></xs:schema>'
        ),
        {
            'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:e="{EXT}" targetNamespace="{EXT}">'
            '<xs:attribute name="version" type="xs:token"/></xs:schema>'
        },
        'Root.attributes',
        {
            'sequence': ['e:version', 'version'],
            'details': {
                'e:version': {'namespace': {'prefix': 'e', 'uri': EXT}, 'type': {'builtin': 'token'}},
                'version': {'type': {'builtin': 'int'}},
            },
        },
    ),
    'a qualified attribute in the element\'s own namespace -> prefix:local, whatever the default namespace is': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:attribute name="a" type="xs:token"/></xs:complexType></xs:element>',
            attributes='attributeFormDefault="qualified"',
        ),
        {},
        'Root.attributes.details',
        {'t:a': {'namespace': {'prefix': 't', 'uri': TARGET}, 'type': {'builtin': 'token'}}},
    ),
    'an attribute declared without a type -> no type (anySimpleType says nothing)': (
        root('<xs:attribute name="anything"/>'),
        {},
        'Root.attributes.details',
        {'anything': {}},
    ),
    'a foreign attribute whose declaring document binds its namespace only as the default -> the prefix another document binds': (
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:attribute ref="e:version"/></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}"',
        ),
        {
            'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{EXT}" targetNamespace="{EXT}">'
            '<xs:attribute name="version" type="xs:token"/></xs:schema>'
        },
        'Root.attributes.sequence',
        ['e:version'],
    ),
    'a tag declared twice, processing other attributes strictly and laxly -> the weaker processing in the union': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:anyAttribute namespace="urn:z urn:b" processContents="strict"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:anyAttribute namespace="urn:m urn:a" processContents="lax"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        'P.attributes.any',
        {'namespace': ['urn:a', 'urn:b', 'urn:m', 'urn:z'], 'processContents': 'lax'},
    ),
    'an attribute whose namespace no document gives a prefix -> a prefix made up for it': (
        # both documents bind the attribute's namespace only as their default one
        (
            f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{EXT}" xmlns:t="{TARGET}" '
            f'targetNamespace="{TARGET}" elementFormDefault="qualified">'
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:attribute ref="version"/></xs:complexType></xs:element></xs:schema>'
        ),
        {'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{EXT}" targetNamespace="{EXT}"><xs:attribute name="version" type="xs:token"/></xs:schema>'},
        'Root.attributes.details',
        {'ns1:version': {'namespace': {'prefix': 'ns1', 'uri': EXT}, 'type': {'builtin': 'token'}}},
    ),
    'attributes of two namespaces no document gives a prefix, ns1 taken -> the next prefixes made up, one per namespace': (
        (
            f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{EXT}" xmlns:t="{TARGET}" xmlns:ns1="urn:unrelated" '
            f'targetNamespace="{TARGET}" elementFormDefault="qualified">'
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:attributeGroup ref="gExt"/></xs:complexType></xs:element></xs:schema>'
        ),
        {
            # each document binds the other namespace only as its default one, its own not at all
            'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="urn:other" targetNamespace="{EXT}">'
            '<xs:import namespace="urn:other" schemaLocation="other.xsd"/>'
            '<xs:attributeGroup name="gExt"><xs:attribute name="version" form="qualified"/><xs:attributeGroup ref="gOther"/></xs:attributeGroup></xs:schema>',
            'other.xsd': '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:other">'
            '<xs:attributeGroup name="gOther"><xs:attribute name="level" form="qualified"/></xs:attributeGroup></xs:schema>',
        },
        'Root.attributes.details',
        {
            'ns2:version': {'namespace': {'prefix': 'ns2', 'uri': EXT}},
            'ns3:level': {'namespace': {'prefix': 'ns3', 'uri': 'urn:other'}},
        },
    ),
    'a substitution member declared without a type -> the attributes of the head\'s type, no wildcard': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Head"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Head" type="tHead"/><xs:element name="Member" substitutionGroup="Head"/>'
            '<xs:complexType name="tHead"><xs:attribute name="kept" type="xs:token" use="required"/></xs:complexType>'
        ),
        {},
        'Member.attributes',
        {'sequence': ['kept'], 'details': {'kept': {'required': True, 'type': {'builtin': 'token'}}}},
    ),
    'two namespaces each bound to the same prefix by another document -> one prefix per namespace': (
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/><xs:import namespace="urn:other" schemaLocation="other.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:attributeGroup ref="e:gExt"/><xs:attributeGroup ref="o:gOther"/></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}" xmlns:o="urn:other"',
        ),
        {
            'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:p="{EXT}" targetNamespace="{EXT}">'
            '<xs:attributeGroup name="gExt"><xs:attribute name="ver" form="qualified"/><xs:attribute name="rev" form="qualified"/></xs:attributeGroup></xs:schema>',
            'other.xsd': '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:p="urn:other" targetNamespace="urn:other">'
            '<xs:attributeGroup name="gOther"><xs:attribute name="lvl" form="qualified"/></xs:attributeGroup></xs:schema>',
        },
        'Root.attributes.sequence',
        ['o:lvl', 'p:rev', 'p:ver'],
    ),
    'an attribute namespace bound to the prefix an element is written with -> another prefix': (
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/><xs:import namespace="urn:other" schemaLocation="other.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="e:Holder"/></xs:sequence>'
            '<xs:attributeGroup ref="o:gOther"/></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}" xmlns:o="urn:other"',
        ),
        {
            # ext.xsd writes Holder with p; other.xsd binds p to the attribute's namespace
            'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:p="{EXT}" targetNamespace="{EXT}" elementFormDefault="qualified">'
            '<xs:element name="Holder"/></xs:schema>',
            'other.xsd': '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:p="urn:other" targetNamespace="urn:other">'
            '<xs:attributeGroup name="gOther"><xs:attribute name="lvl" form="qualified"/></xs:attributeGroup></xs:schema>',
        },
        'Root.attributes.sequence',
        ['o:lvl'],
    ),
    'a declared xml:lang -> kept, keyed xml:lang': (
        schema(
            f'<xs:import namespace="{XML}"/>'
            '<xs:element name="Root"><xs:complexType><xs:attribute ref="xml:lang"/></xs:complexType></xs:element>'
        ),
        {},
        'Root.attributes.sequence',
        ['xml:lang'],
    ),
    'an attribute wildcard listing namespaces -> any, with the namespaces it admits sorted': (
        root('<xs:anyAttribute namespace="urn:z urn:a" processContents="lax"/>'),
        {},
        'Root.attributes',
        {'sequence': [], 'any': {'namespace': ['urn:a', 'urn:z'], 'processContents': 'lax'}, 'details': {}},
    ),
    'a tag declared twice, each declaration admitting other attributes -> the union of what they admit': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:anyAttribute namespace="urn:a" processContents="lax"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:anyAttribute namespace="urn:b ##local" processContents="lax"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        'P.attributes.any',
        {'namespace': ['', 'urn:a', 'urn:b'], 'processContents': 'lax'},
    ),
    'a tag declared twice, one admitting any other namespace, one a listed one -> every namespace but the excluded ones not listed': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:anyAttribute namespace="##other" processContents="lax"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:anyAttribute namespace="##local" processContents="lax"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        'P.attributes.any',
        {'notNamespace': [TARGET], 'processContents': 'lax'},
    ),
    'a restriction without a wildcard of a base that has one -> no wildcard, a restriction does not inherit it': (
        root(
            '<xs:complexContent><xs:extension base="tRestricted"/></xs:complexContent>',
            more='<xs:complexType name="tOpen"><xs:attribute name="name" type="xs:token"/><xs:anyAttribute namespace="##other" processContents="lax"/></xs:complexType>'
            '<xs:complexType name="tRestricted"><xs:complexContent><xs:restriction base="tOpen"><xs:attribute name="name" type="xs:token"/></xs:restriction></xs:complexContent></xs:complexType>',
        ),
        {},
        'Root.attributes',
        {'sequence': ['name'], 'details': {'name': {'type': {'builtin': 'token'}}}},
    ),
    'a tag declared twice, an attribute required in one only -> optional in the union': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:attribute name="type" type="xs:token" use="required"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:attribute name="type" type="xs:token"/><xs:attribute name="extra" type="xs:token" use="required"/>'
            '</xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        'P.attributes.details',
        {'extra': {'type': {'builtin': 'token'}}, 'type': {'type': {'builtin': 'token'}}},
    ),
    'a tag declared twice, an attribute typed differently in each -> no type in the union': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:attribute name="value" type="xs:token"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:attribute name="value" type="xs:int"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        'P.attributes.details.value',
        {},
    ),
    'a tag declared twice with two fixed values -> no fixed value in the union': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:attribute name="kind" type="xs:token" fixed="A"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
            '<xs:attribute name="kind" type="xs:token" fixed="B"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        'P.attributes.details.kind',
        {'type': {'builtin': 'token'}},
    ),
}


@pytest.mark.parametrize(('entry', 'imports', 'path', 'expected'), CASES.values(), ids=CASES.keys())
def test_attributes(definition_of, entry: str, imports: dict[str, str], path: str, expected: Any) -> None:
    assert pick(definition_of(entry, imports=imports), path) == expected
