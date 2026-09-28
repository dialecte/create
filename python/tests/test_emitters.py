"""Tests for emitter ts_helpers and output files."""

import pytest
from pathlib import Path

from generate.emitters.ts_helpers import (
    sparse, ts_string, ts_string_array, ts_key, ts_namespace, ts_facets, ts_type_names,
)
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
        assert ts_string('hello') == "'hello'"

    def test_quotes(self):
        result = ts_string("it's")
        assert result == "'it\\'s'"

    def test_control_characters_are_written_as_escapes(self):
        assert ts_string('a\nb\tc') == "'a\\nb\\tc'"


class TestTsStringArray:
    def test_empty(self):
        assert ts_string_array([]) == '[]'

    def test_values(self):
        result = ts_string_array(['a', 'b'])
        assert "'a'" in result
        assert "'b'" in result


class TestTsKey:
    def test_simple(self):
        assert ts_key('name') == 'name'

    def test_colon(self):
        result = ts_key('eIEC61850-6-100:version')
        assert result.startswith("'")


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


def _hyphenated_elements():
    """Element names that are not TypeScript identifiers, as XML allows."""
    return {
        'document-definition': ElementDef(
            tag='document-definition',
            namespace=Namespace(prefix='', uri=''),
            parents=[],
            attr_sequence=['name'],
            attributes={'name': AttributeDef(required=True)},
            child_sequence=['boolean-value'],
            children={'boolean-value': ChildDef(max_occurs=1)},
        ),
        'boolean-value': ElementDef(
            tag='boolean-value',
            namespace=Namespace(prefix='', uri=''),
            parents=['document-definition'],
        ),
    }


class TestTsTypeNames:
    def test_identifier_safe_names_are_kept_as_they_are(self):
        assert ts_type_names(['LNode', 'Bay', '_private']) == {
            'LNode': 'LNode', 'Bay': 'Bay', '_private': '_private',
        }

    def test_other_names_become_pascal_case(self):
        assert ts_type_names(['boolean-value', 'uid.pre', 'a b']) == {
            'boolean-value': 'BooleanValue', 'uid.pre': 'UidPre', 'a b': 'AB',
        }

    def test_a_leading_digit_is_guarded(self):
        assert ts_type_names(['3d-view']) == {'3d-view': '_3dView'}

    def test_two_names_never_share_an_identifier(self):
        names = ts_type_names(['BooleanValue', 'boolean-value', 'boolean.value'])

        assert names['BooleanValue'] == 'BooleanValue'
        assert len(set(names.values())) == 3


class TestEmittersWithNamesThatAreNotIdentifiers:
    def test_definition_quotes_element_keys(self, tmp_path):
        out = tmp_path / 'definition.generated.ts'
        emit_definition(_hyphenated_elements(), out)
        content = out.read_text()

        assert "\t'document-definition': {" in content
        assert "\t'boolean-value': {" in content
        assert '\tdocument-definition: {' not in content

    def test_constants_quote_element_keys(self, tmp_path):
        out = tmp_path / 'constants.generated.ts'
        emit_constants(
            _hyphenated_elements(),
            descendants={'document-definition': ['boolean-value'], 'boolean-value': []},
            ancestors={'document-definition': [], 'boolean-value': ['document-definition']},
            root_element='document-definition',
            singleton_elements=['document-definition'],
            out=out,
        )
        content = out.read_text()

        assert "\t'boolean-value': {} as AttributesOf<'boolean-value'>," in content
        assert "\t'document-definition': {" in content
        assert "export const ROOT_ELEMENT = 'document-definition' as const" in content

    def test_types_use_valid_identifiers_and_quoted_keys(self, tmp_path):
        out = tmp_path / 'types.generated.ts'
        emit_types(_hyphenated_elements(), out)
        content = out.read_text()

        assert 'export type AttributesBooleanValue = {' in content
        assert 'export type AttributesDocumentDefinition = {' in content
        assert "\t'boolean-value': AttributesBooleanValue" in content
        assert 'Attributesboolean-value' not in content

    def test_identifier_safe_names_are_emitted_unquoted(self, tmp_path):
        elements = {
            'Bay': ElementDef(tag='Bay', namespace=Namespace(prefix='', uri=''), parents=[]),
        }
        types_out = tmp_path / 'types.generated.ts'
        definition_out = tmp_path / 'definition.generated.ts'
        emit_types(elements, types_out)
        emit_definition(elements, definition_out)

        assert 'export type AttributesBay = {' in types_out.read_text()
        assert '\tBay: AttributesBay' in types_out.read_text()
        assert '\tBay: {' in definition_out.read_text()


class TestValuesThatNeedEscaping:
    def _elements(self, attribute: AttributeDef):
        return {
            'Root': ElementDef(
                tag='Root', namespace=Namespace(prefix='', uri=''), parents=[],
                attr_sequence=['kind'], attributes={'kind': attribute},
            ),
        }

    def test_an_enumeration_value_holding_a_quote_is_escaped(self, tmp_path):
        out = tmp_path / 'types.generated.ts'
        emit_types(self._elements(AttributeDef(facets=Facets(enumeration=["don't", 'back\\slash']))), out)

        assert "kind?: 'don\\'t' | 'back\\\\slash' | (string & {})" in out.read_text()

    def test_a_fixed_value_holding_a_quote_is_escaped(self, tmp_path):
        out = tmp_path / 'types.generated.ts'
        emit_types(self._elements(AttributeDef(fixed="it's")), out)

        assert "kind?: 'it\\'s'" in out.read_text()


class TestEmptyObjects:
    def test_an_element_without_attributes_or_children_gets_empty_literals_on_one_line(self, tmp_path):
        out = tmp_path / 'definition.generated.ts'
        emit_definition(
            {'Bay': ElementDef(tag='Bay', namespace=Namespace(prefix='', uri=''), parents=[])}, out,
        )
        content = out.read_text()

        assert 'details: {},' in content
        assert 'details: {\n' not in content


class TestHomonymsInTheDefinition:
    def test_no_homonyms_list_is_written_the_edges_say_it(self, tmp_path):
        out = tmp_path / 'definition.generated.ts'
        declared = ElementDef(tag='variable', namespace=Namespace(prefix='', uri=''), parents=['coil'])
        elements = {
            'coil': ElementDef(
                tag='coil', namespace=Namespace(prefix='', uri=''), parents=[],
                child_sequence=['variable'], children={'variable': ChildDef()},
            ),
            'variable': ElementDef(
                tag='variable', namespace=Namespace(prefix='', uri=''), parents=['struct', 'coil'],
                definitions_by_parent={'coil': declared},
            ),
        }
        emit_definition(elements, out)

        content = out.read_text()
        coil = content[content.index('\tcoil: {'):content.index('\tvariable: {')]
        assert 'attributes: {' in coil  # the declaration under coil, on its edge
        assert 'definition' not in content
        assert 'homonyms' not in content
