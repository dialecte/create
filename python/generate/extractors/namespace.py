"""Extract Namespace from an XSD element."""
from typing import Any

from generate.helpers import local_name, namespace_uri
from generate.ir import Namespace
def extract_namespace(xsd_elem: Any) -> Namespace:
    """Build a Namespace from an XsdElement.

    Uses:
      - xsd_elem.target_namespace → URI
      - xsd_elem.schema.namespaces → prefix lookup
      - xsd_elem.prefixed_name fallback

    xmlschema API:
      XsdComponent.target_namespace: str
      XMLSchemaBase.namespaces: dict[str, str] (prefix → uri)
    """
    uri = getattr(xsd_elem, 'target_namespace', '') or ''
    prefix = _resolve_prefix(xsd_elem, uri)
    return Namespace(prefix=prefix, uri=uri)
def extract_attr_namespace(xsd_attr: Any) -> Namespace | None:
    """Build a Namespace for an XsdAttribute, or None if it's in the element's own namespace.

    A namespace-qualified attribute has a non-empty target_namespace that differs
    from its parent element's target_namespace.

    xmlschema API:
      XsdAttribute.target_namespace: str
      XsdAttribute.qualified: bool
      XsdAttribute.name: str (Clark notation '{uri}local')
    """
    name = getattr(xsd_attr, 'name', '') or ''
    attr_ns = namespace_uri(name)

    if not attr_ns:
        return None

    uri = attr_ns
    prefix = _resolve_prefix(xsd_attr, uri)
    if not prefix:
        return None
    return Namespace(prefix=prefix, uri=uri)
def _resolve_prefix(component: Any, uri: str) -> str:
    """Find the prefix for a namespace URI by walking up to the schema's namespace map."""
    if not uri:
        return ''

    schema = getattr(component, 'schema', None)
    if schema is None:
        return ''

    namespaces = getattr(schema, 'namespaces', {}) or {}
    for pfx, ns_uri in namespaces.items():
        if ns_uri == uri and not pfx:
            return ''
    for pfx, ns_uri in namespaces.items():
        if ns_uri == uri and pfx:
            return pfx
    return ''
