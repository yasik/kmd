"""Regression tests for the kmd-ingest / kmd-lint scripts."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INGEST_SCRIPTS = REPO / "skills" / "kmd-ingest" / "scripts"
LINT_SCRIPTS = REPO / "skills" / "kmd-lint" / "scripts"
sys.path.insert(0, str(INGEST_SCRIPTS))

# isort: off
from kb_common import (  # noqa: E402
    KB,
    _page_snippet,
    build_link_index,
    link_resolves,
    resolve_kb,
)

# isort: on

PAGE = """---
type: concept
created: 2026-09-28
updated: 2026-09-28
author: test
confidence: medium
sources: ["[[sources/Paper]]"]
tags: []
---
# {title}
{body}
"""


@pytest.fixture
def kb(tmp_path: Path) -> KB:
    root = tmp_path / "kb"
    (root / "sources").mkdir(parents=True)
    (root / "concepts").mkdir()
    (root / "assets").mkdir()
    (root / "schema.md").write_text("# KB Schema\n", encoding="utf-8")
    (root / "log.md").write_text("# KB log\n", encoding="utf-8")
    (root / "sources" / "Paper.md").write_text("raw\n", encoding="utf-8")
    (root / "sources" / "Paper.pdf").write_bytes(b"%PDF")
    (root / "assets" / "chart.png").write_bytes(b"png")
    (root / "concepts" / "Topic.md").write_text(
        PAGE.format(title="Topic", body="![[assets/chart.png]] see [[Topic]]"),
        encoding="utf-8",
    )
    resolved = resolve_kb(root)
    assert resolved is not None
    return resolved


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_attachments_resolve_with_their_extension(kb: KB) -> None:
    index = build_link_index(kb)

    assert link_resolves("assets/chart.png", index)
    assert link_resolves("chart.png", index)
    assert link_resolves("sources/Paper.pdf", index)
    assert link_resolves("Topic", index)
    assert not link_resolves("chart", index)


def test_lint_accepts_attachment_embeds(kb: KB) -> None:
    result = run(LINT_SCRIPTS / "lint_mechanical.py", "--kb", str(kb.root))

    assert "broken-link" not in result.stdout


def test_snippet_never_cuts_inside_a_wikilink() -> None:
    body = "Intro text " + "x" * 60 + " [[sources/Some very long source title]] tail"

    snippet = _page_snippet(body)

    assert snippet.endswith("…")
    assert snippet.count("[[") == snippet.count("]]")


def test_log_rejects_prose_in_page_flags(kb: KB) -> None:
    result = run(
        INGEST_SCRIPTS / "kb_log.py",
        *("--kb", str(kb.root), "--action", "ingest", "--title", "t"),
        *("--agent", "test", "--summary", "needs re-sourcing / fabricated quotes"),
    )

    assert result.returncode != 0
    assert "--insight" in result.stderr
    assert "needs re-sourcing" not in (kb.root / "log.md").read_text(encoding="utf-8")


def test_log_accepts_existing_pages(kb: KB) -> None:
    result = run(
        INGEST_SCRIPTS / "kb_log.py",
        *("--kb", str(kb.root), "--action", "ingest", "--title", "t"),
        *("--agent", "test", "--summary", "concepts/Topic.md", "--created", "Topic"),
    )

    assert result.returncode == 0, result.stderr
    assert "- Summary: [[Topic]]" in (kb.root / "log.md").read_text(encoding="utf-8")


def test_skip_entry_closes_an_unreferenced_source(kb: KB) -> None:
    (kb.root / "sources" / "Declined.md").write_text("raw\n", encoding="utf-8")
    lint = LINT_SCRIPTS / "lint_mechanical.py"
    assert "Declined.md" in run(lint, "--kb", str(kb.root)).stdout

    logged = run(
        INGEST_SCRIPTS / "kb_log.py",
        *("--kb", str(kb.root), "--action", "skip", "--agent", "test"),
        *("--title", "low-value promo", "--source", "sources/Declined.md"),
    )

    assert logged.returncode == 0, logged.stderr
    assert "- Source: `sources/Declined.md`" in logged.stdout
    assert "Declined.md" not in run(lint, "--kb", str(kb.root)).stdout


def test_skip_requires_an_existing_source(kb: KB) -> None:
    missing = run(
        INGEST_SCRIPTS / "kb_log.py",
        *("--kb", str(kb.root), "--action", "skip", "--agent", "test"),
        *("--title", "nope", "--source", "sources/Nope.md"),
    )
    outside = run(
        INGEST_SCRIPTS / "kb_log.py",
        *("--kb", str(kb.root), "--action", "skip", "--agent", "test"),
        *("--title", "nope", "--source", "concepts/Topic.md"),
    )

    assert missing.returncode != 0
    assert outside.returncode != 0
