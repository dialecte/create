"""Tests for globals.py: load_attr_mapping and inject_mapped_attributes."""
import json
import tempfile
from pathlib import Path

from generate.globals import inject_mapped_attributes, load_attr_mapping
from generate.ir import AttributeDef, ElementDef, Namespace

NS = Namespace(prefix='scl', uri='http://www.iec.ch/61850/2019/SCL')
EXT_NS_URI = 'http://www.iec.ch/61850/2019/SCL/6-100'


def _elem(tag: str, attrs: dict[str, AttributeDef] | None = None) -> ElementDef:
    attrs = attrs or {}
    return ElementDef(
        tag=tag,
        namespace=NS,
        attr_sequence=sorted(attrs.keys()),
        attributes=dict(attrs),
    )


def _attr(fixed: str | None = None) -> AttributeDef:
    return AttributeDef(required=False, fixed=fixed)


# --- load_attr_mapping ---

def test_load_attr_mapping_reads_json():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'attribute-mapping.json'
        p.write_text(json.dumps({'SCL': {'ext:version': EXT_NS_URI}}))
        result = load_attr_mapping(Path(d) / 'schema.xsd')
    assert result == {'SCL': {'ext:version': EXT_NS_URI}}


def test_load_attr_mapping_missing_returns_empty():
    with tempfile.TemporaryDirectory() as d:
        result = load_attr_mapping(Path(d) / 'schema.xsd')
    assert result == {}


# --- inject_mapped_attributes ---

class _FakeSchema:
    """Minimal schema mock exposing schema.maps.attributes as a Clark-keyed dict."""

    def __init__(self, global_attrs: dict):
        class _Maps:
            def __init__(self, attrs):
                self.attributes = attrs
        self.maps = _Maps(global_attrs)


class _FakeXsdAttr:
    def __init__(self, clark_name: str, fixed: str | None = None):
        self.name = clark_name
        self.fixed = fixed
        self.default = None
        self.use = 'optional'
        self.type = None

        class _FakeSchema:
            namespaces = {'eIEC61850-6-100': EXT_NS_URI}
        self.schema = _FakeSchema()


def test_inject_mapped_attributes_injects_found_attr():
    xsd_attr = _FakeXsdAttr(f'{{{EXT_NS_URI}}}version', fixed='2019')
    schema = _FakeSchema({f'{{{EXT_NS_URI}}}version': xsd_attr})

    elem = _elem('SCL', {'version': _attr()})
    elements = {'SCL': elem}
    mapping = {'SCL': {f'eIEC61850-6-100:version': EXT_NS_URI}}

    count = inject_mapped_attributes(schema, elements, mapping)

    assert count == 1
    assert 'eIEC61850-6-100:version' in elem.attributes
    assert elem.attributes['eIEC61850-6-100:version'].fixed == '2019'
    assert 'eIEC61850-6-100:version' in elem.attr_sequence
    assert elem.attr_sequence == sorted(elem.attr_sequence)


def test_inject_mapped_attributes_skips_missing_clark_name():
    schema = _FakeSchema({})  # attr not in schema
    elem = _elem('SCL')
    elements = {'SCL': elem}
    mapping = {'SCL': {'eIEC61850-6-100:version': EXT_NS_URI}}

    count = inject_mapped_attributes(schema, elements, mapping)

    assert count == 0
    assert 'eIEC61850-6-100:version' not in elem.attributes


def test_inject_mapped_attributes_skips_missing_element():
    xsd_attr = _FakeXsdAttr(f'{{{EXT_NS_URI}}}version')
    schema = _FakeSchema({f'{{{EXT_NS_URI}}}version': xsd_attr})
    elements = {}  # SCL not in elements
    mapping = {'SCL': {'eIEC61850-6-100:version': EXT_NS_URI}}

    count = inject_mapped_attributes(schema, elements, mapping)

    assert count == 0


def test_inject_mapped_attributes_idempotent():
    xsd_attr = _FakeXsdAttr(f'{{{EXT_NS_URI}}}version', fixed='2019')
    schema = _FakeSchema({f'{{{EXT_NS_URI}}}version': xsd_attr})
    existing = AttributeDef(required=False, fixed='2019', namespace=Namespace(prefix='eIEC61850-6-100', uri=EXT_NS_URI))
    elem = _elem('SCL', {'eIEC61850-6-100:version': existing})
    elements = {'SCL': elem}
    mapping = {'SCL': {'eIEC61850-6-100:version': EXT_NS_URI}}

    count = inject_mapped_attributes(schema, elements, mapping)

    assert count == 0  # already present, not re-injected
    assert elem.attr_sequence.count('eIEC61850-6-100:version') == 1  # no duplicate
