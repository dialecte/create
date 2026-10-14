"""The instance tier's two judges of a document: the definition (`predict`, the structural facts: which children, in
which order and namespace; which attributes, required, fixed or admitted by a wildcard; text where the content holds
none; nil) and libxml2 (`judge`), each giving the families of the faults it finds. The families the walk does not
predict yet (values, identity constraints, xsi:type rules) are left out of the comparison on both sides.
"""
import re
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

from proof.matcher import match, viable_prefix, wildcard_admits
from proof.resolve import XSI, Resolved, UnresolvedType, declaration_of, global_declaration, named_type, type_only, with_type

# the families the walk predicts; 'value', 'identity' and 'xsi-type' are not compared yet
STRUCTURE = frozenset({'content', 'attribute', 'nil'})
# the families compared: an error libxml2 reports that the family table does not name is a disagreement, never ignored
COMPARED = STRUCTURE | {'unclassified'}
# a libxml2 fault, confirmed by xmlschema's validator: a choice holding only an abstract element no member substitutes
# for admits nothing (an abstract element never validates), libxml2 builds it as an epsilon and skips it. The walk reads
# a document that way with `as_libxml2`, to tell whether the fault explains a disagreement
LIBXML2_EMPTY_CHOICE = 'libxml2:memberless-abstract-head-as-empty'
XSI_ATTRIBUTES = frozenset({'type', 'nil', 'schemaLocation', 'noNamespaceSchemaLocation'})

# libxml2's schema validity errors, by the family of the rule they enforce
_LIBXML2_FAMILIES = (
    ('SCHEMAV_ELEMENT_CONTENT', 'content'),
    ('SCHEMAV_CVC_COMPLEX_TYPE_2', 'content'),
    ('SCHEMAV_CVC_ELT_1', 'content'),
    ('SCHEMAV_CVC_ELT_2', 'content'),
    ('SCHEMAV_CVC_COMPLEX_TYPE_3', 'attribute'),
    ('SCHEMAV_CVC_COMPLEX_TYPE_4', 'attribute'),
    ('SCHEMAV_CVC_AU', 'attribute'),
    ('SCHEMAV_CVC_ELT_3', 'nil'),
    ('SCHEMAV_CVC_ELT_4', 'xsi-type'),
    ('SCHEMAV_CVC_ELT_5', 'value'),
    ('SCHEMAV_CVC_IDC', 'identity'),
    ('SCHEMAV_CVC_DATATYPE', 'value'),
    ('SCHEMAV_CVC_FACET', 'value'),
    ('SCHEMAV_CVC_ENUMERATION', 'value'),
    ('SCHEMAV_CVC_PATTERN', 'value'),
    ('SCHEMAV_CVC_LENGTH', 'value'),
    ('SCHEMAV_CVC_MINLENGTH', 'value'),
    ('SCHEMAV_CVC_MAXLENGTH', 'value'),
    ('SCHEMAV_CVC_MININCLUSIVE', 'value'),
    ('SCHEMAV_CVC_MAXINCLUSIVE', 'value'),
    ('SCHEMAV_CVC_MINEXCLUSIVE', 'value'),
    ('SCHEMAV_CVC_MAXEXCLUSIVE', 'value'),
    ('SCHEMAV_CVC_TOTALDIGITS', 'value'),
    ('SCHEMAV_CVC_FRACTIONDIGITS', 'value'),
    # an element of a simple type: an attribute on it, a child in it; an abstract type; no type at all
    ('SCHEMAV_CVC_TYPE_3_1_1', 'attribute'),
    ('SCHEMAV_CVC_TYPE_3_1_2', 'content'),
    ('SCHEMAV_CVC_TYPE_2', 'xsi-type'),
    ('SCHEMAV_CVC_TYPE_1', 'content'),
    ('SCHEMAV_CVC_TYPE', 'value'),
    ('SCHEMAV_CVC_SIMPLE_TYPE', 'value'),
)


@dataclass(frozen=True)
class Fault:
    family: str
    path: str
    detail: str


@dataclass(frozen=True)
class Visit:
    """An element the walk assessed: what it was held to, and whether its tag has several declarations (the one its
    parent's particle names applied)."""

    element: etree._Element
    resolved: Resolved
    per_parent: bool


@dataclass
class Prediction:
    faults: list[Fault] = field(default_factory=list)
    # parts of the document the definition cannot speak for yet, by reason: a document with any is not compared
    unpredictable: list[str] = field(default_factory=list)
    visits: list[Visit] = field(default_factory=list)
    # read `as_libxml2`: whether reading a choice with no particle as empty changed what a content model admits
    read_as_libxml2: bool = False

    def families(self) -> frozenset[str]:
        return frozenset(fault.family for fault in self.faults)


def judge(validator: etree.XMLSchema, document: etree._ElementTree | etree._Element) -> frozenset[str]:
    """The families of the faults libxml2 finds ('unclassified' for an error the table does not name)."""
    validator.validate(document)
    return frozenset(_family(entry.type_name) for entry in validator.error_log)


def _family(type_name: str) -> str:
    return next((family for prefix, family in _LIBXML2_FAMILIES if type_name.startswith(prefix)), 'unclassified')


def predict(*, definition: dict[str, Any], types: dict[str, Any], root: etree._Element, as_libxml2: bool = False) -> Prediction:
    """The structural faults the definition finds in a document, walked from its root; `as_libxml2` reads it with
    libxml2's known fault (`LIBXML2_EMPTY_CHOICE`), to tell whether one of them explains a disagreement."""
    prediction = Prediction()
    _Walk(definition=definition, types=types, prediction=prediction, as_libxml2=as_libxml2).root(root)
    return prediction


def predict_at(
    *, definition: dict[str, Any], types: dict[str, Any], element: etree._Element, declaration: dict[str, Any], as_libxml2: bool = False
) -> Prediction:
    """The structural faults the definition finds in one element and what it holds, held to `declaration`: after an
    edit of a document found valid, the only place a fault can be."""
    prediction = Prediction()
    _Walk(definition=definition, types=types, prediction=prediction, as_libxml2=as_libxml2).element(element, declaration)
    return prediction


@dataclass
class _Walk:
    definition: dict[str, Any]
    types: dict[str, Any]
    prediction: Prediction
    as_libxml2: bool = False

    def root(self, element: etree._Element) -> None:
        local, namespace = _name(element)
        declaration = global_declaration(self.definition, local, namespace)
        if declaration is None:
            self._fault('content', element, 'no global declaration for the root')
            return
        self.element(element, declaration)

    def element(self, element: etree._Element, declaration: dict[str, Any], *, per_parent: bool = False) -> None:
        try:
            named = named_type(element)
        except UnresolvedType as unbound:
            named = str(unbound)  # a prefix no namespace is bound to: refused as any type the declaration does not admit
        resolved = with_type(declaration=declaration, named=named, types=self.types)
        if resolved.content is declaration and declaration.get('abstractType'):
            # an abstract type is no type to assess the element against: it must name another it admits
            self._fault('xsi-type', element, 'an abstract type and no xsi:type naming another it admits')
            return
        self.assess(element, resolved, per_parent=per_parent)

    def assess(self, element: etree._Element, resolved: Resolved, *, per_parent: bool = False) -> None:
        self.prediction.visits.append(Visit(element=element, resolved=resolved, per_parent=per_parent))
        self.attributes(element, resolved)
        nil = element.get(f'{{{XSI}}}nil')
        if nil is not None and nil.strip() in ('true', '1'):
            if not resolved.declaration.get('nillable'):
                # refused, the nil says nothing: the content is assessed as for any element
                self._fault('nil', element, 'xsi:nil on an element that is not nillable')
            else:
                if (resolved.content.get('textContent') or {}).get('fixed') is not None:
                    self._fault('nil', element, 'a nil element with a fixed value')
                elif children_of(element) or _text(element):
                    self._fault('nil', element, 'a nil element holds content')
                return
        self.content(element, resolved)

    def attributes(self, element: etree._Element, resolved: Resolved) -> None:
        attributes = resolved.content['attributes']
        by_name = {attribute_name(key, detail): (key, detail) for key, detail in attributes['details'].items()}
        present = set()
        for name, value in element.attrib.items():
            namespace, local = _split(name)
            if namespace == XSI and local in XSI_ATTRIBUTES:
                continue
            found = by_name.get((namespace, local))
            if found is not None:
                present.add(found[0])
                fixed = found[1].get('fixed')
                if fixed is not None and _normalized(value, found[1]) != _normalized(fixed, found[1]):
                    self._fault('attribute', element, f'{name} is not its fixed value')
                continue
            wildcard = attributes.get('any')
            if wildcard is None or not wildcard_admits(wildcard, namespace):
                self._fault('attribute', element, f'{name} is not declared')
            elif wildcard['processContents'] == 'strict':
                # a strict wildcard wants a global attribute declaration: the definition does not write them
                self.prediction.unpredictable.append('strict-attribute-wildcard')
        for key, detail in attributes['details'].items():
            if detail.get('required') and key not in present:
                self._fault('attribute', element, f'{key} is required')

    def content(self, element: etree._Element, resolved: Resolved) -> None:
        content = resolved.content
        children = children_of(element)
        if 'textContent' not in content:
            # element-only content may hold whitespace between its children; empty content holds no character at all
            if _text(element, whitespace='contentModel' not in content):
                self._fault('content', element, 'text where the content holds none')
        names, model = [_name(child) for child in children], content.get('contentModel')
        held = match(model, names, holder=resolved.holder, empty_choice_is_empty=self.as_libxml2)
        if self.as_libxml2 and (held is None) != (match(model, names, holder=resolved.holder) is None):
            self.prediction.read_as_libxml2 = True
        if held is None:
            self._fault('content', element, 'children the content model does not admit')
            # read one by one, the children before the first one the model refuses are still assessed
            held = viable_prefix(model, names, holder=resolved.holder, empty_choice_is_empty=self.as_libxml2)
            if self.as_libxml2 and len(held) != len(viable_prefix(model, names, holder=resolved.holder)):
                self.prediction.read_as_libxml2 = True
        for child, particle in zip(children, held, strict=False):
            if particle['kind'] == 'element':
                declaration = declaration_of(self.definition, particle)
                if declaration is None:
                    self.prediction.unpredictable.append(f'particle-without-declaration:{particle["name"]}')
                else:
                    self.element(child, declaration, per_parent='declaration' in particle)
            else:
                self.wildcard_child(child, particle['processContents'])

    def wildcard_child(self, element: etree._Element, process_contents: str) -> None:
        if process_contents == 'skip':
            return
        declaration = global_declaration(self.definition, *_name(element))
        named = named_type(element) if declaration is None else None
        if declaration is not None:
            self.element(element, declaration)
        elif named is not None:
            # no declaration, but a type it names: the element is assessed by that type (strict or lax alike)
            try:
                self.assess(element, type_only(element_namespace=_name(element)[1], named=named, types=self.types))
            except UnresolvedType as unresolved:
                self.prediction.unpredictable.append(f'xsi-type:{unresolved}')
        elif process_contents == 'strict':
            self._fault('content', element, 'a strict wildcard admits an element with no global declaration')
        else:
            # lax: an element with no declaration is not assessed; its children are, each as lax
            for child in children_of(element):
                self.wildcard_child(child, 'lax')

    def _fault(self, family: str, element: etree._Element, detail: str) -> None:
        self.prediction.faults.append(Fault(family=family, path=element.getroottree().getpath(element), detail=detail))


def _name(element: etree._Element) -> tuple[str, str]:
    qname = etree.QName(element)
    return qname.localname, qname.namespace or ''


def _split(name: str) -> tuple[str, str]:
    if name.startswith('{'):
        namespace, _, local = name[1:].partition('}')
        return namespace, local
    return '', name


def attribute_name(key: str, detail: dict[str, Any]) -> tuple[str, str]:
    """An attribute detail's (namespace, local name): a key `prefix:local` carries its namespace in the detail."""
    namespace = detail.get('namespace')
    return (namespace['uri'], key.rpartition(':')[2]) if namespace else ('', key)


def children_of(element: etree._Element) -> list[etree._Element]:
    return [child for child in element if isinstance(child.tag, str)]


def _text(element: etree._Element, *, whitespace: bool = False) -> bool:
    """Whether the element holds character content other than whitespace (or any at all, with `whitespace`)."""
    pieces = [element.text, *(child.tail for child in element)]
    return any(piece and (whitespace or piece.strip()) for piece in pieces)


_WHITESPACE = re.compile(r'[ \t\n\r]+')
_BUILTIN_WHITESPACE = {'string': 'preserve', 'normalizedString': 'replace'}


def _normalized(value: str, detail: dict[str, Any]) -> str:
    """A value as its datatype's whiteSpace rule reads it: its own facet, else its built-in's (a string preserved, a
    normalizedString replaced, anything else collapsed); equality in value space - `1.0` and `1` - is not compared."""
    datatype = detail.get('type') or {}
    rule = datatype.get('facets', {}).get('whiteSpace')
    if rule is None:
        atomic = 'list' not in datatype and 'union' not in datatype
        rule = _BUILTIN_WHITESPACE.get(datatype.get('builtin', 'string'), 'collapse') if atomic else 'collapse'
    if rule == 'preserve':
        return value
    replaced = re.sub(r'[\t\n\r]', ' ', value)
    return replaced if rule == 'replace' else _WHITESPACE.sub(' ', replaced).strip()
