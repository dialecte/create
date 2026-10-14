"""The corpora tier with nothing fetched: CI runs the whole suite before it fetches the corpora."""
import os
import subprocess
import sys
from pathlib import Path


def test_with_nothing_fetched_the_corpora_tier_collects_and_skips(tmp_path: Path) -> None:
    env = {key: value for key, value in os.environ.items() if key not in ('PROOF_CORPORA', 'PROOF_REQUIRE')}
    env['DIALECTE_CORPORA_DIR'] = str(tmp_path)
    run = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/corpora', '-q', '-p', 'no:cacheprovider'],
        cwd=Path(__file__).parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
