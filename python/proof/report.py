"""The instance tier's report: each process appends one line per pair it ran (`record`), the controlling process
prints the totals once, at the end of the run (`summary`, which also writes every edit a known libxml2 fault explained
to `explained.txt`, for review), and `reset` clears the last run's lines before workers start. Time is summed over
pairs, so it is the tier's own cost whatever the processes and the other tiers do."""
import json
import os
import shutil
from collections import Counter
from pathlib import Path

from proof.instance_tier import Outcome

REPORT = Path(__file__).resolve().parents[1] / '.tmp' / 'proof' / 'instances'


def reset() -> None:
    shutil.rmtree(REPORT, ignore_errors=True)


def record(pair_id: str, outcome: Outcome, *, seconds: float) -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    line = {
        'pair': pair_id,
        'mutated': outcome.mutated,
        'judged': dict(outcome.judged),
        'unpredictable': dict(outcome.unpredictable),
        'knownFaults': dict(outcome.known_faults),
        'explained': outcome.explained,
        'perParent': outcome.per_parent,
        'perParentDecisive': outcome.per_parent_decisive,
        'findings': len(outcome.findings),
        'seconds': seconds,
    }
    with (REPORT / f'{os.environ.get("PYTEST_XDIST_WORKER", "main")}.jsonl').open('a', encoding='utf-8') as report:
        report.write(json.dumps(line) + '\n')


def summary() -> list[str]:
    """The totals of the lines the processes wrote; nothing when no pair ran."""
    lines = [json.loads(line) for path in sorted(REPORT.glob('*.jsonl')) for line in path.read_text(encoding='utf-8').splitlines()]
    if not lines:
        return []
    judged, unpredictable, known = Counter(), Counter(), Counter()
    for line in lines:
        judged.update(line['judged'])
        unpredictable.update(line['unpredictable'])
        known.update(line['knownFaults'])
    seconds = sum(line['seconds'] for line in lines)
    written = [f'instance tier: {len(lines)} pairs, {sum(line["mutated"] for line in lines)} mutated, {sum(judged.values())} edits judged, {seconds:.0f} s summed over pairs']
    written += [f'  {operator:<16} {judged[operator]:>7} judged  {unpredictable[operator]:>5} unpredictable' for operator in sorted(judged.keys() | unpredictable.keys())]
    written.append(
        f'  per parent: {sum(line["perParent"] for line in lines)} edits at a tag declared several ways, '
        f'{sum(line["perParentDecisive"] for line in lines)} another declaration of the tag would judge otherwise'
    )
    written += [f'  explained by {fault}: {count}' for fault, count in sorted(known.items())]
    explained = sorted(edit for line in lines for edit in line['explained'])
    if explained:
        (REPORT / 'explained.txt').write_text('\n'.join(explained) + '\n', encoding='utf-8')
        written.append(f'  each explained edit: {REPORT / "explained.txt"}')
    written.append(f'  findings (each listed or failing): {sum(line["findings"] for line in lines)}')
    return written
