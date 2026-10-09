"""The datatype of a simple value, read level by level: the restrictions down to a built-in, a list or a union, each
level's facets read from what the schema writes (lexical values, never decoded ones)."""
import re
from xml.etree.ElementTree import Element

from xmlschema.validators import XsdAtomicBuiltin, XsdAtomicRestriction, XsdComplexType, XsdList, XsdSimpleType, XsdUnion

from generate.errors import SchemaNotRepresentable
from generate.model.declarations import AtomicType, DataType, Facets, ListType, UnionType

XS = '{http://www.w3.org/2001/XMLSchema}'
_INTEGER_FACETS = {'length': 'length', 'minLength': 'min_length', 'maxLength': 'max_length',
                   'totalDigits': 'total_digits', 'fractionDigits': 'fraction_digits'}
_RANGE_FACETS = {'minInclusive': 'min_inclusive', 'maxInclusive': 'max_inclusive',
                 'minExclusive': 'min_exclusive', 'maxExclusive': 'max_exclusive'}


def datatype_of(simple_type: XsdSimpleType | None) -> DataType | None:
    """The datatype of a value, None when it says nothing of it: anySimpleType, or a plain string."""
    if simple_type is None:
        return None
    datatype = _datatype(simple_type)
    if datatype is None or datatype == AtomicType(builtin='string', facets=Facets()):
        return None
    return datatype


def _datatype(simple_type: XsdSimpleType) -> DataType | None:
    levels: list[XsdAtomicRestriction] = []
    current = simple_type
    # down to a built-in - whatever it derives from is its own, its facets never written - a list or a union
    while isinstance(current, XsdAtomicRestriction) and not _is_builtin(current):
        levels.append(current)
        current = _base_of(current)
        # a restriction of simple content restricts the text of a complex type
        if isinstance(current, XsdComplexType):
            current = current.content
    if _is_builtin(current) and current.local_name != 'anySimpleType':
        white_space = current.white_space if isinstance(current, XsdAtomicBuiltin) else 'collapse'
        facets = _facets(levels, base_white_space=white_space, qualified=_is_qualified_name(current))
        return AtomicType(builtin=current.local_name, facets=facets)
    if isinstance(current, XsdList):
        item = _datatype(current.item_type)
        if item is None:
            item = AtomicType(builtin='anySimpleType', facets=Facets())
        return ListType(item=item, facets=_facets(levels, base_white_space='collapse', qualified=False))
    if isinstance(current, XsdUnion):
        members = tuple(
            _datatype(member) or AtomicType(builtin='anySimpleType', facets=Facets()) for member in _members_of(current)
        )
        return UnionType(members=members, facets=_facets(levels, base_white_space=None, qualified=False))
    # anySimpleType says nothing of a value: the schema library refuses a facet restricting it, so a restriction of it
    # adds none
    if current is not None and current.local_name == 'anySimpleType':
        return None
    raise SchemaNotRepresentable(f'{simple_type.name}: a simple type of an unknown kind: {current!r}')


def _facets(levels: list[XsdAtomicRestriction], *, base_white_space: str | None, qualified: bool) -> Facets:
    """The facets the restriction levels (most derived first) add."""
    found: dict[str, object] = {}
    patterns: list[tuple[str, ...]] = []
    enumeration: list[Element] | None = None
    for level in levels:
        restriction = _restriction_of(level)
        written = [child for child in restriction if child.tag.startswith(XS)]
        values = {}
        for child in written:
            values.setdefault(child.tag[len(XS):], []).append(child)
        for name, field in {**_INTEGER_FACETS, **_RANGE_FACETS, 'whiteSpace': 'white_space'}.items():
            if field not in found and name in values:
                value = values[name][0].get('value', '').strip()
                found[field] = int(value) if name in _INTEGER_FACETS else value
        if 'pattern' in values:
            patterns.insert(0, tuple(child.get('value', '') for child in values['pattern']))
        if enumeration is None and 'enumeration' in values:
            enumeration = values['enumeration']
            enumeration_level = level
    white_space = found.get('white_space') or base_white_space
    if 'white_space' in found and found['white_space'] == base_white_space:
        found.pop('white_space')
    if enumeration is not None:
        found['enumeration'] = tuple(
            _enumeration_value(child, level=enumeration_level, white_space=white_space, qualified=qualified)
            for child in enumeration
        )
    if patterns:
        found['pattern'] = tuple(patterns)
    return Facets(**found)


def _base_of(level: XsdAtomicRestriction) -> XsdSimpleType | XsdComplexType | None:
    """The type a level restricts: inside a redefine, a restriction of its own name restricts the type it redefines."""
    base = _restriction_of(level).get('base')
    if level.redefine is not None and base is not None and level.schema.resolve_qname(base) == level.name:
        return level.redefine
    return level.base_type


def _members_of(union: XsdUnion) -> list[XsdSimpleType]:
    """The members of a union in the order it gives them: those `memberTypes` names, then the ones written inside it
    (the schema library lists the written ones first; the order decides which member a value is taken by)."""
    # a written member is its xs:simpleType child, or that child's derivation the schema library keeps as its element
    written = {id(element) for child in union.elem for element in (child, *child)}
    nested = [member for member in union.member_types if id(member.elem) in written]
    named = [member for member in union.member_types if id(member.elem) not in written]
    return named + nested


def _restriction_of(level: XsdAtomicRestriction) -> Element:
    if level.elem.tag == f'{XS}restriction':
        return level.elem
    restriction = level.elem.find(f'{XS}restriction')
    if restriction is None:
        raise SchemaNotRepresentable(f'{level.name}: a restriction written nowhere')
    return restriction


def _enumeration_value(child: Element, *, level: XsdAtomicRestriction, white_space: str | None, qualified: bool) -> str:
    """An enumeration value as the values it is compared with: white space normalized as the type does; a qualified
    name by namespace and local name (`{uri}local`), resolved where it is written (the default namespace too)."""
    value = child.get('value', '')
    if white_space in ('replace', 'collapse'):
        value = re.sub(r'[\t\n\r]', ' ', value)
    if white_space == 'collapse':
        value = ' '.join(value.split())
    if not qualified:
        return value
    namespaces = {**(level.schema.source.get_nsmap(child) or {}), 'xml': 'http://www.w3.org/XML/1998/namespace'}
    prefix, _, local = value.rpartition(':')
    uri = namespaces.get(prefix) if prefix else namespaces.get('')
    if prefix and uri is None:
        raise SchemaNotRepresentable(f'{level.name}: the enumeration value {value} uses an unbound prefix')
    return f'{{{uri}}}{local}' if uri else local


def _is_builtin(simple_type: XsdSimpleType | None) -> bool:
    """A type the XML Schema namespace names: atomic, or a built-in list (NMTOKENS, IDREFS, ENTITIES)."""
    return simple_type is not None and (simple_type.name or '').startswith(XS)


def _is_qualified_name(builtin: XsdSimpleType) -> bool:
    """Whether the built-in is QName or NOTATION, or derives from one."""
    current = builtin
    while current is not None:
        if current.local_name in ('QName', 'NOTATION'):
            return True
        current = current.base_type
    return False
