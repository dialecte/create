"""xsi:type expansion — resolve XSD type-derivation polymorphism into the IR.

Some schemas (notably IEC 61131-10) model their content polymorphically: a named
element slot is declared with an **abstract** complex type, and instances select a
concrete variant at runtime via the ``xsi:type`` attribute. For example::

    <BodyContent xsi:type="FBD"><Network>…</Network></BodyContent>

Here ``BodyContent`` is the element name; ``FBD`` is a *type* selected via
``xsi:type``. The concrete forms (``FBD``, ``Block``, ``DataSource``, …) have **no**
global element declarations, so the element-instance-driven collector never reaches
their children.

This module reverses the XSD type-derivation graph (``schema.maps.types``) to find,
for any declared type, the concrete types that may substitute it. Their children and
attributes are unioned into the slot element (as optional members, since each is only
required for a specific ``xsi:type``), and an ``xsi:type`` enumeration attribute is
added listing the valid variant names.

This expansion runs automatically for every schema. For slots declared with a
concrete (non-abstract) type that has no derived variants, ``_concrete_substitution_types``
returns ``[]`` and ``expand`` is a no-op — zero overhead. Schemas may freely mix
abstract-typed slots (expanded) with concrete-typed slots (untouched).
"""
from typing import Any

from generate.extractors.attributes import extract_attributes
from generate.extractors.children import extract_children_from_type, iter_type_child_elements
from generate.helpers import local_name
from generate.ir import AttributeDef, ChildDef, Facets, Namespace

XSI_NAMESPACE = Namespace(prefix='xsi', uri='http://www.w3.org/2001/XMLSchema-instance')
XSI_TYPE_KEY = 'xsi:type'


class XsiTypeExpander:
    """Expands abstract-typed element slots with their xsi:type substitution variants."""

    def __init__(self, schema: Any) -> None:
        self._derived = _build_derived_map(schema)

    def expand(
        self,
        xsd_elem: Any,
        attr_seq: list[str],
        attrs: dict[str, AttributeDef],
        child_seq: list[str],
        children: dict[str, ChildDef],
    ) -> None:
        """Union substitution-variant children/attributes into an element's IR (in place).

        Idempotent and additive: existing entries are never overwritten or removed.
        Safe to call multiple times for the same element name (e.g. when the same slot
        is declared in several parents with different abstract base types).
        """
        types = self._concrete_substitution_types(getattr(xsd_elem, 'type', None))
        if not types:
            return

        for variant in types:
            v_seq, _v_any, v_details = extract_children_from_type(variant)
            for name in v_seq:
                if name in children:
                    continue
                detail = v_details[name]
                children[name] = ChildDef(
                    required=False,
                    min_occurs=0,
                    max_occurs=detail.max_occurs,
                    constraints=detail.constraints,
                    facets=detail.facets,
                )
                child_seq.append(name)

        for variant in types:
            a_seq, _a_any, a_details = extract_attributes(variant)
            for key in a_seq:
                if key in attrs:
                    continue
                detail = a_details[key]
                attrs[key] = AttributeDef(
                    required=False,
                    default=detail.default,
                    fixed=detail.fixed,
                    namespace=detail.namespace,
                    facets=detail.facets,
                )
                attr_seq.append(key)

        variant_names = sorted(local_name(getattr(t, 'name', '') or '') for t in types)
        if variant_names and XSI_TYPE_KEY not in attrs:
            attrs[XSI_TYPE_KEY] = AttributeDef(
                required=False,
                namespace=XSI_NAMESPACE,
                facets=Facets(enumeration=variant_names),
            )
            attr_seq.append(XSI_TYPE_KEY)

        # Keep attribute order consistent with extract_attributes (alphabetical).
        attr_seq.sort()

    def iter_variant_child_elements(self, xsd_elem: Any):
        """Yield XsdElement children contributed by an element's substitution variants.

        Used by the collector to recurse into elements that are only reachable through
        xsi:type substitution (e.g. ``Network`` under an abstract ``BodyContent`` slot).
        """
        for variant in self._concrete_substitution_types(getattr(xsd_elem, 'type', None)):
            yield from iter_type_child_elements(variant)

    def _concrete_substitution_types(self, xsd_type: Any) -> list[Any]:
        """Transitive concrete types derivable from *xsd_type* (BFS through abstract bases)."""
        if xsd_type is None:
            return []
        result: list[Any] = []
        seen: set[int] = set()
        queue: list[Any] = [xsd_type]
        while queue:
            current = queue.pop(0)
            for derived in self._derived.get(id(current), []):
                if id(derived) in seen:
                    continue
                seen.add(id(derived))
                queue.append(derived)
                if not getattr(derived, 'abstract', False):
                    result.append(derived)
        result.sort(key=lambda t: local_name(getattr(t, 'name', '') or ''))
        return result


def _build_derived_map(schema: Any) -> dict[int, list[Any]]:
    """Map ``id(base_type)`` → directly-derived complex types across all schemas.

    xmlschema API:
      XMLSchema.maps.types: dict[str, XsdType] — every global type in the schema set
      XsdComplexType.base_type: XsdType | None
      XsdComplexType.derivation: 'extension' | 'restriction' | None
    """
    derived: dict[int, list[Any]] = {}
    types = getattr(getattr(schema, 'maps', None), 'types', None)
    if not types:
        return derived
    for xsd_type in types.values():
        base = getattr(xsd_type, 'base_type', None)
        if base is None:
            continue
        if getattr(xsd_type, 'derivation', None) not in ('extension', 'restriction'):
            continue
        derived.setdefault(id(base), []).append(xsd_type)
    return derived
