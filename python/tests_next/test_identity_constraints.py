"""Identity constraints: unique / key / keyref, their selector and fields parsed over the XSD 1.0 path grammar,
names resolved against the namespaces in scope where the constraint is written."""
from typing import Any

import pytest

from tests_next.conftest import TARGET, pick, schema

EXT = 'urn:dialecte:ext'
HERE = {'namespace': TARGET}


def constrained(selector: str, field: str, *, kind: str = 'unique') -> str:
    """Root holding A (attributes n and e:m, a child B), constrained by one `kind` with `selector` and `field`."""
    return schema(
        f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
        '<xs:element name="Root"><xs:complexType><xs:sequence>'
        '<xs:element name="A" maxOccurs="unbounded"><xs:complexType><xs:sequence><xs:element name="B" minOccurs="0">'
        '<xs:complexType><xs:attribute name="x"/></xs:complexType></xs:element></xs:sequence>'
        '<xs:attribute name="n"/><xs:attribute ref="e:m"/></xs:complexType></xs:element>'
        '</xs:sequence></xs:complexType>'
        f'<xs:{kind} name="c"><xs:selector xpath="{selector}"/><xs:field xpath="{field}"/></xs:{kind}>'
        '</xs:element>',
        attributes=f'xmlns:e="{EXT}"',
    )


EXT_XSD = f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="{EXT}"><xs:attribute name="m"/></xs:schema>'

PATHS: dict[str, tuple[str, str, dict[str, Any], list[dict[str, Any]]]] = {
    'a prefixed step and an attribute in no namespace -> the step in its namespace, the attribute in none': (
        't:A', '@n', {'steps': [{'name': 'A', **HERE}]}, [{'steps': [], 'attribute': {'name': 'n', 'namespace': ''}}],
    ),
    'an unprefixed step -> in no namespace, whatever the default namespace is': (
        'A', '@n', {'steps': [{'name': 'A', 'namespace': ''}]}, [{'steps': [], 'attribute': {'name': 'n', 'namespace': ''}}],
    ),
    'a prefixed attribute -> in its namespace': (
        't:A', '@e:m', {'steps': [{'name': 'A', **HERE}]}, [{'steps': [], 'attribute': {'name': 'm', 'namespace': EXT}}],
    ),
    'the element itself as the field -> its own value, no step, no attribute': (
        't:A', '.', {'steps': [{'name': 'A', **HERE}]}, [{'steps': []}],
    ),
    'a child element as the field -> its value': (
        't:A', 't:B', {'steps': [{'name': 'A', **HERE}]}, [{'steps': [{'name': 'B', **HERE}]}],
    ),
    'a descendant selector -> deep': (
        './/t:A', '@n', {'deep': True, 'steps': [{'name': 'A', **HERE}]}, [{'steps': [], 'attribute': {'name': 'n', 'namespace': ''}}],
    ),
    'self steps inside a path -> gone': (
        './t:A/.', '@n', {'steps': [{'name': 'A', **HERE}]}, [{'steps': [], 'attribute': {'name': 'n', 'namespace': ''}}],
    ),
    'explicit child and attribute axes, spaced out -> the abbreviated meaning': (
        'child :: t:A', 'attribute ::n', {'steps': [{'name': 'A', **HERE}]}, [{'steps': [], 'attribute': {'name': 'n', 'namespace': ''}}],
    ),
    'any element and any attribute of a namespace -> name tests without a name': (
        't:*', '@ e:*', {'steps': [{'namespace': TARGET}]}, [{'steps': [], 'attribute': {'namespace': EXT}}],
    ),
    'any element, any attribute -> name tests without name nor namespace': (
        '*', '@*', {'steps': [{}]}, [{'steps': [], 'attribute': {}}],
    ),
    'a descendant self field, spaced out -> deep, the value of what it reaches': (
        't:A', '. // .', {'steps': [{'name': 'A', **HERE}]}, [{'deep': True, 'steps': []}],
    ),
}


@pytest.mark.parametrize(('selector', 'field', 'selected', 'field_paths'), PATHS.values(), ids=PATHS.keys())
def test_paths(definition_of, selector: str, field: str, selected: dict[str, Any], field_paths: list[dict[str, Any]]) -> None:
    constraint = pick(definition_of(constrained(selector, field), imports={'ext.xsd': EXT_XSD}), 'Root.constraints')[0]
    assert constraint['selector'] == [selected]
    assert constraint['fields'] == [field_paths]


def test_alternatives_in_a_selector_and_in_a_field_are_kept_each(definition_of) -> None:
    constraint = pick(definition_of(constrained('t:A | .//t:B', '@n|t:B/@n'), imports={'ext.xsd': EXT_XSD}), 'Root.constraints')[0]
    assert constraint['selector'] == [{'steps': [{'name': 'A', **HERE}]}, {'deep': True, 'steps': [{'name': 'B', **HERE}]}]
    assert constraint['fields'] == [[
        {'steps': [], 'attribute': {'name': 'n', 'namespace': ''}},
        {'steps': [{'name': 'B', **HERE}], 'attribute': {'name': 'n', 'namespace': ''}},
    ]]


def test_a_constraint_says_its_kind_and_its_name_in_the_target_namespace(definition_of) -> None:
    constraint = pick(definition_of(constrained('t:A', '@n', kind='key'), imports={'ext.xsd': EXT_XSD}), 'Root.constraints')[0]
    assert {key: constraint[key] for key in ('kind', 'name', 'namespace')} == {'kind': 'key', 'name': 'c', 'namespace': TARGET}
    assert 'refer' not in constraint


def test_a_keyref_names_the_key_it_refers_to_by_name_and_namespace(definition_of) -> None:
    entry = constrained('t:A', '@n', kind='key').replace(
        '</xs:key>', '</xs:key><xs:keyref name="r" refer="t:c"><xs:selector xpath="t:A"/><xs:field xpath="@n"/></xs:keyref>'
    )
    constraints = pick(definition_of(entry, imports={'ext.xsd': EXT_XSD}), 'Root.constraints')
    assert [(constraint['kind'], constraint.get('refer')) for constraint in constraints] == [
        ('key', None),
        ('keyref', {'name': 'c', 'namespace': TARGET}),
    ]


def test_a_declaration_with_constraints_is_its_own_way_of_declaring_the_tag(definition_of) -> None:
    # the same named type under two parents: only the constraint tells the declarations apart
    entry = schema(
        '<xs:element name="Root"><xs:complexType><xs:sequence>'
        '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P" type="tP">'
        '<xs:unique name="u"><xs:selector xpath="t:Q"/><xs:field xpath="@n"/></xs:unique></xs:element></xs:sequence></xs:complexType></xs:element>'
        '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P" type="tP"/></xs:sequence></xs:complexType></xs:element>'
        '</xs:sequence></xs:complexType></xs:element>'
        '<xs:complexType name="tP"><xs:sequence><xs:element name="Q" maxOccurs="unbounded"><xs:complexType><xs:attribute name="n"/></xs:complexType></xs:element></xs:sequence></xs:complexType>'
    )
    data = definition_of(entry)
    assert [constraint['name'] for constraint in pick(data, 'P.declarations.1.constraints')] == ['u']
    assert 'constraints' not in pick(data, 'P.declarations.2')
    # the union holds no constraint: one declaration's only
    assert 'constraints' not in data['P']


IDENTITY_FIELDS: dict[str, tuple[str, str, str, str, list[str] | None]] = {
    'a key on an attribute of the selected element -> its identity field': ('t:A', '@n', 'key', 'A', ['n']),
    'a unique on an attribute of the selected element -> its identity field': ('t:A', '@n', 'unique', 'A', ['n']),
    'a field reading an attribute of a child -> no identity field of the selected element': ('t:A', 't:B/@n', 'key', 'A', None),
    'a namespaced attribute -> keyed as the definition keys it': ('t:A', '@e:m', 'key', 'A', ['e:m']),
    'an unprefixed step -> selects elements in no namespace, none here': ('A', '@n', 'key', 'A', None),
    'two attributes in one field -> both': ('t:A', '@n | @e:m', 'key', 'A', ['e:m', 'n']),
    'a descendant selector -> the descendants it reaches': ('.//t:A', '@n', 'key', 'A', ['n']),
    'a descendant selector -> a grandchild too': ('.//t:B', '@x', 'key', 'B', ['x']),
    'a field attribute in another namespace than the one declared -> not that attribute': ('t:A', '@e:n', 'key', 'A', None),
}


@pytest.mark.parametrize(('selector', 'field', 'kind', 'tag', 'expected'), IDENTITY_FIELDS.values(), ids=IDENTITY_FIELDS.keys())
def test_identity_fields(definition_of, selector: str, field: str, kind: str, tag: str, expected: list[str] | None) -> None:
    attributes = pick(definition_of(constrained(selector, field, kind=kind), imports={'ext.xsd': EXT_XSD}), f'{tag}.attributes')
    assert attributes.get('identityFields') == expected


def test_a_keyref_gives_no_identity_field(definition_of) -> None:
    # B keyed by its value, A only referring to it
    entry = constrained('t:A/t:B', '.', kind='key').replace('</xs:key>', '</xs:key><xs:keyref name="r" refer="t:c"><xs:selector xpath="t:A"/><xs:field xpath="@n"/></xs:keyref>')
    assert 'identityFields' not in pick(definition_of(entry, imports={'ext.xsd': EXT_XSD}), 'A.attributes')


@pytest.mark.parametrize(
    ('use', 'expected'),
    [
        pytest.param('optional', None, id='an element a wildcard step reaches, the field optional there -> no identity field'),
        pytest.param('required', ['n'], id='an element a wildcard step reaches, the field required there -> its identity field'),
    ],
)
def test_an_element_reached_by_a_wildcard_step_counts_only_when_it_requires_the_fields(definition_of, use: str, expected: list[str] | None) -> None:
    entry = constrained('*', '@n').replace('<xs:attribute name="n"/>', f'<xs:attribute name="n" use="{use}"/>')
    assert pick(definition_of(entry, imports={'ext.xsd': EXT_XSD}), 'A.attributes').get('identityFields') == expected


def test_identity_fields_are_the_declaration_s_that_the_selector_reaches(definition_of) -> None:
    # A under Root is keyed by n; A under Other, declared another way, is not
    entry = constrained('t:A', '@n', kind='key').replace(
        '</xs:sequence></xs:complexType><xs:key',
        '<xs:element name="Other"><xs:complexType><xs:sequence><xs:element name="A"><xs:complexType>'
        '<xs:attribute name="n"/><xs:attribute name="o"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
        '</xs:sequence></xs:complexType><xs:key',
    )
    data = definition_of(entry, imports={'ext.xsd': EXT_XSD})
    by_way = {pick(data, f'A.declarations.{id}.attributes.sequence')[-1]: pick(data, f'A.declarations.{id}.attributes').get('identityFields') for id in ('1', '2')}
    assert by_way == {'n': ['n'], 'o': None}
    assert pick(data, 'A.attributes.identityFields') == ['n']


def test_a_wildcard_step_reaches_the_children_the_parent_mapping_attaches(definition_of) -> None:
    import json

    entry = schema(
        '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Bay"/></xs:sequence></xs:complexType></xs:element>'
        '<xs:element name="Bay"><xs:complexType><xs:sequence><xs:any namespace="##any" processContents="lax" maxOccurs="unbounded"/></xs:sequence></xs:complexType>'
        '<xs:unique name="u"><xs:selector xpath="./*"/><xs:field xpath="@name"/></xs:unique></xs:element>'
        '<xs:element name="Role"><xs:complexType><xs:attribute name="name" use="required"/></xs:complexType></xs:element>'
    )
    data = definition_of(entry, imports={'parent-mapping.json': json.dumps({'Role': ['Bay']})})
    assert pick(data, 'Role.attributes.identityFields') == ['name']


def test_a_child_the_parent_mapping_attaches_without_a_global_declaration_is_not_identified(definition_of) -> None:
    import json

    # Role is declared only locally: the lax wildcard that admits it under Bay validates nothing of it
    entry = schema(
        '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Bay"/>'
        '<xs:element name="Holder"><xs:complexType><xs:sequence><xs:element name="Role"><xs:complexType>'
        '<xs:attribute name="name" use="required"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
        '</xs:sequence></xs:complexType></xs:element>'
        '<xs:element name="Bay"><xs:complexType><xs:sequence><xs:any namespace="##any" processContents="lax" maxOccurs="unbounded"/></xs:sequence></xs:complexType>'
        '<xs:unique name="u"><xs:selector xpath="./*"/><xs:field xpath="@name"/></xs:unique></xs:element>'
    )
    data = definition_of(entry, imports={'parent-mapping.json': json.dumps({'Role': ['Bay']})})
    assert 'identityFields' not in pick(data, 'Role.attributes')


@pytest.mark.parametrize(
    ('selector', 'use', 'tag', 'expected'),
    [
        pytest.param('.', 'required', 'Root', None, id='a selector of the element itself -> it is not identified by a constraint on itself'),
        pytest.param('.//.', 'optional', 'A', None, id='every descendant, the field optional on one -> not identified, as by a * step'),
        pytest.param('.//.', 'required', 'A', ['n'], id='every descendant, the field required on one -> identified'),
    ],
)
def test_a_selector_without_element_step(definition_of, selector: str, use: str, tag: str, expected: list[str] | None) -> None:
    entry = constrained(selector, '@n').replace('<xs:attribute name="n"/>', f'<xs:attribute name="n" use="{use}"/>')
    entry = entry.replace('</xs:sequence></xs:complexType><xs:unique', '</xs:sequence><xs:attribute name="n" use="required"/></xs:complexType><xs:unique')
    assert pick(definition_of(entry, imports={'ext.xsd': EXT_XSD}), f'{tag}.attributes').get('identityFields') == expected


def test_a_selector_reaches_the_members_of_a_substitution_group(definition_of) -> None:
    entry = schema(
        '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Shape" maxOccurs="unbounded"/></xs:sequence></xs:complexType>'
        '<xs:key name="k"><xs:selector xpath="t:Square"/><xs:field xpath="@id"/></xs:key></xs:element>'
        '<xs:element name="Shape" abstract="true"/>'
        '<xs:element name="Square" substitutionGroup="Shape"><xs:complexType><xs:attribute name="id"/></xs:complexType></xs:element>'
    )
    assert pick(definition_of(entry), 'Square.attributes.identityFields') == ['id']


def test_a_descendant_selector_through_a_recursive_type_ends(definition_of) -> None:
    entry = schema(
        '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="Node" type="tNode"/></xs:sequence></xs:complexType>'
        '<xs:unique name="u"><xs:selector xpath=".//t:Node"/><xs:field xpath="@id"/></xs:unique></xs:element>'
        '<xs:complexType name="tNode"><xs:sequence><xs:element name="Node" type="tNode" minOccurs="0"/></xs:sequence><xs:attribute name="id"/></xs:complexType>'
    )
    assert pick(definition_of(entry), 'Node.attributes.identityFields') == ['id']


def test_a_name_with_characters_beyond_word_characters_is_read(definition_of) -> None:
    # a middle dot and a combining accent are XML name characters
    name = 'na·mé'
    entry = schema(
        f'<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="{name}" maxOccurs="unbounded">'
        '<xs:complexType><xs:attribute name="id"/></xs:complexType></xs:element></xs:sequence></xs:complexType>'
        f'<xs:unique name="u"><xs:selector xpath="t:{name}"/><xs:field xpath="@id"/></xs:unique></xs:element>'
    )
    assert pick(definition_of(entry), f'{name}.attributes.identityFields') == ['id']


def test_declarations_differing_only_by_their_constraints_are_numbered_by_them(definition_of) -> None:
    # two P of one type under one parent, told apart by their constraint only; read in either order, the one
    # holding constraint a is the first
    def with_constraint(name: str) -> str:
        return (f'<xs:element name="P" type="tP"><xs:unique name="{name}"><xs:selector xpath="t:Q"/>'
                '<xs:field xpath="@n"/></xs:unique></xs:element>')

    def schema_with(first: str, second: str) -> str:
        return schema(
            f'<xs:element name="Root"><xs:complexType><xs:sequence>{with_constraint(first)}{with_constraint(second)}'
            '</xs:sequence></xs:complexType></xs:element>'
            '<xs:complexType name="tP"><xs:sequence><xs:element name="Q" maxOccurs="unbounded"><xs:complexType><xs:attribute name="n"/></xs:complexType></xs:element></xs:sequence></xs:complexType>'
        )

    for first, second in (('a', 'b'), ('b', 'a')):
        assert pick(definition_of(schema_with(first, second)), 'P.declarations.1.constraints')[0]['name'] == 'a'


def test_a_prefix_bound_again_on_the_constraint_is_resolved_where_the_constraint_is_written(definition_of) -> None:
    # p is bound to urn:other on the schema, to the target namespace on the unique itself
    entry = constrained('p:A', '@n').replace('<xs:unique name="c">', f'<xs:unique name="c" xmlns:p="{TARGET}">').replace(
        '<xs:schema ', '<xs:schema xmlns:p="urn:other" '
    )
    constraint = pick(definition_of(entry, imports={'ext.xsd': EXT_XSD}), 'Root.constraints')[0]
    assert constraint['selector'] == [{'steps': [{'name': 'A', **HERE}]}]


def test_every_descendant_and_itself_does_not_identify_the_element_the_constraint_is_on(definition_of) -> None:
    entry = constrained('.//.', '@n').replace('<xs:attribute name="n"/>', '<xs:attribute name="n" use="required"/>')
    entry = entry.replace('</xs:sequence></xs:complexType><xs:unique', '</xs:sequence><xs:attribute name="n" use="required"/></xs:complexType><xs:unique')
    data = definition_of(entry, imports={'ext.xsd': EXT_XSD})
    assert 'identityFields' not in pick(data, 'Root.attributes')
    assert pick(data, 'A.attributes.identityFields') == ['n']


@pytest.mark.parametrize('selector', ['.//t:Node', './/.'])
def test_a_constraint_on_an_element_holding_itself_identifies_the_ones_it_holds(definition_of, selector: str) -> None:
    # one global Node, holding Nodes by reference to itself: the Nodes inside are other elements of the declaration
    entry = schema(
        '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Node"/></xs:sequence></xs:complexType></xs:element>'
        '<xs:element name="Node"><xs:complexType><xs:sequence><xs:element ref="Node" minOccurs="0" maxOccurs="unbounded"/></xs:sequence>'
        '<xs:attribute name="id" use="required"/></xs:complexType>'
        f'<xs:unique name="u"><xs:selector xpath="{selector}"/><xs:field xpath="@id"/></xs:unique></xs:element>'
    )
    assert pick(definition_of(entry), 'Node.attributes.identityFields') == ['id']


def test_the_xml_prefix_is_bound_in_every_path_without_a_declaration(definition_of) -> None:
    entry = schema(
        '<xs:import namespace="http://www.w3.org/XML/1998/namespace"/>'
        '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="A" maxOccurs="unbounded"><xs:complexType>'
        '<xs:attribute ref="xml:lang"/></xs:complexType></xs:element></xs:sequence></xs:complexType>'
        '<xs:unique name="u"><xs:selector xpath="t:A"/><xs:field xpath="@xml:lang"/></xs:unique></xs:element>'
    )
    assert pick(definition_of(entry), 'A.attributes.identityFields') == ['xml:lang']
