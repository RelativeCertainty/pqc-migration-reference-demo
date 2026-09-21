"""The app input is generated from all 27 raw source families, never canned UI."""
import json

import pytest

from scripts.build_pqc_enterprise_demo_fixture import prepare


def test_fixture_is_complete_bounded_and_has_no_prebuilt_reports(tmp_path):
    proof = prepare(tmp_path / "input", applications=12)
    fixture = json.loads((tmp_path / "input/synthetic-input.json").read_text())
    assert proof["sourceFamilies"] == 27
    assert proof["estateAreas"] == 10
    assert proof["subjects"] == 132
    assert fixture["synthetic"] is True
    assert fixture["tenantId"] == "synthetic-enterprise"
    assert "reports" not in fixture and "metrics" not in fixture
    assert fixture["sourceBinding"]["sourceScope"] == "all"
    assert len(fixture["observations"]) == proof["observations"]
    assert fixture["method"]["risk_rating_assigned"] is False
    assert all(row["risk_rating"] is None for row in fixture["riskReviews"])
    assert all(not row["execution_authorized"] for row in fixture["riskReviews"])
    assert all(row["imported_page_count"] > 0 for row in fixture["sourceProfiles"])
    assert len({row["subject_ref"] for row in fixture["inventory"]}) == proof["subjects"]
    assert (tmp_path / "input/synthetic-input.json").stat().st_mode & 0o077 == 0


def test_fixture_replay_does_not_overwrite(tmp_path):
    prepare(tmp_path / "input", applications=12)
    before = (tmp_path / "input/synthetic-input.json").read_bytes()
    with pytest.raises(FileExistsError):
        prepare(tmp_path / "input", applications=12)
    assert before == (tmp_path / "input/synthetic-input.json").read_bytes()


def test_invalid_size_creates_no_output(tmp_path):
    with pytest.raises(ValueError):
        prepare(tmp_path / "input", applications=10000)
    assert not (tmp_path / "input").exists()


def test_symlink_output_rejected(tmp_path):
    (tmp_path / "link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink_output_denied"):
        prepare(tmp_path / "link/input", applications=12)
