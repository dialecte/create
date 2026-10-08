"""Declarations: a tag declared one way is its declaration; a tag declared several ways is the union of its
declarations, each one kept and referenced where it applies."""
from typing import Any

import pytest

from tests_next.conftest import TARGET, pick, schema


def root_holding(content: str, *, more: str = '') -> str:
    return schema(f'<xs:element name="Root"><xs:complexType><xs:sequence>{content}</xs:sequence></xs:complexType></xs:element>{more}')


CASES: dict[str, tuple[str, dict[str, Any]]] = {
    'a tag declared twice, nillable in one -> nillable at the tag level, what a record may be under some parent': (
        root_holding(
            '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P" type="xs:int" nillable="true"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P" type="xs:int"/></xs:sequence></xs:complexType></xs:element>'
        ),
        {'P.nillable': True},
    ),
    'a nillable element -> nillable': (
        root_holding('<xs:element name="Child" type="xs:int" nillable="true"/>'),
        {'Child.nillable': True},
    ),
}


@pytest.mark.parametrize(('entry', 'expected'), CASES.values(), ids=CASES.keys())
def test_declarations(definition_of, entry: str, expected: dict[str, Any]) -> None:
    data = definition_of(entry)
    assert {path: pick(data, path) for path in expected} == expected


def test_an_element_not_nillable_says_nothing_of_it(definition_of) -> None:
    data = definition_of(root_holding('<xs:element name="Child" type="xs:int"/>'))
    assert 'nillable' not in data['Child']


EMPTY = {'attributes': {'sequence': [], 'details': {}}, 'children': {'sequence': [], 'details': {}}}
HERE = {'prefix': '', 'uri': TARGET}
EXT = 'urn:dialecte:ext'


def under_left_and_right(left: str, right: str, *, more: str = '') -> str:
    return root_holding(
        f'<xs:element name="Left"><xs:complexType><xs:sequence>{left}</xs:sequence></xs:complexType></xs:element>'
        f'<xs:element name="Right"><xs:complexType><xs:sequence>{right}</xs:sequence></xs:complexType></xs:element>',
        more=more,
    )


def test_a_tag_declared_with_two_fixed_values_keeps_each_declaration_where_it_applies(definition_of) -> None:
    data = definition_of(
        under_left_and_right('<xs:element name="P" type="xs:token" fixed="a"/>', '<xs:element name="P" type="xs:token" fixed="b"/>')
    )
    assert pick(data, 'P.declarations') == {
        '1': {'namespace': HERE, **EMPTY, 'textContent': {'type': {'builtin': 'token'}, 'fixed': 'a'}},
        '2': {'namespace': HERE, **EMPTY, 'textContent': {'type': {'builtin': 'token'}, 'fixed': 'b'}},
    }
    # the tag level is the union: no fixed value, since they differ
    assert pick(data, 'P.textContent') == {'type': {'builtin': 'token'}}
    assert pick(data, 'Left.contentModel.particles') == [
        {'kind': 'element', 'name': 'P', 'minOccurs': 1, 'maxOccurs': 1, 'declaration': '1'}
    ]
    assert pick(data, 'Left.children.details') == {'P': {'declarations': {TARGET: ['1']}}}
    assert pick(data, 'Right.children.details') == {'P': {'declarations': {TARGET: ['2']}}}


def test_a_tag_declared_with_one_named_type_under_two_parents_is_declared_one_way(definition_of) -> None:
    data = definition_of(
        under_left_and_right('<xs:element name="P" type="tP"/>', '<xs:element name="P" type="tP"/>',
                             more='<xs:complexType name="tP"><xs:attribute name="a"/></xs:complexType>')
    )
    assert 'declarations' not in data['P']
    assert pick(data, 'Left.children.details') == {}
    assert pick(data, 'Left.contentModel.particles') == [{'kind': 'element', 'name': 'P', 'minOccurs': 1, 'maxOccurs': 1}]


def test_a_tag_with_a_global_declaration_says_so_a_local_only_one_does_not(definition_of) -> None:
    data = definition_of(root_holding('<xs:element ref="Shared"/><xs:element name="Local"/>', more='<xs:element name="Shared"/>'))
    assert pick(data, 'Shared.global') is True
    assert 'global' not in data['Local']


def test_a_child_declared_by_which_declaration_its_parent_has_is_referenced_from_each(definition_of) -> None:
    # Maven's shape: plugins under build holds a Plugin, under reporting a ReportPlugin
    def plugins(plugin_type: str) -> str:
        return (f'<xs:element name="plugins"><xs:complexType><xs:sequence>'
                f'<xs:element name="plugin" type="{plugin_type}" maxOccurs="unbounded"/></xs:sequence></xs:complexType></xs:element>')

    data = definition_of(
        root_holding(
            f'<xs:element name="build"><xs:complexType><xs:sequence>{plugins("tPlugin")}</xs:sequence></xs:complexType></xs:element>'
            f'<xs:element name="reporting"><xs:complexType><xs:sequence>{plugins("tReportPlugin")}</xs:sequence></xs:complexType></xs:element>',
            more='<xs:complexType name="tPlugin"><xs:attribute name="a"/></xs:complexType>'
            '<xs:complexType name="tReportPlugin"><xs:attribute name="b"/></xs:complexType>',
        )
    )
    assert pick(data, 'build.children.details') == {'plugins': {'declarations': {TARGET: ['1']}}}
    assert pick(data, 'reporting.children.details') == {'plugins': {'declarations': {TARGET: ['2']}}}
    assert pick(data, 'plugins.declarations.1.children.details') == {'plugin': {'declarations': {TARGET: ['1']}}}
    assert pick(data, 'plugins.declarations.2.children.details') == {'plugin': {'declarations': {TARGET: ['2']}}}
    # the tag level of plugins cannot say which plugin: its declarations disagree, both listed; it keeps the shape
    # they share
    assert pick(data, 'plugins.children.details') == {'plugin': {'declarations': {TARGET: ['1', '2']}}}
    assert pick(data, 'plugins.contentModel') == {
        'kind': 'sequence', 'minOccurs': 1, 'maxOccurs': 1, 'particles': [{'kind': 'element', 'name': 'plugin', 'minOccurs': 1}],
    }
    assert pick(data, 'plugin.declarations.1.attributes.sequence') == ['a']
    assert pick(data, 'plugin.declarations.2.attributes.sequence') == ['b']


def test_one_parent_holding_a_tag_through_particles_that_differ_names_each_on_its_particle_only(definition_of) -> None:
    data = definition_of(
        root_holding(''.join(f'<xs:element name="e" type="xs:string" default="{value}"/>' for value in ('z', 'x', 'y')))
    )
    assert [particle['declaration'] for particle in pick(data, 'Root.contentModel.particles')] == ['3', '1', '2']
    # several ids in one namespace: only the particle matched decides
    assert pick(data, 'Root.children.details') == {'e': {'declarations': {TARGET: ['1', '2', '3']}}}
    assert [pick(data, f'e.declarations.{id}.textContent.default') for id in ('1', '2', '3')] == ['x', 'y', 'z']


def test_one_local_name_in_two_namespaces_under_one_parent_gets_an_id_per_namespace(definition_of) -> None:
    data = definition_of(
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="e:Item"/>'
            '<xs:element name="Item"><xs:complexType><xs:attribute name="mine"/></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}"',
        ),
        imports={'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:e="{EXT}" targetNamespace="{EXT}" elementFormDefault="qualified">'
                 '<xs:element name="Item"><xs:complexType><xs:attribute name="theirs"/></xs:complexType></xs:element></xs:schema>'},
    )
    assert pick(data, 'Root.children.details') == {'Item': {'declarations': {EXT: ['1'], TARGET: ['2']}}}
    assert pick(data, 'Item.declarations.1.namespace') == {'prefix': 'e', 'uri': EXT}
    assert pick(data, 'Item.declarations.1.global') is True
    assert pick(data, 'Item.declarations.2.namespace') == HERE
    assert 'global' not in pick(data, 'Item.declarations.2')


def test_two_roots_sharing_a_local_name_in_two_namespaces_are_two_global_declarations(definition_of) -> None:
    data = definition_of(
        schema(f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
               '<xs:element name="Root"><xs:complexType><xs:attribute name="here"/></xs:complexType></xs:element>'),
        imports={'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:e="{EXT}" targetNamespace="{EXT}">'
                 '<xs:element name="Root"><xs:complexType><xs:attribute name="there"/></xs:complexType></xs:element></xs:schema>'},
    )
    declarations = pick(data, 'Root.declarations')
    assert [(declarations[id]['namespace']['uri'], declarations[id].get('global'), declarations[id]['attributes']['sequence']) for id in ('1', '2')] == [
        (EXT, True, ['there']),
        (TARGET, True, ['here']),
    ]


def test_a_recursive_tag_declared_two_ways_references_itself_and_ends(definition_of) -> None:
    data = definition_of(
        under_left_and_right('<xs:element name="X" type="tLoop"/>', '<xs:element name="X" type="xs:int"/>',
                             more='<xs:complexType name="tLoop"><xs:sequence><xs:element name="X" type="tLoop" minOccurs="0"/></xs:sequence></xs:complexType>')
    )
    # the built-in type's QName sorts before tLoop's
    assert pick(data, 'X.declarations.1.textContent') == {'type': {'builtin': 'int'}}
    assert pick(data, 'X.declarations.2.children.details') == {'X': {'declarations': {TARGET: ['2']}}}


def test_a_declaration_blocking_derivations_is_its_own(definition_of) -> None:
    data = definition_of(
        under_left_and_right('<xs:element name="P" type="tP" block="extension"/>', '<xs:element name="P" type="tP"/>',
                             more='<xs:complexType name="tP"><xs:attribute name="a"/></xs:complexType>')
    )
    assert sorted(pick(data, 'P.declarations')) == ['1', '2']
    assert pick(data, 'Left.children.details') == {'P': {'declarations': {TARGET: ['1']}}}


def test_a_tag_nillable_in_one_declaration_only_is_declared_two_ways(definition_of) -> None:
    data = definition_of(under_left_and_right('<xs:element name="P" type="xs:int" nillable="true"/>', '<xs:element name="P" type="xs:int"/>'))
    assert pick(data, 'P.declarations.1.nillable') is True
    assert 'nillable' not in pick(data, 'P.declarations.2')


def test_the_global_declaration_is_numbered_first(definition_of) -> None:
    # the local one's type name sorts first; the global declaration still comes first
    data = definition_of(
        root_holding('<xs:element ref="Item"/><xs:element name="Holder"><xs:complexType><xs:sequence>'
                     '<xs:element name="Item" type="tA"/></xs:sequence></xs:complexType></xs:element>',
                     more='<xs:element name="Item" type="tZ"/><xs:complexType name="tA"><xs:attribute name="a"/></xs:complexType>'
                     '<xs:complexType name="tZ"><xs:attribute name="z"/></xs:complexType>')
    )
    assert pick(data, 'Item.declarations.1.global') is True
    assert pick(data, 'Holder.children.details') == {'Item': {'declarations': {TARGET: ['2']}}}


def test_declarations_in_two_namespaces_are_numbered_by_namespace_before_type(definition_of) -> None:
    # each Root is typed from the other's namespace: by type name the urn:dialecte:test one would come first
    data = definition_of(
        schema(f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
               '<xs:element name="Root" type="e:tShared"/><xs:complexType name="tOther"><xs:attribute name="other"/></xs:complexType>',
               attributes=f'xmlns:e="{EXT}"'),
        imports={'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:t="{TARGET}" targetNamespace="{EXT}">'
                 f'<xs:import namespace="{TARGET}"/>'
                 '<xs:complexType name="tShared"><xs:attribute name="shared"/></xs:complexType>'
                 '<xs:element name="Root" type="t:tOther"/></xs:schema>'},
    )
    assert pick(data, 'Root.declarations.1.namespace.uri') == EXT
    assert pick(data, 'Root.declarations.1.attributes.sequence') == ['other']
    # declared several ways: the tag level, a union, says nothing of a global declaration
    assert 'global' not in data['Root']


@pytest.mark.parametrize(
    ('first', 'second'),
    [
        pytest.param('fixed="b"', 'fixed="a"', id='two fixed values under one parent -> numbered by the value'),
        pytest.param('nillable="true"', '', id='nillable and not under one parent -> the one not nillable first'),
        pytest.param('block="extension"', '', id='blocking and not under one parent -> the one blocking nothing first'),
    ],
)
def test_declarations_held_by_one_parent_are_numbered_by_what_sets_them_apart(definition_of, first: str, second: str) -> None:
    data = definition_of(root_holding(f'<xs:element name="e" type="xs:token" {first}/><xs:element name="e" type="xs:token" {second}/>'))
    assert [particle['declaration'] for particle in pick(data, 'Root.contentModel.particles')] == ['2', '1']


def test_a_namespace_whose_particles_disagree_is_listed_with_each_id_beside_one_that_agrees(definition_of) -> None:
    data = definition_of(
        schema(
            f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="e:X"/>'
            '<xs:element name="X" type="xs:int" default="1"/><xs:element name="X" type="xs:int" default="2"/>'
            '</xs:sequence></xs:complexType></xs:element>',
            attributes=f'xmlns:e="{EXT}"',
        ),
        imports={'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:e="{EXT}" targetNamespace="{EXT}">'
                 '<xs:element name="X"><xs:complexType><xs:attribute name="theirs" use="required"/></xs:complexType></xs:element></xs:schema>'},
    )
    # urn:dialecte:ext decided, urn:dialecte:test only by the particle matched
    assert pick(data, 'Root.children.details') == {'X': {'declarations': {EXT: ['1'], TARGET: ['2', '3']}}}


def test_ways_differing_only_by_their_anonymous_content_are_numbered_by_it_not_by_reading_order(definition_of) -> None:
    def wrapped(order: tuple[str, str]) -> str:
        # L always holds the P with x, R the one with y: only the order they are read in changes
        bodies = {'L': '<xs:attribute name="x"/>', 'R': '<xs:attribute name="y"/>'}
        return root_holding(''.join(
            f'<xs:element name="{side}"><xs:complexType><xs:sequence><xs:element name="W"><xs:complexType><xs:sequence>'
            f'<xs:element name="P"><xs:complexType>{bodies[side]}</xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
            for side in order
        ))

    first = definition_of(wrapped(('L', 'R')))
    second = definition_of(wrapped(('R', 'L')))
    assert pick(first, 'P.declarations.1.attributes.sequence') == pick(second, 'P.declarations.1.attributes.sequence') == ['x']
