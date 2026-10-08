"""The content model: the particle tree an element's content holds, exactly as the schema writes it.

Occurrences follow one convention: `minOccurs` is written only when it is not 0, `maxOccurs` only when it
is bounded (absent = unbounded).
"""
from typing import Any

import pytest

from tests_next.conftest import TARGET, pick, schema

EXT = 'urn:dialecte:ext'

CASES: dict[str, tuple[str, dict[str, str], dict[str, Any]]] = {
    'a sequence of local elements -> a sequence particle holding element particles with their occurrences': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Header"/>'
            '<xs:element name="Item" minOccurs="0" maxOccurs="unbounded"/>'
            '<xs:element name="Note" minOccurs="0" maxOccurs="3"/>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        {
            'Root.contentModel': {
                'kind': 'sequence',
                'minOccurs': 1,
                'maxOccurs': 1,
                'particles': [
                    {'kind': 'element', 'name': 'Header', 'minOccurs': 1, 'maxOccurs': 1},
                    {'kind': 'element', 'name': 'Item'},
                    {'kind': 'element', 'name': 'Note', 'maxOccurs': 3},
                ],
            }
        },
    ),
    'a choice and an all -> told apart, each with its own occurrence': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:choice minOccurs="0" maxOccurs="unbounded"><xs:element name="A"/><xs:element name="B"/></xs:choice>'
            '</xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Services"><xs:complexType><xs:all><xs:element name="X" minOccurs="0"/><xs:element name="Y"/></xs:all></xs:complexType></xs:element>'
        ),
        {},
        {
            'Root.contentModel.particles': [
                {
                    'kind': 'choice',
                    'particles': [
                        {'kind': 'element', 'name': 'A', 'minOccurs': 1, 'maxOccurs': 1},
                        {'kind': 'element', 'name': 'B', 'minOccurs': 1, 'maxOccurs': 1},
                    ],
                }
            ],
            'Services.contentModel': {
                'kind': 'all',
                'minOccurs': 1,
                'maxOccurs': 1,
                'particles': [
                    {'kind': 'element', 'name': 'X', 'maxOccurs': 1},
                    {'kind': 'element', 'name': 'Y', 'minOccurs': 1, 'maxOccurs': 1},
                ],
            },
        },
    ),
    'a named group with its own occurrences beside an empty sequence -> both kept as written': (
        schema(
            '<xs:group name="pair"><xs:sequence><xs:element ref="K"/><xs:element ref="V"/></xs:sequence></xs:group>'
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:sequence/><xs:group ref="pair" minOccurs="2" maxOccurs="5"/>'
            '</xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="K"/><xs:element name="V"/>'
        ),
        {},
        {
            'Root.contentModel.particles': [
                {'kind': 'sequence', 'minOccurs': 1, 'maxOccurs': 1, 'particles': []},
                {
                    'kind': 'sequence',
                    'minOccurs': 2,
                    'maxOccurs': 5,
                    'particles': [
                        {
                            'kind': 'sequence',
                            'minOccurs': 1,
                            'maxOccurs': 1,
                            'particles': [
                                {'kind': 'element', 'name': 'K', 'minOccurs': 1, 'maxOccurs': 1},
                                {'kind': 'element', 'name': 'V', 'minOccurs': 1, 'maxOccurs': 1},
                            ],
                        }
                    ],
                }
            ],
        },
    ),
    'an abstract head with members, a concrete head with one -> a choice of what may stand there, with the head\'s occurrence': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element ref="Shape" maxOccurs="unbounded"/><xs:element ref="Template" minOccurs="0"/>'
            '</xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Shape" abstract="true"/><xs:element name="Square" substitutionGroup="Shape"/>'
            '<xs:element name="Circle" substitutionGroup="Shape"/>'
            '<xs:element name="Template"/><xs:element name="NamedTemplate" substitutionGroup="Template"/>'
        ),
        {},
        {
            'Root.contentModel.particles': [
                {
                    'kind': 'choice',
                    'minOccurs': 1,
                    'particles': [
                        {'kind': 'element', 'name': 'Circle', 'minOccurs': 1, 'maxOccurs': 1},
                        {'kind': 'element', 'name': 'Square', 'minOccurs': 1, 'maxOccurs': 1},
                    ],
                },
                {
                    'kind': 'choice',
                    'maxOccurs': 1,
                    'particles': [
                        {'kind': 'element', 'name': 'Template', 'minOccurs': 1, 'maxOccurs': 1},
                        {'kind': 'element', 'name': 'NamedTemplate', 'minOccurs': 1, 'maxOccurs': 1},
                    ],
                },
            ],
            'Root.children.sequence': ['Circle', 'Square', 'Template', 'NamedTemplate'],
        },
    ),
    'a choice with an empty branch -> the branch kept, so the choice may hold nothing': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:choice><xs:sequence/><xs:element name="A"/></xs:choice></xs:complexType></xs:element>'
        ),
        {},
        {
            'Root.contentModel': {
                'kind': 'choice',
                'minOccurs': 1,
                'maxOccurs': 1,
                'particles': [
                    {'kind': 'sequence', 'minOccurs': 1, 'maxOccurs': 1, 'particles': []},
                    {'kind': 'element', 'name': 'A', 'minOccurs': 1, 'maxOccurs': 1},
                ],
            }
        },
    ),
    'a required reference to an abstract head nothing replaces -> an empty choice, which nothing satisfies': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="A"/><xs:element ref="Shape"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Shape" abstract="true"/>'
        ),
        {},
        {
            'Root.contentModel.particles': [
                {'kind': 'element', 'name': 'A', 'minOccurs': 1, 'maxOccurs': 1},
                {'kind': 'choice', 'minOccurs': 1, 'maxOccurs': 1, 'particles': []},
            ]
        },
    ),
    'a tag declared globally in one namespace and locally in another, with the same content -> one content model': (
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element ref="e:Labels"/>'
            '<xs:element name="Labels"><xs:complexType><xs:sequence><xs:element ref="e:Label"/></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}"',
        ),
        {
            'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{EXT}" targetNamespace="{EXT}" elementFormDefault="qualified">'
            '<xs:element name="Labels"><xs:complexType><xs:sequence><xs:element ref="Label"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Label"/></xs:schema>'
        },
        {
            'Labels.namespace.uri': EXT,
            'Labels.contentModel': {
                'kind': 'sequence',
                'minOccurs': 1,
                'maxOccurs': 1,
                'particles': [{'kind': 'element', 'name': 'Label', 'minOccurs': 1, 'maxOccurs': 1}],
            },
        },
    ),
    'an element particle no document may hold (maxOccurs 0) -> kept in the model, no child, no element': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="A"/>'
            '<xs:element name="Never" minOccurs="0" maxOccurs="0"/></xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        {
            'Root.contentModel.particles': [
                {'kind': 'element', 'name': 'A', 'minOccurs': 1, 'maxOccurs': 1},
                {'kind': 'element', 'name': 'Never', 'maxOccurs': 0},
            ],
            'Root.children.sequence': ['A'],
        },
    ),
    'a required reference to an abstract head nothing replaces, alone -> the model kept, nothing satisfies it': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Shape"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Shape" abstract="true"/>'
        ),
        {},
        {
            'Root.contentModel': {
                'kind': 'sequence',
                'minOccurs': 1,
                'maxOccurs': 1,
                'particles': [{'kind': 'choice', 'minOccurs': 1, 'maxOccurs': 1, 'particles': []}],
            },
        },
    ),
    'a required choice whose only branch is an empty choice -> the model kept, nothing satisfies it': (
        schema('<xs:element name="Root"><xs:complexType><xs:choice><xs:choice/></xs:choice></xs:complexType></xs:element>'),
        {},
        {
            'Root.contentModel': {
                'kind': 'choice',
                'minOccurs': 1,
                'maxOccurs': 1,
                'particles': [{'kind': 'choice', 'minOccurs': 1, 'maxOccurs': 1, 'particles': []}],
            },
        },
    ),
    'a wildcard written in a group of another schema -> other namespaces than that schema\'s': (
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:group ref="e:gAny"/></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}"',
        ),
        {
            'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="{EXT}">'
            '<xs:group name="gAny"><xs:sequence><xs:any namespace="##other" processContents="lax"/></xs:sequence></xs:group></xs:schema>'
        },
        {
            # the group reference holds the group's sequence
            'Root.contentModel.particles': [
                {
                    'kind': 'sequence',
                    'minOccurs': 1,
                    'maxOccurs': 1,
                    'particles': [
                        {'kind': 'any', 'notNamespace': ['', EXT], 'processContents': 'lax', 'minOccurs': 1, 'maxOccurs': 1}
                    ],
                }
            ],
        },
    ),
    'substitution members sharing a name in three namespaces -> sorted by name, then namespace': (
        schema(
            # imported out of order, so the order members are found in is not the sorted one
            f'<xs:import namespace="urn:mmm" schemaLocation="mmm.xsd"/><xs:import namespace="urn:zzz" schemaLocation="zzz.xsd"/>'
            f'<xs:import namespace="urn:aaa" schemaLocation="aaa.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Shape"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Shape" abstract="true"/>'
        ),
        {
            'zzz.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:t="{TARGET}" targetNamespace="urn:zzz"><xs:import namespace="{TARGET}"/><xs:element name="Box" substitutionGroup="t:Shape"/></xs:schema>',
            'aaa.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:t="{TARGET}" targetNamespace="urn:aaa"><xs:import namespace="{TARGET}"/><xs:element name="Box" substitutionGroup="t:Shape"/></xs:schema>',
            'mmm.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:t="{TARGET}" targetNamespace="urn:mmm"><xs:import namespace="{TARGET}"/><xs:element name="Box" substitutionGroup="t:Shape"/></xs:schema>',
        },
        {
            'Root.contentModel.particles': [
                {
                    'kind': 'choice',
                    'minOccurs': 1,
                    'maxOccurs': 1,
                    'particles': [
                        {'kind': 'element', 'name': 'Box', 'namespace': 'urn:aaa', 'minOccurs': 1, 'maxOccurs': 1},
                        {'kind': 'element', 'name': 'Box', 'namespace': 'urn:mmm', 'minOccurs': 1, 'maxOccurs': 1},
                        {'kind': 'element', 'name': 'Box', 'namespace': 'urn:zzz', 'minOccurs': 1, 'maxOccurs': 1},
                    ],
                }
            ],
        },
    ),
    'wildcards in every notation -> what each admits, resolved': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:any namespace="##any" processContents="skip"/>'
            '<xs:any namespace="##other" processContents="lax"/>'
            '<xs:any namespace="##local urn:z urn:a urn:m urn:q urn:c urn:x" processContents="strict"/>'
            '<xs:any namespace="##targetNamespace" processContents="lax" minOccurs="0"/>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        {
            'Root.contentModel.particles': [
                {'kind': 'any', 'notNamespace': [], 'processContents': 'skip', 'minOccurs': 1, 'maxOccurs': 1},
                {'kind': 'any', 'notNamespace': ['', TARGET], 'processContents': 'lax', 'minOccurs': 1, 'maxOccurs': 1},
                {
                    'kind': 'any',
                    'namespace': ['', 'urn:a', 'urn:c', 'urn:m', 'urn:q', 'urn:x', 'urn:z'],
                    'processContents': 'strict',
                    'minOccurs': 1,
                    'maxOccurs': 1,
                },
                {'kind': 'any', 'namespace': [TARGET], 'processContents': 'lax', 'maxOccurs': 1},
            ],
            'Root.children.any': True,
            'Root.children.sequence': [],
        },
    ),
    'a child of another namespace than its parent, one of the same -> only the other one names its namespace': (
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element ref="e:Label"/><xs:element name="Label" type="xs:string"/>'
            '</xs:sequence></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}"',
        ),
        {'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="{EXT}"><xs:element name="Label"/></xs:schema>'},
        {
            'Root.contentModel.particles': [
                {'kind': 'element', 'name': 'Label', 'namespace': EXT, 'minOccurs': 1, 'maxOccurs': 1},
                {'kind': 'element', 'name': 'Label', 'minOccurs': 1, 'maxOccurs': 1},
            ],
            'Root.children.sequence': ['Label'],
        },
    ),
    'a type extending another -> the base content, then the extension\'s': (
        schema(
            '<xs:complexType name="tBase"><xs:sequence><xs:element name="Text" minOccurs="0"/></xs:sequence></xs:complexType>'
            '<xs:element name="Root"><xs:complexType><xs:complexContent><xs:extension base="tBase">'
            '<xs:sequence><xs:element name="Body"/></xs:sequence></xs:extension></xs:complexContent></xs:complexType></xs:element>'
        ),
        {},
        {'Root.children.sequence': ['Text', 'Body']},
    ),
    'an element of a simple type, an empty complex type, simple content -> no content model, no children': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Count" type="xs:int"/><xs:element name="Flag"><xs:complexType/></xs:element>'
            '<xs:element name="Label"><xs:complexType><xs:simpleContent><xs:extension base="xs:string"/></xs:simpleContent></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        {'Count.children': {'sequence': [], 'details': {}}, 'Flag.children': {'sequence': [], 'details': {}}, 'Label.children': {'sequence': [], 'details': {}}},
    ),
}


@pytest.mark.parametrize(('entry', 'imports', 'facts'), CASES.values(), ids=CASES.keys())
def test_content_model(definition_of, entry: str, imports: dict[str, str], facts: dict[str, Any]) -> None:
    data = definition_of(entry, imports=imports)
    assert {path: pick(data, path) for path in facts} == facts


ABSENT_CASES: dict[str, tuple[str, list[str]]] = {
    'a mixed type with no element content -> no content model, only text': (
        schema('<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Note"/></xs:sequence></xs:complexType></xs:element>'
               '<xs:element name="Note"><xs:complexType mixed="true"/></xs:element>'),
        ['Note'],
    ),
    'an element of a simple type, an empty complex type, simple content -> no content model': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Count" type="xs:int"/><xs:element name="Flag"><xs:complexType/></xs:element>'
            '<xs:element name="Label"><xs:complexType><xs:simpleContent><xs:extension base="xs:string"/></xs:simpleContent></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        ['Count', 'Flag', 'Label'],
    ),
    'an optional reference to an abstract head nothing replaces -> no content model, nothing to hold': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Shape" minOccurs="0"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Shape" abstract="true"/>'
        ),
        ['Root'],
    ),
    'a choice that may take an empty branch beside an empty choice -> no content model': (
        schema('<xs:element name="Root"><xs:complexType><xs:choice><xs:choice/><xs:sequence/></xs:choice></xs:complexType></xs:element>'),
        ['Root'],
    ),
    'a tag declared under two parents with two content models -> none at the tag level, each parent has its own': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType><xs:sequence>'
            '<xs:element name="A"/></xs:sequence></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType><xs:sequence>'
            '<xs:element name="B"/></xs:sequence></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        ['P'],
    ),
}


@pytest.mark.parametrize(('entry', 'tags'), ABSENT_CASES.values(), ids=ABSENT_CASES.keys())
def test_no_content_model(definition_of, entry: str, tags: list[str]) -> None:
    data = definition_of(entry)
    assert [tag for tag in tags if 'contentModel' in data[tag]] == []


@pytest.mark.parametrize(
    'prohibited',
    [
        pytest.param('<xs:element name="Never" minOccurs="0" maxOccurs="0"/>', id='an element particle with maxOccurs 0 -> no element of the dialecte'),
        pytest.param(
            '<xs:sequence minOccurs="0" maxOccurs="0"><xs:element name="Never"/></xs:sequence>',
            id='an element in a group with maxOccurs 0 -> no element of the dialecte',
        ),
    ],
)
def test_what_no_document_may_hold_is_no_element(definition_of, prohibited: str) -> None:
    data = definition_of(
        schema(f'<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="A"/>{prohibited}</xs:sequence></xs:complexType></xs:element>')
    )
    assert sorted(data) == ['A', 'Root']
    assert pick(data, 'Root.children.sequence') == ['A']


def test_a_wildcard_no_document_may_hold_admits_no_other_child(definition_of) -> None:
    data = definition_of(
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="A"/>'
            '<xs:any minOccurs="0" maxOccurs="0"/></xs:sequence></xs:complexType></xs:element>'
        )
    )
    assert pick(data, 'Root.children') == {'sequence': ['A'], 'details': {}}
