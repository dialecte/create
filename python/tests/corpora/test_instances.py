"""The instance tier on every (schema, instance) pair of the corpora: the structural faults the definition predicts
are those libxml2 finds, on the instance as it is and on every sampled edit of the mutation operators - exactly the
disagreements `corpora/known-exceptions.json` lists for the pair (`instances/<pair id>/...`)."""
import time

import pytest

from corpora.sources import known_exceptions
from proof import report
from proof.instance_tier import run
from proof.pairs import InstancePair, instance_pairs

EXCEPTIONS = known_exceptions()
PAIRS = instance_pairs()
pytestmark = pytest.mark.corpora


@pytest.mark.parametrize('pair', PAIRS, ids=[pair.id for pair in PAIRS])
def test_the_definition_predicts_the_structural_verdicts_of_libxml2(pair: InstancePair) -> None:
    if isinstance(pair.schema.generated, Exception) or isinstance(pair.schema.validator, Exception):
        pytest.skip('a schema one library refuses: the schema tier lists it')
    started = time.perf_counter()
    outcome = run(pair)
    report.record(pair.id, outcome, seconds=time.perf_counter() - started)
    prefix = f'instances/{pair.id}/'
    listed = {key for key in EXCEPTIONS if key.startswith(prefix)}
    assert sorted(prefix + finding for finding in outcome.findings) == sorted(listed)
