"""The corpora tier runs on demand (`npm run test:corpora`, PROOF_CORPORA=1): every check on every schema the cache
holds, across processes (pytest-xdist). Asked for without a cache, it is skipped - or fails when PROOF_REQUIRE names
`corpora` (CI). The instance tier's counts are gathered per process and printed once, at the end of the run."""
import os

import pytest

from corpora.sources import sources
from proof import report


def _asked() -> bool:
    return os.environ.get('PROOF_CORPORA', '').lower() in ('1', 'true', 'yes')


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # every check of a schema in one process: it reads and generates the schema once (`--dist loadgroup`)
    # (an instance pair is not grouped: a family's thousand instances spread over the processes, each generating the
    # schema once)
    for item in items:
        schema = getattr(getattr(item, 'callspec', None), 'params', {}).get('schema')
        # with nothing fetched, pytest stands a placeholder without an id in for the empty parameter set
        schema_id = getattr(schema, 'id', None)
        if schema_id is not None:
            item.add_marker(pytest.mark.xdist_group(schema_id))
    if _asked() and sources():
        return
    if _asked() and 'corpora' in os.environ.get('PROOF_REQUIRE', '').split(','):
        raise pytest.UsageError('PROOF_REQUIRE=corpora but nothing is fetched: npm run corpora:fetch')
    reason = 'no corpora fetched: npm run corpora:fetch' if _asked() else 'the corpora tier runs on demand: npm run test:corpora'
    for item in items:
        if item.get_closest_marker('corpora'):
            item.add_marker(pytest.mark.skip(reason=reason))



def pytest_configure(config: pytest.Config) -> None:
    # the controlling process, before any worker starts; a run that does not ask for the corpora keeps the last report
    if not hasattr(config, 'workerinput') and _asked():
        report.reset()


def pytest_terminal_summary(terminalreporter, config: pytest.Config) -> None:  # noqa: ANN001 - pytest's signature
    if not hasattr(config, 'workerinput'):
        for line in report.summary():
            terminalreporter.write_line(line)
