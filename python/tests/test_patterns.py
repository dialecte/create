"""XSD patterns as JS sources (u flag, unanchored): each rule on its own, every output compiled by node, and the
conversion checked against libxml2 on values sampled from each pattern, mutated, and adversarial characters."""
import json
import random
import shutil
import subprocess
import re
import unicodedata
from functools import cache

import elementpath.regex as elementpath_regex

import pytest
from lxml import etree

from generate.definition import patterns as P
from generate.definition.patterns import pattern_to_js
from generate.errors import SchemaNotRepresentable

NEEDS_NODE = pytest.mark.skipif(shutil.which('node') is None, reason='needs node')

RULES: dict[str, tuple[str, str]] = {
    'plain characters -> as they are': ('abc', 'abc'),
    'a single-character escape outside a class -> plain, escaped only where JS needs it': (r'a\-b\.c\^', r'a-b\.c\^'),
    'anchors -> plain characters': ('^a$', r'\^a\$'),
    'the dot -> every character but CR and LF': ('a.b', r'a[^\n\r]b'),
    'multi-character escapes -> their XSD meaning': (r'\s\S\d\D', r'[\t\n\r ][^\t\n\r ]\p{Nd}\P{Nd}'),
    'word characters -> all but punctuation, separators and others': (r'\w\W', r'[^\p{P}\p{Z}\p{C}][\p{P}\p{Z}\p{C}]'),
    'a group -> not capturing': ('(ab)+|c', '(?:ab)+|c'),
    'quantities -> as written': ('a{2}b{1,}c{0,3}d?', 'a{2}b{1,}c{0,3}d?'),
    'a category -> as it is': (r'\p{Lu}\P{L}', r'\p{Lu}\P{L}'),
    'a block -> its ranges': (r'\p{IsBasicLatin}', r'[\u{0}-\u{7F}]'),
    'a complemented block -> the ranges around it': (r'\P{IsBasicLatin}', r'[\u{80}-\u{10FFFF}]'),
    'a class with a range and characters -> JS items, ranges in code point order': ('[a-z_0]', '[0_a-z]'),
    'a negated class -> negated': ('[^a-c]', '[^a-c]'),
    'a dash first or last in a class -> a plain dash': ('[-a][a-]', r'[\-a][\-a]'),
    'a class subtraction -> a lookahead on the subtracted class': ('[a-z-[aeiou]]', '(?:(?![aeiou])[a-z])'),
    'a category minus characters -> the category kept, the characters looked ahead': (r'[\p{Nd}-[0-8]]', r'(?:(?![0-8])[\p{Nd}])'),
    'a category inside a class -> as it is': (r'[\p{L}\d_]', r'[_\p{L}\p{Nd}]'),
    'non-ASCII characters -> as code points': ('é ', r'\u{E9}\u{2028}'),
    'a dash before a subtraction -> a plain dash of the class': ('[a-z--[b-z]]', r'(?:(?![b-z])[\-a-z])'),
    'an escaped character starting a range -> the range (the grammar; libxml2 and elementpath deviate)': (r'[\{-\}]', '[{-}]'),
    'a range ending on an escape -> a range': (r'[a-\{]', '[a-{]'),
    'a class minus a negated class -> a lookahead on the negated one': ('[a-z-[^aeiou]]', '(?:(?![^aeiou])[a-z])'),
    'a word item in a class -> an alternative beside the class': (r'[\wa]', r'(?:[a]|[^\p{P}\p{Z}\p{C}])'),
    'a word item in a negated class, quantified -> a lookahead, one group': (r'[^\w]+', r'(?:(?![^\p{P}\p{Z}\p{C}])[^])+'),
    'a heavy subtraction -> as long as what it names, nothing expanded': (r'[\p{L}-[a]]', r'(?:(?![a])[\p{L}])'),
    'ranges that touch -> one range': ('[a-cd-f]', '[a-f]'),
    'a quantity with equal bounds -> as written': ('a{2,2}', 'a{2,2}'),
    'a range of one character -> that character': ('[a-a]', '[a]'),
    'a space -> as it is': ('a b', 'a b'),
    'a complemented block not starting at zero -> the ranges before and after it': (
        r'\P{IsLatin-1Supplement}', r'[\u{0}-\u{7F}\u{100}-\u{10FFFF}]'
    ),
    'blanks inside a class -> tab, line feed, carriage return, space': (r'[\s]', r'[\u{9}-\u{A}\u{D} ]'),
    'non-blanks inside a class -> every character around them': (r'[\S]', r'[\u{0}-\u{8}\u{B}-\u{C}\u{E}-\u{1F}!-\u{10FFFF}]'),
    'categories inside a class -> in code point order': (r'[\p{Nd}\p{Lu}\p{Ll}]', r'[\p{Ll}\p{Lu}\p{Nd}]'),
    'complemented categories inside a class -> in code point order': (r'[\P{Nd}\P{Lu}\P{Ll}]', r'[\P{Ll}\P{Lu}\P{Nd}]'),
}


@pytest.mark.parametrize(('xsd', 'expected'), RULES.values(), ids=RULES.keys())
def test_rules(xsd: str, expected: str | None) -> None:
    js = pattern_to_js(xsd)
    if expected is not None:
        assert js == expected


def test_name_classes_are_the_xml_4th_edition_ones_inside_and_outside_classes() -> None:
    outside = pattern_to_js(r'\i\c')
    assert outside.startswith('[:A-Z_a-z\\u{C0}-\\u{D6}')
    inside = pattern_to_js(r'[\i-]')
    assert inside.startswith('[\\-:A-Z_a-z')


@pytest.mark.parametrize(
    ('xsd', 'reason'),
    [
        pytest.param('a+?', 'quantifier follows a quantifier', id='a lazy quantifier -> refused, XSD has none'),
        pytest.param(r'\p{IsNoSuchBlock}', 'unknown block', id='an unknown block -> refused'),
        pytest.param(r'\p{IsEmoticons}', 'unknown block', id='a block Unicode 3.1 does not have -> refused, XSD 1.0 names those'),
        pytest.param(r'\p{Xx}', 'unknown category', id='an unknown category -> refused'),
        pytest.param('[a', 'unclosed', id='an unclosed class -> refused'),
        pytest.param('(a', 'unclosed', id='an unclosed group -> refused'),
        pytest.param('a)', 'unmatched', id='an unmatched parenthesis -> refused'),
        pytest.param('[z-a]', 'backwards', id='a range going backwards -> refused'),
        pytest.param('a{3,2}', 'quantity', id='a quantity going backwards -> refused'),
        pytest.param(r'\x', 'escape', id='an escape XSD does not have -> refused'),
        pytest.param('a{', 'unclosed', id='an unclosed quantity -> refused'),
        pytest.param('a{\u00b2}', 'quantity', id='a quantity in other digits than ASCII ones -> refused'),
        pytest.param('[a-c-e[x]]', 'neither a range', id='a dash after a range, before a class that is no subtraction -> refused'),
        pytest.param('a{\u0663}', 'quantity', id='a quantity in Arabic-Indic digits -> refused'),
    ],
)
def test_refusals(xsd: str, reason: str) -> None:
    with pytest.raises(SchemaNotRepresentable, match=reason):
        pattern_to_js(xsd)


# --- conformance -------------------------------------------------------------------------------------------------

CONFORMANCE = [
    'abc', r'a\-b\.c\^', '^a$', 'a.b', r'\s+\S*', r'\d{2,4}', r'\D', r'\w+', r'\W', '(ab)+|c', r'\p{Lu}\p{Ll}*',
    r'\P{L}', r'\p{IsBasicLatin}+', r'\p{IsLatin-1Supplement}', r'[a-z-[aeiou]]+', r'[\p{Nd}-[0-8]]', r'[\p{L}\d_]+',
    r'\i\c*', r'[\i-]+', r'[^\c]', r'\I\C', '[^a-c]', '[-a]', r'[\s\w]', r'[^\s]', '[0-9]{4}-[0-9]{2}', 'é.',
    r'[\p{IsGreek}-[\p{Lu}]]', r'([A-Z][a-z]*)?(\.[0-9]+){1,3}', r'[^\p{P}]', r'\.\\\|\?\*\+\(\)\{\}\[\]',
    r'[a-\{]+', r'[a-z--[b-z]]', r'[\P{L}-[0-9]]+', r'[\S]+', r'[\Sa-[b]]', r'[\wa]+', r'[^\w]+', r'[\w-[a]]+',
]
ADVERSARIAL = ['', ' ', '\t', '\n', '\r', ' ', ' ', 'a', 'Z', '0', '9', '_', '-', '.', 'é', 'é',
               '\U00010000', '\U0001d7ce', '٠', '〇', 'Ω', '·', '^', '$', 'ab', 'abc']


def _sample(atom: object, rng: random.Random) -> str:
    match atom:
        case P._RegExp():
            return ''.join(_sample_piece(piece, rng) for piece in rng.choice(atom.branches))
        case P._Literal():
            return atom.char
        case P._CharClass():
            return _pick(_class_points(atom), rng)
        case P._Written():
            pools = {
                '[^\\n\\r]': 'aé 9', '[\\t\\n\\r ]': ' \t', '[^\\t\\n\\r ]': 'x ', '\\p{Nd}': '7١',
                '\\P{Nd}': 'x', '[^\\p{P}\\p{Z}\\p{C}]': 'a1', '[\\p{P}\\p{Z}\\p{C}]': '. ',
            }
            if atom.source in pools:
                return rng.choice(pools[atom.source])
            name = atom.source[3:-1]
            ranges = _category_points(name)
            return _pick(ranges if atom.source.startswith('\\p') else P._complement(ranges), rng)
    raise TypeError(atom)


@cache
def _category_points(name: str) -> tuple[tuple[int, int], ...]:
    """A category's code points as elementpath's tables have them: enough to sample values from."""
    subset = elementpath_regex.unicode_category(name)
    return P._normalized([(item, item) if isinstance(item, int) else (item[0], item[1] - 1) for item in subset.codepoints])


def _class_points(char_class: P._CharClass) -> tuple[tuple[int, int], ...]:
    items = char_class.items
    pairs = list(items.ranges)
    for name in items.categories:
        pairs.extend(_category_points(name))
    for name in items.complemented_categories:
        pairs.extend(P._complement(_category_points(name)))
    if items.atoms:
        pairs.extend(P._complement(P._normalized([pair for name in 'PZC' for pair in _category_points(name)])))
    points = P._normalized(pairs)
    if char_class.negated:
        points = P._complement(points)
    if char_class.subtracted is not None:
        removed = _class_points(char_class.subtracted)
        points = tuple(pair for low, high in points for pair in _without((low, high), removed))
    return points


def _without(span: tuple[int, int], removed: tuple[tuple[int, int], ...]) -> list[tuple[int, int]]:
    pieces = [span]
    for low, high in removed:
        pieces = [part for start, end in pieces for part in ((start, min(end, low - 1)), (max(start, high + 1), end)) if part[0] <= part[1]]
    return pieces


def _sample_piece(piece: P._Piece, rng: random.Random) -> str:
    quantifier = piece.quantifier
    low, high = {'': (1, 1), '?': (0, 1), '*': (0, 3), '+': (1, 3)}.get(quantifier, (None, None))
    if low is None:
        bounds = quantifier[1:-1].split(',')
        low = int(bounds[0])
        high = low if len(bounds) == 1 else (int(bounds[1]) if bounds[1] else low + 2)
    return ''.join(_sample(piece.atom, rng) for _ in range(rng.randint(low, high)))


def _pick(ranges, rng: random.Random) -> str:
    if not ranges:
        return ''
    low, high = rng.choice(ranges)
    return chr(rng.randint(low, high))


def probes_of(pattern: str, seed: int = 0) -> list[str]:
    rng = random.Random(f'{seed}:{pattern}')
    parser = P._Parser(pattern)
    tree = parser.regexp()
    sampled = [_sample(tree, rng) for _ in range(8)]
    mutated = []
    for value in sampled:
        if value:
            index = rng.randrange(len(value))
            mutated.append(value[:index] + value[index + 1 :])
            mutated.append(value[:index] + rng.choice(ADVERSARIAL[5:]) + value[index:])
    # only what an XML document can hold
    return sorted({value for value in [*sampled, *mutated, *ADVERSARIAL] if all(_xml_char(char) for char in value)})


def _xml_char(char: str) -> bool:
    code_point = ord(char)
    return code_point in (0x9, 0xA, 0xD) or 0x20 <= code_point <= 0xD7FF or 0xE000 <= code_point <= 0xFFFD or code_point >= 0x10000


def libxml2_accepts(pattern: str, values: list[str]) -> list[bool]:
    schema = _libxml2_schema(pattern)
    verdicts = []
    for value in values:
        element = etree.Element('v')
        element.text = value
        verdicts.append(schema.validate(element))
    return verdicts


@cache
def _libxml2_schema(pattern: str) -> etree.XMLSchema:
    escaped = pattern.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')
    return etree.XMLSchema(etree.fromstring(
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:element name="v"><xs:simpleType>'
        f'<xs:restriction base="xs:string"><xs:pattern value="{escaped}"/></xs:restriction></xs:simpleType></xs:element></xs:schema>'
    ))


def node_accepts(sources: list[str], values: list[list[str]]) -> list[list[bool]]:
    script = (
        "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        "process.stdout.write(JSON.stringify(input.map(([source, values]) => {"
        "const re = new RegExp('^(?:' + source + ')$', 'u'); return values.map((v) => re.test(v)) })))"
    )
    run = subprocess.run(['node', '-e', script], input=json.dumps(list(zip(sources, values))), capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


@NEEDS_NODE
def test_every_converted_pattern_compiles_under_u() -> None:
    sources = [pattern_to_js(xsd) for xsd, _ in RULES.values()] + [pattern_to_js(pattern) for pattern in CONFORMANCE]
    node_accepts(sources, [[] for _ in sources])


@NEEDS_NODE
def test_conformance_against_libxml2() -> None:
    values = [probes_of(pattern) for pattern in CONFORMANCE]
    verdicts = node_accepts([pattern_to_js(pattern) for pattern in CONFORMANCE], values)
    disagreements = [
        (pattern, value, expected)
        for pattern, probes, by_node in zip(CONFORMANCE, values, verdicts)
        for value, expected, actual in zip(probes, libxml2_accepts(pattern, probes), by_node)
        if expected != actual
        and not unicode_versions_differ(value)
        and not (pattern in KNOWN_LIBXML2_FAULTS and elementpath_sides_with(pattern, value, actual))
    ]
    assert disagreements == []


# where libxml2 is wrong - elementpath, a second implementation, sides with the converter - and why
KNOWN_LIBXML2_FAULTS = {
    r'[a-z--[b-z]]': 'drops the dash before a subtraction',
    r'[\P{L}-[0-9]]+': 'a complemented category inside a class',
}


def elementpath_sides_with(pattern: str, value: str, verdict: bool) -> bool:
    """Whether elementpath, a second implementation, judges `value` as the converted pattern does: libxml2 then is
    the one apart (its known faults: complemented categories inside a class, a dash after an escaped character, and
    a counter inside an alternation - SCL's IP address pattern)."""
    compiled = re.compile(elementpath_regex.translate_pattern(pattern, anchors=False), re.DOTALL)
    return (compiled.fullmatch(value) is not None) == verdict


def unicode_versions_differ(value: str) -> bool:
    """Whether a character of `value` is in another category for libxml2 (its Unicode tables are old) than for
    current Unicode, which JS and this converter follow: the version XSD leaves to the implementation."""
    return any(libxml2_category(char) != unicodedata.category(char) for char in value)


@cache
def libxml2_category(char: str) -> str | None:
    for category in sorted(P.CATEGORIES, key=len, reverse=True):
        if libxml2_accepts(rf'\p{{{category}}}', [char]) == [True]:
            return category
    return None


def test_the_name_class_tables_are_libxml2_s() -> None:
    import ctypes

    from generate.definition.xml_name_classes import NAME_CHAR, NAME_START

    library = ctypes.CDLL(etree.__file__)
    if not hasattr(library, 'xmlIsLetter'):
        pytest.skip('this lxml does not export libxml2\'s name class functions')

    def test_of(name: str):
        function = getattr(library, name)
        function.restype, function.argtypes = ctypes.c_int, [ctypes.c_uint]
        return function

    letter, digit, combining, extender = (test_of(name) for name in ('xmlIsLetter', 'xmlIsDigit', 'xmlIsCombining', 'xmlIsExtender'))

    def ranges(belongs) -> tuple[tuple[int, int], ...]:
        found, start = [], None
        for code_point in range(0x110000):
            if belongs(code_point):
                start = code_point if start is None else start
            elif start is not None:
                found.append((start, code_point - 1))
                start = None
        return tuple(found)

    assert NAME_START == ranges(lambda cp: letter(cp) or cp in (0x3A, 0x5F))
    assert NAME_CHAR == ranges(lambda cp: letter(cp) or digit(cp) or combining(cp) or extender(cp) or cp in (0x2D, 0x2E, 0x3A, 0x5F))


BEHAVIOUR: dict[str, tuple[str, str, bool]] = {
    'a complemented category minus digits -> keeps punctuation': (r'[\P{L}-[0-9]]', '!', True),
    'a complemented category minus digits -> drops the digits': (r'[\P{L}-[0-9]]', '5', False),
    'a complemented category minus digits -> keeps no letter': (r'[\P{L}-[0-9]]', 'a', False),
    'a negated class minus characters -> keeps the others': (r'[^a-c-[x]]', 'y', True),
    'a negated class minus characters -> drops the subtracted': (r'[^a-c-[x]]', 'x', False),
    'a range starting on an escaped character -> holds what lies between': (r'[\{-\}]', '|', True),
    'a range starting on an escaped character -> no dash': (r'[\{-\}]', '-', False),
}


@NEEDS_NODE
@pytest.mark.parametrize(('xsd', 'value', 'expected'), BEHAVIOUR.values(), ids=BEHAVIOUR.keys())
def test_behaviour(xsd: str, value: str, expected: bool) -> None:
    assert node_accepts([pattern_to_js(xsd)], [[value]]) == [[expected]]


def test_the_block_table_is_unicode_3_1_s() -> None:
    from elementpath.regex import unicode_blocks

    from generate.definition.xsd_blocks import BLOCKS

    table = {}
    for part in (
        unicode_blocks.UNICODE_BLOCKS_VER_2_0_0,
        unicode_blocks.UPDATE_BLOCKS_VER_2_1_9,
        unicode_blocks.UPDATE_BLOCKS_VER_3_0_0,
        unicode_blocks.UPDATE_BLOCKS_VER_3_1_0,
    ):
        table.update(part)
    expected = {
        name.replace(' ', ''): tuple((ord(spans[i]), ord(spans[i + 2])) for i in range(0, len(spans), 3))
        for name, spans in table.items()
    }
    assert BLOCKS == expected


def test_a_pattern_nested_deeper_than_the_stack_is_refused_by_name() -> None:
    nested = '(' * 400 + 'a' + ')' * 400
    with pytest.raises(SchemaNotRepresentable, match='nested too deeply'):
        pattern_to_js(nested)


def test_a_pattern_too_deep_is_named_by_its_first_80_characters() -> None:
    nested = '(' * 400 + 'a' + ')' * 400
    with pytest.raises(SchemaNotRepresentable, match=re.escape("'" + '(' * 80 + "'...")):
        pattern_to_js(nested)
