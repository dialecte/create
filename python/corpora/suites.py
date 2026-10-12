"""The two regression suites as cases: each schema document, and each instance with the verdict its suite expects.

- libxml2 (`test/schemas`, `result/schemas`): a schema `<base>_<n>.xsd`, its instances `<base>_<m>.xml`, the verdict
  in the last line of `result/schemas/<base>_<n>_<m>.err` (`validates` / `fails to validate`). The verdict is libxml2's
  own: a disagreement names libxml2 or us, never "the label".
- xmlschema (`tests/test_cases/testfiles`): one case per line, `<path> [options]`; `--errors N` the errors expected
  (none: valid), `--version 1.1` not ours (XSD 1.0 only), `-L URI URL` a location override.
A file the licence review left out is skipped, as is a case whose file is missing.
"""
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from corpora.sources import Source

_LIBXML2_SCHEMA = re.compile(r'^(?P<base>.+)_(?P<number>\d+)\.xsd$')


@dataclass(frozen=True)
class SchemaCase:
    id: str
    entry: Path
    locations: dict[str, Path] = field(default_factory=dict)


@dataclass(frozen=True)
class InstanceCase:
    id: str
    schema: Path
    instance: Path
    valid: bool


def schema_cases(source: Source) -> list[SchemaCase]:
    if source.suite == 'libxml2':
        folder = source.root / 'test' / 'schemas'
        return [SchemaCase(id=f'{source.id}/{path.name}', entry=path) for path in sorted(folder.glob('*.xsd')) if _LIBXML2_SCHEMA.match(path.name)]
    if source.suite == 'xmlschema':
        return [
            SchemaCase(id=f'{source.id}/{case["path"]}', entry=case['file'], locations=case['locations'])
            for case in _xmlschema_cases(source)
            if case['file'].suffix == '.xsd' and case['errors'] == 0
        ]
    raise ValueError(f'{source.id} is no suite')


def instance_cases(source: Source) -> list[InstanceCase]:
    if source.suite != 'libxml2':
        return []  # xmlschema's instance cases name their schema by schemaLocation hints: read at the instance tier
    tests, results = source.root / 'test' / 'schemas', source.root / 'result' / 'schemas'
    cases = []
    for schema in sorted(tests.glob('*.xsd')):
        matched = _LIBXML2_SCHEMA.match(schema.name)
        if not matched:
            continue
        for instance in sorted(tests.glob(f'{matched["base"]}_*.xml')):
            number = instance.stem.rsplit('_', 1)[-1]
            result = results / f'{matched["base"]}_{matched["number"]}_{number}.err'
            verdict = _libxml2_verdict(result) if result.exists() else None
            if verdict is not None:
                cases.append(InstanceCase(id=f'{source.id}/{schema.name}/{instance.name}', schema=schema, instance=instance, valid=verdict))
    return cases


def _libxml2_verdict(result: Path) -> bool | None:
    lines = result.read_text(encoding='utf-8', errors='replace').strip().splitlines()
    last = lines[-1] if lines else ''
    if last.endswith(' validates'):
        return True
    if last.endswith(' fails to validate'):
        return False
    return None  # an internal error, or a schema that does not compile


def _words(line: str) -> list[str]:
    """A manifest line's words, quotes removed (`-L '' x.xsd`): shell rules, plain splitting where they fail."""
    try:
        return [word if word else "''" for word in shlex.split(line)]
    except ValueError:
        return line.split()


def _xmlschema_cases(source: Source) -> list[dict]:
    folder = source.root / 'tests' / 'test_cases'
    cases = []
    for line in (folder / 'testfiles').read_text(encoding='utf-8').splitlines():
        words = _words(line.split('#', 1)[0])
        if not words:
            continue
        path, options = words[0], words[1:]
        file = folder / path
        if not file.is_file():
            continue
        errors, version, locations = 0, '1.0', {}
        position = 0
        while position < len(options):
            option = options[position]
            name, _, inline = option.partition('=')
            if name == '--errors':
                errors = int(inline or options[position + 1])
                position += 0 if inline else 1
            elif name == '--version':
                version = inline or options[position + 1]
                position += 0 if inline else 1
            elif name in ('-L', '--location'):
                namespace = options[position + 1]
                locations['' if namespace == "''" else namespace] = (file.parent / options[position + 2]).resolve()
                position += 2
            position += 1
        if version == '1.0':
            cases.append({'path': path, 'file': file, 'errors': errors, 'locations': locations})
    return cases
