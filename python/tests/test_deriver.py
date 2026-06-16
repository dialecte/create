"""Tests for the deriver module."""

import pytest

from generate.deriver import (
    derive_graph,
    derive_identity_fields,
    derive_root_element,
    derive_singleton_elements,
    _extract_attribute_fields,
    _resolve_constraint_targets,
)
from generate.ir import ChildDef, ElementDef, IdentityConstraint, Namespace
from generate.xpath_parser import FieldPath, FieldTarget, SelectorPath, XPathStep


def _make_elem(tag: str, parents: list[str] | None = None, children: dict[str, ChildDef] | None = None) -> ElementDef:
    return ElementDef(
        tag=tag,
        namespace=Namespace(prefix='', uri=''),
        parents=parents or [],
        children=children or {},
    )


@pytest.fixture
def sample_elements():
    """A → B, C; B → D; C → D (D has two parents)."""
    return {
        'A': _make_elem('A', parents=[], children={
            'B': ChildDef(min_occurs=1, max_occurs=1),
            'C': ChildDef(min_occurs=0, max_occurs=1),
        }),
        'B': _make_elem('B', parents=['A'], children={
            'D': ChildDef(min_occurs=0, max_occurs=None),  # unbounded
        }),
        'C': _make_elem('C', parents=['A'], children={
            'D': ChildDef(min_occurs=0, max_occurs=1),
        }),
        'D': _make_elem('D', parents=['B', 'C']),
    }


class TestDeriveGraph:
    def test_descendants(self, sample_elements):
        descendants, _ = derive_graph(sample_elements)
        assert descendants['A'] == ['B', 'C', 'D']
        assert descendants['B'] == ['D']
        assert descendants['C'] == ['D']
        assert descendants['D'] == []

    def test_ancestors(self, sample_elements):
        _, ancestors = derive_graph(sample_elements)
        assert ancestors['D'] == ['A', 'B', 'C']
        assert ancestors['A'] == []
        assert ancestors['B'] == ['A']


class TestDeriveRootElement:
    def test_single_root(self, sample_elements):
        assert derive_root_element(sample_elements) == 'A'

    def test_no_root_raises(self):
        elems = {'X': _make_elem('X', parents=['Y'])}
        with pytest.raises(ValueError, match='Expected exactly 1 root'):
            derive_root_element(elems)

    def test_multiple_roots_raises(self):
        elems = {
            'X': _make_elem('X'),
            'Y': _make_elem('Y'),
        }
        with pytest.raises(ValueError, match='Expected exactly 1 root'):
            derive_root_element(elems)


class TestDeriveSingletonElements:
    def test_singletons(self, sample_elements):
        singletons = derive_singleton_elements(sample_elements, 'A')
        # A = root (no parents, singleton by definition)
        # B = maxOccurs=1 in A → singleton
        # C = maxOccurs=1 in A → singleton
        # D = maxOccurs=None in B (unbounded) → NOT singleton
        assert 'A' in singletons
        assert 'B' in singletons
        assert 'C' in singletons
        assert 'D' not in singletons


# ---------------------------------------------------------------------------
# Helpers for identity-field tests
# ---------------------------------------------------------------------------

def _selector(name: str) -> list[SelectorPath]:
    return [SelectorPath(steps=(XPathStep(kind='name', value=name),))]


def _attr_field(name: str) -> FieldPath:
    return FieldPath(target=FieldTarget(kind='attribute', value=name, is_attribute=True))


def _elem_field(name: str) -> FieldPath:
    return FieldPath(target=FieldTarget(kind='element', value=name, is_attribute=False))


def _unique(name: str, selector_target: str, attr_names: list[str]) -> IdentityConstraint:
    return IdentityConstraint(
        kind='unique',
        name=name,
        selector=_selector(selector_target),
        fields=[_attr_field(a) for a in attr_names],
    )


def _key(name: str, selector_target: str, attr_names: list[str]) -> IdentityConstraint:
    return IdentityConstraint(
        kind='key',
        name=name,
        selector=_selector(selector_target),
        fields=[_attr_field(a) for a in attr_names],
    )


def _keyref(name: str, selector_target: str, attr_names: list[str]) -> IdentityConstraint:
    return IdentityConstraint(
        kind='keyref',
        name=name,
        selector=_selector(selector_target),
        fields=[_attr_field(a) for a in attr_names],
        refer='someKey',
    )


# ---------------------------------------------------------------------------
# _resolve_constraint_targets
# ---------------------------------------------------------------------------

class TestResolveConstraintTargets:
    def test_unique_resolves_target(self):
        elems = {'Child': _make_elem('Child')}
        c = _unique('u1', 'Child', ['a'])
        assert _resolve_constraint_targets(c, elems) == {'Child'}

    def test_keyref_returns_empty(self):
        elems = {'Child': _make_elem('Child')}
        c = _keyref('kr1', 'Child', ['a'])
        assert _resolve_constraint_targets(c, elems) == set()

    def test_unknown_target_ignored(self):
        elems = {'Child': _make_elem('Child')}
        c = _unique('u1', 'Ghost', ['a'])
        assert _resolve_constraint_targets(c, elems) == set()


# ---------------------------------------------------------------------------
# _extract_attribute_fields
# ---------------------------------------------------------------------------

class TestExtractAttributeFields:
    def test_extracts_attribute_names(self):
        c = _unique('u1', 'X', ['alpha', 'beta'])
        assert _extract_attribute_fields(c) == {'alpha', 'beta'}

    def test_skips_element_fields(self):
        c = IdentityConstraint(
            kind='unique', name='u1',
            selector=_selector('X'),
            fields=[_attr_field('a'), _elem_field('child')],
        )
        assert _extract_attribute_fields(c) == {'a'}

    def test_keyref_returns_empty(self):
        c = _keyref('kr1', 'X', ['a', 'b'])
        assert _extract_attribute_fields(c) == set()


# ---------------------------------------------------------------------------
# derive_identity_fields
# ---------------------------------------------------------------------------

class TestDeriveIdentityFields:
    def test_unique_on_parent_assigns_to_child(self):
        """Parent declares unique targeting Child -> fields assigned to Child."""
        elems = {
            'Parent': _make_elem('Parent', children={'Child': ChildDef()}),
            'Child': _make_elem('Child', parents=['Parent']),
        }
        elems['Parent'].constraints = [_unique('u1', 'Child', ['x', 'y'])]
        result = derive_identity_fields(elems)
        assert result['Child'] == ['x', 'y']
        assert 'Parent' not in result

    def test_key_on_parent_assigns_to_child(self):
        elems = {
            'P': _make_elem('P', children={'C': ChildDef()}),
            'C': _make_elem('C', parents=['P']),
        }
        elems['P'].constraints = [_key('k1', 'C', ['id'])]
        assert derive_identity_fields(elems) == {'C': ['id']}

    def test_keyref_ignored(self):
        elems = {
            'P': _make_elem('P', children={'C': ChildDef()}),
            'C': _make_elem('C', parents=['P']),
        }
        elems['P'].constraints = [_keyref('kr1', 'C', ['ref'])]
        assert derive_identity_fields(elems) == {}

    def test_multiple_parents_union_fields(self):
        """Two parents each declare a unique on same child -> union of fields."""
        elems = {
            'P1': _make_elem('P1', children={'C': ChildDef()}),
            'P2': _make_elem('P2', children={'C': ChildDef()}),
            'C': _make_elem('C', parents=['P1', 'P2']),
        }
        elems['P1'].constraints = [_unique('u1', 'C', ['a', 'b'])]
        elems['P2'].constraints = [_unique('u2', 'C', ['b', 'c'])]
        assert derive_identity_fields(elems) == {'C': ['a', 'b', 'c']}

    def test_no_constraints_returns_empty(self):
        elems = {
            'P': _make_elem('P', children={'C': ChildDef()}),
            'C': _make_elem('C', parents=['P']),
        }
        assert derive_identity_fields(elems) == {}

    def test_result_sorted(self):
        elems = {
            'P': _make_elem('P', children={'C': ChildDef()}),
            'C': _make_elem('C', parents=['P']),
        }
        elems['P'].constraints = [_unique('u1', 'C', ['z', 'a', 'm'])]
        assert derive_identity_fields(elems) == {'C': ['a', 'm', 'z']}
