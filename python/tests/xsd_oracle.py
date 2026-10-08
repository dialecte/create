"""What a conformant XSD validator (libxml2, through lxml) says about a value, for tests to compare with."""
from xml.sax.saxutils import quoteattr

from lxml import etree


def xsd_accepts(simple_type: str, value: str) -> bool:
    """Whether `value` is valid for an attribute of the anonymous simple type `simple_type`.

    `simple_type` is the body of an `<xs:simpleType>` (a restriction, a list, a union), written with the
    `xs` prefix; libxml2 compiles it and judges the value.
    """
    schema = etree.XMLSchema(
        etree.fromstring(
            '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
            '<xs:element name="probe"><xs:complexType><xs:attribute name="value" use="required">'
            f'<xs:simpleType>{simple_type}</xs:simpleType>'
            '</xs:attribute></xs:complexType></xs:element></xs:schema>'
        )
    )
    return schema.validate(etree.fromstring(f'<probe value={quoteattr(value)}/>'))
