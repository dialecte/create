"""Extract attributes from an XSD element."""
from typing import Any

from generate.extractors.facets import extract_facets
from generate.extractors.namespace import extract_attr_namespace
from generate.helpers import local_name
from generate.ir import AttributeDef

# W3C XML namespace attrs (xml:base, xml:lang, xml:space, xml:id, etc.) are
# implicitly valid on every XML element and have no meaning in IEC schemas.
_XML_NS_URI = 'http://www.w3.org/XML/1998/namespace'


def extract_attributes(xsd_elem: Any) -> tuple[list[str], bool, dict[str, AttributeDef]]:
    """Extract attributes from an XSD element.

    Keying follows two rules, so a name is predictable without knowing an element's other
    attributes:
      - an attribute in the element's own (default) namespace is keyed by its bare local name;
      - any non-default-namespace attribute is always keyed ``prefix:local``
        (e.g. ``eIEC61850-6-100:version``, ``xsi:type``) — regardless of collision.

    A prefixed non-default name can never clash with a bare default name, so this is
    collision-safe by construction.

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

    for attr_name, xsd_attr in attributes.items():
        if attr_name is None:
            continue
        ns = extract_attr_namespace(xsd_attr)
        if ns and ns.uri == _XML_NS_URI:
            continue  # skip W3C XML namespace attrs (xml:base, xml:lang, xml:space, xml:id)

        ln = local_name(attr_name)
        # Default namespace → bare local; any non-default namespace → always prefixed.
        key = f'{ns.prefix}:{ln}' if (ns and ns.prefix) else ln

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
