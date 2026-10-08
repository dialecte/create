"""The oracle states what XSD means; the cases below are the facts the generator's patterns must match."""
import pytest

from tests.xsd_oracle import xsd_accepts


def pattern(regex: str) -> str:
    return f'<xs:restriction base="xs:string"><xs:pattern value="{regex}"/></xs:restriction>'


@pytest.mark.parametrize(
    ('simple_type', 'value', 'accepted'),
    [
        pytest.param(pattern('[A-Z]+'), 'ABC', True, id='a value the pattern matches -> accepted'),
        pytest.param(pattern('[A-Z]+'), 'ABC1', False, id='a pattern matches the whole value, not a part -> refused'),
        pytest.param(pattern('a$'), 'a$', True, id='a dollar is a plain character in XSD -> accepted literally'),
        pytest.param(pattern(r'\d'), '٣', True, id='\\d is any Unicode decimal digit -> an Arabic-Indic three accepted'),
        pytest.param(pattern('.'), ' ', True, id='a dot excludes only line feed and carriage return -> U+2028 accepted'),
        pytest.param(pattern(r'\i\c*'), 'été', True, id='name characters are Unicode -> été accepted'),
        pytest.param(pattern('[a-z-[aeiou]]+'), 'xyz', True, id='class subtraction: consonants -> accepted'),
        pytest.param(pattern('[a-z-[aeiou]]+'), 'xyza', False, id='class subtraction: a vowel -> refused'),
    ],
)
def test_xsd_accepts(simple_type: str, value: str, accepted: bool) -> None:
    assert xsd_accepts(simple_type, value) is accepted
