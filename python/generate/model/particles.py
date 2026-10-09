"""What a particle tree lets a document hold."""
from collections.abc import Iterator

from generate.model.declarations import ElementParticle, GroupParticle, Particle, WildcardParticle


def held_leaves(particle: Particle | None) -> Iterator[ElementParticle | WildcardParticle]:
    """The elements and wildcards of a particle tree a document may hold, in content order: a particle
    with `maxOccurs` 0 lets nothing it holds into a document."""
    if particle is None or particle.max_occurs == 0:
        return
    if isinstance(particle, GroupParticle):
        for nested in particle.particles:
            yield from held_leaves(nested)
    else:
        yield particle


def emptiable(particle: Particle) -> bool:
    """Whether a particle is satisfied by no element at all: an empty choice never is."""
    if particle.min_occurs == 0:
        return True
    match particle:
        case GroupParticle(kind='choice'):
            return any(emptiable(nested) for nested in particle.particles)
        case GroupParticle():
            return all(emptiable(nested) for nested in particle.particles)
        case _:
            return False
