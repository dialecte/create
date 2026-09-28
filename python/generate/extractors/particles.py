"""Extract the content model of an element as a particle tree."""
from typing import Any

from generate.ir import Particle


def extract_content_model(xsd_elem: Any) -> Particle | None:
    """The particle tree of an element's content, or None when it holds no elements.

    xmlschema API:
      XsdComplexType.content: XsdGroup (iterable of XsdGroup | XsdElement | XsdAnyElement)
      XsdGroup.model: 'sequence' | 'choice' | 'all'; .min_occurs / .max_occurs (None = unbounded)
      XsdAnyElement.namespace: list[str]; .process_contents: str
      XsdElement.abstract; .iter_substitutes() → concrete members, transitively
    """
    xsd_type = getattr(xsd_elem, 'type', None)
    content = getattr(xsd_type, 'content', None)
    if content is None or getattr(content, 'model', None) is None:
        return None
    particle = _group(content)
    return particle if particle.particles else None


def _group(group: Any) -> Particle:
    particles: list[Particle] = []
    for item in group:
        if getattr(item, 'model', None) is not None:
            nested = _group(item)
            if nested.particles:
                particles.append(nested)
            continue
        cls_name = type(item).__name__
        if 'Any' in cls_name and 'Element' in cls_name:
            particles.append(_wildcard(item))
            continue
        particles.append(_element_or_substitutes(item))
    return Particle(
        kind=group.model,
        min_occurs=getattr(group, 'min_occurs', 1),
        max_occurs=getattr(group, 'max_occurs', 1),
        particles=particles,
    )


def _wildcard(item: Any) -> Particle:
    namespace = getattr(item, 'namespace', None)
    return Particle(
        kind='any',
        min_occurs=getattr(item, 'min_occurs', 1),
        max_occurs=getattr(item, 'max_occurs', 1),
        namespace=list(namespace) if namespace else None,
        process_contents=getattr(item, 'process_contents', None),
    )


def _element_or_substitutes(item: Any) -> Particle:
    """An element particle; a substitution head stands for a choice among its members."""
    min_occ = getattr(item, 'min_occurs', 1)
    max_occ = getattr(item, 'max_occurs', 1)
    iter_substitutes = getattr(item, 'iter_substitutes', None)
    members = sorted(iter_substitutes(), key=lambda m: m.local_name or '') if callable(iter_substitutes) else []
    if not members:
        return Particle(kind='element', name=item.local_name, min_occurs=min_occ, max_occurs=max_occ)

    alternatives = [] if getattr(item, 'abstract', False) else [item]
    alternatives.extend(members)
    return Particle(
        kind='choice',
        min_occurs=min_occ,
        max_occurs=max_occ,
        particles=[Particle(kind='element', name=alt.local_name) for alt in alternatives],
    )
