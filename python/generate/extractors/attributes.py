"""Extract attributes from an XSD element."""
from typing import Any

from generate.extractors.facets import extract_facets
from generate.extractors.namespace import extract_attr_namespace
from generate.helpers import local_name
from generate.ir import AttributeDef, Namespace

# W3C XML namespace attrs (xml:base, xml:lang, xml:space, xml:id, etc.) are
# implicitly valid on every XML element and have no meaning in IEC schemas.
_XML_NS_URI = 'http://www.w3.org/XML/1998/namespace'


def extract_attributes(xsd_elem: Any) -> tuple[list[str], bool, dict[str, AttributeDef]]:
    """Extract attributes from an XSD element.

    Uses qualify-on-collision keying: bare local name by default; a namespace-prefixed
    key (``prefix:local``) only when two or more attributes on the same element share
    the same local name (e.g. SCL ``version`` and 6-100 ``version``).

    Returns:
        (attr_sequence, has_any_attribute, attribute_details)

    xmlschema API:
      XsdElement.attributes: XsdAttributeGroup (dict-like, name → XsdAttribute)
      XsdAttribute.use: str ('optional' | 'required' | 'prohibited')
      XsdAttribute.default: str | None
      XsdAttribute.fixed: str | None
      XsdAttribute.type: XsdSimpleType
      XsdAttributeGroup[attr_name]: XsdAttribute

      Wildcards:
      XsdElement.attributes.wildcard → XsdAnyAttribute | None (xs:anyAttribute)
    """
    sequence: list[str] = []
    details: dict[str, AttributeDef] = {}
    any_attr = False

    attributes = getattr(xsd_elem, 'attributes', None)
    if attributes is None:
        return sequence, any_attr, details

    # Pass 1: collect raw (local_name, namespace, xsd_attr) for collision detection
    raw: list[tuple[str, Namespace | None, Any]] = []
    for attr_name, xsd_attr in attributes.items():
        if attr_name is None:
            continue
        ns = extract_attr_namespace(xsd_attr)
        if ns and ns.uri == _XML_NS_URI:
            continue  # skip W3C XML namespace attrs (xml:base, xml:lang, xml:space, xml:id)
        raw.append((local_name(attr_name), ns, xsd_attr))

    # Detect local-name collisions
    local_count: dict[str, int] = {}
    for ln, _, _ in raw:
        local_count[ln] = local_count.get(ln, 0) + 1
    collision_locals = {ln for ln, cnt in local_count.items() if cnt > 1}

    # Pass 2: build keys and AttributeDefs
    for ln, ns, xsd_attr in raw:
        key = f'{ns.prefix}:{ln}' if (ln in collision_locals and ns and ns.prefix) else ln

        fixed = getattr(xsd_attr, 'fixed', None)
        default = getattr(xsd_attr, 'default', None) if fixed is None else None
        use = getattr(xsd_attr, 'use', 'optional')
        attr_type = getattr(xsd_attr, 'type', None)

        details[key] = AttributeDef(
            required=use == 'required',
            default=default,
            fixed=fixed,
            namespace=ns,
            facets=extract_facets(attr_type),
        )
        sequence.append(key)

    sequence.sort()

    # Check xs:anyAttribute
    wildcard = getattr(attributes, 'wildcard', None)
    any_attr = wildcard is not None

    return sequence, any_attr, details
