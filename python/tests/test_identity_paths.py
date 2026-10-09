"""The path grammar's refusals, on the parser itself: a schema library that loads a schema has already refused these;
the parser refuses them too rather than guess."""
import pytest
import xmlschema
from lxml import etree

from generate.errors import SchemaNotRepresentable
from generate.model.identity_paths import parse_field, parse_selector

NAMESPACES = {'t': 'urn:t'}


@pytest.mark.parametrize(
    ('selector', 'named'),
    [
        pytest.param('t:A t:B', 't:A t:B', id='two steps without a slash -> refused'),
        pytest.param('t:A/@n', 'not attributes', id='a selector ending at an attribute -> refused'),
        pytest.param('x:A', 'unbound prefix x', id='a prefix bound nowhere -> refused'),
        pytest.param('t:A|', 'empty alternative', id='an empty alternative -> refused'),
        pytest.param('t:1A', 'not an identity constraint path', id='a name starting with a digit -> refused'),
        pytest.param('t:A//t:B', 't:A//t:B', id='// inside a path -> refused, only a leading .// is allowed'),
        pytest.param('t:A$', 'not an identity constraint path', id='a character outside the grammar -> refused, never skipped'),
    ],
)
def test_a_selector_outside_the_grammar_is_refused(selector: str, named: str) -> None:
    with pytest.raises(SchemaNotRepresentable, match=named):
        parse_selector(selector, namespaces=NAMESPACES)


def test_a_field_with_a_step_after_its_attribute_is_refused() -> None:
    with pytest.raises(SchemaNotRepresentable, match='@n/t:B'):
        parse_field('@n/t:B', namespaces=NAMESPACES)


# Every form of the XSD 1.0 path grammar, and the ways out of it: the parser accepts exactly what libxml2 loads.
# (The 2 476 paths of the corpora were compared the same way when the parser was written; tier 1 runs them again.)
SELECTORS = {
    'a step': 't:A',
    'two steps': 't:A/t:B',
    'a union': 't:A|t:B',
    'a union with spaces': ' t:A | t:B ',
    'every step deep': './/t:A',
    'one alternative deep': './/t:A|t:B',
    'the element itself': '.',
    'a dot step': './t:A',
    'a dot inside': 't:A/./t:B',
    'the child axis': 'child::t:A',
    'the child axis with spaces': 'child :: t:A',
    'any name': '*',
    'any name in a namespace': 't:*',
    'an unprefixed name': 'A',
    'deep then the element itself': './/.',
    'spaces between dot and slashes': '. // t:A',
    'two steps without a slash': 't:A t:B',
    'an attribute': 't:A/@n',
    'an unbound prefix': 'x:A',
    'an empty alternative': 't:A|',
    'a name starting with a digit': 't:1A',
    'slashes inside': 't:A//t:B',
    'a leading slash': '/t:A',
    'leading slashes without a dot': '//t:A',
    'a parent step': '..',
    'a predicate': 't:A[1]',
    'a function': 'text()',
    'the descendant axis': 'descendant::t:A',
    'a character outside the grammar': 't:A$',
    'an empty path': '',
    'a trailing slash': 't:A/',
}
FIELDS = {
    'an attribute': '@n',
    'an attribute in a namespace': '@t:n',
    'any attribute': '@*',
    'any attribute of a namespace': '@t:*',
    'the attribute axis': 'attribute::n',
    'a step then an attribute': 't:A/@n',
    'deep then an attribute': './/@n',
    'the element value': '.',
    'a child value': 't:A',
    'a union of attributes': '@n|@m',
    'spaces after the at sign': '@ n',
    'a step after an attribute': '@n/t:B',
    'an attribute then a union with a step after one': '@n|@m/t:B',
    'two attributes': '@n/@m',
    'an empty field': '',
    'an at sign alone': '@',
    'a step and a trailing slash': 't:A/',
}


def _schema_text(selector: str, field: str) -> str:
    def attribute(value: str) -> str:
        return value.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')

    return (
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:t="urn:t" targetNamespace="urn:t" '
        'elementFormDefault="qualified"><xs:element name="R"><xs:complexType><xs:sequence>'
        '<xs:element name="A" maxOccurs="unbounded"><xs:complexType><xs:attribute name="n"/></xs:complexType></xs:element>'
        '</xs:sequence></xs:complexType>'
        f'<xs:unique name="u"><xs:selector xpath="{attribute(selector)}"/><xs:field xpath="{attribute(field)}"/></xs:unique>'
        '</xs:element></xs:schema>'
    )


def _libxml2_loads(selector: str, field: str) -> bool:
    try:
        etree.XMLSchema(etree.fromstring(_schema_text(selector, field)))
    except etree.XMLSchemaParseError:
        return False
    return True


def _parses(parse, path: str) -> bool:
    try:
        parse(path, namespaces=NAMESPACES)
    except SchemaNotRepresentable:
        return False
    return True


# where libxml2 loads a path the grammar has no production for - the schema library, a second implementation,
# refuses it with the grammar - and why; a row that stops being a fault fails, so the list only shrinks
KNOWN_LIBXML2_FAULTS = {
    'selector t:A|': 'an empty alternative after the last bar',
    'field @n/t:B': 'a step after an attribute',
    'field @n|@m/t:B': 'a step after an attribute, in one alternative',
    'field @n/@m': 'an attribute after an attribute',
}


def _library_loads(selector: str, field: str) -> bool:
    try:
        xmlschema.XMLSchema10(_schema_text(selector, field))
    except xmlschema.XMLSchemaParseError:
        return False
    return True


def _agrees_with_the_oracles(kind: str, path: str, parsed: bool, selector: str, field: str) -> None:
    if f'{kind} {path}' in KNOWN_LIBXML2_FAULTS:
        assert (parsed, _libxml2_loads(selector, field), _library_loads(selector, field)) == (False, True, False)
    else:
        assert parsed == _libxml2_loads(selector, field)


@pytest.mark.parametrize('path', SELECTORS.values(), ids=SELECTORS.keys())
def test_a_selector_is_parsed_exactly_where_libxml2_loads_it(path: str) -> None:
    _agrees_with_the_oracles('selector', path, _parses(parse_selector, path), path, '@n')


@pytest.mark.parametrize('path', FIELDS.values(), ids=FIELDS.keys())
def test_a_field_is_parsed_exactly_where_libxml2_loads_it(path: str) -> None:
    _agrees_with_the_oracles('field', path, _parses(parse_field, path), 't:A', path)
