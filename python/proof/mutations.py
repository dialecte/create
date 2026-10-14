"""The structural mutation operators of the instance tier: each reads one fact of the definition at an
element the walk assessed and edits a copy of the document there. The verdict is not written by the operator: the
definition's walk predicts the edited document's structural faults, libxml2 judges it, and the two must agree - an
edit the fact says is valid matters as much as one it says is not (it catches an over-strict fact).

| operator        | fact read                         | edits                                                          |
| --------------- | --------------------------------- | -------------------------------------------------------------- |
| ATTR-REQUIRED   | `attributes.details[k].required`  | drop a declared attribute                                      |
| ATTR-FIXED      | `.fixed` (free string types only) | set it to its fixed value, then to another                     |
| ATTR-UNDECLARED | `attributes.details`, `.any`      | add an attribute no detail names: no namespace, the element's, a foreign one |
| CHILD-EDIT      | `contentModel`                    | remove, duplicate, swap a child; insert a declared, an undeclared, a foreign element |
| CHILD-NS        | the particle's `namespace`        | move a child to another namespace                              |
| TEXT            | `textContent` (presence, not typed values) | text in element-only or empty content, text in mixed content |
"""
import copy
import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from lxml import etree

from proof.instances import Visit, attribute_name, children_of
from proof.resolve import XSI

FOREIGN = 'urn:dialecte:proof'
PROBE = 'proofProbe'
STRING_TYPES = frozenset({'string', 'normalizedString', 'token'})


@dataclass(frozen=True)
class Mutation:
    operator: str
    # the edited element's path in the unmutated document, and what was done there: with the pair, the stable id
    path: str
    edit: str
    per_parent: bool
    apply: Callable[[etree._Element], None]
    # the element's position, child index by child index from the root: how the copy finds it
    route: tuple[int, ...]
    # the declaration the walk held the element to: the edited copy is predicted from it
    declaration: dict[str, Any]


Made = tuple[str, Callable[[etree._Element], None]]


@dataclass(frozen=True)
class _Run:
    """`count` edits of one operator at one element, the i-th made on demand: an element of a wide content model
    has (children + 1) x (declared children + 2) insertions, so edits are counted, sampled, then made."""

    operator: str
    visit: Visit
    count: int
    make: Callable[[int], Made]


def mutations(visits: list[Visit], *, size: int | None = None, seed: str = '') -> list[Mutation]:
    """The edits the operators make at the elements the walk assessed (nil elements left alone: what a nil element may hold depends on values): all of
    them, or a seeded sample of `size`, in the order they are found."""
    declared: dict[tuple[int, str], list[tuple[str, str]]] = {}  # per content model and holder, for this call
    runs = [run for visit in visits if not _nil(visit.element) for run in _runs(visit, declared) if run.count]
    total = sum(run.count for run in runs)
    chosen = range(total) if size is None or total <= size else _stratified(runs, size=size, seed=seed)
    found, offset, picked = [], 0, iter(chosen)
    index = next(picked, None)
    for run in runs:
        while index is not None and index < offset + run.count:
            edit, apply = run.make(index - offset)
            element = run.visit.element
            found.append(
                Mutation(
                    operator=run.operator,
                    path=element.getroottree().getpath(element),
                    edit=edit,
                    per_parent=run.visit.per_parent,
                    apply=apply,
                    route=_route(element),
                    declaration=run.visit.resolved.declaration,
                )
            )
            index = next(picked, None)
        offset += run.count
    return found


def mutated(root: etree._Element, mutation: Mutation) -> tuple[etree._Element, etree._Element]:
    """A copy of the document with the mutation applied at its element, and that element."""
    # a deep copy keeps what a reparse would not: entity references left unresolved, the namespaces in scope
    document = copy.deepcopy(root)
    target = document
    for index in mutation.route:
        target = children_of(target)[index]
    mutation.apply(target)
    return document, target


def _stratified(runs: list[_Run], *, size: int, seed: str) -> list[int]:
    """`size` edit indices, each operator first given an equal share of its own edits (insertions outnumber every
    other edit by far: drawn uniformly, an operator reading a rare fact would never run), the rest drawn from all."""
    by_operator: dict[str, list[tuple[int, int]]] = {}  # operator -> (first index, count) of its runs
    offset = 0
    for run in runs:
        by_operator.setdefault(run.operator, []).append((offset, run.count))
        offset += run.count
    share = size // len(by_operator)
    chosen: set[int] = set()
    for operator, spans in sorted(by_operator.items()):
        count = sum(length for _, length in spans)
        for local in random.Random(f'{seed}/{operator}').sample(range(count), min(share, count)):
            chosen.add(_global(spans, local))
    rest = random.Random(seed).sample(range(offset), min(offset, size))
    chosen.update([index for index in rest if index not in chosen][: size - len(chosen)])
    return sorted(chosen)


def _global(spans: list[tuple[int, int]], local: int) -> int:
    """The index among all edits of an operator's `local`-th edit."""
    for first, count in spans:
        if local < count:
            return first + local
        local -= count
    raise IndexError(local)


def _nil(element: etree._Element) -> bool:
    return (element.get(f'{{{XSI}}}nil') or '').strip() in ('true', '1')


def _route(element: etree._Element) -> tuple[int, ...]:
    route = []
    parent = element.getparent()
    while parent is not None:
        route.append(children_of(parent).index(element))
        element, parent = parent, parent.getparent()
    return tuple(reversed(route))


def _runs(visit: Visit, declared: dict[tuple[int, str], list[tuple[str, str]]]) -> list[_Run]:
    element, resolved = visit.element, visit.resolved
    content, children = resolved.content, children_of(visit.element)
    listed = [
        ('ATTR-REQUIRED', _required_edits(element, content['attributes'])),
        ('ATTR-FIXED', _fixed_edits(content['attributes'])),
        ('ATTR-UNDECLARED', _undeclared_edits(element)),
        ('CHILD-EDIT', _child_edits(len(children))),
        ('CHILD-NS', _namespace_edits(children)),
        ('TEXT', _text_edits(content)),
    ]
    runs = [_Run(operator=operator, visit=visit, count=len(edits), make=edits.__getitem__) for operator, edits in listed]
    # insertions: at each position, each declared child, an undeclared one, a foreign one
    model = content.get('contentModel')
    key = (id(model), resolved.holder)
    if key not in declared:
        declared[key] = _declared(model, resolved.holder)
    holder = f'{{{resolved.holder}}}' if resolved.holder else ''
    tags = [*declared[key], ('an undeclared element', f'{holder}ProofProbe'), ('a foreign element', f'{{{FOREIGN}}}ProofProbe')]
    positions = len(children) + 1

    def insertion(index: int) -> Made:
        position, which = divmod(index, len(tags))
        what, tag = tags[which]
        return f'insert {what} at {position + 1}', _inserting(position, tag)

    runs.append(_Run(operator='CHILD-EDIT', visit=visit, count=positions * len(tags), make=insertion))
    return runs


def _required_edits(element: etree._Element, attributes: dict[str, Any]) -> list[Made]:
    edits = []
    for key, detail in attributes['details'].items():
        name = _clark(*attribute_name(key, detail))
        if element.get(name) is not None:
            edits.append((f'drop {key}', _dropping(name)))
    return edits


def _fixed_edits(attributes: dict[str, Any]) -> list[Made]:
    edits = []
    for key, detail in attributes['details'].items():
        fixed, datatype = detail.get('fixed'), detail.get('type') or {}
        if fixed is not None and _free_string(datatype):
            name = _clark(*attribute_name(key, detail))
            edits += [(f'{key} at its fixed value', _setting(name, fixed)), (f'{key} at another value', _setting(name, fixed + 'x'))]
    return edits


def _free_string(datatype: dict[str, Any]) -> bool:
    """A string type no facet but whiteSpace constrains: any other string is a valid value of it, so a value other
    than the fixed one breaks only the fixed rule (a pattern or an enumeration would be broken too, a value fault, not compared)."""
    facets = set(datatype.get('facets', {})) - {'whiteSpace'}
    return datatype.get('builtin', 'string') in STRING_TYPES and not facets and 'list' not in datatype and 'union' not in datatype


def _undeclared_edits(element: etree._Element) -> list[Made]:
    namespace = etree.QName(element).namespace
    places = [('no namespace', ''), ('the element namespace', namespace), ('a foreign namespace', FOREIGN)]
    return [(f'add an attribute in {where}', _setting(_clark(uri, PROBE), 'x')) for where, uri in places if where == 'no namespace' or uri]


def _child_edits(count: int) -> list[Made]:
    edits: list[Made] = []
    for index in range(count):
        edits += [(f'remove child {index + 1}', _removing(index)), (f'duplicate child {index + 1}', _duplicating(index))]
        if index + 1 < count:
            edits.append((f'swap children {index + 1} and {index + 2}', _swapping(index)))
    return edits


def _namespace_edits(children: list[etree._Element]) -> list[Made]:
    edits = []
    for index, child in enumerate(children):
        name = etree.QName(child)
        moved = FOREIGN if name.namespace != FOREIGN else ''
        edits.append((f'move child {index + 1} to {moved or "no namespace"}', _renaming(index, _clark(moved, name.localname))))
    return edits


def _text_edits(content: dict[str, Any]) -> list[Made]:
    text = content.get('textContent')
    if text is None:
        return [('text in content that holds none', _texting('proof'))]
    if not text.get('type') and text.get('fixed') is None:
        return [('text in mixed content', _texting('proof'))]
    return []


def _declared(model: dict[str, Any] | None, holder: str) -> list[tuple[str, str]]:
    """The element particles of a content model, as (what, Clark tag), once each, in a stable order."""
    names = sorted({(particle['name'], particle.get('namespace', holder)) for particle in _element_particles(model)})
    return [(f'a declared {local}', _clark(namespace, local)) for local, namespace in names]


def _clark(namespace: str | None, local: str) -> str:
    return f'{{{namespace}}}{local}' if namespace else local


def _element_particles(particle: dict[str, Any] | None) -> Iterator[dict[str, Any]]:
    if particle is None:
        return
    if particle['kind'] == 'element':
        yield particle
    for nested in particle.get('particles', []):
        yield from _element_particles(nested)


# --- the edits, each on the copy's element -----------------------------------------------------------------------


def _dropping(name: str) -> Callable[[etree._Element], None]:
    return lambda element: element.attrib.pop(name)


def _setting(name: str, value: str) -> Callable[[etree._Element], None]:
    return lambda element: element.set(name, value)


def _removing(index: int) -> Callable[[etree._Element], None]:
    def edit(element: etree._Element) -> None:
        child = children_of(element)[index]
        _keep_tail(child)
        element.remove(child)

    return edit


def _duplicating(index: int) -> Callable[[etree._Element], None]:
    def edit(element: etree._Element) -> None:
        child = children_of(element)[index]
        twin = copy.deepcopy(child)
        twin.tail = None
        child.addnext(twin)

    return edit


def _swapping(index: int) -> Callable[[etree._Element], None]:
    def edit(element: etree._Element) -> None:
        first, second = children_of(element)[index : index + 2]
        first.addprevious(second)

    return edit


def _renaming(index: int, tag: str) -> Callable[[etree._Element], None]:
    def edit(element: etree._Element) -> None:
        children_of(element)[index].tag = tag

    return edit


def _inserting(position: int, tag: str) -> Callable[[etree._Element], None]:
    def edit(element: etree._Element) -> None:
        children = children_of(element)
        inserted = etree.Element(tag)
        if position < len(children):
            children[position].addprevious(inserted)
        else:
            element.append(inserted)

    return edit


def _texting(text: str) -> Callable[[etree._Element], None]:
    def edit(element: etree._Element) -> None:
        element.text = (element.text or '') + text

    return edit


def _keep_tail(child: etree._Element) -> None:
    """A removed child's tail stays in the document (lxml removes it with the child): the text is not the edit."""
    if child.tail:
        previous = child.getprevious()
        if previous is not None:
            previous.tail = (previous.tail or '') + child.tail
        else:
            parent = child.getparent()
            parent.text = (parent.text or '') + child.tail
