"""The sidecar `attribute-mapping.json`, next to the entry document: attributes a wildcard admits that the dialecte
types, `{ "Tag": { "prefix:local": "namespace" } }` - each the schema's global declaration of that attribute."""
import json

import pytest

from generate.definition.sidecars import attach_mapped_attributes
from generate.errors import SidecarMistake
from generate.model.read_schema import read_schema
from tests.conftest import pick, schema

EXT = 'urn:dialecte:ext'

ENTRY = schema(
    f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
    '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="Closed" type="xs:string"/>'
    '<xs:element name="Versioned"><xs:complexType><xs:attribute ref="e:version"/><xs:anyAttribute namespace="##other"/></xs:complexType></xs:element>'
    '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
    '<xs:attribute ref="e:version"/><xs:anyAttribute namespace="##other"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
    '<xs:anyAttribute namespace="##other"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="Listed"><xs:complexType><xs:anyAttribute namespace="urn:a"/></xs:complexType></xs:element>'
    '</xs:sequence>'
    '<xs:attribute name="id" type="xs:token"/><xs:anyAttribute namespace="##other" processContents="lax"/></xs:complexType></xs:element>',
    attributes=f'xmlns:e="{EXT}"',
)
EXT_XSD = (
    f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:e="{EXT}" targetNamespace="{EXT}">'
    '<xs:attribute name="version" type="xs:token"/><xs:attribute name="release" type="xs:unsignedByte" fixed="2"/></xs:schema>'
)


def generate(definition_of, mapping) -> dict:
    return definition_of(ENTRY, imports={'ext.xsd': EXT_XSD, 'attribute-mapping.json': json.dumps(mapping)})


def test_a_mapped_attribute_is_the_schema_s_global_declaration_of_it(definition_of) -> None:
    data = generate(definition_of, {'Root': {'e:version': EXT, 'e:release': EXT}})
    assert pick(data, 'Root.attributes.sequence') == ['e:release', 'e:version', 'id']
    assert pick(data, 'Root.attributes.details.e:release') == {
        'fixed': '2',
        'namespace': {'prefix': 'e', 'uri': EXT},
        'type': {'builtin': 'unsignedByte'},
    }
    assert pick(data, 'Root.attributes.details.e:version') == {'namespace': {'prefix': 'e', 'uri': EXT}, 'type': {'builtin': 'token'}}


@pytest.mark.parametrize(
    ('mapping', 'named'),
    [
        pytest.param(['Root'], 'object', id='a mapping that is not an object -> refused'),
        pytest.param({'Root': ['e:version']}, 'Root', id='attributes not given as an object -> refused, the tag named'),
        pytest.param({'Root': {'e:version': 5}}, 'Root', id='a namespace that is not a string -> refused, the tag named'),
        pytest.param({'Rooot': {'e:version': EXT}}, 'Rooot', id='a tag the schema does not declare -> refused, named'),
        pytest.param({'Root': {'e:versio': EXT}}, 'e:versio', id='an attribute the schema does not declare globally -> refused, named'),
        pytest.param({'Root': {'x:version': EXT}}, 'e:version', id='a key with another prefix than the definition writes -> refused, the right key named'),
        pytest.param({'Closed': {'e:version': EXT}}, 'Closed', id='a tag whose declaration admits no such attribute -> refused, the tag named'),
        pytest.param({'Listed': {'e:version': EXT}}, 'Listed', id='a tag whose wildcard admits other namespaces only -> refused, the tag named'),
        pytest.param({'Versioned': {'e:version': EXT}}, 'already', id='an attribute the tag already declares -> refused, nothing to add'),
    ],
)
def test_a_mapping_mistake_is_refused(definition_of, mapping, named: str) -> None:
    with pytest.raises(SidecarMistake, match=named):
        generate(definition_of, mapping)


def test_without_a_mapping_an_attribute_only_a_wildcard_admits_is_not_listed(definition_of) -> None:
    data = definition_of(ENTRY, imports={'ext.xsd': EXT_XSD})
    assert pick(data, 'Root.attributes.sequence') == ['id']


def test_a_mapped_attribute_some_declarations_of_the_tag_already_declare_is_added_to_the_others(definition_of) -> None:
    data = generate(definition_of, {'P': {'e:version': EXT}})
    typed = {'namespace': {'prefix': 'e', 'uri': EXT}, 'type': {'builtin': 'token'}}
    assert [pick(data, f'P.declarations.{id}.attributes.details') for id in ('1', '2')] == [{'e:version': typed}, {'e:version': typed}]


def test_a_mapped_attribute_s_made_up_prefix_does_not_depend_on_other_global_attributes(definition_of) -> None:
    # no document binds a prefix to either namespace; urn:aaa's attribute sorts first but is not mapped
    def unbound(uri: str, name: str) -> str:
        return f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{uri}" targetNamespace="{uri}"><xs:attribute name="{name}"/></xs:schema>'

    entry = schema(
        f'<xs:import namespace="urn:aaa" schemaLocation="aaa.xsd"/><xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'
        '<xs:element name="Root"><xs:complexType><xs:anyAttribute namespace="##other"/></xs:complexType></xs:element>'
    )
    data = definition_of(
        entry,
        imports={'aaa.xsd': unbound('urn:aaa', 'x'), 'ext.xsd': unbound(EXT, 'version'),
                 'attribute-mapping.json': json.dumps({'Root': {'ns1:version': EXT}})},
    )
    assert pick(data, 'Root.attributes.sequence') == ['ns1:version']


def test_a_declaration_already_declaring_a_mapped_attribute_keeps_its_own_only(tmp_path) -> None:
    (tmp_path / 'ext.xsd').write_text(EXT_XSD, encoding='utf-8')
    (tmp_path / 'entry.xsd').write_text(ENTRY, encoding='utf-8')
    schema_read = read_schema(tmp_path / 'entry.xsd', global_attributes=[(EXT, 'version')])
    declarations = attach_mapped_attributes(
        schema_read.elements, {'P': {'e:version': EXT}}, global_attributes=schema_read.global_attributes
    )
    keys = [[attribute.key for attribute in declaration.attributes] for declaration in declarations if declaration.name == 'P']
    assert sorted(keys) == [['e:version'], ['e:version']]


def test_a_mapping_holding_anything_but_namespaces_is_refused(definition_of) -> None:
    mapping = {'Root': {'e:version': EXT, 'e:release': 2}}
    with pytest.raises(SidecarMistake, match='Root must map to an object of attribute keys and namespaces'):
        definition_of(ENTRY, imports={'ext.xsd': EXT_XSD, 'attribute-mapping.json': json.dumps(mapping)})


def test_a_key_that_is_no_qualified_name_names_no_global_attribute(definition_of) -> None:
    mapping = {'Root': {'e:x:version': EXT}}
    with pytest.raises(SidecarMistake, match="no global attribute e:x:version"):
        definition_of(ENTRY, imports={'ext.xsd': EXT_XSD, 'attribute-mapping.json': json.dumps(mapping)})
