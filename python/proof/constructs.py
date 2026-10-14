"""The XSD constructs a schema writes, read from its documents themselves - no schema library -, and how the
generator treats each one (`constructs.json`): handled (the module that reads it), excluded (why, and what it would
change in an instance: nothing), or XSD 1.1 (refused). A construct in none of them is unclassified: the generator
was never shown to read it, so the proof fails rather than let it pass silently.

A construct is an element of the XML Schema namespace (`element`), one of its attributes (`element@attribute`,
`element@xml:lang` for the XML namespace, `element@vc:minVersion` for the XSD versioning namespace, `element@{foreign}`
for any other namespace). The content of `appinfo` and `documentation` is free text, not schema: it is not walked.
"""
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from lxml import etree

XS = 'http://www.w3.org/2001/XMLSchema'
XML = 'http://www.w3.org/XML/1998/namespace'
# XSD 1.1 conditional inclusion: the schema library, an XSD 1.0 processor aware of it, drops what libxml2 keeps
VERSIONING = 'http://www.w3.org/2007/XMLSchema-versioning'
TABLE = Path(__file__).with_name('constructs.json')
# the elements whose schemaLocation brings in another document of the schema
_REFERENCING = {'include', 'import', 'redefine', 'override'}
_FREE_CONTENT = {'appinfo', 'documentation'}


@dataclass(frozen=True)
class Classification:
    handled: frozenset[str]
    excluded: frozenset[str]
    xsd11: frozenset[str]

    def unclassified(self, constructs: set[str]) -> list[str]:
        return sorted(construct for construct in constructs - self.handled if not self._excluded(construct) and not self._xsd11(construct))

    def refused(self, constructs: set[str]) -> list[str]:
        """The XSD 1.1 constructs: those listed, and every attribute of an XSD 1.1 element."""
        return sorted(construct for construct in constructs if self._xsd11(construct))

    def _excluded(self, construct: str) -> bool:
        """Listed, or an attribute every schema element may carry (`*@xml:lang`)."""
        return construct in self.excluded or ('@' in construct and '*@' + construct.split('@', 1)[1] in self.excluded)

    def _xsd11(self, construct: str) -> bool:
        """Listed, an attribute of a listed element, or an attribute listed for every schema element (`*@vc:minVersion`)."""
        element, _, attribute = construct.partition('@')
        return construct in self.xsd11 or element in self.xsd11 or (attribute != '' and '*@' + attribute in self.xsd11)


def read_table(path: Path = TABLE) -> Classification:
    table = json.loads(path.read_text(encoding='utf-8'))
    return Classification(
        handled=frozenset(table['handled']), excluded=frozenset(table['excluded']), xsd11=frozenset(table['xsd-1.1'])
    )


def documents_of(entry: Path, *, locations: Mapping[str, Path] | None = None) -> list[Path]:
    """`entry` and every local document it includes, imports, redefines or overrides, directly or not, in reading
    order, named by a relative path or a file URL; a remote location is followed only where `locations` maps it to
    a local copy (as the generator reads it)."""
    found: dict[Path, None] = {}
    pending = [entry.resolve()]
    while pending:
        document = pending.pop(0)
        if document in found:
            continue
        found[document] = None
        for reference in etree.parse(str(document)).getroot():
            if not isinstance(reference.tag, str):
                continue
            name = etree.QName(reference)
            location = reference.get('schemaLocation')
            if name.namespace == XS and name.localname in _REFERENCING and location:
                target = (locations or {}).get(location) or _local(document, location)
                if target is not None and target.exists():
                    pending.append(target)
    return list(found)


def _local(document: Path, location: str) -> Path | None:
    """The local file a schemaLocation names, relative to `document` or as a file URL; none for a remote one."""
    url = urlparse(location)
    if url.scheme == 'file':
        return Path(url2pathname(url.path)).resolve()
    # a one-letter scheme is a Windows drive
    if url.scheme and len(url.scheme) > 1:
        return None
    return (document.parent / location).resolve()


def constructs_of(entry: Path, *, locations: Mapping[str, Path] | None = None) -> set[str]:
    """Every construct the documents of the schema whose entry document is `entry` write."""
    constructs: set[str] = set()
    for document in documents_of(entry, locations=locations):
        _walk(etree.parse(str(document)).getroot(), constructs)
    return constructs


def _walk(element: etree._Element, constructs: set[str]) -> None:
    name = etree.QName(element)
    if name.namespace != XS:
        return
    constructs.add(name.localname)
    for attribute in element.attrib:
        qualified = etree.QName(attribute)
        if qualified.namespace is None:
            constructs.add(f'{name.localname}@{qualified.localname}')
        elif qualified.namespace == XML:
            constructs.add(f'{name.localname}@xml:{qualified.localname}')
        elif qualified.namespace == VERSIONING:
            constructs.add(f'{name.localname}@vc:{qualified.localname}')
        else:
            constructs.add(f'{name.localname}@{{foreign}}')
    if name.localname in _FREE_CONTENT:
        return
    for child in element:
        if isinstance(child.tag, str):
            _walk(child, constructs)
