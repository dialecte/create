"""The construct inventory: every construct a schema writes is classified - read by the generator, excluded with
the reason it changes nothing in an instance, or XSD 1.1 -, and the committed schemas write every construct the
generator reads, so the self tier exercises each one."""
import json
from pathlib import Path

import pytest

from proof.constructs import TABLE, constructs_of, documents_of, read_table
from tests.committed_schemas import COMMITTED_SCHEMAS, entry_of
from tests.conftest import schema

CLASSIFICATION = read_table()


@pytest.mark.parametrize('name', sorted(COMMITTED_SCHEMAS))
def test_every_construct_of_the_committed_schemas_is_classified(name: str) -> None:
    constructs = constructs_of(entry_of(name))
    assert CLASSIFICATION.unclassified(constructs) == []
    assert CLASSIFICATION.refused(constructs) == []


def test_the_committed_schemas_write_every_construct_the_generator_reads() -> None:
    # a construct added to the handled class is added to the torture schema in the same change
    written = set().union(*(constructs_of(entry_of(name)) for name in COMMITTED_SCHEMAS))
    assert sorted(CLASSIFICATION.handled - written) == []


def test_a_construct_in_no_class_is_unclassified_and_an_xsd_11_one_refused(tmp_path: Path) -> None:
    entry = tmp_path / 'entry.xsd'
    entry.write_text(
        schema(
            '<xs:element name="Root" invented="1"><xs:complexType><xs:sequence><xs:element name="A"/></xs:sequence>'
            '<xs:assert test="true()"/></xs:complexType></xs:element>'
        ),
        encoding='utf-8',
    )
    constructs = constructs_of(entry)
    assert CLASSIFICATION.unclassified(constructs) == ['element@invented']
    assert CLASSIFICATION.refused(constructs) == ['assert', 'assert@test']


def test_documentation_content_is_free_text_and_foreign_attributes_are_one_construct(tmp_path: Path) -> None:
    entry = tmp_path / 'entry.xsd'
    entry.write_text(
        schema(
            '<xs:annotation><xs:appinfo xmlns:v="urn:vendor" v:tool="x"><v:hint/></xs:appinfo>'
            '<xs:documentation><xs:element name="NotSchema"/></xs:documentation></xs:annotation>'
            '<xs:element xmlns:v="urn:vendor" v:hint="1" name="Root"/>'
        ),
        encoding='utf-8',
    )
    constructs = constructs_of(entry)
    assert CLASSIFICATION.unclassified(constructs) == []
    assert constructs == {
        'schema',
        'schema@targetNamespace',
        'schema@elementFormDefault',
        'annotation',
        'appinfo',
        'appinfo@{foreign}',
        'documentation',
        'element',
        'element@name',
        'element@{foreign}',
    }


def test_every_local_document_reached_is_walked_once_and_a_remote_one_never(tmp_path: Path) -> None:
    (tmp_path / 'part.xsd').write_text(schema('<xs:include schemaLocation="entry.xsd"/><xs:attribute name="p"/>'), encoding='utf-8')
    entry = tmp_path / 'entry.xsd'
    entry.write_text(
        schema(
            '<xs:include schemaLocation="part.xsd"/>'
            '<xs:import namespace="urn:remote" schemaLocation="https://example.org/remote.xsd"/>'
            '<xs:element name="Root"/>'
        ),
        encoding='utf-8',
    )
    assert [path.name for path in documents_of(entry)] == ['entry.xsd', 'part.xsd']


def test_a_document_named_by_a_file_url_is_walked_as_the_schema_library_reads_it(tmp_path: Path) -> None:
    other = tmp_path / 'other.xsd'
    other.write_text(schema('<xs:attribute name="o"/>', target='urn:other'), encoding='utf-8')
    entry = tmp_path / 'entry.xsd'
    entry.write_text(schema(f'<xs:import namespace="urn:other" schemaLocation="{other.as_uri()}"/>'), encoding='utf-8')
    assert [path.name for path in documents_of(entry)] == ['entry.xsd', 'other.xsd']


def test_no_construct_is_in_two_classes() -> None:
    table = json.loads(TABLE.read_text(encoding='utf-8'))
    handled, excluded, xsd11 = set(table['handled']), set(table['excluded']), set(table['xsd-1.1'])
    assert (handled & excluded, handled & xsd11, excluded & xsd11) == (set(), set(), set())
