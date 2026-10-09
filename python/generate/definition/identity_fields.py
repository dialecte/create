"""The attributes that identify an element: those a `unique` or `key` reads on the element its selector selects.

A field identifies the selected element only when it reads one of its own attributes (`@x`, no element step; a
union field, each alternative that does). The selector is walked from the declaration that declares the
constraint, through the declarations the particles hold - names and namespaces as the paths test them, `.//` through
every descendant, and to the elements `parent-mapping.json` attaches - their global declaration, the one the
wildcard that admits them validates them by. An element a `*` step reaches counts only when it requires every such attribute: the author said
"whatever is there", and an element that may lack one has no identity without it.
"""
from dataclasses import dataclass, field

from generate.model.declarations import ElementDeclaration, ElementParticle, NameTest, SelectorPath, TypeDefinition
from generate.model.particles import held_leaves


def identity_fields(
    declarations: tuple[ElementDeclaration, ...],
    *,
    parent_mapping: dict[str, list[str]],
    types: tuple[TypeDefinition, ...] = (),
) -> dict[int, set[str]]:
    """Per declaration key, the keys of the attributes that identify it."""
    by_key = {declaration.key: declaration for declaration in declarations}
    globals_by_name: dict[str, list[ElementDeclaration]] = {}
    for declaration in declarations:
        if declaration.is_global:
            globals_by_name.setdefault(declaration.name, []).append(declaration)
    mapped: dict[str, list[ElementDeclaration]] = {}
    for child, parents in parent_mapping.items():
        for parent in parents:
            mapped.setdefault(parent, []).extend(globals_by_name.get(child, []))
    children = _Children(by_key=by_key, mapped=mapped, variants={variant.name: variant for variant in types})
    found: dict[int, set[str]] = {}
    for declaring in declarations:
        for constraint in declaring.constraints:
            if constraint.kind == 'keyref':
                continue
            tests = [
                path.attribute
                for alternatives in constraint.fields
                for path in alternatives
                if not path.steps and path.attribute is not None and path.attribute.name is not None
            ]
            for path in constraint.selector:
                # a constraint on the element itself does not identify it among others
                if not path.steps and not path.deep:
                    continue
                # `.//.` reaches whatever is there, as `*` does
                reached_by_wildcard = not path.steps or path.steps[-1].name is None
                for target in _selected(declaring, path, children=children):
                    declared = [_attribute_key(target, test) for test in tests]
                    keys = {key for key in declared if key is not None}
                    if reached_by_wildcard and not _requires_all(target, declared):
                        continue
                    if keys:
                        found.setdefault(target.key, set()).update(keys)
    return found


@dataclass
class _Children:
    """The child elements a declaration may hold: (name, namespace, declaration key) of each, found once."""

    by_key: dict[int, ElementDeclaration]
    mapped: dict[str, list[ElementDeclaration]]
    # the types elements may take with xsi:type: what they hold, an instance's element may hold
    variants: dict[str, TypeDefinition]
    found: dict[int, list[tuple[str, str, int]]] = field(default_factory=dict)

    def of(self, key: int) -> list[tuple[str, str, int]]:
        if key not in self.found:
            self.found[key] = self._read(key)
        return self.found[key]

    def _read(self, key: int) -> list[tuple[str, str, int]]:
        declaration = self.by_key[key]
        models = [declaration.content_model, *(self.variants[name].content_model for name in declaration.variants)]
        held = [
            (leaf.name, leaf.namespace, leaf.declaration)
            for model in models
            for leaf in held_leaves(model)
            if isinstance(leaf, ElementParticle) and leaf.declaration in self.by_key
        ]
        attached = [(child.name, child.namespace.uri, child.key) for child in self.mapped.get(declaration.name, [])]
        return held + attached


def _selected(declaring: ElementDeclaration, path: SelectorPath, *, children: _Children) -> list[ElementDeclaration]:
    context = {declaring.key}
    if path.deep and not path.steps:
        # `.//.` without the element itself: it identifies it no more than `.` does (its descendants may be other
        # elements of its own declaration)
        context = _self_and_descendants({child for start in context for _, _, child in children.of(start)}, children=children)
    elif path.deep:
        context = _self_and_descendants(context, children=children)
    for step in path.steps:
        context = {key for parent in context for name, namespace, key in children.of(parent) if _matches(step, name, namespace)}
    return [children.by_key[key] for key in context]


def _self_and_descendants(context: set[int], *, children: _Children) -> set[int]:
    reached = set(context)
    pending = list(context)
    while pending:
        for _, _, key in children.of(pending.pop()):
            if key not in reached:
                reached.add(key)
                pending.append(key)
    return reached


def _matches(test: NameTest, name: str, namespace: str) -> bool:
    return (test.name is None or test.name == name) and (test.namespace is None or test.namespace == namespace)


def _attribute_key(declaration: ElementDeclaration, test: NameTest) -> str | None:
    """The key of the attribute of `declaration` the test names, None when it declares none such."""
    for attribute in declaration.attributes:
        uri = attribute.namespace.uri if attribute.namespace is not None else ''
        if attribute.key.split(':')[-1] == test.name and uri == test.namespace:
            return attribute.key
    return None


def _requires_all(declaration: ElementDeclaration, keys: list[str | None]) -> bool:
    required = {attribute.key for attribute in declaration.attributes if attribute.required}
    return all(key is not None and key in required for key in keys)
