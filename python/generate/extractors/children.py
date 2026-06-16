"""Extract child elements, choices, and text content from an XSD element."""
from typing import Any

from generate.extractors.constraints import extract_constraints
from generate.extractors.facets import extract_facets
from generate.ir import ChildDef, ChoiceGroup, TextContent
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

    for child in _iter_child_elements(content):
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

        min_occ = getattr(child, 'min_occurs', 0)
        max_occ = getattr(child, 'max_occurs', None)  # None = unbounded

        sequence.append(name)
        details[name] = ChildDef(
            required=min_occ > 0,
            min_occurs=min_occ,
            max_occurs=max_occ,
            constraints=extract_constraints(child) or None,
            facets=None,  # Rare: child text content facets
        )

    return sequence, any_child, details
def extract_choices(xsd_elem: Any) -> list[ChoiceGroup]:
    """Extract xs:choice groups from the content model.

    xmlschema API:
      XsdGroup.model: str ('sequence' | 'choice' | 'all')
      XsdGroup is iterable — yields XsdElement | XsdGroup | XsdAnyElement
    """
    content = _get_content_model(xsd_elem)
    if content is None:
        return []

    choices: list[ChoiceGroup] = []
    _walk_groups_for_choices(content, choices)
    return choices
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
    return TextContent(facets=facets) if facets else TextContent()
# --- Internal helpers ---
def _get_content_model(xsd_elem: Any) -> Any:
    """Get the content model (XsdGroup) from an element's type."""
    xsd_type = getattr(xsd_elem, 'type', None)
    if xsd_type is None:
        return None
    return getattr(xsd_type, 'content', None)
def _iter_child_elements(content: Any):
    """Iterate child elements from a content model.

    xmlschema API:
      XsdGroup.iter_elements() → yields XsdElement | XsdAnyElement
    """
    iter_fn = getattr(content, 'iter_elements', None)
    if iter_fn and callable(iter_fn):
        yield from iter_fn()
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
def _walk_groups_for_choices(group: Any, out: list[ChoiceGroup]) -> None:
    """Recursively walk model groups to find xs:choice groups.

    xmlschema API:
      XsdGroup.model: str
      XsdGroup is iterable (yields children)
    """
    model = getattr(group, 'model', None)
    if model is None:
        return

    if model == 'choice':
        options: list[str] = []
        for item in group:
            name = getattr(item, 'local_name', None)
            if name:
                options.append(name)
            # Recurse into nested groups
            if getattr(item, 'model', None) is not None:
                _walk_groups_for_choices(item, out)
        if options:
            out.append(ChoiceGroup(
                options=sorted(options),
                min_occurs=getattr(group, 'min_occurs', 0),
                max_occurs=getattr(group, 'max_occurs', None),
            ))
    else:
        # sequence or all — recurse into nested groups
        for item in group:
            if getattr(item, 'model', None) is not None:
                _walk_groups_for_choices(item, out)
