"""Shared emission helpers for converting IR to TypeScript literals."""
import json
from typing import Any

from generate.ir import (
    AttributeDef,
    ChildDef,
    ChoiceGroup,
    ElementDef,
    Facets,
    IdentityConstraint,
    Namespace,
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
    """Emit a TS string literal, escaping quotes and backslashes."""
    return json.dumps(s, ensure_ascii=False)
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
    lines.append(f'{indent}details: {{')
    for key in elem.attr_sequence:
        attr = elem.attributes[key]
        lines.append(f'{indent}\t{ts_key(key)}: {_ts_attr_def(attr, indent + "\t\t")},')
    lines.append(f'{indent}}},')
    if elem.identity_fields:
        lines.append(f'{indent}identityFields: {ts_string_array(elem.identity_fields)},')
    lines.append(f'{indent[:-1]}}}')
    return '\n'.join(lines)
def ts_child_block(elem: ElementDef, indent: str = '\t\t') -> str:
    """Emit the children block for an element."""
    lines = ['{']
    lines.append(f'{indent}sequence: {ts_string_array(elem.child_sequence)},')
    if elem.child_any:
        lines.append(f'{indent}any: true,')
    lines.append(f'{indent}details: {{')
    for key in elem.child_sequence:
        child = elem.children[key]
        lines.append(f'{indent}\t{ts_key(key)}: {_ts_child_def(child, indent + "\t\t")},')
    lines.append(f'{indent}}},')
    if elem.choices:
        lines.append(f'{indent}choices: {_ts_choices(elem.choices, indent + "\t")},')
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
    f = ts_facets(tc.facets, indent + '\t')
    if f == 'undefined':
        return '{}'
    return f'{{ facets: {f} }}'
# --- Private helpers ---
def _ts_attr_def(attr: AttributeDef, indent: str) -> str:
    """Emit a sparse AttributeDefinition literal."""
    fields: dict[str, Any] = {}
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
def _ts_choices(choices: list[ChoiceGroup], indent: str) -> str:
    """Emit ChoiceGroup array."""
    lines = ['[']
    for cg in choices:
        fields: dict[str, Any] = {'options': cg.options}
        if cg.min_occurs != 0:
            fields['minOccurs'] = cg.min_occurs
        if cg.max_occurs is not None:
            fields['maxOccurs'] = cg.max_occurs
        lines.append(f'{indent}{_emit_object(fields, indent + "\t")},')
    lines.append(f'{indent[:-1]}]')
    return '\n'.join(lines)
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
        return ts_string_array([str(v) for v in value])
    if isinstance(value, Namespace):
        return ts_namespace(value)
    if isinstance(value, Facets):
        return ts_facets(value, indent)
    return str(value)
