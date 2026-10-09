"""The schemas committed as fixtures (`test/fixtures/xsd/<name>`), each with its entry document, the root chosen where
several elements could start a document, and how many valid instances it holds under `instances/` (`test/fixtures/committed-schemas.json`, also read by the CLI
smoke test): the generator's self tier runs on them
without network, and their generated files are committed under `test/fixtures/definition/<name>`."""
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / 'test' / 'fixtures'

COMMITTED_SCHEMAS: dict[str, dict[str, str | int]] = json.loads((FIXTURES / 'committed-schemas.json').read_text(encoding='utf-8'))


def entry_of(name: str) -> Path:
    return FIXTURES / 'xsd' / name / str(COMMITTED_SCHEMAS[name]['entry'])
