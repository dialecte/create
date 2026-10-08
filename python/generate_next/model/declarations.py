"""The schema as the generator reads it: one immutable record per element declaration.

Nothing here knows the definition the generator writes; it says what the schema declares.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Namespace:
    prefix: str
    uri: str


@dataclass(frozen=True)
class Wildcard:
    """The namespaces a wildcard admits, resolved: either the ones listed (`''` for no namespace) or
    every one but those listed (`##any` excludes none, `##other` the declaring schema's own and none)."""

    namespace: tuple[str, ...] | None
    not_namespace: tuple[str, ...] | None
    process_contents: str


@dataclass(frozen=True)
class ElementParticle:
    """An element a content model names, with how often; its namespace is the element's own."""

    name: str
    namespace: str
    min_occurs: int
    # None: unbounded
    max_occurs: int | None


@dataclass(frozen=True)
class WildcardParticle:
    wildcard: Wildcard
    min_occurs: int
    max_occurs: int | None


@dataclass(frozen=True)
class GroupParticle:
    kind: str  # 'sequence' | 'choice' | 'all'
    min_occurs: int
    max_occurs: int | None
    particles: tuple['ElementParticle | WildcardParticle | GroupParticle', ...]


Particle = ElementParticle | WildcardParticle | GroupParticle


@dataclass(frozen=True)
class AttributeDeclaration:
    """An attribute an element may carry (a prohibited one is not declared at all)."""

    # bare local name in the element's own namespace, `prefix:local` in any other
    key: str
    # present for an attribute in another namespace than the element's
    namespace: Namespace | None
    required: bool
    default: str | None
    fixed: str | None
    # the most specific built-in datatype the value derives from; None for a plain string
    builtin: str | None


@dataclass(frozen=True)
class TextDeclaration:
    """The text an element may hold: typed for a simple type or simple content, untyped beside the
    elements of mixed content."""

    # the most specific built-in datatype of the text; None for a plain string or mixed content
    builtin: str | None
    default: str | None
    fixed: str | None


@dataclass(frozen=True)
class ElementDeclaration:
    """One declaration of an element: a global one, or a local one inside a content model."""

    name: str
    namespace: Namespace
    is_global: bool
    documentation: str | None
    attributes: tuple[AttributeDeclaration, ...]
    # None: no attribute wildcard
    any_attribute: Wildcard | None
    # the particle tree of its element content as the schema writes it (a substitution head standing for
    # the choice among its members); None when the content holds no element nor wildcard
    content_model: GroupParticle | None
    # None when the element holds no text (element-only or empty content)
    text: TextDeclaration | None
    # the names of the elements whose content holds this declaration, sorted
    parent_names: tuple[str, ...]
