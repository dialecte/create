"""The schema as the generator reads it: one immutable record per element declaration.

Nothing here knows the definition the generator writes; it says what the schema declares.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Namespace:
    prefix: str
    uri: str


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
class ElementDeclaration:
    """One declaration of an element: a global one, or a local one inside a content model."""

    name: str
    namespace: Namespace
    is_global: bool
    documentation: str | None
    attributes: tuple[AttributeDeclaration, ...]
    # None: no attribute wildcard; otherwise the namespaces it admits
    any_attribute: tuple[str, ...] | None
    # the element names its content holds, in content order, as often as it names them (substitution
    # members included)
    child_names: tuple[str, ...]
    # the names of the elements whose content holds this declaration, sorted
    parent_names: tuple[str, ...]
