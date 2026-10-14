"""The declaration that applies to an element of an instance, read from the definition as a validator reads it:
the root and an element a wildcard admits by their global declaration, any other by the particle of its parent's
content model that holds it (the matcher says which, so a tag declared several ways is never left to the lenient
union); then the type the element names with `xsi:type` when its declaration admits it (any other leaves the element
to its declaration, as libxml2 does). A port of core's `resolveDefinition` for a walk that knows every parent.
"""
from dataclasses import dataclass
from typing import Any

XS = 'http://www.w3.org/2001/XMLSchema'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'


@dataclass(frozen=True)
class Resolved:
    """What an element is held to: its content (attributes, children, content model, text) and its declaration's
    own facts (namespace, nillable, variants, abstract type). `holder` is the namespace its content model's
    particles are written relative to: the declaration's, or the named type's."""

    declaration: dict[str, Any]
    content: dict[str, Any]
    holder: str
    named_type: str | None = None


def global_declaration(definition: dict[str, Any], local: str, namespace: str) -> dict[str, Any] | None:
    """The global declaration of an element (local name, namespace), if the schema has one."""
    entry = definition.get(local)
    if entry is None:
        return None
    ways = list(entry.get('declarations', {}).values()) or [entry]
    return next((way for way in ways if way.get('global') and way['namespace']['uri'] == namespace), None)


def declaration_of(definition: dict[str, Any], particle: dict[str, Any]) -> dict[str, Any] | None:
    """The declaration an element particle holds: the one it names for a tag declared several ways, else the tag's.
    None for a particle of a tag declared several ways that names none (the definition would be wrong: the lenient
    union is no declaration to hold an element to)."""
    entry = definition[particle['name']]
    declarations = entry.get('declarations')
    if not declarations:
        return entry
    return declarations.get(particle['declaration']) if 'declaration' in particle else None


def with_type(*, declaration: dict[str, Any], named: str | None, types: dict[str, Any]) -> Resolved:
    """The element as its declaration holds it, or as the type it names when the declaration admits it (a variant:
    its content swapped in, identity fields, constraints and namespace staying the declaration's). Any other type
    named - unrelated, blocked, unknown, a built-in - is refused (an xsi:type fault, not compared) or, a built-in deriving from a
    simple declared type, changes nothing structural: either way the element is assessed by its declaration."""
    namespace = declaration['namespace']['uri']
    if named is not None and named != declaration.get('type') and named in declaration.get('variants', []) and named in types:
        return Resolved(declaration=declaration, content=types[named], holder=_namespace_of(named), named_type=named)
    return Resolved(declaration=declaration, content=declaration, holder=namespace, named_type=named)


def type_only(*, element_namespace: str, named: str, types: dict[str, Any]) -> Resolved:
    """An element no declaration holds (a wildcard admits it) assessed by the type it names: a variant the
    definition writes, or a built-in type. Any other named type is not in the definition (`TYPES` holds variants)."""
    declaration = {'namespace': {'uri': element_namespace}}
    if named in types:
        return Resolved(declaration=declaration, content=types[named], holder=_namespace_of(named), named_type=named)
    if named.startswith('{' + XS + '}') and named != f'{{{XS}}}anyType':
        return Resolved(declaration=declaration, content=_builtin(named), holder=element_namespace, named_type=named)
    raise UnresolvedType(named)


def _builtin(named: str) -> dict[str, Any]:
    """A built-in simple type's content: its text, no attribute, no child."""
    return {
        'attributes': {'sequence': [], 'details': {}},
        'children': {'sequence': [], 'details': {}},
        'textContent': {'type': {'builtin': named[len(XS) + 2 :]}},
    }


def _namespace_of(named: str) -> str:
    return named[1 : named.index('}')] if named.startswith('{') else ''


class UnresolvedType(Exception):
    """A type an element no declaration holds names, that the definition does not write (or a prefix not bound)."""


def named_type(element: Any) -> str | None:
    """The Clark name of the type an element names with xsi:type, its prefix resolved where it is in scope."""
    value = element.get(f'{{{XSI}}}type')
    if value is None:
        return None
    value = value.strip()
    prefix, _, local = value.rpartition(':')
    namespace = element.nsmap.get(prefix or None)
    if prefix and namespace is None:
        raise UnresolvedType(value)
    return f'{{{namespace}}}{local}' if namespace else local
