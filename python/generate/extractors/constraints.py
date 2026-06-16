"""Extract identity constraints (xs:unique, xs:key, xs:keyref) from XSD elements."""
from typing import Any

from generate.helpers import local_name
from generate.ir import IdentityConstraint
from generate.xpath_parser import parse_field, parse_selector
def extract_constraints(xsd_elem: Any) -> list[IdentityConstraint]:
    """Extract identity constraints from an XSD element.

    Tries compiled constraint objects first, then raw XML fallback.

    xmlschema API (compiled path):
      XsdElement.identities: dict[str, XsdIdentity] — keys/uniques/keyrefs
        XsdIdentity.selector: XsdSelector
          XsdSelector.path: str
        XsdIdentity.fields: list[XsdFieldSelector]
          XsdFieldSelector.path: str
        XsdUnique, XsdKey, XsdKeyref — subclasses
        XsdKeyref.refer: XsdKey | XsdUnique
          .refer.local_name: str

    xmlschema API (raw XML fallback):
      XsdElement.elem: Element — raw lxml/ET element
      Scan for xs:key, xs:unique, xs:keyref tags
    """
    constraints: list[IdentityConstraint] = []
    seen: set[tuple[str, str]] = set()

    # Try compiled identities
    for ic in _iter_identity_constraints(xsd_elem):
        kind = _classify_constraint(ic)
        if kind is None:
            continue

        name = getattr(ic, 'name', '') or ''
        # Use local_name if it's a Clark QName
        if name.startswith('{'):
            name = local_name(name)

        sig = (kind, name)
        if sig in seen:
            continue
        seen.add(sig)

        selector_xpath = _get_selector_path(ic)
        field_xpaths = _get_field_paths(ic)

        selector_paths = parse_selector(selector_xpath)
        field_paths = [parse_field(fp) for fp in field_xpaths]

        refer = None
        if kind == 'keyref':
            refer = _get_refer_name(ic)

        constraints.append(IdentityConstraint(
            kind=kind,
            name=name,
            selector=selector_paths,
            fields=field_paths,
            deep='//' in (selector_xpath or ''),
            refer=refer,
        ))

    return constraints
# --- Internal helpers ---
def _iter_identity_constraints(xsd_elem: Any):
    """Yield identity constraint objects from an element.

    Checks multiple container shapes that xmlschema uses:
      - .identities dict
      - .identity_constraints dict
      - .keys, .uniques, .keyrefs dicts/lists
    """
    # Preferred: .identities (xmlschema v2+)
    identities = getattr(xsd_elem, 'identities', None)
    if identities:
        if hasattr(identities, 'values'):
            yield from identities.values()
        else:
            yield from identities
        return

    # Alternative: .identity_constraints
    ic_map = getattr(xsd_elem, 'identity_constraints', None)
    if ic_map:
        if hasattr(ic_map, 'values'):
            yield from ic_map.values()
        else:
            yield from ic_map
        return

    # Separate containers
    for attr_name in ('keys', 'uniques', 'keyrefs'):
        container = getattr(xsd_elem, attr_name, None)
        if container:
            if hasattr(container, 'values'):
                yield from container.values()
            else:
                yield from container
def _classify_constraint(ic: Any) -> str | None:
    """Determine if an identity constraint is 'unique', 'key', or 'keyref'."""
    # Category attribute
    category = getattr(ic, 'category', None)
    if category:
        cat = str(category).lower()
        if 'key' in cat and 'ref' in cat:
            return 'keyref'
        if 'key' in cat:
            return 'key'
        if 'unique' in cat:
            return 'unique'

    # Class name fallback
    cls_name = type(ic).__name__.lower()
    if 'keyref' in cls_name:
        return 'keyref'
    if 'key' in cls_name:
        return 'key'
    if 'unique' in cls_name:
        return 'unique'

    return None
def _get_selector_path(ic: Any) -> str:
    """Get XPath selector path from a constraint."""
    selector = getattr(ic, 'selector', None)
    if selector is None:
        return ''
    path = getattr(selector, 'path', None)
    if path:
        return str(path)
    # Fallback: selector might be string itself
    return str(selector) if selector else ''
def _get_field_paths(ic: Any) -> list[str]:
    """Get XPath field paths from a constraint."""
    fields = getattr(ic, 'fields', None)
    if not fields:
        return []
    result = []
    for f in fields:
        path = getattr(f, 'path', None)
        if path:
            result.append(str(path))
        elif isinstance(f, str):
            result.append(f)
    return result
def _get_refer_name(ic: Any) -> str | None:
    """Get the name of the referred key/unique for a keyref constraint."""
    refer = getattr(ic, 'refer', None)
    if refer is None:
        return None
    name = getattr(refer, 'local_name', None) or getattr(refer, 'name', None)
    if name:
        return local_name(str(name))
    return str(refer)
