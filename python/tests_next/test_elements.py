"""Elements: what a definition says about each tag, whatever its content."""
from typing import Any

import pytest

from tests_next.conftest import TARGET, schema

CASES: dict[str, tuple[str, dict[str, Any]]] = {
    'one element holding another -> its children named, no edge details while nothing is known of the edge': (
        schema('<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="Child"/></xs:sequence></xs:complexType></xs:element>'),
        {
            'Root': {
                'tag': 'Root',
                'namespace': {'prefix': '', 'uri': TARGET},
                'parents': [],
                'attributes': {'sequence': [], 'details': {}},
                'children': {'sequence': ['Child'], 'details': {}},
                'contentModel': {
                    'kind': 'sequence',
                    'minOccurs': 1,
                    'maxOccurs': 1,
                    'particles': [{'kind': 'element', 'name': 'Child', 'minOccurs': 1, 'maxOccurs': 1}],
                },
            },
            # declared without a type: xs:anyType, any attribute and any element content, lax
            'Child': {
                'tag': 'Child',
                'namespace': {'prefix': '', 'uri': TARGET},
                'parents': ['Root'],
                'attributes': {'sequence': [], 'any': {'notNamespace': [], 'processContents': 'lax'}, 'details': {}},
                'children': {'sequence': [], 'any': True, 'details': {}},
                'textContent': {},
                'contentModel': {
                    'kind': 'sequence',
                    'minOccurs': 1,
                    'maxOccurs': 1,
                    'particles': [{'kind': 'any', 'notNamespace': [], 'processContents': 'lax'}],
                },
            },
        },
    ),
    'one global element with nothing in it -> its tag, namespace, no parents, no attributes, no children': (
        schema('<xs:element name="Root"><xs:complexType/></xs:element>'),
        {
            'Root': {
                'tag': 'Root',
                'namespace': {'prefix': '', 'uri': TARGET},
                'parents': [],
                'attributes': {'sequence': [], 'details': {}},
                'children': {'sequence': [], 'details': {}},
            }
        },
    ),
}


@pytest.mark.parametrize(('entry', 'expected'), CASES.values(), ids=CASES.keys())
def test_definition(definition_of, entry: str, expected: dict[str, Any]) -> None:
    assert definition_of(entry) == expected


def test_the_definition_lists_its_elements_sorted_by_tag_not_in_the_order_they_are_met(definition_of) -> None:
    # met in this order: Root, its local Alpha, then the global Zeta
    data = definition_of(
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="Alpha"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Zeta"/>'
        )
    )
    assert list(data) == ['Alpha', 'Root', 'Zeta']
