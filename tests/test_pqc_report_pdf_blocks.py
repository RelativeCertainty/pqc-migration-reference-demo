"""No-service content guards for PDF copies of both report HTML templates."""
from scripts.render_pqc_workspace_reports import ReportBlocks


def blocks(html):
    parser = ReportBlocks()
    parser.feed(html)
    parser.flush()
    return parser.blocks


def test_definition_terms_and_business_prose_survive_reading_copy_extraction():
    result = blocks("""<html><head><style>not visible</style></head><body>
    <h1>Synthetic report</h1><dl>
    <dt>Protected information</dt><dd>Archived statements &amp; correspondence.</dd>
    <dt>Confidentiality / trust lifetime</dt><dd><strong>Fifteen years</strong>; attributed, not enterprise policy.</dd>
    <dt>Business consequence</dt><dd>Recovery may fail if the former key dependency is lost.</dd>
    <dt>Compatibility constraints</dt><dd>Keep the legacy verifier until compatibility is demonstrated.</dd>
    </dl><p>No execution is authorized.</p></body></html>""")
    assert result == [
        ("h1", "Synthetic report"),
        ("dt", "Protected information"), ("dd", "Archived statements &amp; correspondence."),
        ("dt", "Confidentiality / trust lifetime"), ("dd", "<b>Fifteen years</b>; attributed, not enterprise policy."),
        ("dt", "Business consequence"), ("dd", "Recovery may fail if the former key dependency is lost."),
        ("dt", "Compatibility constraints"), ("dd", "Keep the legacy verifier until compatibility is demonstrated."),
        ("p", "No execution is authorized."),
    ]


def test_definition_rendering_does_not_admit_navigation_script_or_external_resources():
    result = blocks("""<body><nav><dl><dt>Navigation label</dt><dd>Not report content</dd></dl></nav>
    <script>secret()</script><dl><dt>Guidance</dt><dd><a href="https://csrc.nist.gov/pubs/cswp/39/upd1/final">NIST</a>
    <a href="file:///private/file">Literal unsupported link text</a></dd></dl></body>""")
    text = " ".join(value for _, value in result)
    assert "Navigation" not in text and "secret" not in text
    assert 'href="https://csrc.nist.gov/' in text
    assert "file:///" not in text
    assert "Literal unsupported link text" in text
