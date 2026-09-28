"""Extract child elements and text content from an XSD element."""
from typing import Any

from generate.extractors.constraints import extract_constraints
from generate.extractors.datatypes import extract_datatype
from generate.extractors.facets import extract_facets
from generate.extractors.namespace import extract_namespace
from generate.ir import ChildDef, TextContent
def extract_children(xsd_elem: Any) -> tuple[list[str], bool, dict[str, ChildDef]]:
    """Extract child element definitions from an XSD element's content model.

    Returns:
        (child_sequence, has_any_element, child_details)

    xmlschema API:
      XsdElement.type: XsdComplexType
      XsdComplexType.content: XsdGroup (model group)
      XsdGroup.iter_elements() → Iterator[XsdElement | XsdAnyElement]
        Each yielded element has:
          .local_name: str
          .min_occurs: int
          .max_occurs: int | None
      Content wildcards:
      XsdGroup — may contain XsdAnyElement children
    """
    return _extract_children_from_content(_get_content_model(xsd_elem))
def extract_children_from_type(xsd_type: Any) -> tuple[list[str], bool, dict[str, ChildDef]]:
    """Like ``extract_children`` but reads a complex type's content model directly.

    Used by xsi:type expansion where children come from a substitutable type
    (selected via ``xsi:type``) rather than the element's own declared type.
    """
    return _extract_children_from_content(getattr(xsd_type, 'content', None))
def _extract_children_from_content(content: Any) -> tuple[list[str], bool, dict[str, ChildDef]]:
    """Shared core: extract child definitions from a content model (XsdGroup)."""
    sequence: list[str] = []
    details: dict[str, ChildDef] = {}
    any_child = False

    if content is None:
        return sequence, any_child, details

    seen_names: set[str] = set()

    for child, min_occ, max_occ in _iter_child_particles(content):
        # Check if it's a wildcard (xs:any)
        cls_name = type(child).__name__
        if 'Any' in cls_name and 'Element' in cls_name:
            any_child = True
            continue

        name = getattr(child, 'local_name', None)
        if not name:
            continue

        if name in seen_names:
            continue
        seen_names.add(name)

        sequence.append(name)
        details[name] = ChildDef(
            required=min_occ > 0,
            min_occurs=min_occ,
            max_occurs=max_occ,
            constraints=extract_constraints(child) or None,
            facets=None,  # Rare: child text content facets
            # Per-context: the child's declaring-schema namespace. The same local name
            # yields SCL under one type's content and 6-100 under another. Reduced to a
            # sparse override later (strip_canonical_child_namespaces).
            namespace=extract_namespace(child),
        )

    return sequence, any_child, details
def extract_text_content(xsd_elem: Any) -> TextContent | None:
    """Extract text content definition for elements with simple or mixed content.

    xmlschema API:
      XsdComplexType.has_simple_content() → bool
      XsdComplexType.mixed: bool
      XsdComplexType.content_type_label: str ('simple' | 'mixed' | 'element-only' | 'empty')
    """
    xsd_type = getattr(xsd_elem, 'type', None)
    if xsd_type is None:
        return None

    has_simple = False
    if callable(getattr(xsd_type, 'has_simple_content', None)):
        has_simple = xsd_type.has_simple_content()
    mixed = getattr(xsd_type, 'mixed', False)

    if not has_simple and not mixed:
        return None

    # Find the simple type to extract facets from
    facets_source = (
        getattr(xsd_type, 'content', None)
        or getattr(xsd_type, 'simple_type', None)
        or getattr(xsd_type, 'base_type', None)
    )

    facets = extract_facets(facets_source)
    fixed = getattr(xsd_elem, 'fixed', None)
    default = getattr(xsd_elem, 'default', None) if fixed is None else None
    return TextContent(
        facets=facets, type=extract_datatype(facets_source), default=default, fixed=fixed
    )
# --- Internal helpers ---
def _get_content_model(xsd_elem: Any) -> Any:
    """Get the content model (XsdGroup) from an element's type."""
    xsd_type = getattr(xsd_elem, 'type', None)
    if xsd_type is None:
        return None
    return getattr(xsd_type, 'content', None)
def _iter_child_particles(content: Any):
    """Iterate (element, min_occurs, max_occurs) from a content model, substitution groups resolved.

    A member of a substitution group may appear wherever its head may: the head particle stands
    for the head itself (unless abstract) and for every member, transitively. A member takes the
    occurrence of the head particle, since that is the slot it fills.

    xmlschema API:
      XsdGroup.iter_elements() → yields XsdElement | XsdAnyElement
      XsdElement.abstract: bool
      XsdElement.iter_substitutes() → concrete members, transitively
    """
    iter_fn = getattr(content, 'iter_elements', None)
    if not (iter_fn and callable(iter_fn)):
        return
    for particle in iter_fn():
        min_occ = getattr(particle, 'min_occurs', 0)
        max_occ = getattr(particle, 'max_occurs', None)
        if not getattr(particle, 'abstract', False):
            yield particle, min_occ, max_occ
        iter_substitutes = getattr(particle, 'iter_substitutes', None)
        if callable(iter_substitutes):
            # the members come as a set: sorted, so the output is the same on every run
            members = sorted(iter_substitutes(), key=lambda member: member.local_name or '')
            for member in members:
                yield member, min_occ, max_occ
def _iter_child_elements(content: Any):
    """Iterate child elements from a content model, substitution groups resolved."""
    for element, _min_occ, _max_occ in _iter_child_particles(content):
        yield element
def iter_child_elements(xsd_elem: Any):
    """Public helper: iterate XsdElement children of an element for recursive walking."""
    yield from _iter_named_child_elements(_get_content_model(xsd_elem))
def iter_type_child_elements(xsd_type: Any):
    """Public helper: iterate XsdElement children declared in a complex type's content."""
    yield from _iter_named_child_elements(getattr(xsd_type, 'content', None))
def _iter_named_child_elements(content: Any):
    """Iterate non-wildcard XsdElement children of a content model."""
    if content is None:
        return
    for child in _iter_child_elements(content):
        cls_name = type(child).__name__
        if 'Any' in cls_name and 'Element' in cls_name:
            continue
        yield child
