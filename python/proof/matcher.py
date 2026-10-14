"""The proof's content-model matcher: whether a content model, as the definition writes it, admits a list of children,
and which particle holds each child.

The definition writes `minOccurs` only when it is not 0 and `maxOccurs` only when bounded; an element particle names
its `namespace` only when it is not its holder's. A valid schema's content models are deterministic (Unique Particle
Attribution), so for a prefix of the children each end position is reached one way: the first way found is kept.
"""
from collections import deque
from typing import Any

Child = tuple[str, str]  # local name, namespace URI ('' for none)
Particle = dict[str, Any]
# the particles holding the children consumed so far, as a rope: concatenation is O(1), so a content model holding
# tens of thousands of children (an OPC UA node set) is matched in linear time; flattened once, at the end
Held = tuple[()] | tuple[Particle] | tuple['Held', 'Held']
NOTHING: Held = ()


def match(model: Particle | None, children: list[Child], *, holder: str, empty_choice_is_empty: bool = False) -> list[Particle] | None:
    """The particle holding each child, in order, when `model` admits `children`; None when it does not. No model
    admits no child (empty or simple content). A choice with no particle (a memberless abstract head's) admits
    nothing; `empty_choice_is_empty` reads it as libxml2 does, as admitting the empty list (a known libxml2 fault)."""
    if model is None:
        return [] if not children else None
    held = _Matcher(children=children, holder=holder, empty_choice_is_empty=empty_choice_is_empty).ends(model, 0).get(len(children))
    return _flat(held) if held is not None else None


def viable_prefix(model: Particle | None, children: list[Child], *, holder: str, empty_choice_is_empty: bool = False) -> list[Particle]:
    """The particles holding the longest prefix of `children` some admitted list starts with: the children a
    validator reading them one by one (libxml2) assesses before the first one the model refuses. A prefix of a
    viable prefix is viable: the longest is found by bisection."""
    if model is None:
        return []
    best: Held = NOTHING
    low, high = 0, len(children)
    while low <= high:
        length = (low + high) // 2
        matcher = _Matcher(children=children[:length], holder=holder, open_end=True, empty_choice_is_empty=empty_choice_is_empty)
        held = matcher.ends(model, 0).get(length)
        if held is None:
            high = length - 1
        else:
            best, low = held, length + 1
    return _flat(best)


def wildcard_admits(wildcard: dict[str, Any], namespace: str) -> bool:
    """Whether a wildcard (`namespace` listed, or `notNamespace` excluded) admits an item in `namespace`."""
    if 'namespace' in wildcard:
        return namespace in wildcard['namespace']
    return namespace not in wildcard.get('notNamespace', [])


class _Matcher:
    def __init__(self, *, children: list[Child], holder: str, open_end: bool = False, empty_choice_is_empty: bool = False):
        self.children = children
        self.holder = holder
        self.empty_choice_is_empty = empty_choice_is_empty
        # past the last child, any particle may match a child still to come: the list read as a prefix
        self.open_end = open_end
        self.memo: dict[tuple[int, int], dict[int, Held]] = {}

    def ends(self, particle: Particle, start: int) -> dict[int, Held]:
        """Where the particle, with its occurrences, can end when it starts at `start`, and the particles holding
        the children it consumed."""
        key = (id(particle), start)
        if key not in self.memo:
            self.memo[key] = self._occurrences(particle, start)
        return self.memo[key]

    def _occurrences(self, particle: Particle, start: int) -> dict[int, Held]:
        low, high = particle.get('minOccurs', 0), particle.get('maxOccurs')
        result: dict[int, Held] = {}
        # (position, occurrences counted) - counted up to `low` only when unbounded: beyond it every count is alike
        states: dict[tuple[int, int], Held] = {(start, 0): NOTHING}
        pending = deque([(start, 0)])
        while pending:
            position, count = pending.popleft()
            held = states[(position, count)]
            if count >= low:
                result.setdefault(position, held)
            if high is not None and count >= high:
                continue
            for end, more in self._once(particle, position).items():
                # an occurrence consuming nothing only helps reach the minimum
                if end == position and count >= low:
                    continue
                following = count + 1 if high is not None else min(count + 1, low)
                state = (end, following)
                if state not in states:
                    states[state] = _joined(held, more)
                    pending.append(state)
        return result

    def _once(self, particle: Particle, position: int) -> dict[int, Held]:
        """One occurrence of the particle from `position`."""
        kind = particle['kind']
        if self.open_end and position == len(self.children) and kind in ('element', 'any'):
            return {position: NOTHING}
        if kind == 'element':
            child = self.children[position] if position < len(self.children) else None
            namespace = particle.get('namespace', self.holder)
            return {position + 1: (particle,)} if child == (particle['name'], namespace) else {}
        if kind == 'any':
            child = self.children[position] if position < len(self.children) else None
            return {position + 1: (particle,)} if child is not None and wildcard_admits(particle, child[1]) else {}
        if kind == 'sequence':
            reached: dict[int, Held] = {position: NOTHING}
            for nested in particle['particles']:
                following: dict[int, Held] = {}
                for start, held in reached.items():
                    for end, more in self.ends(nested, start).items():
                        following.setdefault(end, _joined(held, more))
                reached = following
            return reached
        if kind == 'choice':
            if not particle['particles'] and self.empty_choice_is_empty:
                return {position: NOTHING}
            reached = {}
            for nested in particle['particles']:
                for end, held in self.ends(nested, position).items():
                    reached.setdefault(end, held)
            return reached
        if kind == 'all':
            return self._all(particle['particles'], position)
        raise ValueError(f'a particle of an unknown kind: {kind}')

    def _all(self, particles: list[Particle], position: int) -> dict[int, Held]:
        """An `all` group: each element particle at most once, in any order; those with `minOccurs` required."""
        required = frozenset(index for index, nested in enumerate(particles) if nested.get('minOccurs', 0) > 0)
        reached: dict[int, Held] = {}
        states: dict[tuple[int, frozenset[int]], Held] = {(position, frozenset()): NOTHING}
        pending = deque([(position, frozenset())])
        while pending:
            at, used = pending.popleft()
            held = states[(at, used)]
            if self.open_end and at == len(self.children):
                # the children read, what is left may still come: the group can end here (the phantom children would
                # otherwise be matched by every subset of what is left, exponential in a wide group, a pom's thirty)
                reached.setdefault(at, held)
                continue
            if required <= used:
                reached.setdefault(at, held)
            for index, nested in enumerate(particles):
                if index in used:
                    continue
                for end, more in self._once(nested, at).items():
                    state = (end, used | {index})
                    if state not in states:
                        states[state] = _joined(held, more)
                        pending.append(state)
        return reached


def _joined(first: Held, second: Held) -> Held:
    if not first:
        return second
    if not second:
        return first
    return (first, second)


def _flat(held: Held) -> list[Particle]:
    """The rope's particles in order (iteratively: a rope of a long list is deep)."""
    found: list[Particle] = []
    pending = [held]
    while pending:
        node = pending.pop()
        if len(node) == 2:
            pending += [node[1], node[0]]
        elif node:
            found.append(node[0])
    return found
