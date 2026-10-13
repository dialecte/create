"""Generated schemas, judged differentially (proof.fuzz): a fixed seed range runs with the suite, so a generator
change that breaks a combination no fixture writes fails here; `npm run fuzz` runs any range."""
from pathlib import Path

from proof import corpus
from proof.fuzz import run

# a few in every run; the proof's self tier and CI run a larger range
DRAWS = 40


def test_no_generated_schema_finds_the_generator_against_both_libraries(tmp_path: Path) -> None:
    report = run(seed='suite', count=DRAWS, out=tmp_path)
    assert report['failing'] == {}, f'shrunk cases in {tmp_path}'
    # the draws stay worth judging: most are schemas both libraries load
    assert report['loaded'] >= DRAWS * 0.8
    # and their generated files type-check with their probes (create's TypeScript side), when it is beside the package
    if corpus.DERIVE_ORACLE.exists():
        assert report['typed'] == report['loaded'] - len(report['failing'])
