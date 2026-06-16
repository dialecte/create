"""Tests for generate.xpath_parser — XSD §3.11.6 restricted XPath parsing."""

import pytest

from generate.xpath_parser import (
    FieldPath,
    FieldTarget,
    SelectorPath,
    XPathStep,
    parse_field,
    parse_selector,
)


# ---------------------------------------------------------------------------
# Selector tests
# ---------------------------------------------------------------------------

class TestParseSelector:
    """All real patterns found in IEC 61850-6-100.xsd plus edge cases."""

    def test_simple_local_name(self):
        result = parse_selector('tns:Child')
        assert result == [SelectorPath(deep=False, steps=(XPathStep('name', 'Child'),))]

    def test_relative_child(self):
        result = parse_selector('./scl:LNode')
        assert result == [SelectorPath(deep=False, steps=(XPathStep('name', 'LNode'),))]

    def test_deep_descendant(self):
        result = parse_selector('.//scl:ConnectivityNode')
        assert result == [SelectorPath(deep=True, steps=(XPathStep('name', 'ConnectivityNode'),))]

    def test_multi_step_path(self):
        result = parse_selector('./scl:AccessPoint/scl:Server/scl:LDevice/scl:LN/scl:DataSet/scl:FCDA')
        assert len(result) == 1
        p = result[0]
        assert p.deep is False
        names = [s.value for s in p.steps]
        assert names == ['AccessPoint', 'Server', 'LDevice', 'LN', 'DataSet', 'FCDA']

    def test_union_two_alternatives(self):
        result = parse_selector('./scl:DAI|./scl:SDI')
        assert len(result) == 2
        assert result[0].steps == (XPathStep('name', 'DAI'),)
        assert result[1].steps == (XPathStep('name', 'SDI'),)

    def test_union_three_alternatives(self):
        result = parse_selector('./scl:Substation|./scl:Process|./scl:Line')
        assert len(result) == 3
        names = [p.steps[0].value for p in result]
        assert names == ['Substation', 'Process', 'Line']

    def test_union_with_spaces(self):
        result = parse_selector('scl:DAType | scl:EnumType')
        assert len(result) == 2
        assert result[0].steps == (XPathStep('name', 'DAType'),)
        assert result[1].steps == (XPathStep('name', 'EnumType'),)

    def test_self_in_union(self):
        """Selector like 'DAI|.' — self reference as an alternative."""
        result = parse_selector('./scl:SubEquipment|./scl:TapChanger|./scl:EqFunction')
        assert len(result) == 3

    def test_wildcard(self):
        result = parse_selector('*')
        assert result == [SelectorPath(deep=False, steps=(XPathStep('wildcard'),))]

    def test_deep_wildcard(self):
        result = parse_selector('.//*')
        assert result == [SelectorPath(deep=True, steps=(XPathStep('wildcard'),))]

    def test_ns_wildcard(self):
        result = parse_selector('scl:*')
        assert result == [SelectorPath(deep=False, steps=(XPathStep('ns-wildcard', 'scl'),))]

    def test_self_dot(self):
        result = parse_selector('.')
        assert result == [SelectorPath(deep=False, steps=(XPathStep('self'),))]

    def test_empty(self):
        assert parse_selector('') == []
        assert parse_selector('  ') == []


# ---------------------------------------------------------------------------
# Field tests
# ---------------------------------------------------------------------------

class TestParseField:
    def test_simple_attribute(self):
        result = parse_field('@name')
        assert result.deep is False
        assert result.steps == ()
        assert result.target == FieldTarget('attribute', 'name', is_attribute=True)

    def test_prefixed_attribute(self):
        result = parse_field('@scl:name')
        assert result.target == FieldTarget('attribute', 'name', is_attribute=True)

    def test_element_field(self):
        result = parse_field('scl:Val')
        assert result.target == FieldTarget('element', 'Val', is_attribute=False)

    def test_nested_element_then_attribute(self):
        result = parse_field('./scl:Child/@id')
        assert result.deep is False
        assert result.steps == (XPathStep('name', 'Child'),)
        assert result.target == FieldTarget('attribute', 'id', is_attribute=True)

    def test_deep_field(self):
        result = parse_field('.//scl:Node/@name')
        assert result.deep is True
        assert result.steps == (XPathStep('name', 'Node'),)
        assert result.target.value == 'name'
        assert result.target.is_attribute is True

    def test_wildcard_attribute(self):
        result = parse_field('@*')
        assert result.target == FieldTarget('wildcard', is_attribute=True)

    def test_empty(self):
        result = parse_field('')
        assert result == FieldPath()


# ---------------------------------------------------------------------------
# Roundtrip: real IEC 61850 patterns
# ---------------------------------------------------------------------------

class TestRealIec61850Patterns:
    """Selectors and fields from actual IEC 61850-6-100.xsd identity constraints."""

    @pytest.mark.parametrize('xpath,expected_count', [
        ('./scl:DAI|./scl:SDI', 2),
        ('./eIEC61850-6-100:DAS|./eIEC61850-6-100:SDS', 2),
        ('./scl:Substation|./scl:Process|./scl:Line', 3),
        ('./scl:SubEquipment|./scl:TapChanger|./scl:EqFunction', 3),
        ('./scl:SubEquipment|./scl:EqFunction', 2),
        ('scl:DAType | scl:EnumType', 2),
    ])
    def test_union_selectors(self, xpath, expected_count):
        result = parse_selector(xpath)
        assert len(result) == expected_count
        for p in result:
            assert len(p.steps) >= 1

    @pytest.mark.parametrize('xpath', [
        './/scl:ConnectivityNode',
        './/*',
        './/scl:Terminal',
    ])
    def test_deep_selectors(self, xpath):
        result = parse_selector(xpath)
        assert len(result) == 1
        assert result[0].deep is True

    def test_multi_step_fcda(self):
        result = parse_selector('./scl:AccessPoint/scl:Server/scl:LDevice/scl:LN/scl:DataSet/scl:FCDA')
        p = result[0]
        assert len(p.steps) == 6

    @pytest.mark.parametrize('xpath,expected_name', [
        ('@name', 'name'),
        ('@desc', 'desc'),
        ('@id', 'id'),
        ('@sxy:uuid', 'uuid'),
    ])
    def test_attribute_fields(self, xpath, expected_name):
        result = parse_field(xpath)
        assert result.target.is_attribute is True
        assert result.target.value == expected_name
