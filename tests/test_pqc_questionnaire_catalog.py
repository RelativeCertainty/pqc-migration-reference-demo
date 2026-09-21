"""Definition compiler proofs; fixtures contain no employer answers or text."""
from copy import deepcopy

import pytest

from scripts.build_pqc_questionnaire_catalog import compile_catalog


def definitions():
    def question(identifier):
        return {"id": identifier, "section": "Synthetic section", "question": f"Synthetic {identifier} question?",
            "whyItMatters": "Synthetic decision support.", "responseType": "long_text", "required": True,
            "requestedEvidence": "Synthetic reference.", "completionCriteria": "Synthetic criterion."}
    rfis = [{"id": f"SRC-RFI-{i:03d}", "title": f"Synthetic template {i}", "systemType": "Synthetic class",
        "purpose": "Synthetic purpose", "requiredSourceProfile": "One per deployment", "defaultCoordinatingRole": "Synthetic function",
        "expectedContributingRoles": ["Synthetic owner"], "systemSpecificQuestions": [question(f"SQ-{j:02d}") for j in range(1, 4)]}
        for i in range(1, 28)]
    source = {"schemaVersion": "synthetic.v1", "metadata": {"id": "synthetic", "classification": "synthetic", "status": "test"},
        "commonQuestionTemplates": [question(f"CQ-{i:02d}") for i in range(1, 25)], "sourceSystemRfis": rfis,
        "operatingContract": {"completionRule": "All required questions addressed; verification separate."},
        "responseVocabulary": {"scheduleEffects": ["none", "blocks_collection"]}}
    hints = {"boundary": "Examples only", "entries": [{"sourceId": r["id"], "examples": ["Synthetic example"]} for r in rfis]}
    return source, hints


def test_all_templates_preserve_all_original_definition_fields():
    source, hints = definitions()
    before = deepcopy(source)
    result = compile_catalog(source, hints, "a" * 64, "b" * 64)
    assert source == before
    assert len(result["templates"]) == 27
    bindings = set()
    for template, original in zip(result["templates"], source["sourceSystemRfis"], strict=True):
        assert len(template["questions"]) == 27
        for question, definition in zip(template["questions"], [*source["commonQuestionTemplates"], *original["systemSpecificQuestions"]], strict=True):
            assert question["id"] == original["id"] + "/" + definition["id"]
            assert question["sourceId"] == definition["id"]
            assert question["prompt"] == definition["question"]
            assert question["evidenceExpectation"] == definition["requestedEvidence"]
            for key in ("section", "whyItMatters", "responseType", "required", "completionCriteria"):
                assert question[key] == definition[key]
            bindings.add(question["id"])
    assert len(bindings) == 729
    assert result["operatingContract"] == source["operatingContract"]


def test_controlled_values_are_preserved_as_text():
    source, hints = definitions()
    source["commonQuestionTemplates"][-1].update(responseType="controlled_value", allowedValues=["yes", "yes_with_qualifications", "no", "pending"])
    result = compile_catalog(source, hints, "a" * 64, "b" * 64)
    assert all(t["questions"][23]["allowedValues"] == ["yes", "yes_with_qualifications", "no", "pending"] for t in result["templates"])


@pytest.mark.parametrize("defect", ["missing_template", "duplicate_template", "missing_common", "missing_specific", "missing_examples", "wrong_type", "boolean_choice"])
def test_incomplete_or_ambiguous_catalogs_fail_closed(defect):
    source, hints = definitions()
    if defect == "missing_template": source["sourceSystemRfis"].pop()
    if defect == "duplicate_template": source["sourceSystemRfis"][-1] = deepcopy(source["sourceSystemRfis"][0])
    if defect == "missing_common": source["commonQuestionTemplates"].pop()
    if defect == "missing_specific": source["sourceSystemRfis"][4]["systemSpecificQuestions"].pop()
    if defect == "missing_examples": hints["entries"].pop()
    if defect == "wrong_type": source["commonQuestionTemplates"][0]["responseType"] = "generic_routing"
    if defect == "boolean_choice": source["commonQuestionTemplates"][0]["allowedValues"] = [True]
    with pytest.raises(ValueError): compile_catalog(source, hints, "a" * 64, "b" * 64)
