"""Tests for collector walk order and namespace resolution.

Covers the case where an extension schema (elementFormDefault="qualified")
declares a local element with the same name as a standard element from an
imported schema, using the imported type (e.g. <xs:element name="LNode"
type="scl:tLNode"/>). The collector must assign the standard namespace to
that element, not the extension namespace.
"""

import textwrap

import pytest
import xmlschema

from generate.collector import collect


# ── XSD fixtures ──────────────────────────────────────────────────────────────

BASE_XSD = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
               xmlns:base="http://example.com/base"
               targetNamespace="http://example.com/base"
               elementFormDefault="qualified">

      <xs:complexType name="tWidget">
        <xs:attribute name="id" type="xs:string" use="required"/>
      </xs:complexType>

      <!-- Widget is a global element in the base schema -->
      <xs:element name="Widget" type="base:tWidget"/>

      <!-- Container holds Widget children -->
      <xs:element name="Container">
        <xs:complexType>
          <xs:sequence>
            <xs:element ref="base:Widget" minOccurs="0" maxOccurs="unbounded"/>
          </xs:sequence>
          <xs:attribute name="name" type="xs:string" use="required"/>
        </xs:complexType>
      </xs:element>
    </xs:schema>
""")

EXTENSION_XSD = textwrap.dedent("""\
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
               xmlns:ext="http://example.com/ext"
               xmlns:base="http://example.com/base"
               targetNamespace="http://example.com/ext"
               elementFormDefault="qualified">

      <xs:import namespace="http://example.com/base" schemaLocation="base.xsd"/>

      <!-- Local element reusing the base type — same name "Widget", different ns -->
      <xs:complexType name="tExtContainer">
        <xs:sequence>
          <xs:element name="Widget" type="base:tWidget"
                      minOccurs="0" maxOccurs="unbounded"/>
        </xs:sequence>
        <xs:attribute name="name" type="xs:string" use="required"/>
      </xs:complexType>

      <xs:element name="ExtContainer" type="ext:tExtContainer"/>
    </xs:schema>
""")


@pytest.fixture()
def schema(tmp_path):
    (tmp_path / "base.xsd").write_text(BASE_XSD)
    (tmp_path / "ext.xsd").write_text(EXTENSION_XSD)
    return xmlschema.XMLSchema(str(tmp_path / "ext.xsd"))


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_shared_element_gets_base_namespace(schema):
    """Widget exists in both schemas. Collector must register it with base namespace."""
    elements = collect(schema)
    assert "Widget" in elements
    ns = elements["Widget"].namespace
    assert ns.uri == "http://example.com/base", (
        f"Expected Widget to have base namespace, got: {ns.uri!r}"
    )
    assert ns.prefix == "base", (
        f"Expected Widget prefix 'base', got: {ns.prefix!r}"
    )


def test_shared_element_parent_links_include_both_parents(schema):
    """Widget should be a child of both Container (base) and ExtContainer (ext)."""
    elements = collect(schema)
    parents = elements["Widget"].parents
    assert "Container" in parents, f"Expected Container in parents, got: {parents}"
    assert "ExtContainer" in parents, f"Expected ExtContainer in parents, got: {parents}"


def test_extension_only_element_gets_ext_namespace(schema):
    """ExtContainer is only in the extension schema — must keep ext namespace."""
    elements = collect(schema)
    assert "ExtContainer" in elements
    ns = elements["ExtContainer"].namespace
    assert ns.uri == "http://example.com/ext", (
        f"Expected ExtContainer to have ext namespace, got: {ns.uri!r}"
    )


def test_base_only_element_gets_base_namespace(schema):
    """Container is only in the base schema — must keep base namespace."""
    elements = collect(schema)
    assert "Container" in elements
    ns = elements["Container"].namespace
    assert ns.uri == "http://example.com/base"
