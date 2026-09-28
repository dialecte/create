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
def strip_canonical_child_namespaces(elements: dict[str, ElementDef]) -> None:
    """Reduce per-edge child namespaces to sparse overrides (in place).

    ``extract_children`` stamps every parent→child edge with the child's
    declaring-schema namespace. Null the edge when it equals the child element's
    canonical namespace, so only edges that OVERRIDE the canonical (the same local
    name declared in a different namespace under this parent, e.g. ``{6-100}Labels``
    under ``DAS`` vs canonical ``{SCL}Labels``) survive and get emitted. Core falls
    back to the element's canonical namespace when an edge carries none.
    """
    for element in elements.values():
        for child_name, child_def in element.children.items():
            canonical = elements.get(child_name)
            if canonical is not None and child_def.namespace == canonical.namespace:
                child_def.namespace = None


def find_root_candidates(elements: dict[str, ElementDef]) -> list[str]:
    """The elements no content model names: the only ones that can start a document."""
    return sorted(name for name, e in elements.items() if not e.parents)


def derive_root_element(
    elements: dict[str, ElementDef],
    override: str | None = None,
    exclude: set[str] | frozenset[str] = frozenset(),
) -> str:
    """The root of a document: the one root candidate, or the one chosen among several.

    Several candidates are never decided silently - a wrong root corrupts every table derived from
    it - so the schema author names one with `--root`. `exclude` holds the parentless elements
    known not to be roots: the orphans a sidecar mapping is about to attach.
    """
    candidates = [name for name in find_root_candidates(elements) if name not in exclude]
    if override is not None:
        if override not in candidates:
            raise ValueError(
                f'Root {override!r} is not a root candidate; the candidates are: {candidates}'
            )
        return override
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError('No root candidate: every element is the child of another')
    raise ValueError(
        'Several elements can start a document; choose one with --root <name>: '
        + ', '.join(candidates)
    )


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
            for target in _resolve_constraint_targets(constraint, elements, declaring=element.tag):
                result.setdefault(target, set())
                result[target] |= _extract_attribute_fields(constraint)
    return {name: sorted(fields) for name, fields in result.items() if fields}


def assign_identity_fields(elements: dict[str, ElementDef], identity_fields: dict[str, list[str]]) -> None:
    """Write the derived identity fields onto each element, and onto each of its definitions by
    parent restricted to the attributes that definition declares: an attribute a declaration does
    not have cannot identify the element there."""
    for name, fields in identity_fields.items():
        element = elements[name]
        element.identity_fields = fields
        for declared in element.definitions_by_parent.values():
            declared.identity_fields = [f for f in fields if f in declared.attributes]


def _resolve_constraint_targets(
    constraint: IdentityConstraint,
    elements: dict[str, ElementDef],
    declaring: str | None = None,
) -> set[str]:
    """Find which element names a constraint's selector targets.

    A selector selects the elements under constraint: the ones each of its paths ENDS at. The steps
    before are only the route from the declaring element, walked as a set of context elements:
    `.` keeps the context, a name replaces it, `*` opens to the children the definition allows
    there (`ns:*` to those of that prefix), and a deep path to every descendant. An element a
    wildcard reaches counts only if it MUST carry the fields: the author said "whatever is there",
    and an element that may lack the attribute would have no identity without it.
    """
    if constraint.kind == 'keyref':
        return set()
    fields = _extract_attribute_fields(constraint)
    targets: set[str] = set()
    for path in constraint.selector:
        if not path.steps:
            continue
        context: set[str] = {declaring} if declaring in elements else set()
        reached_by_wildcard = False
        for step in path.steps:
            if step.kind == 'self':
                continue
            if step.kind == 'name':
                context = {step.value} if step.value in elements else set()
                reached_by_wildcard = False
                continue
            children = _children_of(context, elements, deep=path.deep)
            if step.kind == 'ns-wildcard':
                children = {name for name in children if elements[name].namespace.prefix == step.value}
            context = children
            reached_by_wildcard = True
        if reached_by_wildcard:
            context = {name for name in context if _requires_all(elements[name], fields)}
        targets |= context
    return targets


def _requires_all(element: ElementDef, attribute_names: set[str]) -> bool:
    return all(
        name in element.attributes and element.attributes[name].required for name in attribute_names
    )


def _children_of(context: set[str], elements: dict[str, ElementDef], deep: bool) -> set[str]:
    """The elements the definition allows under the context elements; every descendant when deep."""
    found: set[str] = set()
    frontier = set(context)
    while frontier:
        parent = frontier.pop()
        for child in elements[parent].children:
            if child in elements and child not in found:
                found.add(child)
                if deep:
                    frontier.add(child)
    return found


def _extract_attribute_fields(constraint: IdentityConstraint) -> set[str]:
    """Extract the attribute names a constraint's fields read on the selected element itself.

    A field is evaluated relative to the selected element: `@x` is its own attribute, `child/@x`
    is an attribute of its child and does not identify it.
    """
    if constraint.kind == 'keyref':
        return set()
    return {
        f.target.value
        for f in constraint.fields
        if f.target.is_attribute and f.target.value and not f.steps
    }
