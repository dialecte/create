"""The corpus schemas both tiers read, and the (schema, instance) pairs of the instance tier: each suite instance with
its schema (libxml2's by file name, xmlschema's by the instance's schema location hint), each family instance with
the family entry whose documents declare its root globally. A pair's schema is the schema tier's own `CorpusSchema`
object, so a process generates and compiles it once for both tiers; pairing reads the documents, not the library,
so collecting the tests generates nothing.
"""
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from lxml import etree

from corpora.sources import Source, sources
from corpora.suites import instance_cases, root_of, schema_cases, schema_key
from proof.constructs import XS
from proof.corpus import CorpusSchema


@dataclass(frozen=True)
class InstancePair:
    id: str
    schema: CorpusSchema
    instance: Path
    # a family the licence review admitted schemas-only, or a suite's invalid instance: judged, never mutated
    mutable: bool


@cache
def corpus_schemas() -> tuple[CorpusSchema, ...]:
    """Every schema of the fetched sources: the suites' cases, the families' entries (in manifest order)."""
    found: list[CorpusSchema] = []
    for source in sources():
        if source.suite:
            found += [
                CorpusSchema(id=case.id, entry=case.entry, locations={**source.locations, **case.locations}, suite=True, case_locations=case.locations)
                for case in schema_cases(source)
            ]
        else:
            found += [CorpusSchema(id=_entry_id(source, entry), entry=entry, locations=source.locations) for entry in source.entry_paths()]
    return tuple(found)


@cache
def instance_pairs() -> tuple[InstancePair, ...]:
    by_case = {schema_key(schema.entry, schema.case_locations): schema for schema in corpus_schemas()}
    pairs: list[InstancePair] = []
    for source in sources():
        if source.suite:
            for case in instance_cases(source):
                schema = by_case.get(schema_key(case.schema, case.locations))
                if schema is not None:
                    pairs.append(InstancePair(id=case.id, schema=schema, instance=case.instance, mutable=case.valid))
            continue
        entries = [by_case[schema_key(entry, {})] for entry in source.entry_paths()]
        for instance in source.instance_paths():
            schema = _declaring(entries, instance)
            if schema is not None:
                pairs.append(InstancePair(id=f'{source.id}/{instance.relative_to(source.root).as_posix()}', schema=schema, instance=instance, mutable=source.verdict == 'full'))
    return tuple(pairs)


def _entry_id(source: Source, entry: Path) -> str:
    return f'{source.id}/{entry.relative_to(source.root).as_posix()}'


def _declaring(entries: list[CorpusSchema], instance: Path) -> CorpusSchema | None:
    """The entry whose documents declare the instance's root globally (the first, in manifest order); an instance not
    well-formed goes with the first entry, so the instance tier reports it rather than lose it."""
    element = root_of(instance)
    if element is None:
        return entries[0] if entries else None
    root = etree.QName(element)
    return next((schema for schema in entries if (root.localname, root.namespace or '') in _globals(schema.entry, tuple(schema.locations.items()))), None)


@cache
def _globals(entry: Path, locations: tuple[tuple[str, Path], ...]) -> frozenset[tuple[str, str]]:
    """The (name, namespace) of every global element the documents of a schema declare; a document with no target
    namespace is read in the entry's (a chameleon include takes its includer's)."""
    documents = CorpusSchema(id='', entry=entry, locations=dict(locations)).documents
    entry_namespace = etree.parse(str(entry)).getroot().get('targetNamespace', '')
    found = set()
    for document in documents:
        schema = etree.parse(str(document)).getroot()
        namespace = schema.get('targetNamespace') or entry_namespace
        found |= {(element.get('name'), namespace) for element in schema.iterchildren(f'{{{XS}}}element')}
    return frozenset(found)
