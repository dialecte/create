"""Deriver — compute transitive graphs and derived constants from collected IR.

Phase 3 of the pipeline: Parse → Collect → **Derive** → Emit.
"""
from generate.ir import ElementDef, IdentityConstraint
def derive_graph(
    elements: dict[str, ElementDef],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Compute transitive DESCENDANTS and ANCESTORS from CHILDREN/PARENTS.

    Returns:
        (descendants, ancestors) — each is a dict mapping element name to sorted list.
    """
    children_map = {name: list(e.children.keys()) for name, e in elements.items()}
    parents_map = {name: list(e.parents) for name, e in elements.items()}

    def transitive(graph: dict[str, list[str]], start: str) -> list[str]:
        result: list[str] = []
        visited: set[str] = set()
        queue = list(graph.get(start, []))
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            result.append(node)
            queue.extend(graph.get(node, []))
        return sorted(result)

    descendants = {name: transitive(children_map, name) for name in elements}
    ancestors = {name: transitive(parents_map, name) for name in elements}
    return descendants, ancestors
def derive_root_element(elements: dict[str, ElementDef], override: str | None = None) -> str:
    """Find the document root element.

    If *override* is provided, use it directly (raising if absent).
    Otherwise expect exactly one parentless element.
    """
    if override:
        if override not in elements:
            raise ValueError(f'Root override {override!r} not found in elements')
        return override

    roots = sorted(name for name, e in elements.items() if not e.parents)
    if len(roots) != 1:
        raise ValueError(f'Expected exactly 1 root element, found: {roots}')
    return roots[0]
def derive_singleton_elements(elements: dict[str, ElementDef], root_name: str) -> list[str]:
    """Find elements that can appear at most once in the entire document.

    An element is a document singleton if:
      - It has maxOccurs <= 1 in every parent context (local singleton), AND
      - All of its parents are also document singletons (transitive).

    Computed via fixpoint: start from root, propagate singleton status downward.
    """
    # Step 1: local singletons — maxOccurs <= 1 everywhere
    local_singleton: set[str] = set(elements.keys())
    for elem in elements.values():
        for child_name, child_def in elem.children.items():
            if child_def.max_occurs is None or child_def.max_occurs > 1:
                local_singleton.discard(child_name)

    # Step 2: fixpoint — only keep elements whose entire parent chain is singleton
    doc_singletons: set[str] = {root_name}
    changed = True
    while changed:
        changed = False
        for name, elem in elements.items():
            if name in doc_singletons or name not in local_singleton:
                continue
            if elem.parents and all(p in doc_singletons for p in elem.parents):
                doc_singletons.add(name)
                changed = True

    return sorted(doc_singletons)


def derive_identity_fields(elements: dict[str, ElementDef]) -> dict[str, list[str]]:
    """Precompute which attributes participate in identity constraints per element.

    Scans all element-level constraints, resolves selector targets,
    and assigns field attributes to targeted elements.
    Returns element name -> sorted list of attribute names used in unique/key fields.
    """
    result: dict[str, set[str]] = {}
    for element in elements.values():
        for constraint in element.constraints:
            for target in _resolve_constraint_targets(constraint, elements):
                result.setdefault(target, set())
                result[target] |= _extract_attribute_fields(constraint)
    return {name: sorted(fields) for name, fields in result.items() if fields}


def _resolve_constraint_targets(
    constraint: IdentityConstraint, elements: dict[str, ElementDef]
) -> set[str]:
    """Find which element names a constraint's selector targets."""
    if constraint.kind == 'keyref':
        return set()
    targets: set[str] = set()
    for path in constraint.selector:
        for step in path.steps:
            if step.kind == 'name' and step.value in elements:
                targets.add(step.value)
    return targets


def _extract_attribute_fields(constraint: IdentityConstraint) -> set[str]:
    """Extract attribute names from a constraint's field targets."""
    if constraint.kind == 'keyref':
        return set()
    return {
        f.target.value
        for f in constraint.fields
        if f.target.is_attribute and f.target.value
    }
