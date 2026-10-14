"""The two regression suites as cases: each schema document, and each instance with the verdict its suite expects.

- libxml2 (`test/schemas`, `result/schemas`): a schema `<base>_<n>.xsd`, its instances `<base>_<m>.xml`, the verdict
  in the last line of `result/schemas/<base>_<n>_<m>.err` (`validates` / `fails to validate`). The verdict is libxml2's
  own: a disagreement names libxml2 or us, never "the label".
- xmlschema (`tests/test_cases/testfiles`): one case per line, `<path> [options]`; `--errors N` the errors expected
  (none: valid), `--version 1.1` not ours (XSD 1.0 only), `-L URI URL` a location override. An instance names its
  schema by its root's schemaLocation hint; that schema is a schema case too, unless the manifest lists it with errors.
A file the licence review left out is skipped, as is a case whose file is missing.
"""
import re
import shlex
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from lxml import etree

from corpora.sources import Source

XSI = 'http://www.w3.org/2001/XMLSchema-instance'
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
    locations: dict[str, Path] = field(default_factory=dict)


def schema_cases(source: Source) -> list[SchemaCase]:
    if source.suite == 'libxml2':
        folder = source.root / 'test' / 'schemas'
        return [SchemaCase(id=f'{source.id}/{path.name}', entry=path) for path in sorted(folder.glob('*.xsd')) if _LIBXML2_SCHEMA.match(path.name)]
    if source.suite == 'xmlschema':
        # one case per schema and location overrides: an instance is judged with the overrides its own line gives
        cases: dict[SchemaKey, SchemaCase] = {}
        named = [(case['file'], case['locations']) for case in _xmlschema_cases(source) if case['file'].suffix == '.xsd' and case['errors'] == 0]
        named += [(case.schema, case.locations) for case in instance_cases(source)]
        for entry, locations in named:
            if schema_key(entry, locations) not in cases:
                same_file = sum(key[0] == entry.resolve() for key in cases)
                case_id = _xmlschema_id(source, entry) + (f'#{same_file + 1}' if same_file else '')
                cases[schema_key(entry, locations)] = SchemaCase(id=case_id, entry=entry, locations=locations)
        return list(cases.values())
    raise ValueError(f'{source.id} is no suite')


SchemaKey = tuple[Path, tuple[tuple[str, Path], ...]]


def schema_key(entry: Path, locations: dict[str, Path]) -> SchemaKey:
    """What tells two schema cases apart: the entry document and the location overrides it is read with."""
    return entry.resolve(), tuple(sorted(locations.items()))


def instance_cases(source: Source) -> list[InstanceCase]:
    if source.suite == 'libxml2':
        return _libxml2_instance_cases(source)
    if source.suite == 'xmlschema':
        return _xmlschema_instance_cases(source)
    raise ValueError(f'{source.id} is no suite')


def _libxml2_instance_cases(source: Source) -> list[InstanceCase]:
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


def _xmlschema_instance_cases(source: Source) -> list[InstanceCase]:
    cases = _xmlschema_cases(source)
    erroneous = {case['file'] for case in cases if case['file'].suffix == '.xsd' and case['errors'] > 0}
    found = []
    for case in cases:
        if case['file'].suffix != '.xml':
            continue
        schema = _hinted_schema(case['file'])
        if schema is None or schema in erroneous:
            continue
        found.append(
            InstanceCase(id=f'{source.id}/{case["path"]}', schema=schema, instance=case['file'], valid=case['errors'] == 0, locations=case['locations'])
        )
    return found


def _xmlschema_id(source: Source, file: Path) -> str:
    return f'{source.id}/{file.relative_to((source.root / "tests" / "test_cases").resolve()).as_posix()}'


@cache
def _hinted_schema(instance: Path) -> Path | None:
    """The local schema an instance names for its root's namespace (`schemaLocation`) or for no namespace."""
    root = root_of(instance)
    if root is None:
        return None
    namespace = etree.QName(root).namespace
    if namespace is None:
        location = root.get(f'{{{XSI}}}noNamespaceSchemaLocation')
    else:
        words = (root.get(f'{{{XSI}}}schemaLocation') or '').split()
        location = dict(zip(words[::2], words[1::2], strict=False)).get(namespace)
    if not location or '://' in location:
        return None
    path = (instance.parent / location).resolve()
    return path if path.is_file() else None


def root_of(document: Path) -> etree._Element | None:
    """A document's root element, read up to its start tag; none for a document that is not well-formed there."""
    try:
        for _, element in etree.iterparse(str(document), events=('start',), no_network=True, resolve_entities=False):
            return element
    except etree.XMLSyntaxError:
        pass
    return None


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
        file = (folder / path).resolve()
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
