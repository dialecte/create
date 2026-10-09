"""The definition depends on the schema only: not on the run, the process's hash seed, nor where the schema lies."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.committed_schemas import COMMITTED_SCHEMAS, entry_of

PYTHON_ROOT = Path(__file__).resolve().parents[1]
# a set iterated in hash order is what differs between two seeds; two are enough to see it on these schemas
SEEDS = ('1', '2')


def _source_in_a_fresh_process(entry: Path, seed: str) -> str:
    script = (
        'import json, sys; from pathlib import Path; from generate.__main__ import generate;'
        'sys.stdout.write(json.dumps(generate(Path(sys.argv[1]))["source"]))'
    )
    run = subprocess.run(
        [sys.executable, '-c', script, str(entry)],
        cwd=PYTHON_ROOT,
        env={**os.environ, 'PYTHONHASHSEED': seed},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(run.stdout)


@pytest.mark.parametrize('name', sorted(COMMITTED_SCHEMAS))
def test_a_definition_is_the_same_on_two_runs_and_from_a_copied_tree(name: str, tmp_path: Path) -> None:
    entry = entry_of(name)
    copied = tmp_path / 'elsewhere' / name
    shutil.copytree(entry.parent, copied)
    sources = {
        (where, seed): _source_in_a_fresh_process(path, seed)
        for where, path in (('committed', entry), ('copied', copied / entry.name))
        for seed in SEEDS
    }
    assert len(set(sources.values())) == 1, sorted(sources)
