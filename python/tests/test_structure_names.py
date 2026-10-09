"""Which elements a dialecte has, which children each holds, which parents each has."""
from typing import Any

import pytest

from tests.conftest import TARGET, pick, schema

EXT = 'urn:dialecte:ext'
DEEP = 'urn:dialecte:deep'


def xsd(target: str, body: str, *, imports: str = '') -> str:
    return (
        f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{target}" targetNamespace="{target}" '
        f'elementFormDefault="qualified">{imports}{body}</xs:schema>'
    )


CASES: dict[str, tuple[str, dict[str, str], str, Any]] = {
    'local children in a sequence -> named in content order, each knowing its parent': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Zeta"/><xs:element name="Alpha"/></xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        '',
        {'Root.children.sequence': ['Zeta', 'Alpha'], 'Alpha.parents': ['Root'], 'Zeta.parents': ['Root']},
    ),
    'a reference to a global element, through a named group -> the global is the child': (
        schema(
            '<xs:group name="items"><xs:sequence><xs:element ref="Item"/></xs:sequence></xs:group>'
            '<xs:element name="Root"><xs:complexType><xs:group ref="items"/></xs:complexType></xs:element>'
            '<xs:element name="Item"/>'
        ),
        {},
        '',
        {'Root.children.sequence': ['Item'], 'Item.parents': ['Root'], 'Root.parents': []},
    ),
    'an abstract head with members, one a member of a member -> the members are the children, the head is no element': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Shape"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Shape" abstract="true"/>'
            '<xs:element name="Circle" substitutionGroup="Shape"/>'
            '<xs:element name="Square" substitutionGroup="Shape"/>'
            '<xs:element name="Box" substitutionGroup="Square"/>'
        ),
        {},
        '',
        {'Root.children.sequence': ['Box', 'Circle', 'Square'], 'Box.parents': ['Root'], '@tags': ['Box', 'Circle', 'Root', 'Square']},
    ),
    'an abstract element holding content, a member taking its type -> the member holds it, the abstract one is no element': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Shape"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Shape" abstract="true"><xs:complexType><xs:sequence><xs:element ref="Item"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Square" substitutionGroup="Shape"/>'
            '<xs:element name="Item"/>'
        ),
        {},
        '',
        {'Item.parents': ['Square'], '@tags': ['Item', 'Root', 'Square']},
    ),
    'a head that blocks substitution -> no member in its place': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Template"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Template" block="substitution"/>'
            '<xs:element name="NamedTemplate" substitutionGroup="Template"/>'
        ),
        {},
        '',
        {'Root.children.sequence': ['Template'], 'NamedTemplate.parents': []},
    ),
    'a concrete head with a member -> both are children': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Template"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Template"/><xs:element name="NamedTemplate" substitutionGroup="Template"/>'
        ),
        {},
        '',
        {'Root.children.sequence': ['Template', 'NamedTemplate']},
    ),
    'a child named twice in one sequence -> named once, at its first place': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element ref="Note"/><xs:element ref="Body"/><xs:element ref="Note"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Note"/><xs:element name="Body"/>'
        ),
        {},
        '',
        {'Root.children.sequence': ['Note', 'Body']},
    ),
    'an element wildcard -> names no child': (
        schema('<xs:element name="Root"><xs:complexType><xs:sequence><xs:any namespace="##other" processContents="lax"/></xs:sequence></xs:complexType></xs:element>'),
        {},
        '',
        {'Root.children.sequence': []},
    ),
    'an element that holds itself, and two that hold each other -> walked once, each its own parent': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element ref="Folder"/><xs:element ref="Section"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Folder"><xs:complexType><xs:sequence><xs:element ref="Folder" minOccurs="0"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Section"><xs:complexType><xs:sequence><xs:element ref="Para" minOccurs="0"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Para"><xs:complexType><xs:sequence><xs:element ref="Section" minOccurs="0"/></xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        '',
        {'Folder.parents': ['Folder', 'Root'], 'Section.parents': ['Para', 'Root'], 'Para.parents': ['Section']},
    ),
    'a global element only a schema imported by an imported schema declares -> an element of the dialecte': (
        xsd(TARGET, '<xs:element name="Root"/>', imports=f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'),
        {
            'ext.xsd': xsd(EXT, '<xs:element name="ExtOnly"/>', imports=f'<xs:import namespace="{DEEP}" schemaLocation="deep.xsd"/>'),
            'deep.xsd': xsd(DEEP, '<xs:element name="DeepOnly"/>'),
        },
        '',
        {'@tags': ['DeepOnly', 'ExtOnly', 'Root']},
    ),
    'a tag declared locally first, globally in another namespace later -> the global declaration\'s namespace': (
        # the entry's own namespace sorts before the other one, so the local Label is met first
        xsd(
            TARGET,
            '<xs:element name="Other"><xs:complexType><xs:sequence><xs:element name="Label"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="z:Label"/></xs:sequence></xs:complexType></xs:element>',
            imports='<xs:import namespace="urn:zzz" schemaLocation="zzz.xsd"/>',
        ).replace('<xs:schema ', '<xs:schema xmlns:z="urn:zzz" '),
        {'zzz.xsd': xsd('urn:zzz', '<xs:element name="Label"/>')},
        '',
        {'Label.namespace.uri': 'urn:zzz'},
    ),
    'a tag declared under two parents, each declaration documented -> the documentation met first in content order': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Left"><xs:complexType><xs:sequence><xs:element name="P">'
            '<xs:annotation><xs:documentation>under Left</xs:documentation></xs:annotation></xs:element></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Right"><xs:complexType><xs:sequence><xs:element name="P">'
            '<xs:annotation><xs:documentation>under Right</xs:documentation></xs:annotation></xs:element></xs:sequence></xs:complexType></xs:element>'
            '</xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        '',
        {'P.documentation': 'under Left'},
    ),
    'a local element named like a global substitution head -> no members in its place': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Shape"><xs:complexType/></xs:element></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Other"><xs:complexType><xs:sequence><xs:element ref="Shape"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Shape"/><xs:element name="Circle" substitutionGroup="Shape"/>'
        ),
        {},
        '',
        {'Root.children.sequence': ['Shape'], 'Other.children.sequence': ['Shape', 'Circle'], 'Circle.parents': ['Other']},
    ),
    'an unqualified local element -> in no namespace': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Plain" form="unqualified"/></xs:sequence></xs:complexType></xs:element>'
        ),
        {},
        '',
        {'Plain.namespace': {'prefix': '', 'uri': ''}},
    ),
    'an element declared in a document that binds its namespace only as a prefix -> that prefix': (
        xsd(TARGET, '<xs:element name="Root"/>', imports=f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>'),
        {'ext.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:scl="{EXT}" targetNamespace="{EXT}" elementFormDefault="qualified"><xs:element name="Kid"/></xs:schema>'},
        '',
        {'Kid.namespace': {'prefix': 'scl', 'uri': EXT}},
    ),
    'elements a schema declares in the XML Schema namespace -> elements of the dialecte': (
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="title"/></xs:schema>',
        {},
        '',
        {'@tags': ['title']},
    ),
    'an element of a simple type and one with simple content -> no children': (
        schema(
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Count"/><xs:element ref="Label"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Count" type="xs:int"/>'
            '<xs:element name="Label"><xs:complexType><xs:simpleContent><xs:extension base="xs:string">'
            '<xs:attribute name="lang" type="xs:language"/></xs:extension></xs:simpleContent></xs:complexType></xs:element>'
        ),
        {},
        '',
        {'Count.children.sequence': [], 'Label.children.sequence': [], 'Label.attributes.sequence': ['lang']},
    ),
    'substitution members in two namespaces -> sorted by their names': (
        xsd(
            TARGET,
            '<xs:element name="Root"><xs:complexType><xs:sequence><xs:element ref="Shape"/></xs:sequence></xs:complexType></xs:element>'
            '<xs:element name="Shape" abstract="true"/><xs:element name="Zigzag" substitutionGroup="Shape"/>',
            imports=f'<xs:import namespace="urn:aaa" schemaLocation="aaa.xsd"/>',
        ),
        {'aaa.xsd': f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:t="{TARGET}" targetNamespace="urn:aaa"><xs:import namespace="{TARGET}"/><xs:element name="Bar" substitutionGroup="t:Shape"/></xs:schema>'},
        '',
        {'Root.children.sequence': ['Bar', 'Zigzag']},
    ),
    'a first documentation left empty, a second one written -> the written one': (
        schema('<xs:element name="Root"><xs:annotation><xs:documentation>  </xs:documentation><xs:documentation>The root.</xs:documentation></xs:annotation></xs:element>'),
        {},
        '',
        {'Root.documentation': 'The root.'},
    ),
    'documentation holding markup -> its whole text': (
        schema('<xs:element name="Root"><xs:annotation><xs:documentation><p xmlns="http://www.w3.org/1999/xhtml">The <b>root</b></p> element.</xs:documentation></xs:annotation></xs:element>'),
        {},
        '',
        {'Root.documentation': 'The root element.'},
    ),
    # the globals are walked in namespace order, then name: urn:dialecte:ext's Holder before urn:dialecte:test's Root
    'a tag declared only locally, in two namespaces -> the namespace of the declaration walked first': (
        xsd(
            TARGET,
            '<xs:element name="Root"><xs:complexType><xs:sequence>'
            '<xs:element name="Label"/><xs:element ref="e:Holder"/></xs:sequence></xs:complexType></xs:element>',
            imports=f'<xs:import namespace="{EXT}" schemaLocation="ext.xsd"/>',
        ).replace('<xs:schema ', f'<xs:schema xmlns:e="{EXT}" '),
        {'ext.xsd': xsd(EXT, '<xs:element name="Holder"><xs:complexType><xs:sequence><xs:element name="Label"/></xs:sequence></xs:complexType></xs:element>')},
        '',
        {'Label.namespace.uri': EXT},
    ),
    'a documented declaration -> its first documentation text': (
        schema('<xs:element name="Root"><xs:annotation><xs:documentation>  The root.  </xs:documentation></xs:annotation></xs:element>'),
        {},
        '',
        {'Root.documentation': 'The root.'},
    ),
}


@pytest.mark.parametrize(('entry', 'imports', 'facts'), [(entry, imports, facts) for entry, imports, _, facts in CASES.values()], ids=CASES.keys())
def test_structure_names(definition_of, entry: str, imports: dict[str, str], facts: dict[str, Any]) -> None:
    """Each fact is a value at a path of the definition; `@tags` is the dialecte's element names."""
    data = definition_of(entry, imports=imports)
    actual = {path: sorted(data) if path == '@tags' else pick(data, path) for path in facts}
    assert actual == facts
