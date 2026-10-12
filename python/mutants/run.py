"""Mutation gate of the generator: every small change of its code must make a test fail, or be recorded as a change
that cannot alter any output, with the reason.

    python -m mutants.run [module ...] [--workers N] [--record]

Each module of `generate/` is parsed, every mutation point found (a comparison, a boolean operator, a `not`, a
constant, `sorted` / `reversed` dropped, `min` / `max` and `any` / `all` swapped, a condition negated, a `continue`,
an addition or subtraction), and each mutant runs the whole
suite in a copy of the package - never in place. A mutant the suite lets pass is a survivor. The record of a module
(`mutants/records/<module path>.json`) lists its survivors, each with the reason it is equivalent; the run fails on a
survivor the record does not list, on a listed one without a reason, and on a listed one that no longer survives or
no longer exists (the record only shrinks). `--record` writes the survivors it finds into the records, reasons
empty, for a human to fill or to kill with a test.
"""
import argparse
import ast
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from xml.etree import ElementTree

PYTHON_ROOT = Path(__file__).resolve().parents[1]
CREATE_ROOT = PYTHON_ROOT.parent
GENERATOR = PYTHON_ROOT / 'generate'
RECORDS = Path(__file__).resolve().parent / 'records'
# what the suite reads beside the package: the committed fixtures
FIXTURES = CREATE_ROOT / 'test' / 'fixtures'
# data modules: tables generated from libxml2 / Unicode, each checked whole by its own test
NOT_MUTATED = {'definition/xml_name_classes.py', 'definition/xsd_blocks.py'}


@dataclass(frozen=True)
class Mutant:
    module: str  # path relative to generate/
    identity: str  # stable across unrelated edits: function, operator, original code, occurrence
    line: int
    description: str
    source: str  # the whole mutated module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='mutants', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('modules', nargs='*', help='modules of generate/ to mutate (default: all)')
    parser.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument('--record', action='store_true', help='write the survivors found into the records')
    arguments = parser.parse_args(argv)
    # a terminated run still removes its copies of the package (run_all's `finally`)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    modules = arguments.modules or sorted(
        str(path.relative_to(GENERATOR))
        for path in GENERATOR.rglob('*.py')
        if path.stat().st_size > 0 and str(path.relative_to(GENERATOR)) not in NOT_MUTATED
    )
    unknown = [module for module in modules if not (GENERATOR / module).is_file()]
    if unknown:
        parser.error(f'no such module of generate/: {", ".join(unknown)}')
    mutants = [mutant for module in modules for mutant in mutants_of(module)]
    print(f'{len(mutants)} mutants over {len(modules)} modules, {arguments.workers} workers', flush=True)
    started = time.monotonic()
    survivors = run_all(mutants, workers=arguments.workers)
    print(f'{len(mutants) - len(survivors)} killed, {len(survivors)} survived, {time.monotonic() - started:.0f} s')

    failures = 0
    for module in modules:
        found = {mutant.identity: mutant for mutant in survivors if mutant.module == module}
        existing = {mutant.identity for mutant in mutants if mutant.module == module}
        record = read_record(module)
        if arguments.record:
            # where it is now and what it does, refreshed; the reason kept
            write_record(
                module,
                {
                    identity: {'line': mutant.line, 'mutation': mutant.description, 'equivalent': record.get(identity, {}).get('equivalent', '')}
                    for identity, mutant in found.items()
                },
            )
            record = read_record(module)
        for identity, mutant in sorted(found.items(), key=lambda item: item[1].line):
            if identity not in record:
                failures += 1
                print(f'SURVIVED {module}:{mutant.line} {mutant.description}')
            elif not record[identity].get('equivalent'):
                failures += 1
                print(f'NO REASON {module}:{mutant.line} {mutant.description}')
        for identity, entry in record.items():
            if identity not in existing:
                failures += 1
                print(f'GONE {module}:{entry["line"]} {entry["mutation"]} - remove it from the record')
            elif identity not in found:
                failures += 1
                print(f'KILLED NOW {module}:{entry["line"]} {entry["mutation"]} - remove it from the record')
    print('mutation gate: ' + ('green' if failures == 0 else f'{failures} to resolve'))
    return 0 if failures == 0 else 1


def mutants_of(module: str) -> list[Mutant]:
    """The mutants of one module, each the whole module with one point changed."""
    text = (GENERATOR / module).read_text(encoding='utf-8')
    count = len(list(_points(ast.parse(text))))
    mutants = []
    seen: dict[str, int] = {}
    for index in range(count):
        tree = ast.parse(text)
        node, parent, scope, operator, mutate = list(_points(tree))[index]
        original = ast.unparse(node)
        replacement = mutate(node)
        _replace(parent, node, replacement)
        key = f'{scope}|{operator}|{original}'
        occurrence = seen.get(key, 0)
        seen[key] = occurrence + 1
        mutants.append(
            Mutant(
                module=module,
                identity=hashlib.sha256(f'{key}|{occurrence}'.encode()).hexdigest()[:16],
                line=node.lineno,
                description=f'{scope}: {_short(original)} -> {_short(ast.unparse(replacement))}',
                source=ast.unparse(tree),
            )
        )
    return mutants


def _short(code: str) -> str:
    code = ' '.join(code.split())
    return code if len(code) <= 90 else code[:87] + '...'


_FLIPPED_COMPARISONS = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
}
_SWAPPED_CALLS = {'min': 'max', 'max': 'min', 'any': 'all', 'all': 'any'}
_DROPPED_CALLS = {'sorted', 'reversed'}


def _points(tree: ast.AST):
    """Every mutation point, in a stable order: (node, parent, enclosing scope, operator, mutate(node) -> the node
    replacing it). Docstrings, annotations, decorators and signatures are never mutated."""
    def visit(node: ast.AST, scope: str):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope = f'{scope}.{node.name}' if scope else node.name
        for child in ast.iter_child_nodes(node):
            if _never_mutated(node, child):
                continue
            yield from _point(child, node, scope)
            yield from visit(child, scope)

    yield from visit(tree, '')


def _never_mutated(parent: ast.AST, child: ast.AST) -> bool:
    if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant) and isinstance(child.value.value, str):
        return True
    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return child is parent.returns or child is parent.args or child in parent.decorator_list
    if isinstance(parent, ast.ClassDef):
        return child in parent.decorator_list or child in parent.bases
    if isinstance(parent, (ast.AnnAssign, ast.arg)):
        return child is parent.annotation
    return False


def _point(node: ast.AST, parent: ast.AST, scope: str):
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _FLIPPED_COMPARISONS:
        yield node, parent, scope, 'compare', lambda n: ast.Compare(n.left, [_FLIPPED_COMPARISONS[type(n.ops[0])]()], n.comparators)
    elif isinstance(node, ast.BoolOp):
        yield node, parent, scope, 'boolean', lambda n: ast.BoolOp(ast.Or() if isinstance(n.op, ast.And) else ast.And(), n.values)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        yield node, parent, scope, 'not', lambda n: n.operand
    elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
        yield node, parent, scope, 'bool', lambda n: ast.Constant(not n.value)
    elif isinstance(node, ast.Constant) and type(node.value) is int:
        yield node, parent, scope, 'int', lambda n: ast.Constant(n.value + 1)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _SWAPPED_CALLS:
        yield node, parent, scope, 'call', lambda n: ast.Call(ast.Name(_SWAPPED_CALLS[n.func.id], ast.Load()), n.args, n.keywords)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _DROPPED_CALLS and len(node.args) == 1 and not node.keywords:
        yield node, parent, scope, 'call', lambda n: n.args[0]
    elif isinstance(node, ast.Continue):
        yield node, parent, scope, 'continue', lambda n: ast.Pass()
    elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)) and not _is_text(node):
        yield node, parent, scope, 'arithmetic', lambda n: ast.BinOp(n.left, ast.Sub() if isinstance(n.op, ast.Add) else ast.Add(), n.right)
    # a test written `not x`, `a == b`, `a in b` or `a is b` is already negated by another operator (dropping the
    # `not`, flipping the comparison): negating it again is the same program
    if isinstance(node, (ast.If, ast.While, ast.IfExp, ast.Assert)) and not _negated_elsewhere(node.test):
        yield node.test, node, scope, 'condition', lambda n: ast.UnaryOp(ast.Not(), n)


_NEGATED_BY_A_FLIP = (ast.Eq, ast.NotEq, ast.In, ast.NotIn, ast.Is, ast.IsNot)


def _negated_elsewhere(test: ast.expr) -> bool:
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return True
    return isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], _NEGATED_BY_A_FLIP)


def _is_text(node: ast.BinOp) -> bool:
    """A concatenation of text: `-` would not run, so the mutant says nothing."""
    return any(isinstance(side, (ast.Constant, ast.JoinedStr)) and isinstance(getattr(side, 'value', ''), str) for side in (node.left, node.right))


def _replace(parent: ast.AST, node: ast.AST, replacement: ast.AST) -> None:
    for field, value in ast.iter_fields(parent):
        if value is node:
            setattr(parent, field, replacement)
            return
        if isinstance(value, list) and any(item is node for item in value):
            value[[item is node for item in value].index(True)] = replacement
            return
    raise ValueError(f'{ast.dump(node)} is not a child of its parent')


def run_all(mutants: list[Mutant], *, workers: int) -> list[Mutant]:
    """The mutants the suite lets pass, each run in a worker's own copy of the package."""
    scratch = Path(tempfile.mkdtemp(prefix='dialecte-mutants-'))
    try:
        copies: Queue[Path] = Queue()
        for number in range(workers):
            copies.put(_copy(scratch / f'worker-{number}'))
        baseline, order = _baseline(copies)
        survivors: list[Mutant] = []
        done = 0

        timed_out: list[Mutant] = []

        def run(mutant: Mutant) -> None:
            nonlocal done
            copy = copies.get()
            try:
                outcome = _outcome(copy, mutant, order=order, timeout=max(120.0, baseline * 10))
                if outcome == 'survived':
                    survivors.append(mutant)
                elif outcome == 'timeout':
                    timed_out.append(mutant)
            finally:
                copies.put(copy)
                done += 1
                if done % 50 == 0:
                    print(f'  {done} / {len(mutants)}', flush=True)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(run, mutants))
        # a run slowed by the others is no kill: each mutant that timed out runs again alone, with a generous limit;
        # one that still does not end is a hang the suite notices
        if timed_out:
            print(f'{len(timed_out)} timed out beside the others: each runs again alone', flush=True)
        copy = copies.get()
        for mutant in timed_out:
            # alone, the suite takes about the baseline: ten times it, and two minutes at least, is no slow run
            outcome = _outcome(copy, mutant, order=order, timeout=max(120.0, baseline * 10))
            print(f'  timed out, alone: {outcome} - {mutant.module}:{mutant.line} {mutant.description}', flush=True)
            if outcome == 'survived':
                survivors.append(mutant)
        return survivors
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _copy(root: Path) -> Path:
    python = root / 'python'
    shutil.copytree(PYTHON_ROOT, python, ignore=shutil.ignore_patterns('.venv', '.tmp', '__pycache__', '.pytest_cache', 'mutants', '*.egg-info'))
    shutil.copytree(FIXTURES, root / 'test' / 'fixtures')
    return python


def _baseline(copies: Queue) -> tuple[float, list[str]]:
    """The suite's time without any mutant, and its test files fastest first: a mutant most tests notice stops
    at the first failure (-x), so the cheap inline-schema files run before the oracles that start processes."""
    copy = copies.get()
    try:
        report = copy / '.timings.xml'
        started = time.monotonic()
        run = _pytest(copy, timeout=600, extra=[f'--junitxml={report}'])
        if run.returncode != 0:
            raise SystemExit(f'the suite fails without any mutant:\n{run.stdout[-2000:]}')
        seconds = time.monotonic() - started
        by_file: dict[str, float] = {}
        for case in ElementTree.parse(report).iter('testcase'):
            # classname: a module path (tests.test_x, tests.corpora.test_y) and maybe a class: the longest prefix
            # that names a file of the copy is the test file
            name = _test_file(copy, case.get('classname', ''))
            if name is not None:
                by_file[name] = by_file.get(name, 0.0) + float(case.get('time', 0))
        report.unlink()
        order = sorted(by_file, key=lambda name: (by_file[name], name))
        ordered = _pytest(copy, timeout=600, extra=order)
        if ordered.returncode != 0:
            raise SystemExit(f'the suite run in its fast-first order fails without any mutant:\n{ordered.stdout[-2000:]}')
        return seconds, order
    finally:
        copies.put(copy)


def _test_file(copy: Path, classname: str) -> str | None:
    parts = classname.split('.')
    for length in range(len(parts), 0, -1):
        candidate = '/'.join(parts[:length]) + '.py'
        if (copy / candidate).is_file():
            return candidate
    return None


# The ordered suite passes without the mutant, run with the very same arguments (checked before any mutant): any
# other exit is the mutant's doing - a failing test, a broken import pytest reports as a collection, internal or
# conftest (usage) error. Only `no test collected` (5) says nothing of it: the gate stops there.
_SAYS_NOTHING = {5}


def _outcome(copy: Path, mutant: Mutant, *, order: list[str], timeout: float) -> str:
    """'killed', 'survived' or 'timeout': the suite run on `copy` with `mutant` in place of its module."""
    target = copy / 'generate' / mutant.module
    original = target.read_text(encoding='utf-8')
    target.write_text(mutant.source + '\n', encoding='utf-8')
    try:
        run = _pytest(copy, timeout=timeout, extra=order)
        if run.returncode == 0:
            return 'survived'
        if run.returncode not in _SAYS_NOTHING:
            return 'killed'
        raise SystemExit(f'pytest exited {run.returncode} on {mutant.module}:{mutant.line}, which says nothing of the mutant:\n{run.stdout[-2000:]}')
    except subprocess.TimeoutExpired:
        return 'timeout'
    finally:
        target.write_text(original, encoding='utf-8')


def _pytest(copy: Path, *, timeout: float, extra: list[str]) -> subprocess.CompletedProcess:
    """The suite in `copy`, in a process group of its own: on a timeout the whole group is killed, the node
    processes the oracle tests start included, so none is left to slow the next mutant."""
    command = [sys.executable, '-m', 'pytest', '-x', '-q', '-p', 'no:cacheprovider', '-W', 'ignore', *extra]
    with subprocess.Popen(
        command,
        cwd=copy,
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    ) as process:
        try:
            stdout, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        return subprocess.CompletedProcess(command, process.returncode, stdout, '')


def read_record(module: str) -> dict[str, dict]:
    path = RECORDS / f'{module}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def write_record(module: str, record: dict[str, dict]) -> None:
    path = RECORDS / f'{module}.json'
    if not record:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = dict(sorted(record.items(), key=lambda item: (item[1]['line'], item[0])))
    path.write_text(json.dumps(ordered, indent='\t', ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
