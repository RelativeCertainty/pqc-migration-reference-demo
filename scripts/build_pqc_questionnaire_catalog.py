#!/usr/bin/env python3
"""Compile explicitly selected questionnaire *definitions*, never returned answers.

Copies authoritative text without rewriting questions. The private output is a
data input to the C# application; Python is not a runtime workflow authority.
No network, dependency installation, service launch or enterprise access occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import yaml


def read_definition(path: Path) -> tuple[dict, str]:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("symlink_definition_denied")
    raw = path.read_bytes()
    if len(raw) > 1_048_576:
        raise ValueError("definition_capacity_limit")
    value = yaml.safe_load(raw)
    if not isinstance(value, dict):
        raise ValueError("definition_object_required")
    return value, hashlib.sha256(raw).hexdigest()


def compile_catalog(source: dict, recognition: dict, source_sha: str, recognition_sha: str) -> dict:
    common = source["commonQuestionTemplates"]
    rfis = source["sourceSystemRfis"]
    expected_ids = [f"SRC-RFI-{i:03d}" for i in range(1, 28)]
    if [q["id"] for q in common] != [f"CQ-{i:02d}" for i in range(1, 25)]:
        raise ValueError("exact_common_question_set_required")
    if [r["id"] for r in rfis] != expected_ids:
        raise ValueError("exact_questionnaire_set_required")
    hints = {r["sourceId"]: r["examples"] for r in recognition["entries"]}
    if len(recognition["entries"]) != 27 or set(hints) != set(expected_ids):
        raise ValueError("recognition_crosswalk_incomplete")
    templates = []
    for rfi in rfis:
        specific = rfi["systemSpecificQuestions"]
        if [q["id"] for q in specific] != ["SQ-01", "SQ-02", "SQ-03"]:
            raise ValueError("exact_source_specific_question_set_required")
        questions = []
        for q in [*common, *specific]:
            if q["responseType"] not in {"structured_profile", "long_text", "reference_list", "controlled_value"}:
                raise ValueError("unsupported_response_type")
            if type(q["required"]) is not bool:
                raise ValueError("required_flag_invalid")
            question = {
                "id": f"{rfi['id']}/{q['id']}", "sourceId": q["id"],
                "section": q["section"], "prompt": q["question"],
                "whyItMatters": q["whyItMatters"], "responseType": q["responseType"],
                "required": q["required"], "evidenceExpectation": q["requestedEvidence"],
                "completionCriteria": q["completionCriteria"], "allowedValues": q.get("allowedValues", []),
            }
            if not all(isinstance(question[k], str) and question[k] for k in (
                    "id", "sourceId", "section", "prompt", "whyItMatters", "evidenceExpectation", "completionCriteria")):
                raise ValueError("question_definition_incomplete")
            if not all(isinstance(v, str) for v in question["allowedValues"]):
                raise ValueError("controlled_value_must_be_text")
            questions.append(question)
        templates.append({
            "id": rfi["id"], "title": rfi["title"], "systemType": rfi["systemType"],
            "purpose": rfi["purpose"], "requiredSourceProfile": rfi["requiredSourceProfile"],
            "defaultCoordinatingRole": rfi["defaultCoordinatingRole"],
            "expectedContributingRoles": rfi["expectedContributingRoles"],
            "examples": hints[rfi["id"]], "questions": questions,
        })
    return {
        "schemaVersion": "pqc.questionnaire-catalog.v1",
        "catalogId": source["metadata"]["id"],
        "catalogVersion": f"{source['schemaVersion']}@sha256:{source_sha}",
        "sourceSchemaVersion": source["schemaVersion"], "sourceSha256": source_sha,
        "recognitionSha256": recognition_sha,
        "sourceClassification": source["metadata"]["classification"],
        "sourceStatus": source["metadata"]["status"],
        "recognitionBoundary": recognition["boundary"],
        "operatingContract": source["operatingContract"],
        "scheduleEffects": source["responseVocabulary"]["scheduleEffects"],
        "templates": templates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--recognition", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        source, digest = read_definition(args.catalog.absolute())
        hints, hints_digest = read_definition(args.recognition.absolute())
        output = args.output.absolute()
        if any(p.is_symlink() for p in (output, *output.parents)):
            raise ValueError("symlink_output_denied")
        if output.parent.stat().st_mode & 0o077:
            raise ValueError("owner_only_output_directory_required")
        catalog = compile_catalog(source, hints, digest, hints_digest)
        content = json.dumps(catalog, ensure_ascii=False, indent=2).encode() + b"\n"
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        print(json.dumps({"status": "compiled", "templates": len(catalog["templates"]),
            "questionsPerTemplate": 27, "scopedQuestionBindings": 729,
            "sourceSha256": digest, "outputSha256": hashlib.sha256(content).hexdigest(),
            "sourceTextPreserved": True, "customerResponsesRead": False}))
        return 0
    except (ValueError, KeyError, TypeError, OSError, yaml.YAMLError):
        print('{"status":"questionnaire_definition_compilation_failed"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
