"""Parse XSD identity-constraint XPath selectors and fields (§3.11.6).

Implements the restricted grammar from XSD 1.1 Part 1, §3.11.6.2 (selectors)
and §3.11.6.3 (fields):

  Selector  ::=  Path ( '|' Path )*
  Path      ::=  ('.' '//')? Step ( '/' Step )*
  Step      ::=  '.' | NameTest
  NameTest  ::=  QName | '*' | NCName ':*'

Field variant: last step can also be ``@ NameTest``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from generate.helpers import local_name


# ---------------------------------------------------------------------------
# IR dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class XPathStep:
    """A single step in a selector/field path.

    kind:
      - 'self'        → the literal '.'
      - 'name'        → local element name (ns stripped)
      - 'wildcard'    → '*'
      - 'ns-wildcard' → 'NCName:*'  (value = NCName)
    """
    kind: Literal['self', 'name', 'wildcard', 'ns-wildcard']
    value: str | None = None


@dataclass(frozen=True)
class SelectorPath:
    """One alternative of a selector (before/after '|')."""
    deep: bool = False
    steps: tuple[XPathStep, ...] = ()


@dataclass(frozen=True)
class FieldTarget:
    """The terminal target of a field XPath — element or attribute.

    kind:
      - 'element'   → child element name
      - 'attribute'  → @attrName
      - 'wildcard'   → * or @*
      - 'ns-wildcard' → NCName:* or @NCName:*
    """
    kind: Literal['element', 'attribute', 'wildcard', 'ns-wildcard']
    value: str | None = None
    is_attribute: bool = False


@dataclass(frozen=True)
class FieldPath:
    """Parsed XPath field expression."""
    deep: bool = False
    steps: tuple[XPathStep, ...] = ()
    target: FieldTarget = field(default_factory=lambda: FieldTarget(kind='wildcard'))


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_PIPE_RE = re.compile(r'\s*\|\s*')


def parse_selector(xpath: str) -> list[SelectorPath]:
    """Parse a selector XPath into a list of SelectorPath alternatives."""
    if not xpath or not xpath.strip():
        return []
    alternatives = _PIPE_RE.split(xpath.strip())
    return [_parse_selector_path(alt.strip()) for alt in alternatives if alt.strip()]


def parse_field(xpath: str) -> FieldPath:
    """Parse a field XPath into a FieldPath."""
    if not xpath or not xpath.strip():
        return FieldPath()
    return _parse_field_path(xpath.strip())


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _parse_selector_path(raw: str) -> SelectorPath:
    """Parse one selector alternative (no '|')."""
    deep, remainder = _consume_deep_prefix(raw)
    tokens = _split_steps(remainder)
    steps = tuple(_parse_step(t) for t in tokens)
    return SelectorPath(deep=deep, steps=steps)


def _parse_field_path(raw: str) -> FieldPath:
    """Parse a field XPath expression."""
    deep, remainder = _consume_deep_prefix(raw)
    tokens = _split_steps(remainder)

    if not tokens:
        return FieldPath(deep=deep)

    # Check if last token is an attribute reference
    last = tokens[-1]
    if last.startswith('@'):
        steps = tuple(_parse_step(t) for t in tokens[:-1])
        target = _parse_field_target(last, is_attribute=True)
    else:
        steps = tuple(_parse_step(t) for t in tokens[:-1])
        target = _parse_field_target(last, is_attribute=False)

    return FieldPath(deep=deep, steps=steps, target=target)


def _consume_deep_prefix(raw: str) -> tuple[bool, str]:
    """Strip leading './' or './/' and return (deep, remainder)."""
    if raw.startswith('.//'):
        return True, raw[3:]
    if raw.startswith('./'):
        return False, raw[2:]
    return False, raw


def _split_steps(raw: str) -> list[str]:
    """Split path into step tokens on '/' boundaries."""
    if not raw:
        return []
    parts = raw.split('/')
    return [p.strip() for p in parts if p.strip()]


def _parse_step(token: str) -> XPathStep:
    """Parse a single step token into an XPathStep."""
    if token == '.':
        return XPathStep(kind='self')
    if token == '*':
        return XPathStep(kind='wildcard')
    if token.endswith(':*'):
        prefix = token[:-2]
        return XPathStep(kind='ns-wildcard', value=prefix)
    # QName — strip namespace prefix
    return XPathStep(kind='name', value=local_name(token))


def _parse_field_target(token: str, *, is_attribute: bool) -> FieldTarget:
    """Parse the terminal token of a field path."""
    raw = token.lstrip('@').strip()

    if raw == '*':
        return FieldTarget(kind='wildcard', is_attribute=is_attribute)
    if raw.endswith(':*'):
        return FieldTarget(kind='ns-wildcard', value=raw[:-2], is_attribute=is_attribute)
    return FieldTarget(
        kind='attribute' if is_attribute else 'element',
        value=local_name(raw),
        is_attribute=is_attribute,
    )
