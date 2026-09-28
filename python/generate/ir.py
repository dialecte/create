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
class DataType:
    """What a simple value is: an XSD built-in, a list of one, or a union of several.

    `facets` are the ones restricting THIS level (a list's length, a union member's enumeration);
    the facets of a whole attribute, flattened, stay on the attribute.
    """
    kind: str  # 'atomic' | 'list' | 'union'
    builtin: str | None = None  # atomic: the built-in's local name ('decimal', 'boolean', 'ID', ...)
    item: DataType | None = None  # list
    members: list[DataType] | None = None  # union
    facets: Facets | None = None


@dataclass
class AttributeDef:
    required: bool = False
    default: str | None = None
    fixed: str | None = None
    namespace: Namespace | None = None
    facets: Facets | None = None
    type: DataType | None = None  # None for a plain string: nothing to tell
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
    # Per-edge override: the child's declaring-schema namespace when it differs from
    # the child element's canonical namespace (same local name declared in another
    # namespace under this parent). Emitted sparsely; None ⇒ use the element's own.
    namespace: Namespace | None = None

@dataclass
class Particle:
    """One node of a content model, as the schema wrote it.

    A group (`sequence` / `choice` / `all`) holds `particles`; an `element` has a `name`; an `any`
    has its namespace constraint. Occurrences are the particle's own: a group's says how often the
    whole group repeats, which the flat children table cannot say.
    """
    kind: str  # 'sequence' | 'choice' | 'all' | 'element' | 'any'
    min_occurs: int = 1
    max_occurs: int | None = 1  # None = unbounded
    particles: list[Particle] | None = None
    name: str | None = None
    namespace: list[str] | None = None  # any: '##any', '##other', '##local', '##targetNamespace', URIs
    process_contents: str | None = None  # any: 'strict' | 'lax' | 'skip'
    # A choice the generator made, not the schema: between the content models of the declarations
    # of one homonym name. Not emitted; it tells a later merge where to add the next declaration.
    of_declarations: bool = field(default=False, compare=False, repr=False)


@dataclass
class TextContent:
    facets: Facets | None = None
    type: DataType | None = None
    default: str | None = None  # the element's own default text
    fixed: str | None = None  # the element's own fixed text
@dataclass
class ElementDef:
    tag: str
    namespace: Namespace
    documentation: str | None = None
    parents: list[str] = field(default_factory=list)
    attr_sequence: list[str] = field(default_factory=list)
    attr_any: bool = False
    # the namespace constraint of xs:anyAttribute, when any: '##any', '##other', '##local', URIs
    attr_any_namespace: list[str] | None = None
    attributes: dict[str, AttributeDef] = field(default_factory=dict)
    # nillable="true": an instance may carry xsi:nil="true" and no content
    nillable: bool = False
    child_sequence: list[str] = field(default_factory=list)
    child_any: bool = False
    children: dict[str, ChildDef] = field(default_factory=dict)
    constraints: list[IdentityConstraint] = field(default_factory=list)
    text_content: TextContent | None = None
    identity_fields: list[str] = field(default_factory=list)
    # The content model as a tree; None when the element holds no elements.
    content_model: Particle | None = None
    # For a homonym only: its definition under each parent, as declared there, untouched by the
    # union - a full ElementDef, the same shape as this one, whose `parents` are the parents naming
    # that declaration. The element's own tables are the union of them.
    definitions_by_parent: dict[str, ElementDef] = field(default_factory=dict)
