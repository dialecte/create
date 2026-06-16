"""Collector — recursive walk of XSD schema into ElementDef IR.

Phase 2 of the pipeline: Parse → **Collect** → Derive → Emit.
"""
from typing import Any

from generate.extractors.attributes import extract_attributes
from generate.extractors.children import extract_children, extract_choices, extract_text_content, iter_child_elements
from generate.extractors.constraints import extract_constraints
from generate.extractors.docs import extract_docs
from generate.extractors.namespace import extract_namespace
from generate.ir import ElementDef
from generate.xsi_type import XsiTypeExpander
def collect(schema: Any, expander: XsiTypeExpander | None = None) -> dict[str, ElementDef]:
    """Walk all elements across all schemas (root + imported/included) into a flat IR dict.

    When *expander* is provided, abstract-typed element slots are additionally enriched
    with their ``xsi:type`` substitution variants (children/attributes unioned in, and
    variant-only children walked for recursion). When omitted, behaviour is unchanged.

    xmlschema API:
      XMLSchemaBase.elements: NamespaceView — global elements of this schema
      XMLSchemaBase.includes: dict[str, XMLSchemaBase] — included schemas
      XMLSchemaBase.imports: dict[str, XMLSchemaBase | None] — imported schemas
    """
    elements: dict[str, ElementDef] = {}

    def walk(xsd_elem: Any, parent_name: str | None = None, visited: set[int] | None = None) -> None:
        if visited is None:
            visited = set()

        name = getattr(xsd_elem, 'local_name', None)
        if not name:
            return

        # Already seen this element by tag name — always add parent link first,
        # then id-guard the recursion to prevent infinite loops.
        if name in elements:
            existing = elements[name]
            if parent_name and parent_name not in existing.parents:
                existing.parents.append(parent_name)
            if expander is not None:
                expander.expand(
                    xsd_elem,
                    existing.attr_sequence,
                    existing.attributes,
                    existing.child_sequence,
                    existing.children,
                )
            elem_id = id(xsd_elem)
            if elem_id in visited:
                return
            visited.add(elem_id)
            # Still recurse into children to discover deeper elements
            for child_xsd in iter_child_elements(xsd_elem):
                walk(child_xsd, parent_name=name, visited=visited)
            if expander is not None:
                for child_xsd in expander.iter_variant_child_elements(xsd_elem):
                    walk(child_xsd, parent_name=name, visited=visited)
            return

        elem_id = id(xsd_elem)
        if elem_id in visited:
            return
        visited.add(elem_id)

        attr_seq, attr_any, attrs = extract_attributes(xsd_elem)
        child_seq, child_any, children = extract_children(xsd_elem)

        if expander is not None:
            expander.expand(xsd_elem, attr_seq, attrs, child_seq, children)

        elements[name] = ElementDef(
            tag=name,
            namespace=extract_namespace(xsd_elem),
            documentation=extract_docs(xsd_elem),
            parents=[parent_name] if parent_name else [],
            attr_sequence=attr_seq,
            attr_any=attr_any,
            attributes=attrs,
            child_sequence=child_seq,
            child_any=child_any,
            children=children,
            choices=extract_choices(xsd_elem),
            constraints=extract_constraints(xsd_elem),
            text_content=extract_text_content(xsd_elem),
        )

        for child_xsd in iter_child_elements(xsd_elem):
            walk(child_xsd, parent_name=name, visited=visited)
        if expander is not None:
            for child_xsd in expander.iter_variant_child_elements(xsd_elem):
                walk(child_xsd, parent_name=name, visited=visited)

    # Walk imported/included schemas FIRST so standard elements (e.g. scl:LNode)
    # are registered with their canonical namespace before the root extension
    # schema re-declares them as local elements (e.g. eIEC61850-6-100:LNode).
    for sub_schema in _iter_sub_schemas(schema):
        for root_elem in sub_schema.elements.values():
            walk(root_elem)

    # Walk root schema's global elements (adds extension elements + parent links)
    for root_elem in schema.elements.values():
        walk(root_elem)

    return elements
def _iter_sub_schemas(schema: Any):
    """Yield all imported and included schemas.

    xmlschema API:
      XMLSchemaBase.includes: dict[str, XMLSchemaBase]
      XMLSchemaBase.imports: dict[str, XMLSchemaBase | None]
    """
    seen: set[int] = set()

    includes = getattr(schema, 'includes', None) or {}
    if hasattr(includes, 'values'):
        for included in includes.values():
            if included is not None and id(included) not in seen:
                seen.add(id(included))
                yield included

    imports = getattr(schema, 'imports', None) or {}
    if hasattr(imports, 'values'):
        for imported in imports.values():
            if imported is not None and id(imported) not in seen:
                seen.add(id(imported))
                yield imported
