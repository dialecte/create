"""The schema-level oracles, for any schema the proof reads - a corpus entry, a suite schema, a generated one: each
check returns the disagreements it finds, as stable ids, never a bare boolean; `known-exceptions.json` lists the
ones a reviewed reason explains (plan 10c, P1).

The judges: libxml2 (lxml) for what an instance may hold, our own parsers and the construct table for the rest.
Remote locations a document names are read from the local copies `locations` maps them to, by the generator
(xmlschema's uri_mapper) and by libxml2 (a resolver handing back the copy under its file URL, so a document reached
both ways is one document).
"""
import json
import random
import re
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from lxml import etree

from generate.definition.build import Generated, generate_definition
from generate.definition.patterns import pattern_to_js
from generate.emit.ts_literal import definition_source
from generate.errors import SchemaNotRepresentable
from generate.model.identity_paths import parse_field, parse_selector
from proof.constructs import XS, constructs_of, documents_of, read_table

XSI = 'http://www.w3.org/2001/XMLSchema-instance'
PROBE_NAMESPACE = 'urn:dialecte:probe'
# how many global elements the instance probes visit per schema (seeded, so a run is reproducible)
PROBED_ELEMENTS = 25


class _Mapped(etree.Resolver):
    def __init__(self, locations: Mapping[str, Path]):
        super().__init__()
        self.locations = locations

    def resolve(self, url, public_id, context):  # noqa: ANN001, ARG002 - lxml's signature
        path = self.locations.get(url)
        return self.resolve_string(path.read_bytes(), context, base_url=path.resolve().as_uri()) if path else None


@dataclass
class CorpusSchema:
    """One schema the oracles judge: its entry document and how remote locations are read."""

    id: str
    entry: Path
    locations: Mapping[str, Path] = field(default_factory=dict)
    # a regression suite's schema: one both libraries refuse is a legality case, out of scope
    suite: bool = False

    @cached_property
    def generated(self) -> Generated | Exception:
        try:
            return generate_definition(self.entry, locations=self.locations)
        except Exception as failure:  # noqa: BLE001 - every refusal is a finding, reported by its type
            return failure

    @cached_property
    def library(self):  # noqa: ANN201 - the schema library's model, an exception when it refuses the schema
        import xmlschema

        mapped = {location: path.resolve().as_uri() for location, path in self.locations.items()}
        try:
            return xmlschema.XMLSchema10(str(self.entry), allow='local', uri_mapper=lambda uri: mapped.get(uri, uri))
        except (xmlschema.XMLSchemaException, OSError) as failure:
            return failure

    @cached_property
    def validator(self) -> etree.XMLSchema | Exception:
        parser = etree.XMLParser(no_network=True)
        parser.resolvers.add(_Mapped(self.locations))
        try:
            return etree.XMLSchema(etree.parse(str(self.entry), parser))
        except (etree.XMLSchemaParseError, etree.XMLSyntaxError) as failure:
            return failure

    @cached_property
    def documents(self) -> list[Path]:
        return documents_of(self.entry, locations=self.locations)


# --- the checks ------------------------------------------------------------------------------------------------


def generation(schema: CorpusSchema) -> list[str]:
    """The generator reads the schema; a schema it reads that libxml2 refuses is reported too: the checks libxml2
    judges cannot run on it."""
    generated = schema.generated
    if isinstance(generated, Exception):
        return [f'refused/{type(generated).__name__}']
    return ['libxml2-refuses'] if isinstance(schema.validator, Exception) else []


def read_back(schema: CorpusSchema) -> list[str]:
    """The emitted TypeScript, imported by node, is the data the generator built."""
    generated = schema.generated
    if isinstance(generated, Exception):
        return []
    with tempfile.TemporaryDirectory() as scratch:
        emitted = Path(scratch) / 'definition.generated.ts'
        emitted.write_text(definition_source(generated.definition, generated.types), encoding='utf-8')
        script = f"const m = await import({json.dumps(emitted.as_uri())}); process.stdout.write(JSON.stringify([m.DEFINITION, m.TYPES]))"
        run = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True)
    if run.returncode != 0:
        return ['does-not-import']
    # key order included: it is the order the file is written in
    read = json.loads(run.stdout, object_pairs_hook=list)
    built = json.loads(json.dumps([generated.definition, generated.types]), object_pairs_hook=list)
    return [] if read == built else ['differs']


def derivation(schema: CorpusSchema) -> list[str]:
    """The constants create's TypeScript emitter writes for the definition agree with it (`derivation_of`)."""
    generated = schema.generated
    if isinstance(generated, Exception):
        return []
    return derivation_of(generated.definition, generated.types)


# the oracle of the TypeScript derivations, run by node on generated data (scripts/derive-oracle)
DERIVE_ORACLE = Path(__file__).resolve().parents[2] / 'scripts' / 'derive-oracle' / 'run-oracle.ts'


def derivation_of(definition: dict[str, Any], types: dict[str, Any]) -> list[str]:
    """Each fact the emitted constants state that the definition does not imply, as `<fact>/<element>` or
    `<fact>/<parent>><element>`; `does-not-run` when the oracle itself fails. Nothing where create's scripts are not
    beside the package (a mutant copy of it: the oracle judges the TypeScript side, not the generator)."""
    if not DERIVE_ORACLE.exists():
        return []
    with tempfile.TemporaryDirectory() as scratch:
        data = Path(scratch) / 'generated.json'
        data.write_text(json.dumps({'definition': definition, 'types': types}), encoding='utf-8')
        run = subprocess.run(['node', str(DERIVE_ORACLE), str(data)], capture_output=True, text=True)
    if run.returncode != 0:
        return ['does-not-run']
    return json.loads(run.stdout)


def write_probed(schema: CorpusSchema, folder: Path) -> bool:
    """The schema's generated files - the definition, the constants and types the TypeScript emitter writes - and
    their type probes, in `folder` for `failing_types`; False when there is nothing to write (no definition, no
    root, no oracle beside the package)."""
    generated = schema.generated
    if isinstance(generated, Exception) or not DERIVE_ORACLE.exists():
        return False
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'definition.generated.ts').write_text(definition_source(generated.definition, generated.types), encoding='utf-8')
    data = folder.parent / f'{folder.name}.json'
    data.write_text(json.dumps({'definition': generated.definition, 'types': generated.types}), encoding='utf-8')
    run = subprocess.run(['node', str(DERIVE_ORACLE), str(data), '--write', str(folder)], capture_output=True, text=True)
    data.unlink()
    return run.returncode == 0 and (folder / 'probes.ts').exists()


def failing_types(folders: list[Path]) -> list[Path]:
    """The folders `write_probed` filled whose files or probes do not type-check, judged in one tsc run."""
    if not folders:
        return []
    run = subprocess.run(['node', str(DERIVE_ORACLE.parent / 'type-check.ts'), *map(str, folders)], capture_output=True, text=True)
    if run.returncode != 0:
        return list(folders)
    return [Path(folder) for folder in json.loads(run.stdout)]


def constructs(schema: CorpusSchema) -> list[str]:
    table = read_table()
    found = constructs_of(schema.entry, locations=schema.locations)
    return [f'unclassified/{name}' for name in table.unclassified(found)] + [f'xsd-1.1/{name}' for name in table.refused(found)]


def identity_paths(schema: CorpusSchema) -> list[str]:
    """Every selector and field of a schema libxml2 loads parses (libxml2 refuses a path outside the grammar)."""
    if isinstance(schema.validator, Exception):
        return []
    refused = []
    for document in schema.documents:
        for element in etree.parse(str(document)).iter(f'{{{XS}}}selector', f'{{{XS}}}field'):
            path = element.get('xpath', '')
            # the prefixes in scope where the path is written, `xml` always bound (as the generator reads it)
            namespaces = {prefix: uri for prefix, uri in element.nsmap.items() if prefix} | {'xml': 'http://www.w3.org/XML/1998/namespace'}
            parse = parse_selector if element.tag.endswith('selector') else parse_field
            try:
                parse(path, namespaces=namespaces)
            except SchemaNotRepresentable:
                refused.append(f'refused/{path}')
    return sorted(set(refused))


def patterns_of(schema: CorpusSchema) -> set[str]:
    return {
        element.get('value', '')
        for document in schema.documents
        for element in etree.parse(str(document)).iter(f'{{{XS}}}pattern')
    }


def patterns(texts: set[str], *, judge: Any) -> list[str]:
    """Each pattern converted and judged on its probes by libxml2 and node, as `tests/test_patterns` does; `judge`
    is that module's oracle (passed in: it lives with the tests)."""
    found = []
    convertible = []
    for text in sorted(texts):
        try:
            pattern_to_js(text)
            convertible.append(text)
        except SchemaNotRepresentable:
            found.append(f'refused/{text}')
    for text, value in judge(convertible):
        found.append(f'disagrees/{text}/{value!r}')
    return found


def variants(schema: CorpusSchema) -> list[str]:
    """For a seeded sample of global elements, every named type of the schema named with xsi:type: libxml2 admits it
    exactly when the definition lists it among the declaration's variants (the declared type itself aside). Built-in
    types are not probed: the generator leaves them to core by design (plan 10 B8), which knows their hierarchy."""
    generated, validator = schema.generated, schema.validator
    if isinstance(generated, Exception) or isinstance(validator, Exception):
        return []
    library = schema.library
    named = sorted(name for name, xsd_type in library.maps.types.items() if not name.startswith(f'{{{XS}}}') and xsd_type.schema.meta_schema is not None)
    found = []
    for element in _probed_elements(library, schema.id):
        declaration = _global_declaration(generated.definition, element)
        if declaration is None:
            found.append(f'no-global-declaration/{element.name}')
            continue
        listed = set(declaration.get('variants', []))
        declared = _declared_type_name(library, element)
        for type_name in named:
            if type_name == declared:
                continue
            admitted = _libxml2_admits_type(validator, element.name, type_name)
            if admitted != (type_name in listed):
                found.append(f'{"missing" if admitted else "extra"}/{element.name}/{type_name}')
    return found


def attribute_wildcards(schema: CorpusSchema) -> list[str]:
    """For the same sample, an undeclared attribute in no namespace, the element's, and a foreign one: libxml2 lets
    the element carry it exactly when the definition's attribute wildcard admits it. The namespace set is what is
    judged: a strict wildcard's "no global declaration" complaint counts as admitted (processContents is a separate
    fact of the definition)."""
    generated, validator = schema.generated, schema.validator
    if isinstance(generated, Exception) or isinstance(validator, Exception):
        return []
    found = []
    for element in _probed_elements(schema.library, schema.id):
        declaration = _global_declaration(generated.definition, element)
        if declaration is None:
            continue
        if _abstract_type(validator, element.name):
            continue
        wildcard = declaration['attributes'].get('any')
        element_namespace = element.name[1:].split('}')[0] if element.name.startswith('{') else ''
        for namespace in sorted({'', element_namespace, PROBE_NAMESPACE}):
            admitted = _libxml2_admits_attribute(validator, element.name, namespace)
            if admitted != _wildcard_admits(wildcard, namespace):
                found.append(f'{"missing" if admitted else "extra"}/{element.name}/{namespace or "(none)"}')
    return found


def preserved_sets(schema: CorpusSchema) -> list[str]:
    """A first, coarse inventory diff by local name - what it covers, no more: nothing invented (tags, attribute
    names, constraint names, enumeration values anywhere in the definition) and nothing dropped (global elements,
    constraints declared on them). It does not see a fact dropped from one declaration while kept elsewhere (an
    attribute, a facet, nillable, a wildcard, a local element): the keyed inventory plan 10c names is still to build.
    Named types, groups and particle counts are inlined by design."""
    generated = schema.generated
    if isinstance(generated, Exception):
        return []
    raw = _raw_facts(schema.documents)
    written = _written_facts(generated)
    found = []
    for kind in ('tags', 'attributes', 'constraints', 'enumerations'):
        found += [f'invented/{kind}/{name}' for name in sorted(written[kind] - raw[kind])]
    found += [f'dropped/global/{name}' for name in sorted(raw['globals'] - written['globals'])]
    found += [f'dropped/constraint/{name}' for name in sorted(raw['global-constraints'] - written['constraints'])]
    return found


# --- helpers -----------------------------------------------------------------------------------------------------


def _probed_elements(library, schema_id: str = '') -> list:  # noqa: ANN001
    elements = sorted(
        (element for name, element in library.maps.elements.items() if element.schema.meta_schema is not None and not element.abstract),
        key=lambda element: element.name,
    )
    # seeded by the schema: reproducible, and a different sample per schema
    return random.Random(schema_id).sample(elements, min(PROBED_ELEMENTS, len(elements)))


def _declared_type_name(library, element) -> str | None:  # noqa: ANN001
    """The type a global element declares, as XSD reads it: a member naming no type and declaring none has its
    head's (the schema library gives it anyType when the head blocks substitution)."""
    written = element.elem
    names_none = written.get('type') is None and not any(str(child.tag).rsplit('}', 1)[-1] in ('complexType', 'simpleType') for child in written)
    head = written.get('substitutionGroup')
    if names_none and head is not None:
        return _declared_type_name(library, library.maps.elements[element.schema.resolve_qname(head)])
    return element.type.name


def _global_declaration(definition: dict[str, Any], element) -> dict[str, Any] | None:  # noqa: ANN001
    tag = element.local_name
    namespace = element.name[1:].split('}')[0] if element.name.startswith('{') else ''
    written = definition.get(tag)
    if written is None:
        return None
    ways = written.get('declarations')
    if not ways:
        return written if written['namespace']['uri'] == namespace else None
    return next((way for way in ways.values() if way.get('global') and way['namespace']['uri'] == namespace), None)


def _instance(element_name: str, *, attributes: str = '') -> etree._Element:
    namespace, local = (element_name[1:].split('}') if element_name.startswith('{') else ('', element_name))
    declaration = f'xmlns:e="{namespace}"' if namespace else ''
    tag = f'e:{local}' if namespace else local
    return etree.fromstring(f'<{tag} {declaration} xmlns:xsi="{XSI}" {attributes}/>')


def _libxml2_admits_type(validator: etree.XMLSchema, element_name: str, type_name: str) -> bool:
    namespace, local = (type_name[1:].split('}') if type_name.startswith('{') else ('', type_name))
    qualified = f't:{local}' if namespace else local
    binding = f'xmlns:t="{namespace}"' if namespace else ''
    validator.validate(_instance(element_name, attributes=f'{binding} xsi:type="{qualified}"'))
    # refused: the name does not resolve, the type is blocked or not derived (said of xsi:type), or it is abstract
    # (said of the type: the probe holds nothing else that could be)
    return not any('xsi:type' in error.message or 'is abstract' in error.message for error in validator.error_log)


def _libxml2_admits_attribute(validator: etree.XMLSchema, element_name: str, namespace: str) -> bool:
    attribute = f'p:probe="x" xmlns:p="{namespace}"' if namespace else 'probe="x"'
    validator.validate(_instance(element_name, attributes=attribute))
    for error in validator.error_log:
        if 'probe' in error.message and 'not allowed' in error.message:
            return False
    return True


def _abstract_type(validator: etree.XMLSchema, element_name: str) -> bool:
    """An element whose type is abstract: libxml2 stops at that error, attributes unchecked - no verdict."""
    validator.validate(_instance(element_name))
    return any('abstract' in error.message for error in validator.error_log)


def _wildcard_admits(wildcard: dict[str, Any] | None, namespace: str) -> bool:
    if wildcard is None:
        return False
    if 'namespace' in wildcard:
        return namespace in wildcard['namespace']
    return namespace not in wildcard['notNamespace']


def _raw_facts(documents: list[Path]) -> dict[str, set[str]]:
    facts: dict[str, set[str]] = {kind: set() for kind in ('tags', 'attributes', 'constraints', 'enumerations', 'globals', 'global-constraints')}
    for document in documents:
        root = etree.parse(str(document)).getroot()
        for element in root.iter(f'{{{XS}}}element'):
            if element.get('name'):
                facts['tags'].add(element.get('name'))
        for top in root.findall(f'{{{XS}}}element'):
            if top.get('abstract') not in ('true', '1'):
                facts['globals'].add(top.get('name'))
            for constraint in top.findall(f'{{{XS}}}*'):
                if etree.QName(constraint).localname in ('unique', 'key', 'keyref'):
                    facts['global-constraints'].add(constraint.get('name'))
        for attribute in root.iter(f'{{{XS}}}attribute'):
            # a declared attribute, or one referenced from a namespace whose document is built in (xml:lang)
            name = attribute.get('name') or (attribute.get('ref') or '').split(':')[-1]
            if name:
                facts['attributes'].add(name)
        for constraint in root.iter(f'{{{XS}}}unique', f'{{{XS}}}key', f'{{{XS}}}keyref'):
            facts['constraints'].add(constraint.get('name'))
        for enumeration in root.iter(f'{{{XS}}}enumeration'):
            value = ' '.join(enumeration.get('value', '').split())
            facts['enumerations'].add(value)
            # a QName value is written {uri}local by the generator: its local part stands for it too
            if re.fullmatch(r'[^\s:{}]+:[^\s:{}]+', value):
                facts['enumerations'].add(value.split(':')[1])
    return facts


def _written_facts(generated: Generated) -> dict[str, set[str]]:
    facts: dict[str, set[str]] = {kind: set() for kind in ('tags', 'attributes', 'constraints', 'enumerations', 'globals')}
    facts['tags'] = set(generated.definition)
    for tag, element in generated.definition.items():
        ways = [element, *element.get('declarations', {}).values()]
        if any(way.get('global') for way in ways):
            facts['globals'].add(tag)
    for value in _walk(generated.definition, generated.types):
        if isinstance(value, dict):
            for constraint in value.get('constraints', []) if isinstance(value.get('constraints'), list) else []:
                facts['constraints'].add(constraint['name'])
            facets = value.get('facets') if isinstance(value.get('facets'), dict) else None
            for item in (facets or {}).get('enumeration', []):
                collapsed = ' '.join(item.split())
                facts['enumerations'].add(re.sub(r'^\{[^}]*\}', '', collapsed))
    for element in [*generated.definition.values(), *generated.types.values()]:
        for way in [element, *element.get('declarations', {}).values()]:
            for key in way.get('attributes', {}).get('details', {}):
                facts['attributes'].add(key.split(':')[-1])
    return facts


def _walk(*values: Any):
    pending = list(values)
    while pending:
        value = pending.pop()
        yield value
        if isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)


