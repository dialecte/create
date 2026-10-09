"""The one order the definition writes a set of names in."""
from collections.abc import Iterable


def sorted_names(names: Iterable[str]) -> tuple[str, ...]:
    """`names`, each once, in code point order: whatever order the set they come from iterates in (a set of strings
    iterates in an order its process's hash seed decides), the definition writes them the same way."""
    return tuple(sorted(set(names)))
