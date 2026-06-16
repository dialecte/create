"""Extract facets (validation constraints) from an XSD type, walking the base type chain."""
from typing import Any

from generate.helpers import get_facet_value, local_name, xsd_pattern_to_js
from generate.ir import Facets
def extract_facets(xsd_type: Any) -> Facets | None:
    """Walk base type chain, collect all facets. Return None if empty.

    xmlschema API used:
      XsdSimpleType.facets: dict[str, XsdFacet]  — keyed by Clark-notation QName
      XsdSimpleType.enumeration: iterable of values
      XsdSimpleType.patterns: iterable of XsdPatternFacets
      XsdSimpleType.base_type: XsdSimpleType | XsdComplexType | None
      XsdFacet.value / .v / .min_value / .max_value — scalar facet value
      XsdPatternFacets — iterable, each has .regexps or str()
      XsdEnumerationFacets — iterable, each has .value or is str
    """
    if xsd_type is None:
        return None

    facets = Facets()
    visited: set[int] = set()
    queue: list[Any] = [xsd_type]

    while queue:
        current = queue.pop(0)
        if current is None or id(current) in visited:
            continue
        visited.add(id(current))

        _collect_facets_from_type(current, facets)

        # Walk base type chain
        base = getattr(current, 'base_type', None)
        if base is not None:
            queue.append(base)

        # Walk union member types
        member_types = getattr(current, 'member_types', None)
        if member_types:
            for mt in member_types:
                if mt is not None and id(mt) not in visited:
                    queue.append(mt)

        # Walk simple_type (for complexType with simpleContent)
        simple = getattr(current, 'simple_type', None)
        if simple is not None and id(simple) not in visited:
            queue.append(simple)

    return None if facets.is_empty() else facets
def _collect_facets_from_type(current: Any, facets: Facets) -> None:
    """Read facets dict from a single type level and populate the Facets dataclass."""
    raw_facets = getattr(current, 'facets', None)
    if not raw_facets:
        return

    # Ensure it's dict-like
    items = raw_facets.items() if hasattr(raw_facets, 'items') else []

    for name, facet in items:
        local = local_name(str(name))
        match local:
            case 'enumeration':
                new_enums = _extract_enumeration(current, facet)
                if new_enums:
                    if facets.enumeration is None:
                        facets.enumeration = new_enums
                    else:
                        existing = set(facets.enumeration)
                        facets.enumeration.extend(v for v in new_enums if v not in existing)
            case 'pattern':
                new_patterns = _extract_patterns(current, facet)
                if new_patterns:
                    if facets.pattern is None:
                        facets.pattern = new_patterns
                    else:
                        existing = set(facets.pattern)
                        facets.pattern.extend(p for p in new_patterns if p not in existing)
            case 'minLength':
                if facets.min_length is None:
                    facets.min_length = get_facet_value(facet)
            case 'maxLength':
                if facets.max_length is None:
                    facets.max_length = get_facet_value(facet)
            case 'length':
                if facets.length is None:
                    facets.length = get_facet_value(facet)
            case 'minInclusive':
                if facets.min_inclusive is None:
                    facets.min_inclusive = get_facet_value(facet)
            case 'maxInclusive':
                if facets.max_inclusive is None:
                    facets.max_inclusive = get_facet_value(facet)
            case 'minExclusive':
                if facets.min_exclusive is None:
                    facets.min_exclusive = get_facet_value(facet)
            case 'maxExclusive':
                if facets.max_exclusive is None:
                    facets.max_exclusive = get_facet_value(facet)
            case 'totalDigits':
                if facets.total_digits is None:
                    facets.total_digits = get_facet_value(facet)
            case 'fractionDigits':
                if facets.fraction_digits is None:
                    facets.fraction_digits = get_facet_value(facet)
            case 'whiteSpace':
                if facets.white_space is None:
                    facets.white_space = get_facet_value(facet)
def _extract_enumeration(xsd_type: Any, facet: Any) -> list[str]:
    """Extract enumeration values from a type or its facet object.

    xmlschema stores enumerations in multiple ways:
      - XsdSimpleType.enumeration → list of values directly
      - XsdEnumerationFacets → iterable, .values or .enumeration
      - Fallback: scan raw elem for xs:enumeration value=...
    """
    # Direct enumeration property on the type
    enum = getattr(xsd_type, 'enumeration', None)
    if enum:
        return [str(v) for v in enum]

    # Facet object approaches
    values = getattr(facet, 'values', None)
    if values:
        return [str(v) for v in values]

    enum_list = getattr(facet, 'enumeration', None)
    if enum_list:
        result = []
        for item in enum_list:
            v = getattr(item, 'value', None)
            result.append(str(v) if v is not None else str(item))
        return result

    # Raw XML fallback
    elem = getattr(xsd_type, 'elem', None)
    if elem is not None:
        result = []
        for child in elem.iter():
            tag = getattr(child, 'tag', '')
            if 'enumeration' in str(tag):
                val = child.get('value')
                if val is not None:
                    result.append(val)
        if result:
            return result

    return []
def _extract_patterns(xsd_type: Any, facet: Any) -> list[str]:
    """Extract regex pattern strings from a type or facet.

    xmlschema API:
      XsdPatternFacets.regexps: list[str] — the actual regex strings
      XsdSimpleType.patterns: XsdPatternFacets — same object as facet dict entry
    """
    # XsdPatternFacets (the facet dict entry) has .regexps with actual regex strings
    regexps = getattr(facet, 'regexps', None)
    if regexps:
        return [xsd_pattern_to_js(str(r)) for r in regexps]

    # Fallback: via type.patterns property (same object, different access path)
    patterns = getattr(xsd_type, 'patterns', None)
    if patterns:
        regexps = getattr(patterns, 'regexps', None)
        if regexps:
            return [xsd_pattern_to_js(str(r)) for r in regexps]

    return []
