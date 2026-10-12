"""Fetch the corpora of `manifest.json` into the cache, each at its pinned version, checked by sha256.

    python -m corpora.fetch [source ...] [--pin]

Only sources the licence review admitted are in the manifest (plan 10b); an entry without its licence, terms and
verdict is refused. Three kinds of source:
- `archive`: a .zip or .tar.gz, sha256-pinned, of which only the `keep` paths are written (`strip` removed first);
- `files`: single files, each pinned by its own sha256, written at its path;
- `crawl`: schema documents found by following `schemaLocation` from `start`, on the `hosts` listed (`skip`: URLs
  of documents the review excluded, never fetched); written under `<host>/<path>`, every remote location they name
  mapped to the local copy when the corpus is read. The crawl runs only with `--pin`; a normal fetch takes exactly
  the files the manifest lists.
Downloads are kept in the cache (`_downloads/`) and checked against their pinned sha256 on every run, then each
source is rebuilt from them: a run without network rebuilds the cache, and nothing is used for being cached.
Then per source: `exclude` (globs) are removed, files a `marker` rule covers but whose text lacks the marker are
removed (a licence header that must be there), and `substitute` places our own documents (`overrides/`) at the paths
of excluded W3C infrastructure schemas. `--pin` writes the sha256 of everything fetched (and the crawled file lists)
into the manifest, for review before it is committed. Downloaded files are data: nothing in them is run.
"""
import argparse
import fnmatch
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from lxml import etree

from corpora.sources import MANIFEST, OVERRIDES, REQUIRED_FIELDS, W3C_INFRASTRUCTURE, cache_root, read_manifest

XS = 'http://www.w3.org/2001/XMLSchema'
USER_AGENT = 'dialecte-create-corpora/1 (+https://github.com/dialecte/create)'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='corpora.fetch', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('sources', nargs='*', help='source ids (default: all)')
    parser.add_argument('--pin', action='store_true', help='record the sha256 of what is fetched (and crawl) into the manifest')
    arguments = parser.parse_args(argv)

    manifest = read_manifest()
    by_id = {source['id']: source for source in manifest['sources']}
    unknown = [name for name in arguments.sources if name not in by_id]
    if unknown:
        parser.error(f'unknown sources: {", ".join(unknown)}')
    root = cache_root()
    previous = json.loads((root / 'manifest.lock.json').read_text()) if (root / 'manifest.lock.json').exists() else {}
    lock: dict[str, dict] = {}
    for source in (by_id[name] for name in arguments.sources or by_id):
        missing = [field for field in REQUIRED_FIELDS if not source.get(field)]
        if missing:
            raise SystemExit(f'{source["id"]}: no {", ".join(missing)} in the manifest - a source is fetched only once its licence is reviewed')
        target = root / source['id']
        written = _fetch(source, target=target, pin=arguments.pin, downloads=root / '_downloads')
        lock[source['id']] = written
        print(f'{source["id"]}: {written["files"]} files, {written["bytes"] // 1024} KiB', flush=True)
    if not arguments.sources:
        _prune(root / '_downloads', manifest)
    (root / 'manifest.lock.json').write_text(json.dumps({**previous, **lock}, indent='\t', sort_keys=True) + '\n')
    if arguments.pin:
        MANIFEST.write_text(json.dumps(manifest, indent='\t', ensure_ascii=False) + '\n')
        # written as the package's formatter writes it, so `npm run check` stays green
        formatter = MANIFEST.parents[2] / 'node_modules' / '.bin' / 'oxfmt'
        if formatter.exists():
            subprocess.run([str(formatter), str(MANIFEST)], capture_output=True)
        print(f'pinned: review {MANIFEST} before committing it')
    return 0


def _fetch(source: dict, *, target: Path, pin: bool, downloads: Path) -> dict:
    fetch = source['fetch']
    staging = Path(tempfile.mkdtemp(prefix=f'corpora-{source["id"]}-'))
    try:
        def get(url: str, expected: str | None) -> bytes:
            return _download(url) if pin else _kept(url, expected, downloads)

        if fetch['kind'] == 'archive':
            data = get(fetch['url'], fetch.get('sha256'))
            fetch['sha256'] = _checked(fetch['url'], data, fetch.get('sha256'), pin=pin)
            _extract(data, url=fetch['url'], strip=fetch.get('strip', ''), keep=fetch['keep'], into=staging)
        elif fetch['kind'] == 'files':
            for path, entry in fetch['files'].items():
                data = get(entry['url'], entry.get('sha256'))
                entry['sha256'] = _checked(entry['url'], data, entry.get('sha256'), pin=pin)
                _write(staging, path, data)
        elif fetch['kind'] == 'crawl':
            if pin:
                fetch['files'] = _crawl(fetch, staging)
            else:
                for url, sha256 in fetch['files'].items():
                    data = get(url, sha256)
                    _checked(url, data, sha256, pin=False)
                    _write(staging, _crawl_path(url), data)
        else:
            raise SystemExit(f'{source["id"]}: unknown fetch kind {fetch["kind"]!r}')
        _apply_rules(source, staging)
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging), target)
        files = [path for path in target.rglob('*') if path.is_file()]
        return {'files': len(files), 'bytes': sum(path.stat().st_size for path in files), 'verdict': source['verdict']}
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _prune(downloads: Path, manifest: dict) -> None:
    """Kept downloads no source of the manifest names any more."""
    wanted = set()
    for source in manifest['sources']:
        fetch = source['fetch']
        urls = [fetch['url']] if fetch['kind'] == 'archive' else [entry['url'] for entry in fetch['files'].values()] if fetch['kind'] == 'files' else list(fetch['files'])
        wanted |= {hashlib.sha256(url.encode()).hexdigest() for url in urls}
    for kept in downloads.glob('*') if downloads.exists() else []:
        if kept.name not in wanted:
            kept.unlink()


def _kept(url: str, expected: str | None, downloads: Path) -> bytes:
    """The bytes of `url`: the copy kept from an earlier run when it still has the pinned sha256, else downloaded and
    kept. Every run checks what it uses against the manifest - nothing is trusted because it is cached."""
    kept = downloads / hashlib.sha256(url.encode()).hexdigest()
    if expected is not None and kept.exists() and hashlib.sha256(kept.read_bytes()).hexdigest() == expected:
        return kept.read_bytes()
    data = _download(url)
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_bytes(data)
    return data


def _download(url: str, *, hosts: list[str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        landed = urllib.parse.urlsplit(response.geturl()).netloc
        if hosts is not None and landed not in hosts:
            raise SystemExit(f'{url} redirects to {response.geturl()}, on a host the manifest does not list - review it')
        return response.read()


def _checked(url: str, data: bytes, expected: str | None, *, pin: bool) -> str:
    actual = hashlib.sha256(data).hexdigest()
    if expected is None and not pin:
        raise SystemExit(f'{url}: no sha256 in the manifest - run with --pin and review it')
    if expected is not None and actual != expected:
        if pin:
            print(f'  {url}: sha256 changed ({expected[:12]}… -> {actual[:12]}…) - its licence must be read again', flush=True)
        else:
            raise SystemExit(f'{url}: sha256 {actual} is not the pinned {expected} - the source changed')
    return actual


def _extract(data: bytes, *, url: str, strip: str, keep: list[str], into: Path) -> None:
    """The members under `keep` (after `strip`), as plain files: absolute paths, `..`, links and devices refused."""
    members: list[tuple[str, bytes]] = []
    if url.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    members.append((info.filename, archive.read(info)))
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
            for member in archive.getmembers():
                if member.isfile():
                    handle = archive.extractfile(member)
                    members.append((member.name, handle.read() if handle else b''))
                elif not member.isdir():
                    continue  # links, devices: never written
    for name, content in members:
        if not name.startswith(strip):
            continue
        relative = name[len(strip):]
        if any(relative == prefix.rstrip('/') or relative.startswith(prefix) for prefix in keep):
            _write(into, relative, content)


def _write(root: Path, relative: str, data: bytes) -> None:
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise SystemExit(f'refused path in a downloaded source: {relative!r}')
    target = root.joinpath(*path.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def _crawl_path(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return f'{parsed.netloc}{parsed.path}'


def _crawl(fetch: dict, staging: Path) -> dict[str, str]:
    """Every schema document reachable from `start` through include / import / redefine, on the allowed hosts;
    W3C infrastructure schemas are never fetched (our own `overrides` stand for them)."""
    pending = list(fetch['start'])
    found: dict[str, str] = {}
    while pending:
        url = _canonical(pending.pop(0))
        if url in found or url in W3C_INFRASTRUCTURE or url in fetch.get('skip', []):
            continue
        host = urllib.parse.urlsplit(url).netloc
        if host not in fetch['hosts']:
            raise SystemExit(f'crawl reaches {url}, on a host the manifest does not list - review it')
        data = _download(url, hosts=fetch['hosts'])
        found[url] = hashlib.sha256(data).hexdigest()
        _write(staging, _crawl_path(url), data)
        for location in _locations(data):
            pending.append(urllib.parse.urljoin(url, location))
    return dict(sorted(found.items()))


def _canonical(url: str) -> str:
    return 'https://' + url[len('http://'):] if url.startswith('http://') else url


def _locations(data: bytes) -> list[str]:
    root = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
    return [
        element.get('schemaLocation')
        for element in root
        if isinstance(element.tag, str)
        and etree.QName(element).namespace == XS
        and etree.QName(element).localname in ('include', 'import', 'redefine')
        and element.get('schemaLocation')
    ]


def _apply_rules(source: dict, root: Path) -> None:
    files = {path.relative_to(root).as_posix(): path for path in root.rglob('*') if path.is_file()}
    for relative, path in files.items():
        if any(fnmatch.fnmatch(relative, pattern) for pattern in source.get('exclude', [])):
            path.unlink()
            continue
        for rule in source.get('marker', []):
            if fnmatch.fnmatch(relative, rule['glob']) and not any(fnmatch.fnmatch(relative, pattern) for pattern in rule.get('except', [])):
                texts = [rule['text']] if isinstance(rule['text'], str) else rule['text']
                if not any(text.encode() in path.read_bytes() for text in texts):
                    path.unlink()
                    break
    for relative, override in source.get('substitute', {}).items():
        _write(root, relative, (OVERRIDES / override).read_bytes())
    for relative, imported in source.get('wrappers', {}).items():
        _write(root, relative, _wrapper(root, relative, imported))


def _wrapper(root: Path, relative: str, imported: list[str]) -> bytes:
    """A schema of ours that imports the documents `imported` (globs, in order): one entry reading several
    documents together - companion schemas that import a namespace without a location, or every document type of a
    family sharing one closure."""
    here = root.joinpath(*PurePosixPath(relative).parent.parts)
    imports = []
    for pattern in imported:
        matched = sorted(path for path in root.rglob('*') if path.is_file() and fnmatch.fnmatch(path.relative_to(root).as_posix(), pattern))
        if not matched:
            raise SystemExit(f'wrapper {relative}: nothing matches {pattern}')
        for path in matched:
            namespace = etree.parse(str(path)).getroot().get('targetNamespace', '')
            location = Path(os.path.relpath(path, here)).as_posix()
            imports.append(f'\t<xs:import namespace="{namespace}" schemaLocation="{location}"/>\n')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!-- written by python/corpora/fetch.py (MIT): reads the documents below together -->\n'
        f'<xs:schema xmlns:xs="{XS}">\n' + ''.join(imports) + '</xs:schema>\n'
    ).encode()


if __name__ == '__main__':
    sys.exit(main())
