"""The selector and field paths of an identity constraint, parsed over the XSD 1.0 path grammar:

    Selector ::= Path ( '|' Path )*            Path ::= ( '.' '//' )? Step ( '/' Step )*
    Field    ::= Path ( '|' Path )*            Path ::= ( '.' '//' )? ( Step '/' )* ( Step | Attribute )
    Step     ::= '.' | ( 'child' '::' )? NameTest
    Attribute ::= ( '@' | 'attribute' '::' ) NameTest
    NameTest ::= QName | '*' | NCName ':' '*'

Whitespace may separate any two tokens. An unprefixed name is in no namespace (XSD 1.0 has no default namespace
for these paths); a prefix is resolved with the namespaces in scope where the constraint is written.
"""
import re

from generate.errors import SchemaNotRepresentable
from generate.model.declarations import FieldPath, NameTest, SelectorPath

# XML 1.0 name characters, the colon left out (NCName)
_NAME_START = (
    'A-Z_a-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d'
    '\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd\U00010000-\U000effff'
)
_NAME = rf'[{_NAME_START}][{_NAME_START}\-.0-9\u00b7\u0300-\u036f\u203f-\u2040]*'
_TOKEN = re.compile(rf'\s*(//|/|\||@|::|\.|\*|{_NAME}(?::(?:\*|{_NAME}))?)')


def parse_selector(path: str, *, namespaces: dict[str, str]) -> tuple[SelectorPath, ...]:
    """The alternatives of a selector."""
    alternatives = []
    for tokens in _alternatives(path):
        deep, steps, attribute = _path(tokens, namespaces=namespaces, path=path)
        if attribute is not None:
            raise SchemaNotRepresentable(f'a selector selects elements, not attributes: {path!r}')
        alternatives.append(SelectorPath(deep=deep, steps=steps))
    return tuple(alternatives)


def parse_field(path: str, *, namespaces: dict[str, str]) -> tuple[FieldPath, ...]:
    """The alternatives of a field."""
    alternatives = []
    for tokens in _alternatives(path):
        deep, steps, attribute = _path(tokens, namespaces=namespaces, path=path)
        alternatives.append(FieldPath(deep=deep, steps=steps, attribute=attribute))
    return tuple(alternatives)


def _alternatives(path: str) -> list[list[str]]:
    tokens: list[str] = []
    position = 0
    while position < len(path.rstrip()):
        match = _TOKEN.match(path, position)
        if match is None:
            raise SchemaNotRepresentable(f'not an identity constraint path: {path!r}')
        tokens.append(match.group(1))
        position = match.end()
    alternatives: list[list[str]] = [[]]
    for token in tokens:
        if token == '|':
            alternatives.append([])
        else:
            alternatives[-1].append(token)
    if any(not alternative for alternative in alternatives):
        raise SchemaNotRepresentable(f'an empty alternative in an identity constraint path: {path!r}')
    return alternatives


def _path(
    tokens: list[str], *, namespaces: dict[str, str], path: str
) -> tuple[bool, tuple[NameTest, ...], NameTest | None]:
    """(deep, the element steps - `.` ones dropped -, the attribute the path ends at)."""
    deep = tokens[:2] == ['.', '//']
    position = 2 if deep else 0
    steps: list[NameTest] = []
    attribute: NameTest | None = None
    while True:
        token = tokens[position] if position < len(tokens) else None
        following = tokens[position + 1] if position + 1 < len(tokens) else None
        if token == '.':
            position += 1
        elif token == '@' or (token == 'attribute' and following == '::'):
            position += 1 if token == '@' else 2
            attribute = _name_test(tokens, position, namespaces=namespaces, path=path)
            position += 1
        else:
            if token == 'child' and following == '::':
                position += 2
            steps.append(_name_test(tokens, position, namespaces=namespaces, path=path))
            position += 1
        if position == len(tokens):
            return deep, tuple(steps), attribute
        if attribute is not None or tokens[position] != '/':
            raise SchemaNotRepresentable(f'not an identity constraint path: {path!r}')
        position += 1


def _name_test(tokens: list[str], position: int, *, namespaces: dict[str, str], path: str) -> NameTest:
    token = tokens[position] if position < len(tokens) else ''
    if token == '*':
        return NameTest(name=None, namespace=None)
    if not re.fullmatch(rf'{_NAME}(:(\*|{_NAME}))?', token):
        raise SchemaNotRepresentable(f'not an identity constraint path: {path!r}')
    if ':' not in token:
        return NameTest(name=token, namespace='')
    prefix, local = token.split(':', 1)
    if prefix not in namespaces:
        raise SchemaNotRepresentable(f'an identity constraint path uses the unbound prefix {prefix}: {path!r}')
    return NameTest(name=None if local == '*' else local, namespace=namespaces[prefix])
