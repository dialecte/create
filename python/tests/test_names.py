"""The one order the definition writes a set of names in."""
from generate.model.names import sorted_names


def test_names_are_written_once_each_in_code_point_order_whatever_order_they_come_in() -> None:
    assert sorted_names(['b', 'a', 'B', 'b', '']) == ('', 'B', 'a', 'b')
