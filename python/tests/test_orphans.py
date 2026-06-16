"""Tests for orphan detection and parent injection."""
import json
import tempfile
from pathlib import Path

from generate.ir import ChildDef, ElementDef, Namespace
from generate.orphans import detect_orphans, inject_orphan_parents, load_parent_mapping

NS = Namespace(prefix='', uri='')


def _elem(tag: str, parents: list[str] | None = None, children: dict[str, ChildDef] | None = None) -> ElementDef:
    return ElementDef(tag=tag, namespace=NS, parents=parents or [], children=children or {})


# --- load_parent_mapping ---

def test_load_parent_mapping_reads_json():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'parent-mapping.json'
        p.write_text(json.dumps({'Foo': ['Bar', 'Baz']}))
        entry = Path(d) / 'schema.xsd'
        result = load_parent_mapping(entry)
    assert result == {'Foo': ['Bar', 'Baz']}


def test_load_parent_mapping_missing_returns_empty():
    with tempfile.TemporaryDirectory() as d:
        entry = Path(d) / 'schema.xsd'
        result = load_parent_mapping(entry)
    assert result == {}


# --- detect_orphans ---

def test_detect_orphans_excludes_root():
    elements = {
        'SCL': _elem('SCL'),
        'Orphan': _elem('Orphan'),
        'Child': _elem('Child', parents=['SCL']),
    }
    orphans = detect_orphans(elements, 'SCL')
    assert orphans == ['Orphan']


def test_detect_orphans_empty_when_all_have_parents():
    elements = {
        'Root': _elem('Root'),
        'A': _elem('A', parents=['Root']),
    }
    assert detect_orphans(elements, 'Root') == []


# --- inject_orphan_parents ---

def test_inject_sets_parents_and_children():
    elements = {
        'SCL': _elem('SCL'),
        'Bay': _elem('Bay', parents=['SCL']),
        'Ext': _elem('Ext'),
    }
    mapping = {'Ext': ['SCL', 'Bay']}
    unmapped = inject_orphan_parents(elements, mapping, root_name='SCL')

    assert unmapped == []
    assert elements['Ext'].parents == ['SCL', 'Bay']
    assert 'Ext' in elements['SCL'].children
    assert 'Ext' in elements['Bay'].children
    assert elements['SCL'].children['Ext'].required is False
    assert elements['SCL'].children['Ext'].max_occurs is None
    assert 'Ext' in elements['SCL'].child_sequence
    assert 'Ext' in elements['Bay'].child_sequence


def test_inject_returns_unmapped_orphans():
    elements = {
        'Root': _elem('Root'),
        'Known': _elem('Known'),
        'Unknown': _elem('Unknown'),
    }
    mapping = {'Known': ['Root']}
    unmapped = inject_orphan_parents(elements, mapping, root_name='Root')
    assert unmapped == ['Unknown']


def test_inject_skips_nonexistent_parents():
    elements = {
        'Root': _elem('Root'),
        'Ext': _elem('Ext'),
    }
    mapping = {'Ext': ['Root', 'Ghost']}
    inject_orphan_parents(elements, mapping, root_name='Root')
    assert elements['Ext'].parents == ['Root']


def test_inject_idempotent_on_existing_child():
    existing_child = ChildDef(required=True, min_occurs=1, max_occurs=1)
    elements = {
        'Root': _elem('Root', children={'Ext': existing_child}),
        'Ext': _elem('Ext'),
    }
    mapping = {'Ext': ['Root']}
    inject_orphan_parents(elements, mapping, root_name='Root')
    # Should not overwrite the existing ChildDef
    assert elements['Root'].children['Ext'].required is True
    assert elements['Root'].children['Ext'].max_occurs == 1
