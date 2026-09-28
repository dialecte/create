"""Tests for the deriver module."""

import pytest

from generate.deriver import (
    derive_graph,
    derive_identity_fields,
    derive_root_element,
    derive_singleton_elements,
    strip_canonical_child_namespaces,
    _extract_attribute_fields,
    _resolve_constraint_targets,
)
from generate.ir import AttributeDef, ChildDef, ElementDef, IdentityConstraint, Namespace
from generate.xpath_parser import FieldPath, FieldTarget, SelectorPath, XPathStep


def _make_elem(
    tag: str,
    parents: list[str] | None = None,
    children: dict[str, ChildDef] | None = None,
    attr_sequence: list[str] | None = None,
    attributes: dict[str, AttributeDef] | None = None,
) -> ElementDef:
    return ElementDef(
        tag=tag,
        namespace=Namespace(prefix='', uri=''),
        parents=parents or [],
        children=children or {},
        attr_sequence=attr_sequence or [],
        attributes=attributes or {},
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
        with pytest.raises(ValueError, match='No root candidate'):
            derive_root_element(elems)

    def test_multiple_roots_raises(self):
        elems = {
            'X': _make_elem('X'),
            'Y': _make_elem('Y'),
        }
        with pytest.raises(ValueError, match='Several elements can start a document.*X, Y'):
            derive_root_element(elems)


class TestStripCanonicalChildNamespaces:
    def test_nulls_matching_edge_keeps_override(self):
        # `Labels` is canonically SCL but is re-declared in 6-100 under `DAS`.
        scl = Namespace(prefix='', uri='http://www.iec.ch/61850/2003/SCL')
        ext = Namespace(prefix='eIEC61850-6-100', uri='http://www.iec.ch/61850/2019/SCL/6-100')
        elements = {
            'Labels': ElementDef(tag='Labels', namespace=scl, parents=['Substation', 'DAS']),
            'Substation': ElementDef(
                tag='Substation', namespace=scl,
                children={'Labels': ChildDef(namespace=scl)},
            ),
            'DAS': ElementDef(
                tag='DAS', namespace=ext,
                children={'Labels': ChildDef(namespace=ext)},
            ),
        }

        strip_canonical_child_namespaces(elements)

        # Edge matching the child's canonical namespace → dropped (core falls back).
        assert elements['Substation'].children['Labels'].namespace is None
        # Edge overriding the canonical namespace → kept (emitted as the sparse override).
        assert elements['DAS'].children['Labels'].namespace == ext

    def test_unknown_child_element_left_untouched(self):
        ext = Namespace(prefix='x', uri='urn:x')
        elements = {
            'P': ElementDef(
                tag='P', namespace=Namespace(prefix='', uri=''),
                children={'Ghost': ChildDef(namespace=ext)},
            ),
        }

        strip_canonical_child_namespaces(elements)

        assert elements['P'].children['Ghost'].namespace == ext


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


def _path(*names: str) -> SelectorPath:
    return SelectorPath(
        steps=tuple(
            XPathStep(kind='wildcard') if name == '*' else XPathStep(kind='name', value=name)
            for name in names
        ),
    )


def _wildcard_path() -> SelectorPath:
    return SelectorPath(steps=(XPathStep(kind='wildcard'),))


def _constraint(kind: str, selector: list[SelectorPath], fields: list[FieldPath]) -> IdentityConstraint:
    return IdentityConstraint(kind=kind, name=f'{kind}-1', selector=selector, fields=fields)


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

    # A selector names the elements under constraint: the ones its path ENDS at. The steps before
    # are the route to them, whatever the schema.
    def test_multi_step_selector_targets_last_step_only(self):
        elems = {n: _make_elem(n) for n in 'ABC'}
        c = _constraint('key', [_path('A', 'B', 'C')], [_attr_field('x')])
        assert _resolve_constraint_targets(c, elems) == {'C'}

    def test_union_selector_targets_the_last_step_of_each_alternative(self):
        elems = {n: _make_elem(n) for n in 'ABDE'}
        c = _constraint('unique', [_path('A', 'B'), _path('D', 'E')], [_attr_field('x')])
        assert _resolve_constraint_targets(c, elems) == {'B', 'E'}

    def test_self_selector_targets_the_declaring_element(self):
        elems = {n: _make_elem(n) for n in 'PC'}
        c = _constraint('unique', [SelectorPath(steps=(XPathStep(kind='self'),))], [_attr_field('x')])
        assert _resolve_constraint_targets(c, elems, declaring='P') == {'P'}

    # A wildcard selects whatever the definition allows there: the children of the context element
    # that can carry the field, since an element without the attribute is not identified by it.
    def test_wildcard_targets_the_declaring_elements_children_that_carry_the_field(self):
        elems = {
            'P': _make_elem('P', children={'X': ChildDef(), 'Y': ChildDef(), 'Z': ChildDef()}),
            'X': _make_elem('X', parents=['P']),
            'Y': _make_elem('Y', parents=['P']),
            'Z': _make_elem('Z', parents=['P']),
        }
        for name in ('X', 'Y'):
            elems[name].attr_sequence = ['name']
            elems[name].attributes = {'name': AttributeDef(required=True)}
        c = _constraint('unique', [_wildcard_path()], [_attr_field('name')])
        assert _resolve_constraint_targets(c, elems, declaring='P') == {'X', 'Y'}

    # An element that MAY carry the field is not identified by it: without the attribute it
    # would have no identity. Only a wildcard needs this rule; a named selector says which elements.
    def test_wildcard_skips_a_child_that_only_may_carry_the_field(self):
        elems = {
            'P': _make_elem('P', children={'X': ChildDef(), 'Y': ChildDef()}),
            'X': _make_elem('X', parents=['P'], attr_sequence=['uuid'], attributes={'uuid': AttributeDef(required=True)}),
            'Y': _make_elem('Y', parents=['P'], attr_sequence=['uuid'], attributes={'uuid': AttributeDef()}),
        }
        c = _constraint('unique', [_wildcard_path()], [_attr_field('uuid')])
        assert _resolve_constraint_targets(c, elems, declaring='P') == {'X'}

    def test_wildcard_under_an_element_without_children_targets_nothing(self):
        elems = {'P': _make_elem('P')}
        c = _constraint('unique', [_wildcard_path()], [_attr_field('name')])
        assert _resolve_constraint_targets(c, elems, declaring='P') == set()

    def test_wildcard_after_a_named_step_targets_that_elements_children(self):
        elems = {
            'P': _make_elem('P', children={'A': ChildDef()}),
            'A': _make_elem('A', parents=['P'], children={'B': ChildDef()}),
            'B': _make_elem('B', parents=['A'], attr_sequence=['id'], attributes={'id': AttributeDef(required=True)}),
        }
        c = _constraint('key', [_path('A', '*')], [_attr_field('id')])
        assert _resolve_constraint_targets(c, elems, declaring='P') == {'B'}

    def test_namespace_wildcard_keeps_the_children_of_that_prefix_only(self):
        elems = {
            'P': _make_elem('P', children={'X': ChildDef(), 'Ext': ChildDef()}),
            'X': _make_elem('X', parents=['P'], attr_sequence=['name'], attributes={'name': AttributeDef(required=True)}),
            'Ext': ElementDef(
                tag='Ext', namespace=Namespace(prefix='ext', uri='urn:ext'), parents=['P'],
                attr_sequence=['name'], attributes={'name': AttributeDef(required=True)},
            ),
        }
        c = _constraint(
            'unique',
            [SelectorPath(steps=(XPathStep(kind='ns-wildcard', value='ext'),))],
            [_attr_field('name')],
        )
        assert _resolve_constraint_targets(c, elems, declaring='P') == {'Ext'}

    def test_deep_wildcard_targets_every_descendant_that_carries_the_field(self):
        elems = {
            'P': _make_elem('P', children={'A': ChildDef()}),
            'A': _make_elem('A', parents=['P'], children={'B': ChildDef()}, attr_sequence=['id'], attributes={'id': AttributeDef(required=True)}),
            'B': _make_elem('B', parents=['A'], attr_sequence=['id'], attributes={'id': AttributeDef(required=True)}),
        }
        c = _constraint('unique', [SelectorPath(deep=True, steps=(XPathStep(kind='wildcard'),))], [_attr_field('id')])
        assert _resolve_constraint_targets(c, elems, declaring='P') == {'A', 'B'}


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

    # A field is read relative to the selected element: `child/@x` is an attribute of its child,
    # not one of its own.
    def test_skips_an_attribute_reached_through_a_step(self):
        through_child = FieldPath(
            steps=(XPathStep(kind='name', value='child'),),
            target=FieldTarget(kind='attribute', value='x', is_attribute=True),
        )
        c = _constraint('unique', _selector('X'), [_attr_field('a'), through_child])
        assert _extract_attribute_fields(c) == {'a'}


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

    def test_intermediate_steps_of_a_selector_get_no_fields(self):
        elems = {
            'P': _make_elem('P', children={'A': ChildDef()}),
            'A': _make_elem('A', parents=['P'], children={'B': ChildDef()}),
            'B': _make_elem('B', parents=['A'], children={'C': ChildDef()}),
            'C': _make_elem('C', parents=['B']),
        }
        elems['P'].constraints = [_constraint('key', [_path('A', 'B', 'C')], [_attr_field('inst')])]
        assert derive_identity_fields(elems) == {'C': ['inst']}

    def test_a_self_selector_identifies_the_declaring_element(self):
        elems = {'P': _make_elem('P')}
        elems['P'].constraints = [
            _constraint('unique', [SelectorPath(steps=(XPathStep(kind='self'),))], [_attr_field('id')]),
        ]
        assert derive_identity_fields(elems) == {'P': ['id']}

    def test_a_wildcard_unique_identifies_each_child_by_the_field_it_carries(self):
        elems = {
            'Bay': _make_elem('Bay', children={'Function': ChildDef(), 'Private': ChildDef()}),
            'Function': _make_elem('Function', parents=['Bay'], attr_sequence=['name'], attributes={'name': AttributeDef(required=True)}),
            'Private': _make_elem('Private', parents=['Bay']),
        }
        elems['Bay'].constraints = [_constraint('unique', [_wildcard_path()], [_attr_field('name')])]
        assert derive_identity_fields(elems) == {'Function': ['name']}

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
