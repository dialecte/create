"""Internal Representation — Python dataclasses for XSD schema data.

Never serialized directly. Used as the in-memory model between
Parse → Collect → Derive → Emit phases.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generate.xpath_parser import FieldPath, SelectorPath
@dataclass
class Namespace:
    prefix: str
    uri: str
@dataclass
class Facets:
    enumeration: list[str] | None = None
    pattern: list[str] | None = None
    min_length: int | None = None
    max_length: int | None = None
    length: int | None = None
    min_inclusive: int | str | None = None
    max_inclusive: int | str | None = None
    min_exclusive: int | str | None = None
    max_exclusive: int | str | None = None
    total_digits: int | None = None
    fraction_digits: int | None = None
    white_space: str | None = None  # 'preserve' | 'replace' | 'collapse'

    def is_empty(self) -> bool:
        return all(v is None for v in vars(self).values())
@dataclass
class AttributeDef:
    required: bool = False
    default: str | None = None
    fixed: str | None = None
    namespace: Namespace | None = None
    facets: Facets | None = None
@dataclass
class IdentityConstraint:
    kind: str  # 'unique' | 'key' | 'keyref'
    name: str
    selector: list[SelectorPath]  # parsed XPath alternatives (union)
    fields: list[FieldPath]  # parsed field XPath expressions
    deep: bool = False
    refer: str | None = None  # keyref only

@dataclass
class ChildDef:
    required: bool = False
    min_occurs: int = 0
    max_occurs: int | None = None  # None = unbounded
    constraints: list[IdentityConstraint] | None = None
    facets: Facets | None = None

@dataclass
class ChoiceGroup:
    options: list[str]
    min_occurs: int = 0
    max_occurs: int | None = None
@dataclass
class TextContent:
    facets: Facets | None = None
@dataclass
class ElementDef:
    tag: str
    namespace: Namespace
    documentation: str | None = None
    parents: list[str] = field(default_factory=list)
    attr_sequence: list[str] = field(default_factory=list)
    attr_any: bool = False
    attributes: dict[str, AttributeDef] = field(default_factory=dict)
    child_sequence: list[str] = field(default_factory=list)
    child_any: bool = False
    children: dict[str, ChildDef] = field(default_factory=dict)
    choices: list[ChoiceGroup] = field(default_factory=list)
    constraints: list[IdentityConstraint] = field(default_factory=list)
    text_content: TextContent | None = None
    identity_fields: list[str] = field(default_factory=list)
