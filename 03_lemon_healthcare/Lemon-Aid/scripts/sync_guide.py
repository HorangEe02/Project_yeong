#!/usr/bin/env python3
"""Sync PROJECT_GUIDE.md into guide.html's embedded markdown source."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "PROJECT_GUIDE.md"
HTML_PATH = ROOT / "guide.html"
EXPECTED_SCRIPT_CLOSE_COUNT = 3

MD_SOURCE_RE = re.compile(
    r'(<script id="md-source" type="text/plain">\r?\n)(.*?)(\r?\n</script>)',
    re.DOTALL,
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def info(message: str) -> None:
    print(f"  {message}")


def ok(message: str) -> None:
    print(f"OK: {message}")


def load_md() -> str:
    if not MD_PATH.exists():
        fail(f"PROJECT_GUIDE.md not found: {MD_PATH}")
    return MD_PATH.read_text(encoding="utf-8")


def load_html() -> str:
    if not HTML_PATH.exists():
        fail(f"guide.html not found: {HTML_PATH}")
    raw = HTML_PATH.read_bytes()
    if b"\x00" in raw:
        info("guide.html contains NULL bytes; removing them")
        raw = raw.replace(b"\x00", b"")
        HTML_PATH.write_bytes(raw)
    return raw.decode("utf-8")


def validate_md(markdown: str) -> None:
    if "</script>" in markdown:
        fail("PROJECT_GUIDE.md contains </script>, which would break guide.html")

    splits = re.findall(r"^---SPLIT---$", markdown, re.MULTILINE)
    info(f"PROJECT_GUIDE.md SPLIT count: {len(splits)} (sections {len(splits) + 1})")

    inline_split = re.findall(r"`---SPLIT---`", markdown)
    if inline_split:
        fail(
            "PROJECT_GUIDE.md contains inline-code ---SPLIT--- markers; "
            "avoid writing the marker literally inside prose or tables"
        )


def sync(markdown: str, html: str) -> tuple[str, bool]:
    match = MD_SOURCE_RE.search(html)
    if not match:
        fail('guide.html is missing the <script id="md-source"> block')

    current_markdown = match.group(2)
    if current_markdown == markdown:
        return html, False

    new_html = (
        html[: match.start()]
        + match.group(1)
        + markdown
        + match.group(3)
        + html[match.end() :]
    )
    return new_html, True


def verify_after(html: str, markdown: str) -> None:
    markdown_splits = len(re.findall(r"^---SPLIT---$", markdown, re.MULTILINE))
    html_splits = len(re.findall(r"^---SPLIT---$", html, re.MULTILINE))
    if markdown_splits != html_splits:
        fail(
            f"SPLIT count mismatch: PROJECT_GUIDE.md {markdown_splits} vs "
            f"guide.html {html_splits}"
        )

    close_count = html.count("</script>")
    if close_count != EXPECTED_SCRIPT_CLOSE_COUNT:
        fail(
            f"guide.html has {close_count} </script> tags; "
            f"expected {EXPECTED_SCRIPT_CLOSE_COUNT}"
        )

    if not html.rstrip().endswith("</html>"):
        fail("guide.html does not end with </html>")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync PROJECT_GUIDE.md to guide.html")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only verify; exit 1 when guide.html needs regeneration",
    )
    args = parser.parse_args()

    markdown = load_md()
    html = load_html()

    validate_md(markdown)

    new_html, changed = sync(markdown, html)
    verify_after(new_html, markdown)

    if not changed:
        ok("guide.html is already synchronized")
        return 0

    if args.check:
        fail("guide.html is not synchronized with PROJECT_GUIDE.md; run scripts/sync_guide.py")

    HTML_PATH.write_bytes(new_html.encode("utf-8"))
    ok(f"guide.html synchronized ({len(new_html):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
