"""Shared emission helpers for converting IR to TypeScript literals."""
import re
from typing import Any

from generate.ir import (
    AttributeDef,
    ChildDef,
    DataType,
    ElementDef,
    Facets,
    IdentityConstraint,
    Namespace,
    Particle,
    TextContent,
)
from generate.xpath_parser import FieldPath, FieldTarget, SelectorPath, XPathStep
def sparse(d: dict[str, Any]) -> dict[str, Any]:
    """Drop keys whose values are default (None, False, [], 0, {})."""
    return {
        k: v
        for k, v in d.items()
        if v is not None and v is not False and v != [] and v != 0 and v != {}
    }
def ts_string(s: str) -> str:
    """Emit a single-quoted TS string literal, the way the formatters of the dialectes want it."""
    escaped = (
        s.replace('\\', '\\\\')
        .replace("'", "\\'")
        .replace('\n', '\\n')
        .replace('\r', '\\r')
        .replace('\t', '\\t')
    )
    return f"'{escaped}'"
def ts_string_array(items: list[str], indent: str = '') -> str:
    """Emit a TS readonly string array literal."""
    if not items:
        return '[]'
    inner = ', '.join(ts_string(i) for i in items)
    return f'[{inner}]'
def ts_record(data: dict[str, list[str]], indent: str = '\t') -> str:
    """Emit a TS Record<string, string[]> literal."""
    if not data:
        return '{}'
    lines = ['{']
    for key in sorted(data.keys()):
        arr = ts_string_array(data[key])
        lines.append(f'{indent}{ts_key(key)}: {arr},')
    lines.append('}')
    return '\n'.join(lines)
def ts_key(name: str) -> str:
    """Quote a TS object key if it contains special characters."""
    if ':' in name or '-' in name or ' ' in name or not name.isidentifier():
        return ts_string(name)
    return name
def _to_pascal_case(name: str) -> str:
    """Turn any XML name into a TS identifier: 'boolean-value' -> 'BooleanValue'."""
    parts = [part for part in re.split(r'[^0-9A-Za-z_]+', name) if part]
    identifier = ''.join(part[0].upper() + part[1:] for part in parts) or '_'
    return f'_{identifier}' if identifier[0].isdigit() else identifier
def ts_edge_type_name(type_names: dict[str, str], element: str, parent: str) -> str:
    """The type of an element's attributes as declared under a parent: `AttributesPInAddress`."""
    return f"Attributes{type_names[element]}In{type_names.get(parent) or _to_pascal_case(parent)}"


def ts_type_names(names: list[str]) -> dict[str, str]:
    """Map every element name to a unique TS identifier, for building type names.

    An XML name may hold characters a TS identifier may not ('-', '.'). A name that already is an
    identifier is kept untouched, so the output for such schemas does not change. The others are
    turned into PascalCase; should two names end up alike, the later one gets a numeric suffix.
    """
    type_names: dict[str, str] = {}
    taken: set[str] = set()

    identifier_safe = [name for name in names if name.isidentifier()]
    for name in identifier_safe:
        type_names[name] = name
        taken.add(name)

    for name in sorted(name for name in names if not name.isidentifier()):
        candidate = _to_pascal_case(name)
        suffix = 2
        unique = candidate
        while unique in taken:
            unique = f'{candidate}_{suffix}'
            suffix += 1
        type_names[name] = unique
        taken.add(unique)

    return type_names
def ts_namespace(ns: Namespace) -> str:
    """Emit a Namespace object literal."""
    return f"{{ prefix: {ts_string(ns.prefix)}, uri: {ts_string(ns.uri)} }}"
def ts_facets(facets: Facets | None, indent: str = '\t\t\t') -> str:
    """Emit a sparse Facets literal."""
    if facets is None or facets.is_empty():
        return 'undefined'

    fields: dict[str, Any] = {}
    if facets.enumeration is not None:
        fields['enumeration'] = facets.enumeration
    if facets.pattern is not None:
        fields['pattern'] = facets.pattern
    if facets.min_length is not None:
        fields['minLength'] = facets.min_length
    if facets.max_length is not None:
        fields['maxLength'] = facets.max_length
    if facets.length is not None:
        fields['length'] = facets.length
    if facets.min_inclusive is not None:
        fields['minInclusive'] = facets.min_inclusive
    if facets.max_inclusive is not None:
        fields['maxInclusive'] = facets.max_inclusive
    if facets.min_exclusive is not None:
        fields['minExclusive'] = facets.min_exclusive
    if facets.max_exclusive is not None:
        fields['maxExclusive'] = facets.max_exclusive
    if facets.total_digits is not None:
        fields['totalDigits'] = facets.total_digits
    if facets.fraction_digits is not None:
        fields['fractionDigits'] = facets.fraction_digits
    if facets.white_space is not None:
        fields['whiteSpace'] = facets.white_space

    if not fields:
        return 'undefined'

    return _emit_object(fields, indent)
def ts_attr_block(elem: ElementDef, indent: str = '\t\t') -> str:
    """Emit the attributes block for an element."""
    lines = ['{']
    lines.append(f'{indent}sequence: {ts_string_array(elem.attr_sequence)},')
    if elem.attr_any:
        lines.append(f'{indent}any: true,')
        if elem.attr_any_namespace:
            lines.append(f'{indent}anyNamespace: {ts_string_array(elem.attr_any_namespace)},')
    if elem.attr_sequence:
        lines.append(f'{indent}details: {{')
        for key in elem.attr_sequence:
            attr = elem.attributes[key]
            lines.append(f'{indent}\t{ts_key(key)}: {_ts_attr_def(attr, indent + "\t\t")},')
        lines.append(f'{indent}}},')
    else:
        lines.append(f'{indent}details: {{}},')
    if elem.identity_fields:
        lines.append(f'{indent}identityFields: {ts_string_array(elem.identity_fields)},')
    lines.append(f'{indent[:-1]}}}')
    return '\n'.join(lines)
def ts_element_body(
    elem: ElementDef,
    indent: str,
    edge_definitions: dict[str, ElementDef] | None = None,
) -> list[str]:
    """The lines inside an element definition literal - the same at the tag level and on an edge.

    Sparse: only non-default fields. `edge_definitions` holds, per child, the child's declaration
    under THIS element when it differs from the child's tag-level one (a homonym).
    """
    lines = [f"{indent}tag: {ts_string(elem.tag)},"]
    lines.append(f'{indent}namespace: {ts_namespace(elem.namespace)},')
    if elem.documentation:
        lines.append(f'{indent}documentation: {ts_string(elem.documentation)},')
    lines.append(f'{indent}parents: {ts_string_array(elem.parents)},')
    if elem.nillable:
        lines.append(f'{indent}nillable: true,')
    lines.append(f'{indent}attributes: {ts_attr_block(elem, indent + "\t")},')
    lines.append(f'{indent}children: {ts_child_block(elem, indent + "\t", edge_definitions)},')
    if elem.content_model is not None:
        lines.append(f'{indent}contentModel: {ts_content_model(elem.content_model, indent + "\t")},')
    if elem.constraints:
        lines.append(f'{indent}constraints: {ts_constraints(elem.constraints, indent + "\t")},')
    if elem.text_content:
        lines.append(f'{indent}textContent: {ts_text_content(elem.text_content, indent + "\t")},')
    return lines


def ts_child_block(
    elem: ElementDef,
    indent: str = '\t\t',
    edge_definitions: dict[str, ElementDef] | None = None,
) -> str:
    """Emit the children block for an element.

    `edge_definitions` holds, per child, the child's declaration under THIS element when it
    differs from the child's tag-level one (a homonym): its content is written on the edge.
    """
    lines = ['{']
    lines.append(f'{indent}sequence: {ts_string_array(elem.child_sequence)},')
    if elem.child_any:
        lines.append(f'{indent}any: true,')
    if elem.child_sequence:
        lines.append(f'{indent}details: {{')
        for key in elem.child_sequence:
            child = elem.children[key]
            declared = (edge_definitions or {}).get(key)
            if declared is None:
                lines.append(f'{indent}\t{ts_key(key)}: {_ts_child_def(child, indent + "\t\t")},')
            else:
                lines.append(f'{indent}\t{ts_key(key)}: {_ts_child_def_with_declaration(child, declared, indent + "\t\t")},')
        lines.append(f'{indent}}},')
    else:
        lines.append(f'{indent}details: {{}},')
    lines.append(f'{indent[:-1]}}}')
    return '\n'.join(lines)
def _ts_child_def_with_declaration(child: ChildDef, declared: ElementDef, indent: str) -> str:
    """A child edge carrying what the child holds as declared under this parent.

    The edge already is that declaration (occurrence, namespace, constraints); its content -
    attributes, children, content model, text - sits next to them, all of it, so a reader takes
    the four together and never mixes them with the tag-level union.
    """
    lines = ['{']
    edge = _ts_child_def(child, indent)
    if edge != '{}':
        lines.append(f'{indent}{edge[2:-2]},')
    if declared.nillable:
        lines.append(f'{indent}nillable: true,')
    lines.append(f'{indent}attributes: {ts_attr_block(declared, indent + "\t")},')
    lines.append(f'{indent}children: {ts_child_block(declared, indent + "\t")},')
    if declared.content_model is not None:
        lines.append(f'{indent}contentModel: {ts_content_model(declared.content_model, indent + "\t")},')
    if declared.text_content:
        lines.append(f'{indent}textContent: {ts_text_content(declared.text_content, indent + "\t")},')
    lines.append(f'{indent[:-1]}}}')
    return '\n'.join(lines)


def ts_constraints(constraints: list[IdentityConstraint], indent: str = '\t\t') -> str:
    """Emit an array of constraints."""
    if not constraints:
        return '[]'
    lines = ['[']
    for c in constraints:
        lines.append(f'{indent}{_ts_constraint(c, indent + "\t")},')
    lines.append(f'{indent[:-1]}]')
    return '\n'.join(lines)
def ts_text_content(tc: TextContent, indent: str = '\t\t') -> str:
    """Emit a TextContent literal."""
    fields: dict[str, Any] = {}
    if tc.default is not None:
        fields['default'] = tc.default
    if tc.fixed is not None:
        fields['fixed'] = tc.fixed
    if tc.type is not None:
        fields['type'] = tc.type
    if tc.facets is not None and not tc.facets.is_empty():
        fields['facets'] = tc.facets
    return _emit_object(fields, indent + '\t')


def ts_content_model(particle: Particle, indent: str = '\t\t') -> str:
    """Emit a Particle tree, in the occurrence convention of `children.details`:
    an absent minOccurs is 0, an absent maxOccurs is unbounded."""
    fields: dict[str, Any] = {'kind': particle.kind}
    if particle.kind == 'element':
        fields['name'] = particle.name or ''
    if particle.kind == 'any':
        if particle.namespace:
            fields['namespace'] = particle.namespace
        if particle.process_contents:
            fields['processContents'] = particle.process_contents
    if particle.min_occurs != 0:
        fields['minOccurs'] = particle.min_occurs
    if particle.max_occurs is not None:
        fields['maxOccurs'] = particle.max_occurs
    if particle.particles is not None:
        fields['particles'] = [_NestedParticle(p) for p in particle.particles]
    return _emit_object(fields, indent)


class _NestedParticle:
    def __init__(self, particle: Particle) -> None:
        self.particle = particle


def ts_datatype(datatype: DataType, indent: str = '\t\t\t', nested: bool = False) -> str:
    """Emit a DataType literal: `{ builtin }`, `{ list, facets? }` or `{ union, facets? }`.

    At the top, an atomic type's facets are not repeated: flattened, they are on the attribute
    already. Inside a list or a union each part keeps its own, which the flat view cannot tell apart.
    """
    fields: dict[str, Any] = {}
    if datatype.kind == 'atomic':
        fields['builtin'] = datatype.builtin or ''
    if datatype.kind == 'list' and datatype.item is not None:
        fields['list'] = _NestedDataType(datatype.item)
    if datatype.kind == 'union':
        fields['union'] = [_NestedDataType(member) for member in datatype.members or []]
    has_facets = datatype.facets is not None and not datatype.facets.is_empty()
    if has_facets and (nested or datatype.kind != 'atomic'):
        fields['facets'] = datatype.facets
    return _emit_object(fields, indent)


class _NestedDataType:
    """A datatype inside another: emitted with its own facets."""

    def __init__(self, datatype: DataType) -> None:
        self.datatype = datatype
# --- Private helpers ---
def _ts_attr_def(attr: AttributeDef, indent: str) -> str:
    """Emit a sparse AttributeDefinition literal."""
    fields: dict[str, Any] = {}
    if attr.type is not None:
        fields['type'] = attr.type
    if attr.required:
        fields['required'] = True
    if attr.default is not None:
        fields['default'] = attr.default
    if attr.fixed is not None:
        fields['fixed'] = attr.fixed
    if attr.namespace is not None:
        fields['namespace'] = attr.namespace
    if attr.facets is not None and not attr.facets.is_empty():
        fields['facets'] = attr.facets

    if not fields:
        return '{}'
    return _emit_object(fields, indent)
def _ts_child_def(child: ChildDef, indent: str) -> str:
    """Emit a sparse ChildDefinition literal."""
    fields: dict[str, Any] = {}
    if child.required:
        fields['required'] = True
    if child.min_occurs != 0:
        fields['minOccurs'] = child.min_occurs
    if child.max_occurs is not None:
        fields['maxOccurs'] = child.max_occurs
    if child.constraints:
        fields['constraints'] = child.constraints
    if child.namespace is not None:
        fields['namespace'] = child.namespace

    if not fields:
        return '{}'
    return _emit_object(fields, indent)
def _ts_constraint(c: IdentityConstraint, indent: str) -> str:
    """Emit a single IdentityConstraint literal."""
    fields: dict[str, Any] = {'kind': c.kind, 'name': c.name}
    if c.refer:
        fields['refer'] = c.refer
    if c.deep:
        fields['deep'] = True
    # Emit as raw TS — handled below for structured types
    parts: list[str] = []
    for key, value in fields.items():
        parts.append(f'{ts_key(key)}: {_emit_value(value, indent)}')
    parts.append(f'selector: {_ts_selector_paths(c.selector)}')
    parts.append(f'fields: {_ts_field_paths(c.fields)}')
    inner = ', '.join(parts)
    return '{ ' + inner + ' }'


def _ts_selector_paths(paths: list[SelectorPath]) -> str:
    """Emit selector paths array."""
    if not paths:
        return '[]'
    items = [_ts_selector_path(p) for p in paths]
    return '[' + ', '.join(items) + ']'


def _ts_selector_path(p: SelectorPath) -> str:
    """Emit a single SelectorPath literal."""
    parts: list[str] = []
    if p.deep:
        parts.append('deep: true')
    parts.append(f'steps: {_ts_xpath_steps(p.steps)}')
    return '{ ' + ', '.join(parts) + ' }'


def _ts_field_paths(fields: list[FieldPath]) -> str:
    """Emit field paths array."""
    if not fields:
        return '[]'
    items = [_ts_field_path(f) for f in fields]
    return '[' + ', '.join(items) + ']'


def _ts_field_path(f: FieldPath) -> str:
    """Emit a single FieldPath literal."""
    parts: list[str] = []
    if f.deep:
        parts.append('deep: true')
    if f.steps:
        parts.append(f'steps: {_ts_xpath_steps(f.steps)}')
    parts.append(f'target: {_ts_field_target(f.target)}')
    return '{ ' + ', '.join(parts) + ' }'


def _ts_xpath_steps(steps: tuple[XPathStep, ...]) -> str:
    """Emit an array of XPathStep literals."""
    if not steps:
        return '[]'
    items = [_ts_xpath_step(s) for s in steps]
    return '[' + ', '.join(items) + ']'


def _ts_xpath_step(s: XPathStep) -> str:
    """Emit a single XPathStep."""
    if s.value is not None:
        return '{ ' + f"kind: '{s.kind}', value: {ts_string(s.value)}" + ' }'
    return '{ ' + f"kind: '{s.kind}'" + ' }'


def _ts_field_target(t: FieldTarget) -> str:
    """Emit a FieldTarget literal."""
    parts = [f"kind: '{t.kind}'"]
    if t.value is not None:
        parts.append(f'value: {ts_string(t.value)}')
    if t.is_attribute:
        parts.append('isAttribute: true')
    return '{ ' + ', '.join(parts) + ' }'
def _emit_object(fields: dict[str, Any], indent: str) -> str:
    """Emit a TS object literal from a dict, handling typed values."""
    if not fields:
        return '{}'

    parts: list[str] = []
    for key, value in fields.items():
        ts_val = _emit_value(value, indent)
        parts.append(f'{ts_key(key)}: {ts_val}')

    if len(parts) == 1:
        return '{ ' + parts[0] + ' }'
    inner = ', '.join(parts)
    return '{ ' + inner + ' }'
def _emit_value(value: Any, indent: str) -> str:
    """Emit a TS value from a Python value."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return ts_string(value)
    if isinstance(value, list):
        if all(isinstance(v, str) for v in value):
            return ts_string_array(value)
        if all(isinstance(v, IdentityConstraint) for v in value):
            return ts_constraints(value, indent)
        if all(isinstance(v, _NestedDataType) for v in value):
            return '[' + ', '.join(ts_datatype(v.datatype, indent, nested=True) for v in value) + ']'
        if all(isinstance(v, _NestedParticle) for v in value):
            return '[' + ', '.join(ts_content_model(v.particle, indent) for v in value) + ']'
        return ts_string_array([str(v) for v in value])
    if isinstance(value, _NestedDataType):
        return ts_datatype(value.datatype, indent, nested=True)
    if isinstance(value, DataType):
        return ts_datatype(value, indent)
    if isinstance(value, Namespace):
        return ts_namespace(value)
    if isinstance(value, Facets):
        return ts_facets(value, indent)
    return str(value)
