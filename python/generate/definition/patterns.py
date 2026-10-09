"""XSD regular expressions as JavaScript sources, valid under the `u` flag and unanchored (a pattern matches the whole
value: the reader wraps it `^(?:...)$`).

Parsed over the XSD 1.0 grammar - branches, pieces with `? * + {n} {n,} {n,m}`, groups, `.`, single-character,
multi-character, category and block escapes, character classes with negation, ranges and subtraction - and written
with XSD's meaning: `.` excludes only CR and LF, `\\s` is the four XML blanks, `\\d` the decimal digits, `\\w` every
character but punctuation, separators and others, `\\i` / `\\c` the XML 1.0 4th-edition name classes (GD1), blocks the
Unicode 3.1 ones XSD 1.0 names, `^` and `$` plain characters. Categories stay `\\p{X}`: one Unicode, the engine's.
A class subtraction is a lookahead (`[A-[B]]` is `(?![B])[A]`: one character of A that is not in B), and a class
item JS cannot place in a class (`\\w`) an alternative: nothing is expanded into code points.
"""
import re
from dataclasses import dataclass
from functools import cache

from generate.model.names import sorted_names
from generate.definition.xml_name_classes import NAME_CHAR, NAME_START
from generate.definition.xsd_blocks import BLOCKS
from generate.errors import SchemaNotRepresentable

MAX_CODE_POINT = 0x10FFFF
CATEGORIES = frozenset(
    'L Lu Ll Lt Lm Lo M Mn Mc Me N Nd Nl No P Pc Pd Ps Pe Pi Pf Po Z Zs Zl Zp S Sm Sc Sk So C Cc Cf Co Cn'.split()
)
SINGLE_ESCAPES = {'n': '\n', 'r': '\r', 't': '\t', '\\': '\\', '|': '|', '.': '.', '?': '?', '*': '*', '+': '+',
                  '(': '(', ')': ')', '{': '{', '}': '}', '-': '-', '[': '[', ']': ']', '^': '^'}
# outside a class: what is not a NormalChar
_META = set('.\\?*+{}()|[]')
_BLANKS = ((0x09, 0x0A), (0x0D, 0x0D), (0x20, 0x20))
# XSD quantities are ASCII digits
_QUANTITY = re.compile(r'[0-9]+(,[0-9]*)?')
# `\w`: every character but punctuation, separators and others - no JS class item says that, so an alternative
_WORD = '[^\\p{P}\\p{Z}\\p{C}]'


@cache
def pattern_to_js(pattern: str) -> str:
    """The JS source of an XSD pattern; a pattern outside the XSD grammar is refused, and so is one nested deeper
    than the reader's stack (hundreds of groups)."""
    parser = _Parser(pattern)
    try:
        regexp = parser.regexp()
        if parser.position != len(pattern):
            parser.fail('an unmatched ")"')
        return _written_regexp(regexp)
    except RecursionError:
        raise SchemaNotRepresentable(f'the pattern {pattern[:80]!r}... is nested too deeply to convert') from None


# --- code point ranges -------------------------------------------------------------------------------------------

def _normalized(ranges: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    merged: list[tuple[int, int]] = []
    for low, high in sorted(ranges):
        if merged and low <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], high))
        else:
            merged.append((low, high))
    return tuple(merged)


def _complement(ranges: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    result = []
    next_low = 0
    for low, high in ranges:
        if low > next_low:
            result.append((next_low, low - 1))
        next_low = high + 1
    if next_low <= MAX_CODE_POINT:
        result.append((next_low, MAX_CODE_POINT))
    return tuple(result)


_NAME_START = _normalized(list(NAME_START))
_NAME_CHAR = _normalized(list(NAME_CHAR))


# --- syntax tree -------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class _ClassItems:
    """A union of characters: code point ranges, categories JS writes as they are (`\\p{X}`, `\\P{X}`), and atoms JS
    cannot place inside a class (`\\w`), written as alternatives."""

    ranges: tuple[tuple[int, int], ...] = ()
    categories: frozenset[str] = frozenset()
    complemented_categories: frozenset[str] = frozenset()
    atoms: tuple[str, ...] = ()

    def union(self, other: '_ClassItems') -> '_ClassItems':
        return _ClassItems(
            ranges=_normalized([*self.ranges, *other.ranges]),
            categories=self.categories | other.categories,
            complemented_categories=self.complemented_categories | other.complemented_categories,
            atoms=tuple(dict.fromkeys([*self.atoms, *other.atoms])),
        )


@dataclass(frozen=True)
class _CharClass:
    items: _ClassItems
    negated: bool = False
    subtracted: '_CharClass | None' = None


@dataclass(frozen=True)
class _Literal:
    char: str


@dataclass(frozen=True)
class _Written:
    """An atom whose JS source is known as it stands (`.`, multi-character and category escapes outside a class)."""

    source: str


@dataclass(frozen=True)
class _Piece:
    atom: object
    quantifier: str = ''


@dataclass(frozen=True)
class _RegExp:
    branches: tuple[tuple[_Piece, ...], ...]


@dataclass
class _Parser:
    pattern: str
    position: int = 0

    def fail(self, reason: str):
        raise SchemaNotRepresentable(f'the pattern {self.pattern!r} is not an XSD regular expression: {reason}')

    def peek(self, offset: int = 0) -> str | None:
        index = self.position + offset
        return self.pattern[index] if index < len(self.pattern) else None

    def take(self) -> str:
        char = self.peek()
        if char is None:
            self.fail('it ends too soon')
        self.position += 1
        return char

    def regexp(self) -> _RegExp:
        branches = [self.branch()]
        while self.peek() == '|':
            self.position += 1
            branches.append(self.branch())
        return _RegExp(branches=tuple(branches))

    def branch(self) -> tuple[_Piece, ...]:
        pieces = []
        while self.peek() is not None and self.peek() not in '|)':
            pieces.append(self.piece())
        return tuple(pieces)

    def piece(self) -> _Piece:
        atom = self.atom()
        quantifier = self.quantifier()
        if quantifier and self.peek() is not None and self.peek() in '?*+{':
            self.fail('a quantifier follows a quantifier (XSD has no lazy or possessive quantifiers)')
        return _Piece(atom=atom, quantifier=quantifier)

    def quantifier(self) -> str:
        char = self.peek()
        if char is not None and char in '?*+':
            self.position += 1
            return char
        if char != '{':
            return ''
        end = self.pattern.find('}', self.position)
        if end < 0:
            self.fail('an unclosed "{"')
        quantity = self.pattern[self.position + 1 : end]
        low, _, high = quantity.partition(',')
        if not _QUANTITY.fullmatch(quantity) or (high and int(high) < int(low)):
            self.fail(f'the quantity {{{quantity}}}')
        self.position = end + 1
        return '{' + quantity + '}'

    def atom(self) -> object:
        char = self.take()
        if char == '(':
            inner = self.regexp()
            if self.peek() != ')':
                self.fail('an unclosed "("')
            self.position += 1
            return inner
        if char == '[':
            return self.class_expression()
        if char == '.':
            return _Written('[^\\n\\r]')
        if char == '\\':
            return self.escape_outside_class()
        if char in _META:
            self.fail(f'a "{char}" where a character is expected')
        return _Literal(char)

    def escape_outside_class(self) -> object:
        char = self.take()
        if char in SINGLE_ESCAPES:
            return _Literal(SINGLE_ESCAPES[char])
        if char in 'pP':
            return self.property(complemented=char == 'P', inside_class=False)
        written = {
            's': '[\\t\\n\\r ]',
            'S': '[^\\t\\n\\r ]',
            'd': '\\p{Nd}',
            'D': '\\P{Nd}',
            'w': _WORD,
            'W': '[\\p{P}\\p{Z}\\p{C}]',
        }
        if char in written:
            return _Written(written[char])
        if char in 'iIcC':
            ranges = _NAME_START if char in 'iI' else _NAME_CHAR
            return _CharClass(items=_ClassItems(ranges=ranges), negated=char in 'IC')
        self.fail(f'the escape \\{char}')

    def property(self, *, complemented: bool, inside_class: bool) -> object:
        """`\\p{...}` / `\\P{...}`: a category written as it is, a block as its ranges."""
        if self.take() != '{':
            self.fail('a "\\p" without "{"')
        end = self.pattern.find('}', self.position)
        if end < 0:
            self.fail('an unclosed "\\p{"')
        name = self.pattern[self.position : end]
        self.position = end + 1
        if name.startswith('Is'):
            if name[2:] not in BLOCKS:
                self.fail(f'the unknown block {name}')
            ranges = _normalized(list(BLOCKS[name[2:]]))
            items = _ClassItems(ranges=_complement(ranges) if complemented else ranges)
            return items if inside_class else _CharClass(items=items)
        if name not in CATEGORIES:
            self.fail(f'the unknown category {name}')
        if inside_class:
            return _ClassItems(categories=frozenset() if complemented else frozenset({name}),
                               complemented_categories=frozenset({name}) if complemented else frozenset())
        return _Written(('\\P' if complemented else '\\p') + '{' + name + '}')

    def class_expression(self) -> _CharClass:
        """After `[`: a positive or negated group, possibly minus a class, up to `]`."""
        negated = self.peek() == '^'
        if negated:
            self.position += 1
        items = _ClassItems()
        first = True
        while True:
            char = self.peek()
            if char is None:
                self.fail('an unclosed "["')
            if char == ']' and not first:
                self.position += 1
                return _CharClass(items=items, negated=negated)
            if char == '-' and self.peek(1) == '[' and not first:
                self.position += 2
                subtracted = self.class_expression()
                if self.take() != ']':
                    self.fail('a subtraction not closing its class')
                return _CharClass(items=items, negated=negated, subtracted=subtracted)
            items = items.union(self.class_item(first=first))
            first = False

    def class_item(self, *, first: bool) -> _ClassItems:
        """One item of a class: a character or a range of them (either end may be a single-character escape), or a
        multi-character, category or block escape. A dash is plain first, last, or right before a subtraction."""
        char = self.take()
        if char == '[':
            self.fail('a "[" inside a class')
        if char == ']' and first:
            self.fail('an empty class')
        if char == '\\':
            escaped = self.peek()
            if escaped is None or escaped not in SINGLE_ESCAPES:
                return self.escape_inside_class()
            self.position += 1
            low = SINGLE_ESCAPES[escaped]
        else:
            plain_dash = first or self.peek() == ']' or (self.peek() == '-' and self.peek(1) == '[')
            if char == '-' and not plain_dash:
                self.fail('a "-" that is neither a range, the first nor the last character of a class')
            low = char
        if self.peek() == '-' and self.peek(1) not in (']', '[', None):
            self.position += 1
            high = self.take()
            if high == '\\':
                escaped = self.take()
                if escaped not in SINGLE_ESCAPES:
                    self.fail('a range ending on a multi-character escape')
                high = SINGLE_ESCAPES[escaped]
            elif high in '[]-':
                self.fail(f'a range ending on "{high}"')
            if ord(high) < ord(low):
                self.fail(f'the range {low}-{high} goes backwards')
            return _ClassItems(ranges=((ord(low), ord(high)),))
        return _ClassItems(ranges=((ord(low), ord(low)),))

    def escape_inside_class(self) -> _ClassItems:
        char = self.take()
        if char in 'pP':
            return self.property(complemented=char == 'P', inside_class=True)
        if char == 'd':
            return _ClassItems(categories=frozenset({'Nd'}))
        if char == 'D':
            return _ClassItems(complemented_categories=frozenset({'Nd'}))
        if char == 'W':
            return _ClassItems(categories=frozenset({'P', 'Z', 'C'}))
        if char == 'w':
            return _ClassItems(atoms=(_WORD,))
        ranges = {
            's': _BLANKS,
            'S': _complement(_BLANKS),
            'i': _NAME_START,
            'I': _complement(_NAME_START),
            'c': _NAME_CHAR,
            'C': _complement(_NAME_CHAR),
        }
        if char in ranges:
            return _ClassItems(ranges=ranges[char])
        self.fail(f'the escape \\{char}')


# --- JS source ---------------------------------------------------------------------------------------------------

def _written_regexp(regexp: _RegExp) -> str:
    return '|'.join(''.join(_written_piece(piece) for piece in branch) for branch in regexp.branches)


def _written_piece(piece: _Piece) -> str:
    return _written_atom(piece.atom) + piece.quantifier


def _written_atom(atom: object) -> str:
    match atom:
        case _Literal():
            return _outside(atom.char)
        case _Written():
            return atom.source
        case _CharClass():
            source = _written_class(atom)
            # a lookahead before the class makes two atoms: one group, so a quantifier takes both
            return '(?:' + source + ')' if source.startswith('(?!') else source
        case _RegExp():
            return '(?:' + _written_regexp(atom) + ')'
    raise TypeError(atom)


def _written_class(char_class: _CharClass) -> str:
    """One character of the class: its JS class, `(?:[...]|atom)` when it holds an atom JS cannot place in a class,
    `(?!atom)` before a negated one, `(?!subtracted)` before it all."""
    items = char_class.items
    body = ''.join(_inside_range(low, high) for low, high in items.ranges)
    body += ''.join('\\p{' + name + '}' for name in sorted_names(items.categories))
    body += ''.join('\\P{' + name + '}' for name in sorted_names(items.complemented_categories))
    if char_class.negated:
        source = ''.join(f'(?!{atom})' for atom in items.atoms) + '[^' + body + ']'
    elif items.atoms:
        options = ([f'[{body}]'] if body else []) + list(items.atoms)
        source = options[0] if len(options) == 1 else '(?:' + '|'.join(options) + ')'
    else:
        source = '[' + body + ']'
    if char_class.subtracted is not None:
        source = '(?!' + _written_class(char_class.subtracted) + ')' + source
    return source


_SYNTAX = set('^$\\.*+?()[]{}|/')


def _outside(char: str) -> str:
    if char in _SYNTAX:
        return '\\' + char
    return char if _printable(char) else _code_point(ord(char))


def _inside_range(low: int, high: int) -> str:
    if low == high:
        return _inside(low)
    return _inside(low) + '-' + _inside(high)


def _inside(code_point: int) -> str:
    char = chr(code_point)
    if char in '\\]^-[':
        return '\\' + char
    return char if _printable(char) else _code_point(code_point)


def _printable(char: str) -> bool:
    return 0x20 <= ord(char) < 0x7F


def _code_point(code_point: int) -> str:
    return '\\u{' + format(code_point, 'X') + '}'
