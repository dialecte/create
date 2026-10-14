"""The proof's content-model matcher: whether a content model admits a list of children, and which particle each
child is held by - read on the definition as the generator writes it (`minOccurs` absent = 0, `maxOccurs` absent =
unbounded, an element particle without `namespace` in its holder's)."""
from typing import Any

import pytest

from proof.matcher import match, viable_prefix

HOLDER = 'urn:h'


def element(name: str, *, min_occurs: int = 1, max_occurs: int | None = 1, namespace: str | None = None, declaration: str | None = None) -> dict[str, Any]:
    written: dict[str, Any] = {'kind': 'element', 'name': name}
    if namespace is not None:
        written['namespace'] = namespace
    if min_occurs:
        written['minOccurs'] = min_occurs
    if max_occurs is not None:
        written['maxOccurs'] = max_occurs
    if declaration is not None:
        written['declaration'] = declaration
    return written


def group(kind: str, *particles: dict[str, Any], min_occurs: int = 1, max_occurs: int | None = 1) -> dict[str, Any]:
    written: dict[str, Any] = {'kind': kind, 'particles': list(particles)}
    if min_occurs:
        written['minOccurs'] = min_occurs
    if max_occurs is not None:
        written['maxOccurs'] = max_occurs
    return written


def wildcard(*, namespace: list[str] | None = None, not_namespace: list[str] | None = None, min_occurs: int = 1, max_occurs: int | None = 1) -> dict[str, Any]:
    written: dict[str, Any] = {'kind': 'any', 'processContents': 'lax'}
    if namespace is not None:
        written['namespace'] = namespace
    if not_namespace is not None:
        written['notNamespace'] = not_namespace
    if min_occurs:
        written['minOccurs'] = min_occurs
    if max_occurs is not None:
        written['maxOccurs'] = max_occurs
    return written


def children(*names: str) -> list[tuple[str, str]]:
    """`A` in the holder's namespace, `x:A` in `urn:x`, `-:A` in none."""
    found = []
    for name in names:
        prefix, _, local = name.rpartition(':')
        found.append((local, {'': HOLDER, 'x': 'urn:x', '-': ''}[prefix]))
    return found


AB = group('sequence', element('A'), element('B'))

ADMITS = [
    pytest.param(None, [], True, id='no content model, no child -> admitted'),
    pytest.param(None, ['A'], False, id='no content model, a child -> refused'),
    pytest.param(AB, ['A', 'B'], True, id='a sequence in order -> admitted'),
    pytest.param(AB, ['B', 'A'], False, id='a sequence out of order -> refused'),
    pytest.param(AB, ['A'], False, id='a sequence missing a required child -> refused'),
    pytest.param(AB, ['A', 'B', 'B'], False, id='a sequence with one child too many -> refused'),
    pytest.param(group('sequence', element('A', min_occurs=0), element('B')), ['B'], True, id='an optional child left out -> admitted'),
    pytest.param(group('sequence', element('A', max_occurs=None)), ['A', 'A', 'A'], True, id='an unbounded child repeated -> admitted'),
    pytest.param(group('sequence', element('A', max_occurs=2)), ['A', 'A', 'A'], False, id='a child repeated past its maximum -> refused'),
    pytest.param(group('sequence', element('A', min_occurs=2, max_occurs=3)), ['A'], False, id='a child under its minimum -> refused'),
    pytest.param(group('choice', element('A'), element('B')), ['B'], True, id='a choice: one branch -> admitted'),
    pytest.param(group('choice', element('A'), element('B')), ['A', 'B'], False, id='a choice: two branches -> refused'),
    pytest.param(group('choice', element('A'), element('B'), max_occurs=None), ['B', 'A', 'B'], True, id='a repeated choice -> admitted'),
    pytest.param(group('sequence', AB, min_occurs=1, max_occurs=None), ['A', 'B', 'A', 'B'], True, id='a repeated sequence (A, B)+ -> admitted'),
    pytest.param(group('sequence', AB, min_occurs=1, max_occurs=None), ['A', 'B', 'A'], False, id='a repeated sequence cut short -> refused'),
    pytest.param(group('all', element('A'), element('B', min_occurs=0)), ['B', 'A'], True, id='an all group in any order -> admitted'),
    pytest.param(group('all', element('A'), element('B', min_occurs=0)), ['B'], False, id='an all group missing a required child -> refused'),
    pytest.param(group('all', element('A'), element('B')), ['A', 'A', 'B'], False, id='an all group: a child twice -> refused'),
    pytest.param(group('all', element('A'), element('B'), min_occurs=0), [], True, id='an optional all group, empty -> admitted'),
    pytest.param(group('sequence', element('A', namespace='urn:x')), ['x:A'], True, id='a child in the namespace its particle names -> admitted'),
    pytest.param(group('sequence', element('A')), ['x:A'], False, id='a child in another namespace than its particle -> refused'),
    pytest.param(group('sequence', element('A', namespace='')), ['-:A'], True, id='a child in no namespace, its particle in none -> admitted'),
    pytest.param(group('sequence', wildcard(not_namespace=[])), ['x:Z'], True, id='##any admits a foreign element'),
    pytest.param(group('sequence', wildcard(not_namespace=[HOLDER, ''])), ['Z'], False, id='##other refuses the target namespace'),
    pytest.param(group('sequence', wildcard(not_namespace=[HOLDER, ''])), ['-:Z'], False, id='##other refuses no namespace'),
    pytest.param(group('sequence', wildcard(namespace=[''])), ['-:Z'], True, id='##local admits no namespace'),
    pytest.param(group('sequence', wildcard(namespace=['urn:x'], max_occurs=None, min_occurs=0)), [], True, id='an optional repeated wildcard, nothing -> admitted'),
    pytest.param(group('sequence', group('sequence', min_occurs=0)), [], True, id='an empty optional group -> admitted'),
    pytest.param(group('choice'), [], False, id='an empty required choice admits nothing'),
    pytest.param(group('sequence', element('A', min_occurs=0, max_occurs=None), element('A', min_occurs=0)), ['A', 'A'], True, id='a sequence a repetition can end where the next starts -> admitted'),
]


@pytest.mark.parametrize(('model', 'names', 'admitted'), ADMITS)
def test_what_a_content_model_admits(model: dict[str, Any] | None, names: list[str], admitted: bool) -> None:
    assert (match(model, children(*names), holder=HOLDER) is not None) is admitted


def test_each_child_is_held_by_the_particle_it_matched() -> None:
    # P declared two ways: the first occurrence is the first particle's declaration, the others the second's
    first, second = element('P', declaration='1'), element('P', max_occurs=None, declaration='2')
    held = match(group('sequence', first, element('Q'), second), children('P', 'Q', 'P', 'P'), holder=HOLDER)
    assert held is not None
    assert [particle.get('declaration', particle['name']) for particle in held] == ['1', 'Q', '2', '2']


def test_a_child_a_wildcard_admits_is_held_by_the_wildcard() -> None:
    any_foreign = wildcard(not_namespace=[HOLDER, ''])
    held = match(group('sequence', element('A'), any_foreign), children('A', 'x:Z'), holder=HOLDER)
    assert held is not None and held[1] is any_foreign


PREFIXES = [
    pytest.param(group('sequence', element('A'), element('B')), ['A', 'B'], ['A', 'B'], id='an admitted list: every child'),
    pytest.param(group('sequence', element('A'), element('B')), ['A'], ['A'], id='a list cut short: every child (the model wants more)'),
    pytest.param(group('sequence', element('A'), element('B')), ['A', 'A', 'B'], ['A'], id='a child twice: the children before the second'),
    pytest.param(group('sequence', element('A'), element('B')), ['B'], [], id='a first child the model refuses: none'),
    pytest.param(group('sequence', element('A', max_occurs=None), element('B')), ['A', 'A', 'C'], ['A', 'A'], id='a repetition, then a stranger'),
    pytest.param(group('all', element('A'), element('B')), ['B', 'B'], ['B'], id='an all group: a child twice'),
    pytest.param(group('choice', group('sequence', element('A'), element('B')), group('sequence', element('A'), element('C'))), ['A', 'D'], ['A'], id='a prefix two branches share'),
    pytest.param(None, ['A'], [], id='no model: none'),
    pytest.param(group('all', *(element(f'E{index}') for index in range(40))), ['E3', 'E3'], ['E3'], id='a wide all group: what is left may still come (no subset walk)'),
]


@pytest.mark.parametrize(('model', 'names', 'assessed'), PREFIXES)
def test_the_children_read_one_by_one_before_the_first_one_refused(model: dict[str, Any] | None, names: list[str], assessed: list[str]) -> None:
    assert [particle['name'] for particle in viable_prefix(model, children(*names), holder=HOLDER)] == assessed


def test_a_choice_with_no_particle_admits_nothing_unless_read_as_libxml2() -> None:
    # a memberless abstract head's choice: nothing validates against it; libxml2 builds it as an epsilon
    model = group('sequence', element('A'), group('choice'), element('B', min_occurs=0))
    assert match(model, children('A'), holder=HOLDER) is None
    assert match(model, children('A'), holder=HOLDER, empty_choice_is_empty=True) is not None
    # the model admits no list at all: no prefix of one is viable, not even the first child
    assert viable_prefix(model, children('A', 'B', 'C'), holder=HOLDER) == []
    assert [particle['name'] for particle in viable_prefix(model, children('A', 'B', 'C'), holder=HOLDER, empty_choice_is_empty=True)] == ['A', 'B']
