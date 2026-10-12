"""The corpora as the proof reads them: the admitted sources of `manifest.json`, where their cached copies lie, and
the remote locations their documents name mapped to those copies (so no fetched file is ever rewritten)."""
import fnmatch
import json
import os
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'manifest.json'
OVERRIDES = HERE / 'overrides'
CREATE_ROOT = HERE.parents[1]
# fields without which a source is not fetched: its licence was reviewed (plan 10b, licence table)
REQUIRED_FIELDS = ('license', 'terms', 'verdict')

# W3C infrastructure schemas the licence review excluded: never fetched, our own declarations stand for them
W3C_INFRASTRUCTURE = {
    'https://www.w3.org/2001/xml.xsd': 'xml.xsd',
    'https://www.w3.org/2009/01/xml.xsd': 'xml.xsd',
    'https://www.w3.org/XML/1998/namespace': 'xml.xsd',
    'https://www.w3.org/1999/xlink.xsd': 'xlink.xsd',
    'https://www.w3.org/XML/2008/06/xlink.xsd': 'xlink.xsd',
}


@dataclass(frozen=True)
class Source:
    id: str
    family: str
    verdict: str  # 'full' (mutable copies allowed) or 'schemas-only'
    root: Path  # the cached copy
    entries: tuple[str, ...]  # glob patterns of entry documents, relative to `root`
    instances: tuple[str, ...]  # glob patterns of valid instance documents
    locations: dict[str, Path]  # remote location named in a document -> the local copy read instead
    suite: str | None  # 'libxml2' or 'xmlschema' for a regression suite (entries and instances read from it)

    def entry_paths(self) -> list[Path]:
        return _matching(self.root, self.entries)

    def instance_paths(self) -> list[Path]:
        return _matching(self.root, self.instances)


def read_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def cache_root() -> Path:
    return Path(os.environ.get('DIALECTE_CORPORA_DIR') or CREATE_ROOT / '.corpora').resolve()


def fetched() -> dict[str, dict]:
    """What the cache holds, by source id (empty when nothing was fetched)."""
    lock = cache_root() / 'manifest.lock.json'
    return json.loads(lock.read_text(encoding='utf-8')) if lock.exists() else {}


def sources() -> list[Source]:
    """The admitted sources the cache holds, in manifest order."""
    held = fetched()
    found = []
    for entry in read_manifest()['sources']:
        if entry['id'] not in held:
            continue
        root = cache_root() / entry['id']
        found.append(
            Source(
                id=entry['id'],
                family=entry['family'],
                verdict=entry['verdict'],
                root=root,
                entries=tuple(entry.get('entries', [])),
                instances=tuple(entry.get('instances', [])),
                locations=_locations(entry, root),
                suite=entry.get('suite'),
            )
        )
    return found


def _locations(entry: dict, root: Path) -> dict[str, Path]:
    mapped: dict[str, Path] = {}
    for url, override in W3C_INFRASTRUCTURE.items():
        mapped[url] = OVERRIDES / override
    fetch = entry['fetch']
    if fetch['kind'] == 'crawl':
        for url in fetch['files']:
            parsed = urllib.parse.urlsplit(url)
            mapped[url] = root / parsed.netloc / parsed.path.lstrip('/')
    for url, relative in entry.get('locations', {}).items():
        mapped[url] = root / relative
    # a document may name either scheme
    for url in list(mapped):
        if url.startswith('https://'):
            mapped.setdefault('http://' + url[len('https://'):], mapped[url])
    return mapped


def _matching(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    files = sorted(path for path in root.rglob('*') if path.is_file())
    return [path for path in files if any(fnmatch.fnmatch(path.relative_to(root).as_posix(), pattern) for pattern in patterns)]
