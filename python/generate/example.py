"""The facts a scaffolded package's worked example is written with.

The scaffold writes them into the example, so a reader opens real element names instead of lookups:
the root, the first child it allows, and the attributes that child requires, each with a value the
schema accepts.
"""
from typing import Any

from generate.ir import AttributeDef, ElementDef

PLACEHOLDER_VALUE = 'hello-world'


def example_facts(elements: dict[str, ElementDef], root_element: str) -> dict[str, Any]:
    root = elements[root_element]
    child_name = next((name for name in root.child_sequence if name in elements), None)
    return {
        'root': {'name': root_element, 'namespaceUri': root.namespace.uri},
        'child': None if child_name is None else _child_facts(root, elements[child_name]),
    }


def _child_facts(root: ElementDef, child: ElementDef) -> dict[str, Any]:
    # the namespace the child has under the root: an edge may name another than the element's own
    edge_namespace = root.children[child.tag].namespace
    namespace = edge_namespace if edge_namespace is not None else child.namespace
    # as declared under the root, when the schema declares the child differently elsewhere
    declared = child.definitions_by_parent.get(root.tag, child)
    return {
        'name': child.tag,
        'namespaceUri': namespace.uri,
        'requiredAttributes': [
            {'name': name, 'value': _accepted_value(attribute)}
            for name in declared.attr_sequence
            # an attribute of another namespace is keyed `prefix:local`: left to code that knows it
            if (attribute := declared.attributes[name]).required and ':' not in name
        ],
    }


def _accepted_value(attribute: AttributeDef) -> str:
    """The fixed value, else the first enumerated value, else a placeholder. A required attribute has
    no default: XSD allows one only on an optional attribute."""
    if attribute.fixed is not None:
        return attribute.fixed
    enumeration = attribute.facets.enumeration if attribute.facets is not None else None
    return enumeration[0] if enumeration else PLACEHOLDER_VALUE
