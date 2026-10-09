"""The committed schemas are what they claim: schemas libxml2 loads, with instances it judges valid - the input the
generator's self tier and its instance oracle start from."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from lxml import etree

from generate.definition.build import generate_definition
from tests.committed_schemas import COMMITTED_SCHEMAS, FIXTURES, entry_of

INSTANCES = {name: sorted((entry_of(name).parent / 'instances').glob('*.xml')) for name in COMMITTED_SCHEMAS}


@pytest.mark.parametrize(
    'instance',
    [pytest.param(path, id=f'{name}/{path.name}') for name, paths in INSTANCES.items() for path in paths],
)
def test_every_committed_instance_is_valid_for_libxml2(instance: Path) -> None:
    name = instance.parent.parent.name
    validator = etree.XMLSchema(etree.parse(str(entry_of(name))))
    assert validator.validate(etree.parse(str(instance))), [error.message for error in validator.error_log]


@pytest.mark.parametrize('name', sorted(COMMITTED_SCHEMAS))
def test_each_committed_schema_has_the_instances_it_declares(name: str) -> None:
    assert len(INSTANCES[name]) == int(COMMITTED_SCHEMAS[name].get('instances', 0))


@pytest.mark.skipif(shutil.which('node') is None, reason='needs Node to read the committed definition back')
@pytest.mark.parametrize('name', sorted(COMMITTED_SCHEMAS))
def test_the_generator_writes_the_committed_definition_of_each_committed_schema(name: str) -> None:
    # the facts, key order included; the smoke test checks the formatted bytes through the shipped engine
    committed = FIXTURES / 'definition' / name / 'definition.generated.ts'
    script = f"const m = await import({json.dumps(committed.as_uri())}); process.stdout.write(JSON.stringify([m.DEFINITION, m.TYPES]))"
    run = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, check=True)
    generated = generate_definition(entry_of(name))
    assert json.dumps([generated.definition, generated.types]) == json.dumps(json.loads(run.stdout))
