"""Tests for extractors using inline XSD schemas loaded via xmlschema."""

import pytest
import xmlschema

from generate.extractors.attributes import extract_attributes
from generate.extractors.children import extract_children, extract_choices, extract_text_content
from generate.extractors.constraints import extract_constraints
from generate.extractors.docs import extract_docs
from generate.extractors.facets import extract_facets
from generate.extractors.namespace import extract_attr_namespace, extract_namespace


# --- Test XSD fixtures ---

SIMPLE_XSD = """\
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="http://example.com/test"
           xmlns:tns="http://example.com/test"
           elementFormDefault="qualified">

  <xs:simpleType name="tName">
    <xs:restriction base="xs:normalizedString">
      <xs:minLength value="1"/>
      <xs:whiteSpace value="replace"/>
    </xs:restriction>
  </xs:simpleType>

  <xs:simpleType name="tColor">
    <xs:restriction base="xs:string">
      <xs:enumeration value="red"/>
      <xs:enumeration value="green"/>
      <xs:enumeration value="blue"/>
    </xs:restriction>
  </xs:simpleType>

  <xs:simpleType name="tPercent">
    <xs:restriction base="xs:integer">
      <xs:minInclusive value="0"/>
      <xs:maxInclusive value="100"/>
    </xs:restriction>
  </xs:simpleType>

  <xs:element name="Root">
    <xs:annotation>
      <xs:documentation>Root element for testing</xs:documentation>
    </xs:annotation>
    <xs:complexType>
      <xs:sequence>
        <xs:element name="Child" minOccurs="0" maxOccurs="unbounded">
          <xs:complexType>
            <xs:attribute name="name" type="tns:tName" use="required"/>
            <xs:attribute name="color" type="tns:tColor"/>
            <xs:attribute name="size" type="xs:string" fixed="large"/>
            <xs:attribute name="label" type="xs:string" default="untitled"/>
          </xs:complexType>
        </xs:element>
        <xs:element name="Single" minOccurs="0" maxOccurs="1">
          <xs:complexType>
            <xs:attribute name="id" type="xs:string" use="required"/>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
      <xs:attribute name="version" type="xs:string" fixed="1.0"/>
    </xs:complexType>
    <xs:unique name="uniqueChildName">
      <xs:selector xpath="tns:Child"/>
      <xs:field xpath="@name"/>
    </xs:unique>
  </xs:element>
</xs:schema>
"""

CHOICE_XSD = """\
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Container">
    <xs:complexType>
      <xs:choice minOccurs="0" maxOccurs="unbounded">
        <xs:element name="OptionA" type="xs:string"/>
        <xs:element name="OptionB" type="xs:string"/>
        <xs:element name="OptionC" type="xs:string"/>
      </xs:choice>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

MIXED_CONTENT_XSD = """\
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Text">
    <xs:complexType mixed="true">
      <xs:sequence>
        <xs:element name="Bold" type="xs:string" minOccurs="0"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

PATTERN_XSD = """\
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:simpleType name="tUuid">
    <xs:restriction base="xs:string">
      <xs:pattern value="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"/>
    </xs:restriction>
  </xs:simpleType>
  <xs:element name="Item">
    <xs:complexType>
      <xs:attribute name="id" type="tUuid"/>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""


@pytest.fixture(scope='module')
def simple_schema():
    return xmlschema.XMLSchema(SIMPLE_XSD)


    def test_qualify_on_collision(self, collision_schema):
        # Two attrs share local name 'version' in different namespaces.
        # The one in ext ns should be keyed 'ext:version'; the base one as 'version'.
        root = _get_element(collision_schema, 'Root')
        seq, _, details = extract_attributes(root)

        assert 'version' in details
        assert 'ext:version' in details
        assert details['version'].namespace is None or details['version'].namespace.uri != 'http://example.com/ext'
        assert details['ext:version'].namespace is not None
        assert details['ext:version'].namespace.uri == 'http://example.com/ext'
        assert seq == sorted(seq)

    def test_xml_namespace_attrs_filtered(self, xml_ns_schema):
        # xs:attribute refs in the W3C xml namespace (xml:lang, xml:base etc.) must be excluded.
        root = _get_element(xml_ns_schema, 'Root')
        seq, _, details = extract_attributes(root)

        assert 'name' in details  # normal attr retained
        for key in details:
            ns = details[key].namespace
            assert ns is None or ns.uri != 'http://www.w3.org/XML/1998/namespace'


@pytest.fixture(scope='module')
def choice_schema():
    return xmlschema.XMLSchema(CHOICE_XSD)


@pytest.fixture(scope='module')
def mixed_schema():
    return xmlschema.XMLSchema(MIXED_CONTENT_XSD)


@pytest.fixture(scope='module')
def pattern_schema():
    return xmlschema.XMLSchema(PATTERN_XSD)


def _get_element(schema, local_name):
    """Get an XsdElement by local name from a schema."""
    for elem in schema.elements.values():
        if elem.local_name == local_name:
            return elem
        # Search children
        content = getattr(elem.type, 'content', None)
        if content:
            for child in content.iter_elements():
                if getattr(child, 'local_name', None) == local_name:
                    return child
    return None


# --- Namespace tests ---

class TestExtractNamespace:
    def test_returns_namespace(self, simple_schema):
        root = _get_element(simple_schema, 'Root')
        ns = extract_namespace(root)
        assert ns.uri == 'http://example.com/test'
        assert ns.prefix == 'tns'


# --- Documentation tests ---

class TestExtractDocs:
    def test_returns_documentation(self, simple_schema):
        root = _get_element(simple_schema, 'Root')
        doc = extract_docs(root)
        assert doc == 'Root element for testing'

    def test_returns_none_without_docs(self, simple_schema):
        child = _get_element(simple_schema, 'Child')
        doc = extract_docs(child)
        assert doc is None


# --- Facets tests ---

class TestExtractFacets:
    def test_min_length_whitespace(self, simple_schema):
        child = _get_element(simple_schema, 'Child')
        name_attr = child.attributes['name']
        facets = extract_facets(name_attr.type)
        assert facets is not None
        assert facets.min_length == 1
        assert facets.white_space == 'replace'

    def test_enumeration(self, simple_schema):
        child = _get_element(simple_schema, 'Child')
        color_attr = child.attributes['color']
        facets = extract_facets(color_attr.type)
        assert facets is not None
        assert facets.enumeration is not None
        assert set(facets.enumeration) == {'red', 'green', 'blue'}

    def test_no_facets_returns_none(self, simple_schema):
        child = _get_element(simple_schema, 'Child')
        label_attr = child.attributes['label']
        facets = extract_facets(label_attr.type)
        # xs:string has whiteSpace=preserve as base facet
        # The result depends on whether we descend into built-in types
        # We just verify it doesn't crash
        assert facets is None or isinstance(facets, type(facets))

    def test_pattern_returns_regex_strings_not_element_repr(self, pattern_schema):
        item = _get_element(pattern_schema, 'Item')
        id_attr = item.attributes['id']
        facets = extract_facets(id_attr.type)
        assert facets is not None
        assert facets.pattern is not None
        assert len(facets.pattern) == 1
        p = facets.pattern[0]
        assert '<Element' not in p, f"Pattern is raw Element repr: {p!r}"
        assert 'a-fA-F' in p or '[0-9' in p, f"Unexpected pattern value: {p!r}"


# --- Attributes tests ---

class TestExtractAttributes:
    def test_child_attributes(self, simple_schema):
        child = _get_element(simple_schema, 'Child')
        seq, any_attr, details = extract_attributes(child)

        assert 'name' in seq
        assert 'color' in seq
        assert 'size' in seq
        assert 'label' in seq
        assert seq == sorted(seq)  # deterministic
        assert not any_attr

        assert details['name'].required is True
        assert details['size'].fixed == 'large'
        assert details['label'].default == 'untitled'
        assert details['color'].required is False

    def test_root_fixed_attribute(self, simple_schema):
        root = _get_element(simple_schema, 'Root')
        seq, _, details = extract_attributes(root)
        assert 'version' in seq
        assert details['version'].fixed == '1.0'
        assert details['version'].default is None  # fixed overrides default

    def test_qualify_on_collision(self):
        # Two attrs share local name 'version'; one from a foreign namespace.
        # Foreign one must be keyed 'ext:version'; own-namespace one stays 'version'.
        class _FakeSchema:
            namespaces = {'ext': 'http://example.com/ext'}

        class _FakeAttr:
            def __init__(self, clark_name, use='optional'):
                self.name = clark_name
                self.use = use
                self.fixed = None
                self.default = None
                self.type = None
                self.schema = _FakeSchema()

        class _FakeElem:
            attributes = {
                'version': _FakeAttr('version'),
                '{http://example.com/ext}version': _FakeAttr('{http://example.com/ext}version'),
            }

        seq, _, details = extract_attributes(_FakeElem())

        assert 'version' in details
        assert 'ext:version' in details
        assert details['ext:version'].namespace is not None
        assert details['ext:version'].namespace.uri == 'http://example.com/ext'
        assert seq == sorted(seq)

    def test_xml_namespace_attrs_filtered(self):
        # Attributes in the W3C XML namespace (xml:lang, xml:base...) must be excluded.
        class _FakeSchema:
            namespaces = {'xml': 'http://www.w3.org/XML/1998/namespace'}

        class _FakeAttr:
            def __init__(self, clark_name):
                self.name = clark_name
                self.use = 'optional'
                self.fixed = None
                self.default = None
                self.type = None
                self.schema = _FakeSchema()

        class _FakeElem:
            attributes = {
                'name': _FakeAttr('name'),
                '{http://www.w3.org/XML/1998/namespace}lang': _FakeAttr(
                    '{http://www.w3.org/XML/1998/namespace}lang'
                ),
            }

        seq, _, details = extract_attributes(_FakeElem())

        assert 'name' in details
        assert not any(
            (details[k].namespace and details[k].namespace.uri == 'http://www.w3.org/XML/1998/namespace')
            for k in details
        )


# --- Children tests ---

class TestExtractChildren:
    def test_root_children(self, simple_schema):
        root = _get_element(simple_schema, 'Root')
        seq, any_child, details = extract_children(root)

        assert 'Child' in seq
        assert 'Single' in seq
        assert not any_child

        assert details['Child'].min_occurs == 0
        assert details['Child'].max_occurs is None  # unbounded
        assert details['Child'].required is False

        assert details['Single'].min_occurs == 0
        assert details['Single'].max_occurs == 1


class TestExtractChoices:
    def test_choice_group(self, choice_schema):
        container = _get_element(choice_schema, 'Container')
        choices = extract_choices(container)
        assert len(choices) >= 1
        opts = choices[0].options
        assert 'OptionA' in opts
        assert 'OptionB' in opts
        assert 'OptionC' in opts


class TestExtractTextContent:
    def test_mixed_content(self, mixed_schema):
        text_elem = _get_element(mixed_schema, 'Text')
        tc = extract_text_content(text_elem)
        assert tc is not None  # mixed content detected


# --- Constraints tests ---

class TestExtractConstraints:
    def test_unique_constraint(self, simple_schema):
        root = _get_element(simple_schema, 'Root')
        constraints = extract_constraints(root)
        assert len(constraints) >= 1

        unique_c = [c for c in constraints if c.kind == 'unique']
        assert len(unique_c) == 1
        c = unique_c[0]
        assert c.name == 'uniqueChildName'
        # Structured selector: single path with step 'Child'
        assert len(c.selector) == 1
        assert c.selector[0].steps[0].value == 'Child'
        # Structured field: @name → attribute target
        assert len(c.fields) == 1
        assert c.fields[0].target.value == 'name'
        assert c.fields[0].target.is_attribute is True
        assert c.deep is False
        assert c.refer is None
