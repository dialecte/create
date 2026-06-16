"""Shared utility functions for the generation pipeline."""
import re
import unicodedata
from typing import Any


# ---------------------------------------------------------------------------
# XSD pattern → JS regex conversion
# ---------------------------------------------------------------------------

# XSD Unicode block names → (start, end) code-point ranges.
# Covers all blocks that appear in IEC 61850 XSDs and common XML XSD patterns.
# Source: Unicode 15.1 block ranges.
_UNICODE_BLOCKS: dict[str, tuple[int, int]] = {
    'IsBasicLatin':             (0x0000, 0x007F),
    'IsLatin-1Supplement':      (0x0080, 0x00FF),
    'IsLatinExtended-A':        (0x0100, 0x017F),
    'IsLatinExtended-B':        (0x0180, 0x024F),
    'IsIPAExtensions':          (0x0250, 0x02AF),
    'IsSpacingModifierLetters': (0x02B0, 0x02FF),
    'IsCombiningDiacriticalMarks': (0x0300, 0x036F),
    'IsGreek':                  (0x0370, 0x03FF),
    'IsCyrillic':               (0x0400, 0x04FF),
    'IsArmenian':               (0x0530, 0x058F),
    'IsHebrew':                 (0x0590, 0x05FF),
    'IsArabic':                 (0x0600, 0x06FF),
    'IsThai':                   (0x0E00, 0x0E7F),
    'IsHiragana':               (0x3040, 0x309F),
    'IsKatakana':               (0x30A0, 0x30FF),
    'IsCJKUnifiedIdeographs':   (0x4E00, 0x9FFF),
}


def _block_range_escape(start: int, end: int) -> str:
    """Emit a JS-safe character range string like ``\\x00-\\x7F``."""
    def _esc(cp: int) -> str:
        if cp <= 0xFF:
            return f'\\x{cp:02x}'
        if cp <= 0xFFFF:
            return f'\\u{cp:04x}'
        return f'\\u{{{cp:x}}}'
    return f'{_esc(start)}-{_esc(end)}'


def xsd_pattern_to_js(pattern: str) -> str:
    """Convert an XSD regular expression to a JS-compatible regex string.

    Handles:
      - ``\\i`` / ``\\I`` (XML initial name char class)
      - ``\\c`` / ``\\C`` (XML name char class)
      - ``\\p{BlockName}`` → Unicode code-point range
      - ``&#xHHHH;`` and ``&#DDD;`` XML character references
    """
    result = pattern

    # \i  → XML initial name character (letter, underscore, colon)
    result = result.replace(r'\i', '[A-Za-z_:]')
    # \I  → complement
    result = result.replace(r'\I', '[^A-Za-z_:]')

    # \c  → XML name character (letter, digit, dot, dash, underscore, colon)
    result = result.replace(r'\c', '[-.:0-9A-Z_a-z]')
    # \C  → complement
    result = result.replace(r'\C', '[^-.:0-9A-Z_a-z]')

    # \p{BlockName} → code-point range
    def _replace_block(m: re.Match[str]) -> str:
        name = m.group(1)
        rng = _UNICODE_BLOCKS.get(name)
        if rng:
            return _block_range_escape(*rng)
        # Unknown block — leave as-is (will fail in JS, intentionally loud)
        return m.group(0)

    result = re.sub(r'\\p\{([^}]+)\}', _replace_block, result)

    # XML hex character reference &#xHHHH;
    result = re.sub(
        r'&#x([0-9A-Fa-f]+);',
        lambda m: chr(int(m.group(1), 16)),
        result,
    )
    # XML decimal character reference &#DDD;
    result = re.sub(
        r'&#(\d+);',
        lambda m: chr(int(m.group(1), 10)),
        result,
    )

    return result
def local_name(qname: str) -> str:
    """Extract local name from a Clark-notation QName like '{uri}local' or 'prefix:local'."""
    if qname.startswith('{'):
        return qname.split('}', 1)[-1]
    if ':' in qname:
        return qname.split(':', 1)[-1]
    return qname
def namespace_uri(qname: str) -> str | None:
    """Extract namespace URI from Clark-notation QName '{uri}local'. Returns None if absent."""
    if qname.startswith('{'):
        return qname[1:].split('}', 1)[0]
    return None
def tokenize_xpath(xpath: str) -> list[str]:
    """Split an XPath selector into its element path tokens.

    Strips namespace prefixes and leading './'.
    Examples:
        'tNS:LNode'       -> ['LNode']
        './/SubNetwork'    -> ['SubNetwork']
        'Bay/ConductingEquipment' -> ['Bay', 'ConductingEquipment']
    """
    if not xpath:
        return []
    # Remove leading ./ or .//
    cleaned = re.sub(r'^\.//?', '', xpath)
    parts = cleaned.split('/')
    tokens = []
    for part in parts:
        part = part.strip()
        if not part or part == '.':
            continue
        # Strip namespace prefix
        tokens.append(local_name(part))
    return tokens
def get_facet_value(facet: Any) -> Any:
    """Extract a scalar value from an xmlschema facet object.

    Tries multiple access patterns that xmlschema uses across versions.
    """
    for attr in ('value', 'v', 'min_value', 'max_value'):
        val = getattr(facet, attr, None)
        if val is not None:
            return val
    # Fallback: try elem attribute
    elem = getattr(facet, 'elem', None)
    if elem is not None:
        raw = elem.get('value')
        if raw is not None:
            try:
                return int(raw)
            except (ValueError, TypeError):
                return raw
    return None
