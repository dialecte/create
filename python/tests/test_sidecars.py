"""The sidecar `parent-mapping.json`, next to the entry document: parents the schema cannot name for an
element a wildcard admits."""
import json

import pytest

from generate.errors import SidecarMistake
from tests.conftest import pick, schema

ENTRY = schema(
    '<xs:element name="Root"><xs:complexType><xs:sequence>'
    '<xs:element ref="Bay" maxOccurs="unbounded"/></xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="Bay"><xs:complexType><xs:sequence><xs:element name="Name"/>'
    '<xs:any namespace="##any" processContents="lax" minOccurs="0" maxOccurs="unbounded"/></xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="Resources"/>'
)


def test_an_element_the_mapping_attaches_is_a_child_of_each_parent_named_without_a_particle(definition_of) -> None:
    data = definition_of(ENTRY, imports={'parent-mapping.json': json.dumps({'Resources': ['Bay']})})
    assert pick(data, 'Resources.parents') == ['Bay']
    assert pick(data, 'Bay.children.sequence') == ['Name', 'Resources']
    particle_names = [particle.get('name') for particle in pick(data, 'Bay.contentModel.particles')]
    assert particle_names == ['Name', None]


def test_without_a_mapping_an_element_only_a_wildcard_admits_has_no_parent(definition_of) -> None:
    data = definition_of(ENTRY)
    assert pick(data, 'Resources.parents') == []


@pytest.mark.parametrize(
    ('mapping', 'named'),
    [
        pytest.param({'Resourcez': ['Bay']}, 'Resourcez', id='a mapped element the schema does not declare -> refused, named'),
        pytest.param({'Resources': ['Baj']}, 'Baj', id='a parent the schema does not declare -> refused, named'),
        pytest.param({'Resources': 'Bay'}, 'Resources', id='parents not given as a list -> refused, the entry named'),
        pytest.param({'Root': ['Bay'], 'Resources': ['Bay']}, 'no element without a parent', id='a mapping leaving no element without a parent -> refused, no root left'),
        pytest.param({'Resources': ['Root']}, 'Root', id='a parent whose content admits no other element -> refused, the parent named'),
        pytest.param({'Name': ['Bay']}, 'Name', id='an element the parent already holds -> refused, nothing for the mapping to add'),
    ],
)
def test_a_mapping_naming_what_the_schema_does_not_declare_is_refused(definition_of, mapping: dict, named: str) -> None:
    with pytest.raises(SidecarMistake, match=named):
        definition_of(ENTRY, imports={'parent-mapping.json': json.dumps(mapping)})


def test_an_element_with_a_parent_of_its_own_keeps_it_and_gains_the_mapped_ones(definition_of) -> None:
    entry = ENTRY.replace(
        '<xs:element ref="Bay" maxOccurs="unbounded"/>',
        '<xs:element ref="Bay" maxOccurs="unbounded"/><xs:element ref="Resources" minOccurs="0"/>',
    )
    data = definition_of(entry, imports={'parent-mapping.json': json.dumps({'Resources': ['Bay']})})
    assert pick(data, 'Resources.parents') == ['Bay', 'Root']
    assert pick(data, 'Root.children.sequence') == ['Bay', 'Resources']


def test_a_mapping_given_as_a_list_is_refused(definition_of) -> None:
    with pytest.raises(SidecarMistake, match='object'):
        definition_of(ENTRY, imports={'parent-mapping.json': json.dumps([['Resources', 'Bay']])})


def test_a_root_that_holds_itself_still_counts_as_the_root_a_mapping_leaves(definition_of) -> None:
    entry = ENTRY.replace(
        '<xs:element ref="Bay" maxOccurs="unbounded"/></xs:sequence>',
        '<xs:element ref="Bay" maxOccurs="unbounded"/><xs:element ref="Root" minOccurs="0"/></xs:sequence>',
    )
    data = definition_of(entry, imports={'parent-mapping.json': json.dumps({'Resources': ['Bay']})})
    assert pick(data, 'Root.parents') == ['Root']


def test_a_parent_wildcard_that_does_not_admit_the_namespace_of_the_element_is_refused(definition_of) -> None:
    entry = ENTRY.replace('<xs:any namespace="##any"', '<xs:any namespace="##other"')
    with pytest.raises(SidecarMistake, match='Bay'):
        definition_of(entry, imports={'parent-mapping.json': json.dumps({'Resources': ['Bay']})})


def test_several_mapped_children_follow_the_schema_children_sorted_by_name(definition_of) -> None:
    entry = ENTRY.replace('<xs:element name="Resources"/>', '<xs:element name="Resources"/><xs:element name="Assets"/>')
    data = definition_of(entry, imports={'parent-mapping.json': json.dumps({'Resources': ['Bay'], 'Assets': ['Bay']})})
    assert pick(data, 'Bay.children.sequence') == ['Name', 'Assets', 'Resources']


@pytest.mark.parametrize(
    ('written', 'rewritten'),
    [
        pytest.param('<xs:element name="Resources"/>', '<xs:element name="Resources"/><xs:element name="Label" type="xs:string"/>', id='a parent of a simple type -> refused, it holds no element'),
        pytest.param('<xs:any namespace="##any"', '<xs:any namespace="urn:a urn:b"', id='a parent whose wildcard lists other namespaces -> refused'),
        pytest.param('processContents="lax" minOccurs="0" maxOccurs="unbounded"', 'processContents="lax" minOccurs="0" maxOccurs="0"', id='a parent whose only wildcard no document may hold -> refused'),
    ],
)
def test_a_parent_whose_content_admits_no_such_element_is_refused(definition_of, written: str, rewritten: str) -> None:
    parent = 'Label' if 'Label' in rewritten else 'Bay'
    with pytest.raises(SidecarMistake, match=f'content of {parent}'):
        definition_of(ENTRY.replace(written, rewritten), imports={'parent-mapping.json': json.dumps({'Resources': [parent]})})


def bay_declared_twice(right_content: str) -> str:
    """Bay declared under Left (Name, then any element) and under Right (`right_content`)."""
    return schema(
        '<xs:element name="Root"><xs:complexType><xs:sequence>'
        '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="Bay"><xs:complexType><xs:sequence>'
        '<xs:element name="Name"/><xs:any namespace="##any" processContents="lax"/></xs:sequence></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
        f'<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="Bay"><xs:complexType><xs:sequence>{right_content}'
        '</xs:sequence></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
        '</xs:sequence></xs:complexType></xs:element>'
        '<xs:element name="Resources"/>'
    )


def test_a_parent_declared_twice_admits_what_a_wildcard_of_each_declaration_admits(definition_of) -> None:
    entry = bay_declared_twice('<xs:any namespace="##any" processContents="lax"/>')
    data = definition_of(entry, imports={'parent-mapping.json': json.dumps({'Resources': ['Bay']})})
    assert 'contentModel' not in data['Bay']
    assert pick(data, 'Resources.parents') == ['Bay']
    # listed in each way Bay is declared too: a reader going through the parent's declaration finds it
    assert [pick(data, f'Bay.declarations.{id}.children.sequence') for id in ('1', '2')] == [['Name', 'Resources'], ['Resources']]


@pytest.mark.parametrize(
    'right_content',
    [
        pytest.param('<xs:element name="Name"/>', id='one declaration without a wildcard -> refused'),
        pytest.param('<xs:any namespace="##other" processContents="lax"/>', id='one declaration admitting other namespaces only -> refused'),
    ],
)
def test_a_parent_declared_twice_must_admit_the_element_in_each_declaration(definition_of, right_content: str) -> None:
    with pytest.raises(SidecarMistake, match='content of Bay'):
        definition_of(bay_declared_twice(right_content), imports={'parent-mapping.json': json.dumps({'Resources': ['Bay']})})


STRICT = ENTRY.replace('processContents="lax"', 'processContents="strict"')


def test_a_strict_wildcard_admits_an_element_declared_globally(definition_of) -> None:
    data = definition_of(STRICT, imports={'parent-mapping.json': json.dumps({'Resources': ['Bay']})})
    assert pick(data, 'Resources.parents') == ['Bay']


def test_a_strict_wildcard_does_not_admit_an_element_declared_only_locally(definition_of) -> None:
    entry = STRICT.replace(
        '<xs:element name="Resources"/>',
        '<xs:element name="Holder"><xs:complexType><xs:sequence><xs:element name="Res"/></xs:sequence></xs:complexType></xs:element>',
    )
    with pytest.raises(SidecarMistake, match='content of Bay'):
        definition_of(entry, imports={'parent-mapping.json': json.dumps({'Res': ['Bay']})})


def test_a_parent_named_twice_is_refused(definition_of) -> None:
    with pytest.raises(SidecarMistake, match='Bay'):
        definition_of(ENTRY, imports={'parent-mapping.json': json.dumps({'Resources': ['Bay', 'Bay']})})
