"""Tests for emitter ts_helpers and output files."""

import pytest
from pathlib import Path

from generate.emitters.ts_helpers import sparse, ts_string, ts_string_array, ts_key, ts_namespace, ts_facets
from generate.emitters.definition import emit_definition
from generate.emitters.constants import emit_constants
from generate.emitters.types import emit_types
from generate.ir import (
    AttributeDef, ChildDef, ElementDef, Facets, IdentityConstraint, Namespace, TextContent,
)


class TestSparse:
    def test_drops_defaults(self):
        assert sparse({'a': None, 'b': False, 'c': [], 'd': 0, 'e': {}}) == {}

    def test_keeps_values(self):
        assert sparse({'a': 1, 'b': 'x', 'c': True, 'd': [1]}) == {
            'a': 1, 'b': 'x', 'c': True, 'd': [1],
        }


class TestTsString:
    def test_basic(self):
        assert ts_string('hello') == '"hello"'

    def test_quotes(self):
        result = ts_string('say "hi"')
        assert '\\"' in result


class TestTsStringArray:
    def test_empty(self):
        assert ts_string_array([]) == '[]'

    def test_values(self):
        result = ts_string_array(['a', 'b'])
        assert '"a"' in result
        assert '"b"' in result


class TestTsKey:
    def test_simple(self):
        assert ts_key('name') == 'name'

    def test_colon(self):
        result = ts_key('eIEC61850-6-100:version')
        assert result.startswith('"')


class TestTsNamespace:
    def test_basic(self):
        result = ts_namespace(Namespace(prefix='scl', uri='http://scl.example'))
        assert 'scl' in result
        assert 'http://scl.example' in result


class TestTsFacets:
    def test_empty(self):
        assert ts_facets(None) == 'undefined'
        assert ts_facets(Facets()) == 'undefined'

    def test_with_values(self):
        f = Facets(min_length=1, white_space='replace')
        result = ts_facets(f)
        assert 'minLength' in result
        assert 'whiteSpace' in result


class TestEmitDefinition:
    def test_writes_file(self, tmp_path):
        elements = {
            'Root': ElementDef(
                tag='Root',
                namespace=Namespace(prefix='', uri='http://test'),
                parents=[],
                attr_sequence=['name'],
                attributes={'name': AttributeDef(required=True)},
                child_sequence=['Child'],
                children={'Child': ChildDef(max_occurs=1)},
            ),
            'Child': ElementDef(
                tag='Child',
                namespace=Namespace(prefix='', uri='http://test'),
                parents=['Root'],
                attr_sequence=[],
                attributes={},
                child_sequence=[],
                children={},
            ),
        }
        out = tmp_path / 'definition.generated.ts'
        emit_definition(elements, out)
        content = out.read_text()
        assert 'DEFINITION' in content
        assert 'Root' in content
        assert 'Child' in content
        assert 'as const' in content


class TestEmitConstants:
    def test_writes_file(self, tmp_path):
        elements = {
            'A': ElementDef(
                tag='A',
                namespace=Namespace(prefix='', uri=''),
                parents=[],
                attr_sequence=['x'],
                attributes={'x': AttributeDef()},
                child_sequence=['B'],
                children={'B': ChildDef()},
            ),
            'B': ElementDef(
                tag='B',
                namespace=Namespace(prefix='', uri=''),
                parents=['A'],
            ),
        }
        out = tmp_path / 'constants.generated.ts'
        emit_constants(
            elements,
            descendants={'A': ['B'], 'B': []},
            ancestors={'A': [], 'B': ['A']},
            root_element='A',
            singleton_elements=['A', 'B'],
            out=out,
        )
        content = out.read_text()
        assert 'ELEMENT_NAMES' in content
        assert 'ROOT_ELEMENT' in content
        assert 'SINGLETON_ELEMENTS' in content
        assert 'ATTRIBUTES' in content
        assert 'REQUIRED_ATTRIBUTES' in content
        assert "'A'" in content


class TestEmitTypes:
    def test_writes_file(self, tmp_path):
        elements = {
            'Root': ElementDef(
                tag='Root',
                namespace=Namespace(prefix='', uri=''),
                attr_sequence=['name', 'eIEC:ver'],
                attributes={
                    'name': AttributeDef(required=True, facets=Facets(enumeration=['a', 'b'])),
                    'eIEC:ver': AttributeDef(fixed='2.0', namespace=Namespace(prefix='eIEC', uri='http://iec')),
                },
            ),
        }
        out = tmp_path / 'types.generated.ts'
        emit_types(elements, out)
        content = out.read_text()
        assert 'AttributesRoot' in content
        assert "'a' | 'b'" in content
        assert 'eIEC:ver' in content
        assert 'AvailableElement' in content
        assert 'AttributesOf' in content
        assert 'RequiredAttributeNames' in content
