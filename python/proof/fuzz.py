"""Generated schemas, judged differentially (plan 10c, P7, first version: the schema tier).

    python -m proof.fuzz [--seed S] [--count N] [--out DIR]

Each draw is a valid-looking XSD 1.0 schema set of two documents (two namespaces) combining what the generator
reads: derivation chains of complex and simple types with block / final / blockDefault / abstract, substitution
trees under heads that may block, attribute wildcards of every kind, named groups and attribute groups, lists,
unions and facets on several levels, identity constraints, nillable and fixed values. A draw counts only if libxml2
and the schema library both load it (the draw rate is reported). Then the schema-tier oracles of `proof.corpus`
run, plus substitution membership through a holder element per head. A disagreement **fails only when both
libraries side against the generator**; where the libraries disagree with each other the case is kept for review
(each has its own faults - plan 10 and 10c list them) without failing. A failing case is shrunk - components and
particles removed while it still fails - and written to `--out`, to become a named test.
"""
import argparse
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import xmlschema
from lxml import etree

from proof import corpus
from proof.corpus import CorpusSchema

XS = 'http://www.w3.org/2001/XMLSchema'
A, B = 'urn:fuzz:a', 'urn:fuzz:b'
BUILTINS = ['xs:string', 'xs:token', 'xs:int', 'xs:decimal', 'xs:date', 'xs:boolean', 'xs:NCName']
PATTERNS = ['[A-Z]{2}[0-9]*', '\\d{1,3}', '[a-z-[aeiou]]+', '\\i\\c*', '(ab)+|c', '[\\p{Lu}\\p{Nd}]+']
DERIVATIONS = ['', 'extension', 'restriction', '#all', 'extension restriction']


@dataclass
class Draw:
    a: str
    b: str
    holders: dict[str, list[str]]  # holder element -> the head it holds (by local name)


def draw_schema(rng: random.Random) -> Draw:
    """Two documents: B (imported, other namespace) holds base types and a head; A derives from them."""
    bases: dict[str, str | None] = {}
    b_types, b_parts = _types(rng, prefix='b', count=rng.randint(1, 3), bases=[], derived_from=bases)
    head_type = rng.choice(b_types)
    b_parts.append(f'<xs:element name="BHead" type="b:{head_type}"{_flag(rng, "abstract")}{_block(rng)}/>')
    b_parts.append(_attribute_group(rng, 'bAttrs'))
    a_types, a_parts = _types(rng, prefix='a', count=rng.randint(2, 5), bases=[f'b:{name}' for name in b_types], derived_from=bases)
    members = []
    # each element's type, qualified: a member's type must derive from its head's
    element_types = {'b:BHead': f'b:{head_type}'}
    for index in range(rng.randint(1, 4)):
        head = rng.choice(['b:BHead'] + [f'a:M{other}' for other in range(index)])
        head_type_name = element_types[head]
        derived = [f'a:{name}' for name in a_types if _derives(f'a:{name}', head_type_name, bases)]
        if derived and rng.random() < 0.8:
            type_name = rng.choice(derived)
            typed = f' type="{type_name}"'
        else:
            type_name, typed = head_type_name, ''  # naming no type: the head's
        element_types[f'a:M{index}'] = type_name
        members.append(f'<xs:element name="M{index}" substitutionGroup="{head}"{typed}{_flag(rng, "abstract", 0.15)}{_block(rng, 0.2)}/>')
    a_parts += members
    holders = {'HoldsB': ['BHead'], **{f'Holds{index}': [f'M{index}'] for index in range(len(members)) if rng.random() < 0.5}}
    for holder, (head,) in holders.items():
        prefix = 'b' if head.startswith('B') else 'a'
        a_parts.append(
            f'<xs:element name="{holder}"><xs:complexType><xs:sequence>'
            f'<xs:element ref="{prefix}:{head}" minOccurs="0" maxOccurs="unbounded"/></xs:sequence></xs:complexType></xs:element>'
        )
    a_parts.append(_keyed(rng))
    a_doc = _document(A, 'a', a_parts, imports=[(B, 'b.xsd')], block_default=rng.random() < 0.2 and rng.choice(DERIVATIONS[1:]))
    b_doc = _document(B, 'b', b_parts, imports=[])
    return Draw(a=a_doc, b=b_doc, holders=holders)


def _derives(type_name: str, ancestor: str, bases: dict[str, str | None]) -> bool:
    current: str | None = type_name
    while current is not None:
        if current == ancestor:
            return True
        current = bases.get(current)
    return False


def _types(
    rng: random.Random, *, prefix: str, count: int, bases: list[str], derived_from: dict[str, str | None]
) -> tuple[list[str], list[str]]:
    names, parts = [], []
    for index in range(count):
        name = f'{prefix}T{index}'
        candidates = bases + [f'{prefix}:{other}' for other in names]
        kind = rng.random()
        if candidates and kind < 0.6:
            base = rng.choice(candidates)
            derived_from[f'{prefix}:{name}'] = base
            method = 'extension' if rng.random() < 0.7 else 'restriction'
            body = _content(rng, prefix) if method == 'extension' else ''
            parts.append(
                f'<xs:complexType name="{name}"{_flag(rng, "abstract", 0.15)}{_block(rng, 0.3)}>'
                f'<xs:complexContent><xs:{method} base="{base}">{body}</xs:{method}></xs:complexContent></xs:complexType>'
            )
        else:
            derived_from[f'{prefix}:{name}'] = None
            parts.append(f'<xs:complexType name="{name}"{_flag(rng, "abstract", 0.1)}{_block(rng, 0.3)}>{_content(rng, prefix)}{_attributes(rng)}</xs:complexType>')
        names.append(name)
    for index in range(rng.randint(0, 2)):
        parts.append(_simple_type(rng, f'{prefix}S{index}'))
    return names, parts


def _content(rng: random.Random, prefix: str) -> str:
    kind = rng.choice(['sequence', 'choice'])
    particles = ''.join(
        f'<xs:element name="{prefix}E{rng.randint(0, 9)}x{index}" type="{rng.choice(BUILTINS)}" minOccurs="{rng.randint(0, 1)}"/>'
        for index in range(rng.randint(0, 3))
    )
    return f'<xs:{kind} minOccurs="0">{particles}</xs:{kind}>' if particles else ''


def _attributes(rng: random.Random) -> str:
    attributes = ''.join(f'<xs:attribute name="at{index}" type="{rng.choice(BUILTINS)}"/>' for index in range(rng.randint(0, 2)))
    if rng.random() < 0.5:
        namespace = rng.choice(['##any', '##other', '##local', '##targetNamespace', f'{A} ##local', B])
        attributes += f'<xs:anyAttribute namespace="{namespace}" processContents="{rng.choice(["lax", "skip", "strict"])}"/>'
    return attributes


def _attribute_group(rng: random.Random, name: str) -> str:
    return f'<xs:attributeGroup name="{name}">{_attributes(rng)}</xs:attributeGroup>'


def _simple_type(rng: random.Random, name: str) -> str:
    facet = rng.choice([
        f'<xs:pattern value="{rng.choice(PATTERNS)}"/>',
        '<xs:enumeration value="x"/><xs:enumeration value="y z"/>',
        f'<xs:maxLength value="{rng.randint(1, 9)}"/>',
    ])
    return f'<xs:simpleType name="{name}"><xs:restriction base="xs:string">{facet}</xs:restriction></xs:simpleType>'


def _keyed(rng: random.Random) -> str:
    kind = rng.choice(['unique', 'key'])
    selector = rng.choice(['a:Entry', './/a:Entry', './a:Entry | a:Entry'])
    return (
        '<xs:element name="Keyed"><xs:complexType><xs:sequence>'
        '<xs:element name="Entry" maxOccurs="unbounded"><xs:complexType><xs:attribute name="id" type="xs:token" use="required"/>'
        '</xs:complexType></xs:element></xs:sequence></xs:complexType>'
        f'<xs:{kind} name="entryId"><xs:selector xpath="{selector}"/><xs:field xpath="@id"/></xs:{kind}></xs:element>'
    )


def _flag(rng: random.Random, name: str, chance: float = 0.2) -> str:
    return f' {name}="true"' if rng.random() < chance else ''


def _block(rng: random.Random, chance: float = 0.3) -> str:
    return f' block="{rng.choice(DERIVATIONS)}"' if rng.random() < chance else ''


def _document(target: str, prefix: str, parts: list[str], *, imports: list[tuple[str, str]], block_default: str | bool = False) -> str:
    imported = ''.join(f'<xs:import namespace="{namespace}" schemaLocation="{location}"/>' for namespace, location in imports)
    default = f' blockDefault="{block_default}"' if block_default else ''
    return (
        f'<xs:schema xmlns:xs="{XS}" xmlns:a="{A}" xmlns:b="{B}" targetNamespace="{target}" '
        f'elementFormDefault="qualified"{default}>{imported}{"".join(parts)}</xs:schema>'
    )


# --- judging -----------------------------------------------------------------------------------------------------


def write(draw: Draw, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'a.xsd').write_text(draw.a, encoding='utf-8')
    (folder / 'b.xsd').write_text(draw.b, encoding='utf-8')
    return folder / 'a.xsd'


LOAD_SECONDS = 20
_LOADER = (
    'import sys, xmlschema\n'
    'from lxml import etree\n'
    "xmlschema.XMLSchema10(sys.argv[1], allow='local')\n"
    'etree.XMLSchema(etree.parse(sys.argv[1]))\n'
)


def loads(entry: Path) -> str:
    """'loaded' when both libraries load the draw, else 'refused' - or 'hangs': libxml2 loops on some schemas, in C,
    so the libraries load it in a process of their own, stopped after LOAD_SECONDS."""
    try:
        run = subprocess.run([sys.executable, '-c', _LOADER, str(entry)], capture_output=True, timeout=LOAD_SECONDS)
    except subprocess.TimeoutExpired:
        return 'hangs'
    return 'loaded' if run.returncode == 0 else 'refused'


def judge(entry: Path, draw: Draw) -> tuple[list[str], list[str]]:
    """(findings both libraries support, disagreements the libraries do not settle - between themselves, or against
    the specification's own rule where the oracle has it)."""
    schema = CorpusSchema(id=entry.parent.name, entry=entry)
    findings = [f'generation/{item}' for item in corpus.generation(schema)]
    if findings:
        return findings, []
    for check in (corpus.constructs, corpus.identity_paths, corpus.preserved_sets, corpus.derivation):
        findings += [f'{check.__name__}/{item}' for item in check(schema)]
    disputed = []
    for check in (corpus.variants, corpus.attribute_wildcards):
        for item in check(schema):
            (findings if _library_agrees_with_libxml2(schema, check.__name__, item) else disputed).append(f'{check.__name__}/{item}')
    for item in _substitution(schema, draw):
        agreed = _library_agrees_with_libxml2(schema, 'substitution', item) and _specification_agrees_with_libxml2(schema, draw, item)
        (findings if agreed else disputed).append(f'substitution/{item}')
    return findings, disputed


def _specification_agrees_with_libxml2(schema: CorpusSchema, draw: Draw, item: str) -> bool:
    """Substitution Group OK (Transitive), written here on its own (a third voter: both libraries have faults on
    blocked derivations, plan 10c P0): the member stands for the holder's head when the head does not block
    substitution and the member's type derives from the head's by no method the head, the head's type or a type
    between them blocks (a member naming no type has its head's type)."""
    library = schema.library
    kind, holder, candidate = item.split('/')
    head = library.maps.elements[f'{{{A}}}{draw.holders[holder][0]}' if not draw.holders[holder][0].startswith('B') else f'{{{B}}}BHead']
    member = library.maps.elements[f'{{{B}}}BHead' if candidate == 'BHead' else f'{{{A}}}{candidate}']
    admitted = (not member.abstract) and (member is head or _substitutes(library, head, member))
    return admitted == (kind == 'missing')


def _substitutes(library, head, member) -> bool:  # noqa: ANN001
    chain_head = member
    while chain_head is not head:
        affiliation = chain_head.elem.get('substitutionGroup')
        if affiliation is None or chain_head.abstract and chain_head is member:
            return False
        chain_head = library.maps.elements[chain_head.schema.resolve_qname(affiliation)]
    head_block = _methods(head.elem.get('block', head.schema.block_default if hasattr(head.schema, 'block_default') else ''))
    if 'substitution' in head_block:
        return False
    head_type = _type_of(library, head)
    # clause 2.3: the methods of the whole derivation must not meet the union of the head's block, its type's, and
    # every type's strictly between the member's type and the head's
    blocked = (head_block | _methods(getattr(head_type, 'block', ''))) - {'substitution'}
    methods: set[str] = set()
    step = _type_of(library, member)
    target = _key(head_type)
    while _key(step) != target:
        if step is None:
            return False
        methods.add(getattr(step, 'derivation', None) or 'restriction')
        step = _base(step)
        if step is not None and _key(step) != target:
            blocked |= _methods(getattr(step, 'block', '')) - {'substitution'}
    return not methods & blocked


def _key(xsd_type) -> object:  # noqa: ANN001
    """A type as the chain compares it: a built-in by its name (the library keeps several copies of each), any other
    by identity."""
    if xsd_type is None:
        return None
    name = xsd_type.name or ''
    return name if name.startswith(f'{{{XS}}}') else id(xsd_type)


def _base(xsd_type):  # noqa: ANN001, ANN202
    """The type `xsd_type` derives from: a complex type naming none restricts anyType; anyType derives from nothing."""
    if (xsd_type.name or '') == f'{{{XS}}}anyType':
        return None
    if xsd_type.base_type is not None:
        return xsd_type.base_type
    return xsd_type.schema.maps.types[f'{{{XS}}}anyType'] if not xsd_type.is_simple() else xsd_type.schema.maps.types[f'{{{XS}}}anySimpleType']


def _type_of(library, element):  # noqa: ANN001, ANN202
    name = corpus._declared_type_name(library, element)
    return library.maps.types.get(name) if name else element.type


def _methods(block: str) -> set[str]:
    words = set((block or '').split())
    return {'extension', 'restriction', 'substitution'} if '#all' in words else words


def _substitution(schema: CorpusSchema, draw: Draw) -> list[str]:
    """Each holder holds its head or a member: libxml2 accepts the element exactly when the definition's model of the
    holder names it."""
    generated, validator = schema.generated, schema.validator
    found = []
    for holder in draw.holders:
        model = generated.definition.get(holder, {}).get('contentModel')
        if model is None or any(leaf.get('kind') == 'any' for leaf in _leaves(model)):
            continue  # any content (anyType, a wildcard): nothing to tell apart
        held = {leaf['name'] for leaf in _leaves(model) if leaf.get('kind') == 'element'}
        for candidate in sorted(name for name in generated.definition if name == 'BHead' or name.startswith('M')):
            namespace = B if candidate == 'BHead' else A
            accepted = _libxml2_holds(validator, holder, candidate, namespace)
            if accepted != (candidate in held):
                found.append(f'{"missing" if accepted else "extra"}/{holder}/{candidate}')
    return found


def _leaves(particle: dict) -> list[dict]:
    if particle.get('kind') in ('element', 'any'):
        return [particle]
    return [leaf for child in particle.get('particles', []) for leaf in _leaves(child)]


def _libxml2_holds(validator: etree.XMLSchema, holder: str, candidate: str, namespace: str) -> bool:
    validator.validate(etree.fromstring(f'<a:{holder} xmlns:a="{A}" xmlns:x="{namespace}"><x:{candidate}/></a:{holder}>'))
    # not held: the model does not expect it, or it is an abstract element; an abstract TYPE is the instance's fault
    return not any(
        'is not expected' in error.message or ('abstract' in error.message and 'type definition' not in error.message)
        for error in validator.error_log
    )


def _library_agrees_with_libxml2(schema: CorpusSchema, check: str, item: str) -> bool:
    """Whether the schema library judges the probe of `item` as libxml2 did (then the generator is the odd one)."""
    library = schema.library
    kind, *rest = item.split('/')
    admitted_by_libxml2 = kind == 'missing'
    if check == 'variants':
        element, type_name = rest[0], '/'.join(rest[1:])
        namespace, local = type_name[1:].split('}')
        instance = corpus._instance(element, attributes=f'xmlns:t="{namespace}" xsi:type="t:{local}"')
        reasons = [str(error.reason or error) for error in library.iter_errors(etree.tostring(instance).decode())]
        # the library's refusals: blocked, not derived (cannot substitute), unknown, abstract
        refusals = ('xsi:type', 'is abstract', 'cannot substitute', 'is blocked', 'not found')
        admitted = not any(word in reason for reason in reasons for word in refusals)
    elif check == 'attribute_wildcards':
        element, namespace = rest[0], '/'.join(rest[1:])
        namespace = '' if namespace == '(none)' else namespace
        attribute = f'p:probe="x" xmlns:p="{namespace}"' if namespace else 'probe="x"'
        instance = corpus._instance(element, attributes=attribute)
        admitted = not any('probe' in str(error.reason or error) and 'not allowed' in str(error.reason or error) for error in library.iter_errors(etree.tostring(instance).decode()))
    else:
        holder, candidate = rest
        namespace = B if candidate == 'BHead' else A
        document = f'<a:{holder} xmlns:a="{A}" xmlns:x="{namespace}"><x:{candidate}/></a:{holder}>'
        reasons = [str(error.reason or '') for error in library.iter_errors(document)]
        admitted = not any(
            'Unexpected child' in reason or 'is blocked' in reason or ('abstract' in reason and 'XsdComplexType' not in reason)
            for reason in reasons
        )
    return admitted == admitted_by_libxml2


# --- shrinking ---------------------------------------------------------------------------------------------------


SHRINK_SECONDS = 120


def shrink(draw: Draw, failing: str, scratch: Path) -> Draw:
    """`draw` with every component and particle removed that it still fails without (the same finding): rounds
    of removals, each node tried once a round, until a round removes nothing or SHRINK_SECONDS pass."""
    current = draw
    deadline = time.monotonic() + SHRINK_SECONDS
    changed = True
    while changed and time.monotonic() < deadline:
        changed = False
        for document in ('a', 'b'):
            tree = etree.fromstring(getattr(current, document).encode())
            nodes = [node for node in tree.iter() if isinstance(node.tag, str) and node is not tree and etree.QName(node).localname != 'import']
            for node in reversed(nodes):
                parent = node.getparent()
                if parent is None or time.monotonic() > deadline:
                    continue
                index = parent.index(node)
                parent.remove(node)
                candidate = Draw(**{**current.__dict__, document: etree.tostring(tree).decode()})
                if _still_fails(candidate, failing, scratch):
                    current, changed = candidate, True
                else:
                    parent.insert(index, node)
    return current


def _still_fails(draw: Draw, failing: str, scratch: Path) -> bool:
    folder = scratch / 'shrink'
    shutil.rmtree(folder, ignore_errors=True)
    entry = write(draw, folder)
    if loads(entry) != 'loaded':
        return False
    try:
        findings, _ = judge(entry, draw)
    except Exception:  # noqa: BLE001 - a holder removed by the shrink: no longer the same case
        return False
    # the very finding: a shrink that drifts to another disagreement explains nothing
    return failing in findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='proof.fuzz', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seed', default='0')
    parser.add_argument('--count', type=int, default=200)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / '.tmp' / 'fuzz')
    parser.add_argument('--workers', type=int, default=WORKERS, help='draws judged at once, each in its own process')
    arguments = parser.parse_args(argv)
    report = run(seed=arguments.seed, count=arguments.count, out=arguments.out, workers=arguments.workers)
    print(
        f'{report["drawn"]} drawn, {report["loaded"]} loaded by both libraries, {report["typed"]} type-checked with their '
        f'probes, {len(report["hangs"])} hanging a library, '
        f'{len(report["failing"])} failing, {len(report["disputed"])} disputed between the libraries'
    )
    for name, findings in report['failing'].items():
        print(f'FAILING {name}: {findings[:3]}')
    for name, disputed in report['disputed'].items():
        print(f'disputed {name}: {disputed[:3]}')
    return 1 if report['failing'] else 0


# draws are independent (each seeded by its index): judged in parallel, merged in index order - a run is reproducible
WORKERS = min(6, os.cpu_count() or 1)


@dataclass
class _Judged:
    """What one draw gave: whether it hung or loaded, its findings, and the folder its probes were written to."""

    name: str
    draw: Draw
    hangs: bool = False
    loaded: bool = False
    findings: tuple[str, ...] = ()
    disputed: tuple[str, ...] = ()
    probed: Path | None = None


def run(*, seed: str, count: int, out: Path, workers: int = WORKERS) -> dict:
    report: dict = {'drawn': 0, 'loaded': 0, 'typed': 0, 'hangs': [], 'failing': {}, 'disputed': {}}
    scratch = Path(tempfile.mkdtemp(prefix='dialecte-fuzz-'))
    try:
        jobs = [(seed, index, scratch, out) for index in range(count)]
        if workers > 1:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                judged = list(pool.map(_judge_draw, jobs))
        else:
            judged = [_judge_draw(job) for job in jobs]
        # each judged draw's generated files and type probes, type-checked together once the draws are judged
        probed: dict[Path, _Judged] = {}
        for outcome in judged:
            report['drawn'] += 1
            if outcome.hangs:
                report['hangs'].append(outcome.name)
            if not outcome.loaded:
                continue
            report['loaded'] += 1
            if outcome.findings:
                report['failing'][outcome.name] = list(outcome.findings)
            if outcome.disputed:
                report['disputed'][outcome.name] = list(outcome.disputed)
            if outcome.probed is not None:
                probed[outcome.probed] = outcome
        report['typed'] = len(probed)
        for folder in corpus.failing_types(list(probed)):
            outcome = probed[folder]
            write(outcome.draw, out / outcome.name)
            report['failing'][outcome.name] = ['types/probes']
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return report


def _judge_draw(job: tuple[str, int, Path, Path]) -> _Judged:
    """One draw, written, loaded by both libraries, judged and - with no finding - written with its type probes."""
    seed, index, scratch, out = job
    name = f'{seed}-{index}'
    draw = draw_schema(random.Random(f'{seed}:{index}'))
    entry = write(draw, scratch / name)
    loaded = loads(entry)
    if loaded == 'hangs':
        write(draw, out / f'{name}-libxml2-hangs')
    if loaded != 'loaded':
        return _Judged(name=name, draw=draw, hangs=loaded == 'hangs')
    findings, disputed = judge(entry, draw)
    if findings:
        write(shrink(draw, findings[0], scratch), out / name)
    if disputed:
        write(draw, out / f'{name}-disputed')
    folder = scratch / 'probed' / name
    probed = folder if not findings and corpus.write_probed(CorpusSchema(id=name, entry=entry), folder) else None
    return _Judged(
        name=name, draw=draw, loaded=True, findings=tuple(findings), disputed=tuple(disputed), probed=probed,
    )


if __name__ == '__main__':
    sys.exit(main())
