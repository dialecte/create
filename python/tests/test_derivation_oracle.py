"""The constants create's TypeScript emitter writes for a definition agree with it: the oracle of
`scripts/derive-oracle`, run on generated data the way the corpus and fuzz tiers run it."""
from pathlib import Path
from typing import Any

import pytest

from proof import corpus
from proof.corpus import CorpusSchema
from tests.test_patterns import NEEDS_NODE

FIXTURES = Path(__file__).resolve().parents[2] / 'test' / 'fixtures' / 'xsd'
TORTURE = FIXTURES / 'torture' / 'torture.xsd'
CORE_TEST = FIXTURES / 'core-test' / 'test.xsd'

# a mutant copy of the package has no scripts beside it
pytestmark = pytest.mark.skipif(not corpus.DERIVE_ORACLE.exists(), reason="needs create's scripts/derive-oracle")


def element(*, parents: list[str], children: list[str]) -> dict[str, Any]:
    return {
        'tag': '', 'namespace': {'prefix': '', 'uri': 'urn:t'}, 'parents': parents,
        'attributes': {'sequence': [], 'details': {}}, 'children': {'sequence': children, 'details': {}},
    }


@NEEDS_NODE
def test_a_definition_whose_tables_agree_has_no_disagreement() -> None:
    definition = {'Root': element(parents=[], children=['A']), 'A': element(parents=['Root'], children=[])}
    assert corpus.derivation_of(definition, {}) == []


@NEEDS_NODE
def test_a_parent_nothing_holds_it_by_is_a_disagreement_of_the_parents_and_ancestors() -> None:
    # A lists Other as a parent, but Other's children do not hold A: up and down disagree
    definition = {
        'Root': element(parents=[], children=['A']),
        'A': element(parents=['Other', 'Root'], children=[]),
        'Other': element(parents=['Root'], children=[]),
    }
    definition['Root']['children']['sequence'] = ['A', 'Other']
    assert corpus.derivation_of(definition, {}) == ['parents/A', 'ancestors/A']


@NEEDS_NODE
def test_the_files_written_for_a_schema_and_their_probes_type_check(tmp_path: Path) -> None:
    schema = CorpusSchema(id='torture', entry=TORTURE)
    assert corpus.write_probed(schema, tmp_path / 'torture')
    assert corpus.failing_types([tmp_path / 'torture']) == []


@NEEDS_NODE
def test_a_required_attribute_the_written_types_make_optional_fails_the_type_check(tmp_path: Path) -> None:
    schema = CorpusSchema(id='core-test', entry=CORE_TEST)
    assert corpus.write_probed(schema, tmp_path / 'core-test')
    types = tmp_path / 'core-test' / 'types.generated.ts'
    types.write_text(types.read_text().replace('\taA: ', '\taA?: '))
    assert corpus.failing_types([tmp_path / 'core-test']) == [tmp_path / 'core-test']
