"""The path grammar's refusals, on the parser itself: a schema library that loads a schema has already refused these;
the parser refuses them too rather than guess."""
import pytest

from generate_next.errors import SchemaNotRepresentable
from generate_next.model.identity_paths import parse_field, parse_selector

NAMESPACES = {'t': 'urn:t'}


@pytest.mark.parametrize(
    ('selector', 'named'),
    [
        pytest.param('t:A t:B', 't:A t:B', id='two steps without a slash -> refused'),
        pytest.param('t:A/@n', 'not attributes', id='a selector ending at an attribute -> refused'),
        pytest.param('x:A', 'unbound prefix x', id='a prefix bound nowhere -> refused'),
        pytest.param('t:A|', 'empty alternative', id='an empty alternative -> refused'),
        pytest.param('t:1A', 'not an identity constraint path', id='a name starting with a digit -> refused'),
        pytest.param('t:A//t:B', 't:A//t:B', id='// inside a path -> refused, only a leading .// is allowed'),
        pytest.param('t:A$', 'not an identity constraint path', id='a character outside the grammar -> refused, never skipped'),
    ],
)
def test_a_selector_outside_the_grammar_is_refused(selector: str, named: str) -> None:
    with pytest.raises(SchemaNotRepresentable, match=named):
        parse_selector(selector, namespaces=NAMESPACES)


def test_a_field_with_a_step_after_its_attribute_is_refused() -> None:
    with pytest.raises(SchemaNotRepresentable, match='@n/t:B'):
        parse_field('@n/t:B', namespaces=NAMESPACES)
