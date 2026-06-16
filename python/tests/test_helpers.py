"""Tests for generate.helpers."""

import pytest

from generate.helpers import get_facet_value, local_name, namespace_uri, tokenize_xpath, xsd_pattern_to_js


class TestLocalName:
    def test_clark_notation(self):
        assert local_name('{http://example.com}local') == 'local'

    def test_prefixed(self):
        assert local_name('xs:element') == 'element'

    def test_plain(self):
        assert local_name('name') == 'name'

    def test_empty(self):
        assert local_name('') == ''


class TestNamespaceUri:
    def test_clark_notation(self):
        assert namespace_uri('{http://example.com}local') == 'http://example.com'

    def test_no_namespace(self):
        assert namespace_uri('local') is None

    def test_prefixed_no_clark(self):
        assert namespace_uri('xs:element') is None


class TestTokenizeXpath:
    def test_simple_element(self):
        assert tokenize_xpath('LNode') == ['LNode']

    def test_prefixed_element(self):
        assert tokenize_xpath('tNS:LNode') == ['LNode']

    def test_path(self):
        assert tokenize_xpath('Bay/ConductingEquipment') == ['Bay', 'ConductingEquipment']

    def test_relative_path(self):
        assert tokenize_xpath('./SubNetwork') == ['SubNetwork']

    def test_deep_path(self):
        assert tokenize_xpath('.//SubNetwork') == ['SubNetwork']

    def test_empty(self):
        assert tokenize_xpath('') == []


class TestGetFacetValue:
    def test_value_attr(self):
        class FakeFacet:
            value = 42
        assert get_facet_value(FakeFacet()) == 42

    def test_elem_fallback(self):
        from xml.etree.ElementTree import Element
        elem = Element('facet', value='10')

        class FakeFacet:
            pass

        f = FakeFacet()
        f.elem = elem
        assert get_facet_value(f) == 10

    def test_none_when_nothing(self):
        class FakeFacet:
            pass
        assert get_facet_value(FakeFacet()) is None


class TestXsdPatternToJs:
    def test_passthrough_plain_regex(self):
        assert xsd_pattern_to_js('[0-9]+') == '[0-9]+'

    def test_initial_name_char(self):
        assert xsd_pattern_to_js(r'\i\c*') == '[A-Za-z_:][-.:0-9A-Z_a-z]*'

    def test_complement_classes(self):
        assert xsd_pattern_to_js(r'\I') == '[^A-Za-z_:]'
        assert xsd_pattern_to_js(r'\C') == '[^-.:0-9A-Z_a-z]'

    def test_unicode_block_basic_latin(self):
        result = xsd_pattern_to_js(r'[\p{IsBasicLatin}]*')
        assert r'\x00-\x7f' in result
        assert r'\p{' not in result

    def test_unicode_block_latin1_supplement(self):
        result = xsd_pattern_to_js(r'[\p{IsLatin-1Supplement}]*')
        assert r'\x80-\xff' in result

    def test_combined_blocks(self):
        result = xsd_pattern_to_js(r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]*')
        assert r'\x00-\x7f' in result
        assert r'\x80-\xff' in result

    def test_xml_hex_char_ref(self):
        result = xsd_pattern_to_js('&#x41;')
        assert result == 'A'

    def test_xml_decimal_char_ref(self):
        result = xsd_pattern_to_js('&#65;')
        assert result == 'A'

    def test_unknown_block_preserved(self):
        result = xsd_pattern_to_js(r'\p{IsUnknownBlock123}')
        assert r'\p{IsUnknownBlock123}' in result

    def test_uuid_pattern_unchanged(self):
        p = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
        assert xsd_pattern_to_js(p) == p
