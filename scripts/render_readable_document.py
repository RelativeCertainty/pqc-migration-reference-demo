#!/usr/bin/env python3
"""Render Markdown as a polished, self-contained browser reading copy."""

from __future__ import annotations

import argparse
import hashlib
import html
import math
import os
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token


CLASSIFICATIONS = ("private", "internal", "public")
RENDERER_VERSION = "1"
_BARE_URL_RE = re.compile(r"(?<![<(])https?://[^\s<>()]+")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_WORD_RE = re.compile(r"\b[\w'’-]+\b", re.UNICODE)


@dataclass(frozen=True)
class Heading:
    level: int
    identifier: str
    label: str


def _split_url_trailing_punctuation(value: str) -> tuple[str, str]:
    trailing = ""
    while value and value[-1] in ".,;:!?":
        trailing = value[-1] + trailing
        value = value[:-1]
    pairs = ((")", "("), ("]", "["), ("}", "{"))
    for closing, opening in pairs:
        while value.endswith(closing) and value.count(closing) > value.count(opening):
            trailing = closing + trailing
            value = value[:-1]
    return value, trailing


def _autolink_text_segment(segment: str) -> str:
    def replace(match: re.Match[str]) -> str:
        url, trailing = _split_url_trailing_punctuation(match.group(0))
        if not url:
            return match.group(0)
        return f"<{url}>{trailing}"

    return _BARE_URL_RE.sub(replace, segment)


def autolink_bare_urls(markdown: str) -> str:
    """Convert bare web URLs to CommonMark autolinks outside code spans/fences."""

    rendered_lines: list[str] = []
    active_fence: tuple[str, int] | None = None

    for line in markdown.splitlines(keepends=True):
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            marker_type = marker[0]
            marker_length = len(marker)
            if active_fence is None:
                active_fence = (marker_type, marker_length)
            elif marker_type == active_fence[0] and marker_length >= active_fence[1]:
                active_fence = None
            rendered_lines.append(line)
            continue

        if active_fence is not None:
            rendered_lines.append(line)
            continue

        parts = re.split(r"(`+)", line)
        in_code = False
        processed: list[str] = []
        for part in parts:
            if part.startswith("`"):
                in_code = not in_code
                processed.append(part)
            elif in_code:
                processed.append(part)
            else:
                processed.append(_autolink_text_segment(part))
        rendered_lines.append("".join(processed))

    return "".join(rendered_lines)


def _heading_label(inline: Token) -> str:
    if not inline.children:
        return inline.content.strip()
    visible_types = {"text", "code_inline", "html_inline"}
    return "".join(
        child.content for child in inline.children if child.type in visible_types
    ).strip()


def _slugify(label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label)
    ascii_label = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_label).strip("-")
    return slug or "section"


def _decorate_headings(tokens: list[Token]) -> tuple[list[Heading], str | None]:
    headings: list[Heading] = []
    first_h1: str | None = None
    counts: dict[str, int] = {}

    for index, token in enumerate(tokens[:-1]):
        if token.type != "heading_open":
            continue
        inline = tokens[index + 1]
        if inline.type != "inline":
            continue
        level = int(token.tag.removeprefix("h"))
        label = _heading_label(inline) or "Untitled section"
        base = _slugify(label)
        counts[base] = counts.get(base, 0) + 1
        identifier = base if counts[base] == 1 else f"{base}-{counts[base]}"
        token.attrSet("id", identifier)
        headings.append(Heading(level=level, identifier=identifier, label=label))
        if level == 1 and first_h1 is None:
            first_h1 = label

    return headings, first_h1


def _safe_href(value: str) -> str | None:
    candidate = html.unescape(value).strip()
    compact = re.sub(r"[\x00-\x20]+", "", candidate).lower()
    if compact.startswith(("javascript:", "vbscript:", "data:", "file:")):
        return None
    if candidate.startswith("//"):
        return None
    scheme = urlsplit(candidate).scheme.lower()
    if scheme and scheme not in {"http", "https", "mailto"}:
        return None
    return candidate


def _harden_links(tokens: list[Token]) -> None:
    for token in tokens:
        if token.children:
            _harden_links(token.children)
        if token.type != "link_open":
            continue
        href = token.attrGet("href") or ""
        safe = _safe_href(href)
        if safe is None:
            token.attrSet("href", "#unsafe-link-suppressed")
            token.attrSet("aria-disabled", "true")
            token.attrJoin("class", "unsafe-link")
            token.attrSet("title", "Unsafe link target suppressed")
            continue
        token.attrSet("href", safe)
        if urlsplit(safe).scheme.lower() in {"http", "https", "mailto"}:
            token.attrSet("rel", "noopener noreferrer")
            token.attrSet("referrerpolicy", "no-referrer")


def _install_safe_image_renderer(markdown: MarkdownIt) -> None:
    def render_image(
        renderer: object,
        tokens: list[Token],
        index: int,
        options: dict[str, object],
        env: dict[str, object],
    ) -> str:
        token = tokens[index]
        label = renderer.renderInlineAsText(token.children or [], options, env)
        label = label.strip() or "Image"
        source = _safe_href(token.attrGet("src") or "")
        safe_label = html.escape(label)
        if source is None:
            return f'<span class="image-placeholder">[Image suppressed: {safe_label}]</span>'
        safe_source = html.escape(source, quote=True)
        return (
            '<span class="image-placeholder">[Image not loaded automatically: '
            f'{safe_label} — <a href="{safe_source}" rel="noopener noreferrer" '
            'referrerpolicy="no-referrer">open image</a>]</span>'
        )

    markdown.add_render_rule("image", render_image)


def _toc_markup(headings: list[Heading]) -> str:
    visible = [heading for heading in headings if heading.level in (2, 3)]
    if not visible:
        return '<p class="toc-empty">No section headings</p>'
    items = "\n".join(
        (
            f'<li class="toc-level-{heading.level}">'
            f'<a href="#{html.escape(heading.identifier, quote=True)}">'
            f"{html.escape(heading.label)}</a></li>"
        )
        for heading in visible
    )
    return f'<ol class="toc-list">{items}</ol>'


def _human_timestamp(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds).astimezone().strftime(
        "%B %-d, %Y at %-I:%M %p %Z"
    )


def _page_template(
    *,
    body: str,
    title: str,
    toc: str,
    classification: str,
    source_name: str,
    source_hash: str,
    modified: str,
    word_count: int,
    reading_minutes: int,
) -> str:
    safe_title = html.escape(title)
    safe_source_name = html.escape(source_name)
    source_href = quote(source_name)
    robots = (
        "index,follow" if classification == "public" else "noindex,nofollow,noarchive"
    )
    class_label = {
        "private": "Private local reader",
        "internal": "Internal reader",
        "public": "Public reading copy",
    }[classification]
    class_note = {
        "private": "Keep this copy local unless sharing is explicitly approved.",
        "internal": "Not intended for public distribution.",
        "public": "Approved presentation copy.",
    }[classification]

    return f"""<!doctype html>
<html lang="en" data-classification="{classification}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="{robots}">
  <meta name="referrer" content="no-referrer">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; object-src 'none'; base-uri 'none'; form-action 'none'">
  <meta name="color-scheme" content="light dark">
  <meta name="generator" content="PBA readable document renderer v{RENDERER_VERSION}">
  <title>{safe_title}</title>
  <style>
    :root {{
      --page: #edf1f5;
      --paper: #ffffff;
      --text: #20252d;
      --muted: #647080;
      --line: #d9e0e8;
      --accent: #285f86;
      --accent-soft: #e9f2f8;
      --notice: #7c4b13;
      --notice-bg: #fff3dc;
      --code: #f4f6f8;
      --shadow: 0 18px 55px rgba(31, 43, 58, 0.11);
      --measure: 76ch;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --page: #11161d;
        --paper: #1a212b;
        --text: #e8edf3;
        --muted: #a8b3c0;
        --line: #35404e;
        --accent: #8fc8ed;
        --accent-soft: #203848;
        --notice: #f0c47b;
        --notice-bg: #3a2b19;
        --code: #111821;
        --shadow: 0 18px 55px rgba(0, 0, 0, 0.32);
      }}
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      background: var(--page);
      color: var(--text);
      font-family: ui-serif, Georgia, Cambria, "Times New Roman", serif;
      font-size: 18px;
      line-height: 1.72;
      text-rendering: optimizeLegibility;
    }}
    a {{ color: var(--accent); text-underline-offset: 0.16em; }}
    a:hover {{ text-decoration-thickness: 2px; }}
    :focus-visible {{ outline: 3px solid var(--accent); outline-offset: 3px; }}
    .skip-link {{
      position: fixed;
      z-index: 10;
      top: 0.5rem;
      left: 0.5rem;
      padding: 0.65rem 0.9rem;
      background: var(--paper);
      border: 2px solid var(--accent);
      transform: translateY(-160%);
    }}
    .skip-link:focus {{ transform: none; }}
    .topbar {{
      border-bottom: 1px solid var(--line);
      background: color-mix(in srgb, var(--paper) 92%, transparent);
      backdrop-filter: blur(10px);
    }}
    .topbar-inner {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 0.85rem clamp(1rem, 3vw, 2.5rem);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      font-size: 0.83rem;
    }}
    .classification {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      color: var(--notice);
      font-weight: 700;
      letter-spacing: 0.02em;
    }}
    .classification::before {{
      content: "";
      width: 0.62rem;
      height: 0.62rem;
      border-radius: 50%;
      background: currentColor;
    }}
    .reader-actions {{ display: flex; flex-wrap: wrap; gap: 0.55rem; }}
    .reader-actions a,
    .reader-actions button {{
      appearance: none;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--paper);
      color: var(--text);
      cursor: pointer;
      font: inherit;
      padding: 0.42rem 0.75rem;
      text-decoration: none;
    }}
    .reader-actions a:hover,
    .reader-actions button:hover {{ border-color: var(--accent); }}
    .shell {{
      max-width: 1320px;
      margin: 0 auto;
      padding: clamp(1.1rem, 3vw, 2.6rem);
      display: grid;
      grid-template-columns: minmax(210px, 270px) minmax(0, 1fr);
      gap: clamp(1.1rem, 3vw, 2.8rem);
      align-items: start;
    }}
    .toc {{
      position: sticky;
      top: 1.3rem;
      max-height: calc(100vh - 2.6rem);
      overflow: auto;
      padding: 1rem 0.9rem 1rem 0;
      color: var(--muted);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      font-size: 0.8rem;
      line-height: 1.35;
    }}
    .toc-title {{
      margin: 0 0 0.7rem;
      color: var(--text);
      font-size: 0.76rem;
      font-weight: 800;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }}
    .toc-list {{ margin: 0; padding: 0; list-style: none; }}
    .toc-list li {{ margin: 0.22rem 0; }}
    .toc-list a {{
      display: block;
      padding: 0.28rem 0.4rem;
      border-left: 2px solid transparent;
      color: var(--muted);
      text-decoration: none;
    }}
    .toc-list a:hover,
    .toc-list a:focus {{
      border-left-color: var(--accent);
      color: var(--accent);
      background: var(--accent-soft);
    }}
    .toc-level-3 {{ padding-left: 0.75rem; }}
    .paper {{
      min-width: 0;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: clamp(1.25rem, 5vw, 4.5rem);
    }}
    .document-meta {{
      max-width: var(--measure);
      margin: 0 auto 2.5rem;
      padding: 0 0 1.15rem;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      font-size: 0.78rem;
      line-height: 1.5;
    }}
    .document-meta strong {{ color: var(--text); }}
    .document-meta code {{ overflow-wrap: anywhere; word-break: break-all; }}
    .notice {{
      max-width: var(--measure);
      margin: 0 auto 2rem;
      padding: 0.85rem 1rem;
      border-left: 4px solid var(--notice);
      border-radius: 6px;
      background: var(--notice-bg);
      color: var(--notice);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      font-size: 0.86rem;
      line-height: 1.5;
    }}
    article > * {{ max-width: var(--measure); margin-left: auto; margin-right: auto; }}
    article h1,
    article h2,
    article h3,
    article h4 {{
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      line-height: 1.2;
      letter-spacing: -0.025em;
      scroll-margin-top: 1.5rem;
    }}
    article h1 {{
      margin-top: 0;
      margin-bottom: 1.4rem;
      font-size: clamp(2.1rem, 5vw, 3.5rem);
      font-weight: 760;
    }}
    article h2 {{
      margin-top: 3.4rem;
      margin-bottom: 1rem;
      padding-top: 0.5rem;
      border-top: 1px solid var(--line);
      font-size: clamp(1.5rem, 3vw, 2rem);
    }}
    article h3 {{ margin-top: 2.4rem; font-size: 1.25rem; }}
    article h4 {{ margin-top: 2rem; font-size: 1.05rem; }}
    article p {{ margin-top: 0.85rem; margin-bottom: 0.85rem; }}
    article ul,
    article ol {{ padding-left: 1.45rem; }}
    article li {{ margin: 0.42rem 0; padding-left: 0.15rem; }}
    article li::marker {{ color: var(--accent); font-weight: 700; }}
    article blockquote {{
      padding: 0.2rem 0 0.2rem 1.2rem;
      border-left: 4px solid var(--accent);
      color: var(--muted);
      font-style: italic;
    }}
    article code {{
      padding: 0.12em 0.32em;
      border-radius: 5px;
      background: var(--code);
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 0.84em;
      overflow-wrap: anywhere;
    }}
    article pre {{
      max-width: 100%;
      padding: 1rem;
      border: 1px solid var(--line);
      border-radius: 9px;
      background: var(--code);
      overflow: auto;
      line-height: 1.45;
    }}
    article pre code {{ padding: 0; background: transparent; overflow-wrap: normal; }}
    article hr {{ margin-top: 2.8rem; margin-bottom: 2.8rem; border: 0; border-top: 1px solid var(--line); }}
    article img {{ max-width: 100%; height: auto; }}
    .image-placeholder {{
      display: inline-block;
      padding: 0.3rem 0.5rem;
      border: 1px dashed var(--line);
      border-radius: 6px;
      color: var(--muted);
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-size: 0.86rem;
    }}
    .unsafe-link {{ color: var(--muted); text-decoration: line-through; }}
    article table {{
      display: block;
      max-width: 100%;
      border-collapse: collapse;
      overflow-x: auto;
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-size: 0.88rem;
    }}
    article th,
    article td {{ padding: 0.58rem 0.7rem; border: 1px solid var(--line); text-align: left; }}
    .footer {{
      max-width: var(--measure);
      margin: 3.5rem auto 0;
      padding-top: 1rem;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-size: 0.76rem;
    }}
    @media (max-width: 900px) {{
      body {{ font-size: 17px; }}
      .shell {{ display: block; padding: 0; }}
      .toc {{
        position: static;
        max-height: 20rem;
        overflow: auto;
        padding: 1rem 1.1rem;
        border-bottom: 1px solid var(--line);
        background: var(--paper);
      }}
      .toc-list {{ columns: 2; column-gap: 1.4rem; }}
      .paper {{ border: 0; border-radius: 0; box-shadow: none; }}
    }}
    @media (max-width: 560px) {{
      .topbar-inner {{ align-items: flex-start; flex-direction: column; }}
      .toc-list {{ columns: 1; }}
      .paper {{ padding: 1.2rem 1rem 2.5rem; }}
      article h1 {{ font-size: 2rem; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      html {{ scroll-behavior: auto; }}
    }}
    @media print {{
      :root {{ --paper: #fff; --text: #111; --muted: #444; --line: #ccc; }}
      @page {{ size: auto; margin: 0.7in; }}
      body {{ background: #fff; color: #111; font-size: 11pt; }}
      .topbar,
      .toc,
      .notice,
      .skip-link,
      .reader-actions {{ display: none !important; }}
      .shell {{ display: block; max-width: none; padding: 0; }}
      .paper {{ border: 0; border-radius: 0; box-shadow: none; padding: 0; }}
      article > * {{ max-width: none; }}
      article h1 {{ font-size: 24pt; }}
      article h2 {{ break-after: avoid; font-size: 16pt; }}
      article h3,
      article h4 {{ break-after: avoid; }}
      article pre,
      article blockquote {{ break-inside: avoid; }}
      a {{ color: inherit; text-decoration: none; }}
      a[href^="http"]::after {{ content: " (" attr(href) ")"; font-size: 0.75em; overflow-wrap: anywhere; }}
    }}
  </style>
</head>
<body>
  <a class="skip-link" href="#document">Skip to document</a>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="classification">{html.escape(class_label)}</div>
      <div class="reader-actions" aria-label="Reader actions">
        <a href="{source_href}">Open source</a>
        <button type="button" onclick="window.print()">Print / Save PDF</button>
      </div>
    </div>
  </header>
  <main class="shell" id="document">
    <nav class="toc" aria-label="Table of contents">
      <p class="toc-title">Contents</p>
      {toc}
    </nav>
    <div class="paper">
      <div class="document-meta">
        <strong>{safe_source_name}</strong><br>
        {word_count:,} words · about {reading_minutes} minute{'s' if reading_minutes != 1 else ''} · source updated {html.escape(modified)}<br>
        Source SHA-256: <code>{source_hash}</code> · renderer v{RENDERER_VERSION}
      </div>
      <aside class="notice"><strong>{html.escape(class_label)}.</strong> {html.escape(class_note)}</aside>
      <article>
        {body}
      </article>
      <footer class="footer">
        Generated locally from {safe_source_name}. The Markdown source remains the durable record.
      </footer>
    </div>
  </main>
</body>
</html>
"""


def render_document(
    source_path: Path,
    *,
    classification: str = "private",
    title_override: str | None = None,
) -> str:
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"unsupported classification: {classification}")
    source_path = source_path.resolve()
    source = source_path.read_text(encoding="utf-8")
    linked_source = autolink_bare_urls(source)

    markdown = MarkdownIt("commonmark", {"html": False})
    _install_safe_image_renderer(markdown)
    tokens = markdown.parse(linked_source)
    headings, first_h1 = _decorate_headings(tokens)
    _harden_links(tokens)
    body = markdown.renderer.render(tokens, markdown.options, {})

    title = title_override or first_h1 or source_path.stem.replace("_", " ").strip()
    words = len(_WORD_RE.findall(source))
    reading_minutes = max(1, math.ceil(words / 220))
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    modified = _human_timestamp(source_path.stat().st_mtime)

    return _page_template(
        body=body,
        title=title,
        toc=_toc_markup(headings),
        classification=classification,
        source_name=source_path.name,
        source_hash=source_hash,
        modified=modified,
        word_count=words,
        reading_minutes=reading_minutes,
    )


def default_output_path(source_path: Path) -> Path:
    return source_path.with_name(f"{source_path.stem}.readable.html")


def _write_atomically(output: Path, rendered: str, *, classification: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    file_mode = 0o644 if classification == "public" else 0o600
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, file_mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a Markdown file as a self-contained browser reader."
    )
    parser.add_argument("source", type=Path, help="Markdown source file")
    parser.add_argument("--output", type=Path, help="Output HTML path")
    parser.add_argument("--title", help="Override the document title")
    parser.add_argument(
        "--classification",
        choices=CLASSIFICATIONS,
        default="private",
        help="Reader classification (default: private)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit nonzero if the output is missing or stale; do not write it",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress success output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source.resolve()
    if not source.is_file():
        print(f"error: source file not found: {source}", file=sys.stderr)
        return 2
    if source.suffix.lower() not in {".md", ".markdown"}:
        print(f"error: source must be Markdown: {source}", file=sys.stderr)
        return 2

    output = (args.output or default_output_path(source)).resolve()
    rendered = render_document(
        source,
        classification=args.classification,
        title_override=args.title,
    )

    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            print(f"stale or missing readable document: {output}", file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"readable document is current: {output}")
        return 0

    _write_atomically(output, rendered, classification=args.classification)
    if not args.quiet:
        print(f"wrote readable document: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
