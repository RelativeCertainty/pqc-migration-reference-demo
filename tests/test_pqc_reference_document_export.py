"""Pure source parsing checks; actual Office files require separate visual QA."""

import importlib.util
import sys
from pathlib import Path

import pytest


# The document tool uses the installed offline Office environment. Keep these
# syntax tests separate from production-runtime dependency requirements.
pytest.importorskip("docx")
_path = Path(__file__).parents[1] / "scripts/export_pqc_reference_documents.py"
_spec = importlib.util.spec_from_file_location("pqc_reference_export", _path)
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
parse = _module.parse_markdown


def test_all_text_and_list_semantics_survive_parsing():
    result = parse(
        "# Draft\n\nA soft\nline.\n\n1. First\n   continuation\n"
        "2. Second\n\n## Details\n\n- Parent\n  - Child\n"
        "\n```sh\ncommand --arg\n  literal indent\n```\n"
    )
    assert [(b.kind, b.text, b.level) for b in result] == [
        ("heading", "Draft", 1),
        ("paragraph", "A soft line.", 0),
        ("number", "First\ncontinuation", 0),
        ("number", "Second", 0),
        ("heading", "Details", 2),
        ("bullet", "Parent", 0),
        ("bullet", "Child", 1),
        ("code", "command --arg", 0),
        ("code", "  literal indent", 0),
    ]
    assert result[3].start == 2


def test_links_and_code_preserve_display_text():
    assert (
        _module._plain_inline(
            "[Official API](https://example.invalid/api?v=1) and `field_name` with **emphasis**"
        )
        == "Official API and field_name with emphasis"
    )


@pytest.mark.parametrize(
    "source",
    [
        "No title",
        "# Title\n# Second",
        "# Title\n```\nunclosed",
        "# Title\n| table |",
        "# Title\n![image](x.png)",
    ],
)
def test_unhandled_structure_fails_instead_of_losing_content(source):
    with pytest.raises(ValueError):
        parse(source)


def test_business_brief_and_named_detail_overrides_are_explicit():
    tokens = _module.STYLE_TOKENS
    assert tokens["body"] == {
        "font": "Calibri",
        "pt": 11,
        "before": 0,
        "after": 6,
        "line": 264,
    }
    assert tokens["list"] == {
        "left_dxa": 720,
        "hanging_dxa": 360,
        "after": 8,
        "line": 280,
    }
    assert tokens["named_overrides"]["detail_appendix"]["pt"] == 10
    assert tokens["named_overrides"]["no_decorative_rules"] is True
