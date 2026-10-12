"""The corpora tier runs on demand (`npm run test:corpora`, PROOF_CORPORA=1): every check on every schema the cache
holds, a few minutes. Asked for without a cache, it is skipped - or fails when PROOF_REQUIRE names `corpora` (CI)."""
import os

import pytest

from corpora.sources import sources


def _asked() -> bool:
    return os.environ.get('PROOF_CORPORA', '').lower() in ('1', 'true', 'yes')


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if _asked() and sources():
        return
    if _asked() and 'corpora' in os.environ.get('PROOF_REQUIRE', '').split(','):
        raise pytest.UsageError('PROOF_REQUIRE=corpora but nothing is fetched: npm run corpora:fetch')
    reason = 'no corpora fetched: npm run corpora:fetch' if _asked() else 'the corpora tier runs on demand: npm run test:corpora'
    for item in items:
        if item.get_closest_marker('corpora'):
            item.add_marker(pytest.mark.skip(reason=reason))
