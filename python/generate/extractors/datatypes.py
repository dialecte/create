"""Extract what a simple type IS: the XSD built-in it bottoms out in, as a list or a union or not."""
from typing import Any

from generate.extractors.facets import _collect_facets_from_type
from generate.ir import DataType, Facets

BUILTIN_CLASS = 'XsdAtomicBuiltin'


def extract_datatype(xsd_type: Any) -> DataType | None:
    """The datatype of a simple type, or None when there is nothing to tell: a plain string.

    xmlschema API:
      XsdAtomicBuiltin.local_name: the built-in's name
      XsdAtomicRestriction.base_type: the type it restricts
      XsdList.item_type, XsdUnion.member_types
      a restriction of a list or a union has the list/union as base_type
    """
    datatype = _resolve(xsd_type, set())
    if datatype is None:
        return None
    # a string, restricted or not, is what a value is by default; its facets are on the attribute
    if datatype.kind == 'atomic' and datatype.builtin == 'string':
        return None
    return datatype


def _resolve(xsd_type: Any, visited: set[int]) -> DataType | None:
    facets = Facets()
    current = xsd_type
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        # the built-in's own facets are what the name says: not repeated
        if type(current).__name__ == BUILTIN_CLASS:
            name = getattr(current, 'local_name', None)
            if name is None or name == 'anySimpleType':
                return None
            return DataType(kind='atomic', builtin=name, facets=_or_none(facets))
        _collect_facets_from_type(current, facets)
        item_type = getattr(current, 'item_type', None)
        if item_type is not None:
            return DataType(kind='list', item=_resolve(item_type, visited), facets=_or_none(facets))
        member_types = getattr(current, 'member_types', None)
        if member_types:
            members = [_resolve(member, set(visited)) for member in member_types]
            return DataType(kind='union', members=[m for m in members if m is not None], facets=_or_none(facets))
        current = getattr(current, 'base_type', None)
    return None


def _or_none(facets: Facets) -> Facets | None:
    return None if facets.is_empty() else facets
