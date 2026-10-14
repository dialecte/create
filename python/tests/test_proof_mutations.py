"""The mutation operators on inline rows: every edit of a valid document the instance tier's schema covers (choices,
all groups, a tag declared two ways, wildcards, fixed and required attributes, mixed and simple content, xsi:type),
predicted from the edited element and judged by libxml2 on the whole document - the two agree on every edit."""
from collections import Counter
from pathlib import Path

from lxml import etree

from proof.instances import COMPARED, judge, predict, predict_at
from proof.mutations import mutated, mutations
from tests.test_proof_instances import OTHER, SCHEMA, document

VALID = document(
    '<A a="v"/><C1/><All><X/></All><Left><Item l="1"/></Left><Open o:x="1"/><Lax><Unknown/></Lax>'
    '<Mixed>text<B/></Mixed><Simple>s</Simple><P xsi:type="t:tExt" e="1"><Base/><Extra/></P>',
    root_attributes='req="1" fix="1"',
)
OPERATORS = {'ATTR-REQUIRED', 'ATTR-FIXED', 'ATTR-UNDECLARED', 'CHILD-EDIT', 'CHILD-NS', 'TEXT'}


def test_every_edit_is_predicted_as_libxml2_judges_it(tmp_path: Path, generated_of) -> None:
    (tmp_path / 'other.xsd').write_text(OTHER, encoding='utf-8')
    generated = generated_of(SCHEMA.replace('<xs:element name="Root">', '<xs:import namespace="urn:other" schemaLocation="other.xsd"/><xs:element name="Root">'))
    validator = etree.XMLSchema(etree.parse(str(tmp_path / 'entry.xsd')))
    root = etree.fromstring(VALID)
    prediction = predict(definition=generated.definition, types=generated.types, root=root)
    assert prediction.faults == [] and judge(validator, root) == frozenset()
    disagreements, ran = [], Counter()
    for mutation in mutations(prediction.visits):
        copy, edited = mutated(root, mutation)
        expected = predict_at(definition=generated.definition, types=generated.types, element=edited, declaration=mutation.declaration)
        assert expected.unpredictable == [], mutation
        ran[mutation.operator] += 1
        if expected.families() & COMPARED != judge(validator, copy) & COMPARED:
            disagreements.append(f'{mutation.operator} {mutation.path} {mutation.edit}')
    assert disagreements == []
    assert set(ran) == OPERATORS


def test_a_sample_is_seeded_and_keeps_the_order_found(generated_of) -> None:
    generated = generated_of(SCHEMA.replace('<xs:element name="Root">', '<xs:import namespace="urn:other"/><xs:element name="Root">'))
    visits = predict(definition=generated.definition, types=generated.types, root=etree.fromstring(VALID)).visits
    every = [(mutation.path, mutation.edit) for mutation in mutations(visits)]
    drawn = [(mutation.path, mutation.edit) for mutation in mutations(visits, size=40, seed='pair')]
    assert drawn == [(mutation.path, mutation.edit) for mutation in mutations(visits, size=40, seed='pair')]
    assert drawn != [(mutation.path, mutation.edit) for mutation in mutations(visits, size=40, seed='other')]
    assert len(drawn) == 40 and drawn == [found for found in every if found in drawn]
    # every operator gets its share, however few its edits beside the insertions
    operators = {mutation.operator for mutation in mutations(visits)}
    assert {mutation.operator for mutation in mutations(visits, size=40, seed='pair')} == operators
    assert len(set(every)) == len(every) > 40
