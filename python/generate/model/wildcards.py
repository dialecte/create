"""Wildcards resolved against the document that writes them, and the attribute wildcard of a type.

A type's attribute wildcard is computed here from what each document writes, not taken from the schema
library: it merges the `##other` of a base type with the one of a type extending it as if both were
written in the same document, which loses what the base's admits.
"""
from generate.model.names import sorted_names
from xml.etree.ElementTree import Element

from xmlschema.validators import XsdAttributeGroup, XsdComplexType, XsdComponent

from generate.errors import SchemaNotRepresentable
from generate.model.declarations import Wildcard

XS = '{http://www.w3.org/2001/XMLSchema}'
# how strictly a wildcard has what it admits checked, from the least strict on
PROCESS_CONTENTS = ('skip', 'lax', 'strict')


def wildcard_of(written: Element, *, target_namespace: str) -> Wildcard:
    """The wildcard an `<any>` or `<anyAttribute>` writes, its namespaces resolved against
    `target_namespace` - the one of the document that writes it (absent: '')."""
    process_contents = written.get('processContents', 'strict')
    tokens = written.get('namespace', '##any').split()
    if tokens == ['##any']:
        return Wildcard(namespace=None, not_namespace=(), process_contents=process_contents)
    if tokens == ['##other']:
        # every namespace but the declaring document's own, and not the absence of one
        excluded = sorted_names({target_namespace, ''})
        return Wildcard(namespace=None, not_namespace=excluded, process_contents=process_contents)
    special = {'##targetNamespace': target_namespace, '##local': ''}
    listed = sorted_names(special.get(token, token) for token in tokens)
    return Wildcard(namespace=listed, not_namespace=None, process_contents=process_contents)


def union(wildcards: list[Wildcard], *, process_contents: str) -> Wildcard:
    """What any of `wildcards` admits: the namespaces they list add up; one some exclude stays excluded
    only when every excluding wildcard excludes it and none lists it."""
    listed = {namespace for wildcard in wildcards for namespace in wildcard.namespace or ()}
    exclusions = [set(wildcard.not_namespace) for wildcard in wildcards if wildcard.not_namespace is not None]
    if exclusions:
        excluded = set.intersection(*exclusions) - listed
        return Wildcard(namespace=None, not_namespace=sorted_names(excluded), process_contents=process_contents)
    return Wildcard(namespace=sorted_names(listed), not_namespace=None, process_contents=process_contents)


def intersection(wildcards: list[Wildcard], *, process_contents: str) -> Wildcard:
    """What every one of `wildcards` admits. XSD 1.0 cannot express it for two wildcards admitting the namespaces
    other than two different ones: the schema is in error (other than one namespace and other than none is
    other than that namespace)."""
    excluded_names = {
        frozenset(wildcard.not_namespace) - {''} for wildcard in wildcards if wildcard.not_namespace
    } - {frozenset()}
    if len(excluded_names) > 1:
        raise SchemaNotRepresentable('XSD 1.0 cannot express what wildcards excluding different namespaces both admit')
    excluded = {namespace for wildcard in wildcards for namespace in wildcard.not_namespace or ()}
    lists = [set(wildcard.namespace) for wildcard in wildcards if wildcard.namespace is not None]
    if lists:
        kept = set.intersection(*lists) - excluded
        return Wildcard(namespace=sorted_names(kept), not_namespace=None, process_contents=process_contents)
    return Wildcard(namespace=None, not_namespace=sorted_names(excluded), process_contents=process_contents)


def admits(wildcard: Wildcard, namespace: str) -> bool:
    """Whether `wildcard` admits an element or attribute of `namespace` ('' for none)."""
    if wildcard.namespace is not None:
        return namespace in wildcard.namespace
    return namespace not in (wildcard.not_namespace or ())


def weakest_process_contents(wildcards: list[Wildcard]) -> str:
    return min((wildcard.process_contents for wildcard in wildcards), key=PROCESS_CONTENTS.index)


def attribute_wildcard_of(complex_type: XsdComplexType) -> Wildcard | None:
    """The attribute wildcard of a complex type: the one it declares - its `<anyAttribute>` and those of
    the attribute groups it references, intersected - and, for a type that extends another, the union with
    the base type's, processed as the type's own says. A restriction keeps only what it declares. None
    when the type admits no other attribute."""
    derivation_types = []
    current: XsdComplexType | None = complex_type
    # each level a type extends, down to one that restricts (anyType restricts itself)
    while isinstance(current, XsdComplexType):
        derivation_types.append(current)
        if current.derivation != 'extension':
            break
        current = current.base_type
    # from the restricting level up, every level an extension of the one before
    wildcard: Wildcard | None = None
    for level in reversed(derivation_types):
        declared = _declared_wildcard(level)
        if declared is not None:
            wildcard = declared if wildcard is None else union([declared, wildcard], process_contents=declared.process_contents)
    # a wildcard that admits no namespace at all (what an intersection may leave) admits nothing
    return None if wildcard is None or wildcard.namespace == () else wildcard


def _declared_wildcard(complex_type: XsdComplexType) -> Wildcard | None:
    # a derived type writes its attributes in its extension or restriction, any other in itself
    holder = complex_type.elem
    content = next((child for child in holder if child.tag in (f'{XS}complexContent', f'{XS}simpleContent')), None)
    if content is not None:
        holder = next(child for child in content if child.tag in (f'{XS}extension', f'{XS}restriction'))
    return _wildcard_in(holder, component=complex_type)


def _wildcard_in(holder: Element, *, component: XsdComponent) -> Wildcard | None:
    """The `<anyAttribute>` written in `holder` intersected with the attribute wildcards of the attribute
    groups it references, each resolved in its own document; processed as the `<anyAttribute>` says, else
    as the first group with one."""
    found: list[Wildcard] = []
    local = holder.find(f'{XS}anyAttribute')
    if local is not None:
        found.append(wildcard_of(local, target_namespace=component.target_namespace or ''))
    for reference in holder.findall(f'{XS}attributeGroup'):
        name = component.schema.resolve_qname(reference.get('ref'))
        # inside a redefine, a group naming itself names the group it redefines
        redefining = isinstance(component, XsdAttributeGroup) and name == component.name
        group = component.redefine if redefining else component.maps.attribute_groups[name]
        referenced = _wildcard_in(group.elem, component=group)
        if referenced is not None:
            found.append(referenced)
    if not found:
        return None
    return intersection(found, process_contents=found[0].process_contents)
