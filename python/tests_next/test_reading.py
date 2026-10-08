"""How the schema is read: deep schemas, documents out of reach, immutable records, what is refused."""
import pytest

from generate_next.errors import SchemaNotReadable
from generate_next.model.read_schema import read_schema
from tests_next.conftest import pick, schema


def test_a_chain_of_fifteen_hundred_references_is_read_without_exhausting_the_stack(definition_of) -> None:
    depth = 1500
    chain = ''.join(
        f'<xs:element name="E{level}"><xs:complexType><xs:sequence>'
        f'<xs:element ref="E{level + 1}" minOccurs="0"/></xs:sequence></xs:complexType></xs:element>'
        for level in range(depth)
    )
    data = definition_of(schema(chain + f'<xs:element name="E{depth}"/>'))
    assert pick(data, f'E{depth}.parents') == [f'E{depth - 1}']


def test_a_document_out_of_reach_is_refused_not_downloaded(definition_of) -> None:
    entry = schema(
        '<xs:import namespace="urn:remote" schemaLocation="http://example.invalid/remote.xsd"/>'
        '<xs:element name="Root"/>'
    )
    with pytest.raises(SchemaNotReadable, match='http://example.invalid/remote.xsd'):
        definition_of(entry)


def test_the_declarations_read_are_immutable_records(tmp_path) -> None:
    entry = tmp_path / 'entry.xsd'
    entry.write_text(
        schema('<xs:element name="Root"><xs:complexType><xs:sequence><xs:element name="A"/></xs:sequence>'
               '<xs:anyAttribute namespace="##other"/></xs:complexType></xs:element>'),
        encoding='utf-8',
    )
    root = next(declaration for declaration in read_schema(entry) if declaration.name == 'Root')
    assert isinstance(root.content_model.particles, tuple)
    assert isinstance(root.attributes, tuple)
    assert isinstance(root.any_attribute.not_namespace, tuple)
    with pytest.raises(AttributeError):
        root.name = 'Other'  # type: ignore[misc]


def test_one_name_in_two_namespaces_across_the_declarations_of_a_tag_gets_two_keys(definition_of) -> None:
    def attribute_in(uri: str) -> str:
        """A document declaring a global attribute x in `uri`, which it binds to the prefix e."""
        return (
            f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:e="{uri}" targetNamespace="{uri}">'
            '<xs:attribute name="x" type="xs:token"/></xs:schema>'
        )

    entry = (
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="urn:t" xmlns:a="urn:a" xmlns:b="urn:b" '
        'targetNamespace="urn:t" elementFormDefault="qualified">'
        '<xs:import namespace="urn:a" schemaLocation="a.xsd"/><xs:import namespace="urn:b" schemaLocation="b.xsd"/>'
        '<xs:element name="Root"><xs:complexType><xs:sequence>'
        '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
        '<xs:attribute ref="a:x"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
        '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P"><xs:complexType>'
        '<xs:attribute ref="b:x"/></xs:complexType></xs:element></xs:sequence></xs:complexType></xs:element>'
        '</xs:sequence></xs:complexType></xs:element></xs:schema>'
    )
    # both documents bind their namespace to e: the namespace needed second takes the entry's prefix for it
    data = definition_of(entry, imports={'a.xsd': attribute_in('urn:a'), 'b.xsd': attribute_in('urn:b')})
    assert pick(data, 'P.attributes.details') == {
        'b:x': {'namespace': {'prefix': 'b', 'uri': 'urn:b'}, 'type': {'builtin': 'token'}},
        'e:x': {'namespace': {'prefix': 'e', 'uri': 'urn:a'}, 'type': {'builtin': 'token'}},
    }


def test_a_document_an_include_names_but_that_is_out_of_reach_is_refused(definition_of) -> None:
    entry = schema('<xs:include schemaLocation="missing.xsd"/><xs:element name="Root"/>')
    with pytest.raises(SchemaNotReadable, match='missing.xsd'):
        definition_of(entry)
