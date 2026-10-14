"""Every check of the schema tier on every corpus schema: its disagreements are exactly those
`corpora/known-exceptions.json` lists for it - a new one fails, and so does a listed one that no longer occurs."""
from pathlib import Path

import pytest

from corpora.sources import known_exceptions
from proof import corpus
from proof.corpus import CorpusSchema
from proof.pairs import corpus_schemas, instance_pairs
from tests.test_patterns import (
    KNOWN_LIBXML2_FAULTS,
    elementpath_sides_with,
    libxml2_accepts,
    node_accepts,
    probes_of,
    unicode_versions_differ,
)

EXCEPTIONS = known_exceptions()


SCHEMAS = corpus_schemas()
pytestmark = pytest.mark.corpora


def _loaded_by_both(schema: CorpusSchema) -> None:
    """A schema one of the libraries refuses is a schema-legality question, out of the generator's scope (a suite
    holds many on purpose); a corpus family entry is never one."""
    if schema.suite and isinstance(schema.validator, Exception) and isinstance(schema.library, Exception):
        pytest.skip('refused by both libraries: a schema-legality case')


def _expect(check: str, schema: CorpusSchema, found: list[str]) -> None:
    prefix = f'{check}/{schema.id}/'
    listed = {key for key in EXCEPTIONS if key.startswith(prefix)}
    assert sorted({prefix + item for item in found}) == sorted(listed)


@pytest.mark.parametrize('schema', SCHEMAS, ids=[schema.id for schema in SCHEMAS])
def test_the_generator_reads_the_schema(schema: CorpusSchema) -> None:
    _loaded_by_both(schema)
    _expect('generation', schema, corpus.generation(schema))


@pytest.mark.parametrize('schema', SCHEMAS, ids=[schema.id for schema in SCHEMAS])
def test_the_emitted_definition_reads_back_as_its_data(schema: CorpusSchema) -> None:
    _loaded_by_both(schema)
    _expect('read-back', schema, corpus.read_back(schema))


@pytest.mark.parametrize('schema', SCHEMAS, ids=[schema.id for schema in SCHEMAS])
def test_the_emitted_constants_agree_with_the_definition(schema: CorpusSchema) -> None:
    _loaded_by_both(schema)
    _expect('derivation', schema, corpus.derivation(schema))


@pytest.mark.parametrize('schema', SCHEMAS, ids=[schema.id for schema in SCHEMAS])
def test_the_emitted_types_type_check_with_their_probes(schema: CorpusSchema, tmp_path: Path) -> None:
    # the schema's emitted files and their type probes, judged on their own: schemas run in parallel (xdist)
    _loaded_by_both(schema)
    folder = tmp_path / 'typed'
    failing = corpus.failing_types([folder]) if corpus.write_probed(schema, folder) else []
    _expect('types', schema, ['probes'] if failing else [])


@pytest.mark.parametrize('schema', SCHEMAS, ids=[schema.id for schema in SCHEMAS])
def test_every_construct_is_classified(schema: CorpusSchema) -> None:
    _loaded_by_both(schema)
    _expect('constructs', schema, corpus.constructs(schema))


@pytest.mark.parametrize('schema', SCHEMAS, ids=[schema.id for schema in SCHEMAS])
def test_every_identity_path_libxml2_loads_parses(schema: CorpusSchema) -> None:
    _loaded_by_both(schema)
    _expect('identity-paths', schema, corpus.identity_paths(schema))


@pytest.mark.parametrize('schema', SCHEMAS, ids=[schema.id for schema in SCHEMAS])
def test_every_pattern_is_converted_and_agrees_with_libxml2(schema: CorpusSchema) -> None:
    _loaded_by_both(schema)
    _expect('patterns', schema, corpus.patterns(corpus.patterns_of(schema), judge=_judge_patterns))


@pytest.mark.parametrize('schema', SCHEMAS, ids=[schema.id for schema in SCHEMAS])
def test_the_variants_are_those_libxml2_lets_an_instance_name(schema: CorpusSchema) -> None:
    _loaded_by_both(schema)
    _expect('variants', schema, corpus.variants(schema))


@pytest.mark.parametrize('schema', SCHEMAS, ids=[schema.id for schema in SCHEMAS])
def test_the_attribute_wildcards_admit_what_libxml2_admits(schema: CorpusSchema) -> None:
    _loaded_by_both(schema)
    _expect('attribute-wildcards', schema, corpus.attribute_wildcards(schema))


@pytest.mark.parametrize('schema', SCHEMAS, ids=[schema.id for schema in SCHEMAS])
def test_the_definition_keeps_the_sets_the_documents_declare(schema: CorpusSchema) -> None:
    _loaded_by_both(schema)
    _expect('preserved-sets', schema, corpus.preserved_sets(schema))


def test_every_listed_exception_names_a_schema_and_a_reviewed_reason() -> None:
    known = {schema.id for schema in SCHEMAS} | {pair.id for pair in instance_pairs()}
    for key, entry in EXCEPTIONS.items():
        check, _, rest = key.partition('/')
        assert any(rest.startswith(schema_id + '/') for schema_id in known), key
        assert entry.get('reason') and entry.get('since'), key


def _judge_patterns(texts: list[str]) -> list[tuple[str, str]]:
    probes = [probes_of(text) for text in texts]
    verdicts = node_accepts(_converted(texts), probes)
    disagreements = []
    for text, values, by_node in zip(texts, probes, verdicts):
        for value, expected, actual in zip(values, libxml2_accepts(text, values), by_node):
            if expected == actual or unicode_versions_differ(value):
                continue
            if text in KNOWN_LIBXML2_FAULTS and elementpath_sides_with(text, value, actual):
                continue
            disagreements.append((text, value))
    return disagreements


def _converted(texts: list[str]) -> list[str]:
    from generate.definition.patterns import pattern_to_js

    return [pattern_to_js(text) for text in texts]
