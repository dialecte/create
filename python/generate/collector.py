"""Collector — recursive walk of XSD schema into ElementDef IR.

Phase 2 of the pipeline: Parse → **Collect** → Derive → Emit.
"""
import copy
from typing import Any

from generate.extractors.attributes import extract_attribute_model
from generate.extractors.children import extract_children, extract_text_content, iter_child_elements
from generate.extractors.constraints import extract_constraints
from generate.extractors.docs import extract_docs
from generate.extractors.namespace import extract_namespace
from generate.extractors.particles import extract_content_model
from generate.ir import AttributeDef, DataType, ElementDef, Particle
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
    # per element: what each declaration (type identity) declares - taken before the union of a
    # homonym widens the element - and which declaration each parent names
    declarations: dict[str, dict[int, ElementDef]] = {}
    parent_declaration: dict[str, dict[str, int]] = {}

    def walk(xsd_elem: Any, parent_name: str | None = None, visited: set[int] | None = None) -> None:
        if visited is None:
            visited = set()

        name = getattr(xsd_elem, 'local_name', None)
        if not name:
            return
        # an abstract element never appears in a document: only its substitutes do
        if getattr(xsd_elem, 'abstract', False):
            return

        identity = _type_identity(xsd_elem)

        # Already seen this element by tag name — always add parent link first,
        # then id-guard the recursion to prevent infinite loops.
        if name in elements:
            existing = elements[name]
            if parent_name and parent_name not in existing.parents:
                existing.parents.append(parent_name)
            if parent_name:
                parent_declaration[name][parent_name] = identity
            if identity not in declarations[name]:
                declarations[name][identity] = _merge_homonym(existing, xsd_elem)
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

        element = _extract_element(xsd_elem)
        declarations[name] = {identity: copy.deepcopy(element)}
        parent_declaration[name] = {parent_name: identity} if parent_name else {}

        if expander is not None:
            expander.expand(
                xsd_elem,
                element.attr_sequence,
                element.attributes,
                element.child_sequence,
                element.children,
            )

        element.parents = [parent_name] if parent_name else []
        elements[name] = element

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

    # A homonym keeps, per parent, the definition that parent names; each one lists its parents.
    for name, element in elements.items():
        if len(declarations[name]) <= 1:
            continue
        for parent, identity in sorted(parent_declaration[name].items()):
            declared = declarations[name].get(identity)
            if declared is None:
                continue
            declared.parents.append(parent)
            element.definitions_by_parent[parent] = declared

    return elements


def _type_identity(xsd_elem: Any) -> int:
    """What tells two declarations of a name apart: the type object they are declared with.

    A named type reused under several parents is the same object; an anonymous type is its own.
    """
    return id(getattr(xsd_elem, 'type', None))


def _extract_element(xsd_elem: Any) -> ElementDef:
    """One declaration of an element, as the schema wrote it, with no parent yet."""
    attr_seq, attr_any, attrs, attr_any_namespace = extract_attribute_model(xsd_elem)
    child_seq, child_any, children = extract_children(xsd_elem)
    return ElementDef(
        tag=xsd_elem.local_name,
        namespace=extract_namespace(xsd_elem),
        documentation=extract_docs(xsd_elem),
        attr_sequence=attr_seq,
        attr_any=attr_any,
        attr_any_namespace=attr_any_namespace,
        attributes=attrs,
        nillable=bool(getattr(xsd_elem, 'nillable', False)),
        child_sequence=child_seq,
        child_any=child_any,
        children=children,
        constraints=extract_constraints(xsd_elem),
        text_content=extract_text_content(xsd_elem),
        content_model=extract_content_model(xsd_elem),
    )


def _merge_homonym(existing: ElementDef, xsd_elem: Any) -> ElementDef:
    """Widen an element with a declaration of the same name that has another type.

    A dialecte knows an element by its tag, so both declarations become one element. Nothing a
    valid document may hold is dropped: attributes and children are the union, required only
    where every declaration requires it, occurrences the widest, text content kept if any
    declaration has it, the content models offered as a choice. Returns this declaration as its
    own definition, untouched by the union: `collect` writes it under each parent naming it, which
    is what makes the widening visible.
    """
    declared = _extract_element(xsd_elem)
    attr_seq, attr_any, attrs, attr_any_namespace = extract_attribute_model(xsd_elem)
    child_seq, child_any, children = extract_children(xsd_elem)
    existing.nillable = existing.nillable or declared.nillable

    for attr_name, attribute in attrs.items():
        if attr_name in existing.attributes:
            _widen_attribute(existing.attributes[attr_name], attribute)
        else:
            attribute.required = False
            existing.attributes[attr_name] = attribute
            existing.attr_sequence.append(attr_name)
    for attr_name in existing.attr_sequence:
        if attr_name not in attrs:
            existing.attributes[attr_name].required = False
    existing.attr_any = existing.attr_any or attr_any
    if attr_any_namespace:
        existing.attr_any_namespace = sorted(
            set(existing.attr_any_namespace or []) | set(attr_any_namespace)
        )

    for child_name, child in children.items():
        if child_name in existing.children:
            known = existing.children[child_name]
            known.required = known.required and child.required
            known.min_occurs = min(known.min_occurs, child.min_occurs)
            if known.max_occurs is not None:
                known.max_occurs = (
                    None if child.max_occurs is None else max(known.max_occurs, child.max_occurs)
                )
        else:
            child.required = False
            child.min_occurs = 0
            existing.children[child_name] = child
            existing.child_sequence.append(child_name)
    for child_name in existing.child_sequence:
        if child_name not in children:
            existing.children[child_name].required = False
            existing.children[child_name].min_occurs = 0
    existing.child_any = existing.child_any or child_any

    if existing.text_content is None:
        existing.text_content = extract_text_content(xsd_elem)

    # the content models cannot be merged: a document holds one declaration OR the other
    model = extract_content_model(xsd_elem)
    if model is not None:
        existing.content_model = _one_of(existing.content_model, model)
    return declared


def _widen_attribute(known: AttributeDef, other: AttributeDef) -> None:
    """An attribute declared by two declarations of one name: what either of them accepts."""
    known.required = known.required and other.required
    if known.fixed != other.fixed:
        known.fixed = None
    if known.default != other.default:
        known.default = None
    if known.type != other.type and other.type is not None:
        members = list(known.type.members or [known.type]) if known.type is not None else []
        members.extend(other.type.members or [other.type])
        known.type = DataType(kind='union', members=members)
    if other.facets is None:
        known.facets = None  # the other declaration restricts nothing
        return
    if known.facets is None:
        return
    a, b = known.facets, other.facets
    a.enumeration = _either(a.enumeration, b.enumeration)
    a.pattern = _either(a.pattern, b.pattern)
    a.min_length = _widest(a.min_length, b.min_length, min)
    a.min_inclusive = _widest(a.min_inclusive, b.min_inclusive, min)
    a.min_exclusive = _widest(a.min_exclusive, b.min_exclusive, min)
    a.max_length = _widest(a.max_length, b.max_length, max)
    a.max_inclusive = _widest(a.max_inclusive, b.max_inclusive, max)
    a.max_exclusive = _widest(a.max_exclusive, b.max_exclusive, max)
    a.length = a.length if a.length == b.length else None
    a.total_digits = _widest(a.total_digits, b.total_digits, max)
    a.fraction_digits = _widest(a.fraction_digits, b.fraction_digits, max)
    a.white_space = a.white_space if a.white_space == b.white_space else None


def _either(a: list | None, b: list | None) -> list | None:
    """Both lists of allowed values, each value once; None when either side allows anything."""
    if a is None or b is None:
        return None
    return list(dict.fromkeys([*a, *b]))


def _widest(a, b, pick):
    """The looser of two bounds; None when either side has none."""
    if a is None or b is None:
        return None
    try:
        return pick(a, b)
    except TypeError:
        return None


def _one_of(known: Particle | None, other: Particle) -> Particle:
    """A choice between the content models of two declarations of one name."""
    if known is None:
        return other
    if known.of_declarations and known.particles is not None:
        known.particles.append(other)
        return known
    return Particle(kind='choice', particles=[known, other], of_declarations=True)


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
