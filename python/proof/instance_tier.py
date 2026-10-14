"""The instance tier on one (schema, instance) pair: the definition's structural prediction against libxml2's verdict,
on the instance as it is and on the edits of the mutation operators, as stable ids (`known-exceptions.json` lists
the ones a reviewed reason explains). A disagreement carries xmlschema's verdict, the second opinion that tells a
libxml2 fault (`libxml2:*`, xmlschema siding with us) from a fact of ours (xmlschema siding with libxml2). A known
libxml2 fault the walk can read a document with explains a disagreement when that reading gives libxml2's verdict and
xmlschema sides with us: it is counted by name, not listed.

Mutations start from an instance its suite or licence lets us edit, that libxml2 accepts and that the definition
predicts valid with nothing left unpredictable: any other starting point would blur which edit a verdict is about.
"""
import os
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from lxml import etree

from proof.instances import COMPARED, LIBXML2_EMPTY_CHOICE, Prediction, judge, predict, predict_at
from proof.mutations import mutated, mutations
from proof.pairs import InstancePair

# mutations per instance (seeded); PROOF_FULL=1 runs every one
SAMPLE = 40


@dataclass
class Outcome:
    findings: list[str] = field(default_factory=list)
    # what ran, for the report: mutations judged per operator, those left out as unpredictable, the known libxml2
    # faults that explained a disagreement; edits at a tag declared several ways, and among them those another
    # declaration of the tag would judge otherwise (libxml2 agreeing with the one the parent names: the evidence the
    # per-parent resolution is needed, and right)
    judged: Counter = field(default_factory=Counter)
    unpredictable: Counter = field(default_factory=Counter)
    known_faults: Counter = field(default_factory=Counter)
    # the ids of the disagreements a known libxml2 fault explained: what a reviewer reads to trust each use
    explained: list[str] = field(default_factory=list)
    per_parent: int = 0
    per_parent_decisive: int = 0
    mutated: bool = False


def run(pair: InstancePair) -> Outcome:
    generated, validator = pair.schema.generated, pair.schema.validator
    outcome = Outcome()
    try:
        root = etree.parse(str(pair.instance), etree.XMLParser(no_network=True, resolve_entities=False)).getroot()
    except etree.XMLSyntaxError:
        outcome.findings.append('unmutated/not-well-formed')
        return outcome
    prediction = predict(definition=generated.definition, types=generated.types, root=root)
    if prediction.unpredictable:
        outcome.findings += sorted({f'unmutated/unpredictable/{reason}' for reason in prediction.unpredictable})
        return outcome
    verdict = judge(validator, root)

    def as_libxml2() -> Prediction:
        return predict(definition=generated.definition, types=generated.types, root=root, as_libxml2=True)

    disagreement = _disagreement(pair, root, prediction, verdict, as_libxml2=as_libxml2, outcome=outcome, edit='unmutated')
    if disagreement is not None:
        outcome.findings.append(f'unmutated/{disagreement}')
        return outcome
    if not pair.mutable or verdict or prediction.faults:
        return outcome
    outcome.mutated = True
    size = None if os.environ.get('PROOF_FULL', '').lower() in ('1', 'true', 'yes') else SAMPLE
    for mutation in mutations(prediction.visits, size=size, seed=pair.id):
        document, edited = mutated(root, mutation)
        at = {'definition': generated.definition, 'types': generated.types, 'element': edited, 'declaration': mutation.declaration}
        expected = predict_at(**at)
        if expected.unpredictable:
            outcome.unpredictable[mutation.operator] += 1
            continue
        outcome.judged[mutation.operator] += 1
        if mutation.per_parent:
            outcome.per_parent += 1
            outcome.per_parent_decisive += _another_declaration_differs(generated.definition, at, expected)
        found = judge(validator, document)
        edit = f'{mutation.operator}/{mutation.path}/{mutation.edit}'
        disagreement = _disagreement(pair, document, expected, found, as_libxml2=_reading_at(at), outcome=outcome, edit=edit)
        if disagreement is not None:
            outcome.findings.append(f'{edit}/{disagreement}')
    return outcome


def _reading_at(at: dict) -> Callable[[], Prediction]:
    def as_libxml2() -> Prediction:
        return predict_at(**at, as_libxml2=True)

    return as_libxml2


def _another_declaration_differs(definition: dict, at: dict, expected: Prediction) -> bool:
    """Whether another declaration of the edited element's tag would predict another verdict than the one its
    parent's particle names (a declaration naming a type it cannot resolve is left out)."""
    held = at['declaration']
    ways = definition[etree.QName(at['element']).localname]['declarations'].values()
    for way in ways:
        if way is held:
            continue
        other = predict_at(**{**at, 'declaration': way})
        if not other.unpredictable and other.families() & COMPARED != expected.families() & COMPARED:
            return True
    return False


def _disagreement(
    pair: InstancePair,
    document: etree._Element,
    prediction: Prediction,
    verdict: frozenset[str],
    *,
    as_libxml2: Callable[[], Prediction],
    outcome: Outcome,
    edit: str,
) -> str | None:
    """None when the definition and libxml2 agree, or when libxml2's known fault explains why they do not."""
    ours, theirs = prediction.families() & COMPARED, verdict & COMPARED
    if ours == theirs:
        return None
    library = pair.schema.library
    if isinstance(library, Exception):
        second = 'xmlschema-refuses-the-schema'
    else:
        second = 'xmlschema-valid' if library.is_valid(etree.tostring(document).decode()) else 'xmlschema-invalid'
    # the fault explains the disagreement only when it is in play (the reading changed a verdict of a content model)
    # and the reading gives libxml2's verdict, xmlschema siding with us
    # (and the schema's documents declare an abstract element nothing substitutes for: the fault's only source)
    in_play = second == ('xmlschema-invalid' if ours else 'xmlschema-valid') and pair.schema.memberless_abstract_heads
    reading = as_libxml2() if in_play else None
    if reading is not None and reading.read_as_libxml2 and reading.families() & COMPARED == theirs:
        outcome.known_faults[LIBXML2_EMPTY_CHOICE] += 1
        outcome.explained.append(f'{LIBXML2_EMPTY_CHOICE}: {pair.id}/{edit}')
        return None
    return f"ours={'+'.join(sorted(ours)) or 'valid'}/libxml2={'+'.join(sorted(theirs)) or 'valid'}/{second}"
