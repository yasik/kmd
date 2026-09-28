#!/usr/bin/env python3
r"""Append a canonical entry to the KB's log.md.

The log format is parsed by lint and skimmed by humans, so entries are
always written through this script — never by hand. One entry per
operation:

    ## [2026-07-16] ingest | GPU Memory Math for LLMs
    - Source: `sources/GPU Memory Math for LLMs (2026 Edition).md`
    - Summary: [[GPU memory math for LLMs]]
    - Pages created: [[GPU memory math for LLMs]]
    - Pages updated: [[LLM inference hardware planning]]
    - Key insight: VRAM planning is dominated by KV cache, not weights.
    - By: kmd-intake

Only the header and `By:` are mandatory; other bullets appear when their
flags are given. Page names are written as [[wikilinks]] (pass titles or
paths — `.md` and directories are stripped) and must name existing files,
so prose passed to a page flag fails loudly instead of logging a broken
link. A `skip` entry closes a source that intake reviewed and declined:
it needs `--source` (an existing file under sources/) and a reason in
`--title`; lint stops reporting that source as unreferenced.

Typical usage example:

  python3 kb_log.py --action ingest --title "GPU Memory Math" \\
      --agent kmd-intake --source "sources/GPU Memory Math.md" \\
      --created "GPU memory math for LLMs" \\
      --insight "VRAM planning is dominated by KV cache, not weights."

  python3 kb_log.py --action skip --agent kmd-intake \\
      --title "LLM summary with unverifiable quotes" \\
      --source "sources/Talk summary.md"
"""

import argparse
import sys
from enum import StrEnum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# isort: off
from kb_common import (  # noqa: E402
    KB,
    KBError,
    build_link_index,
    find_kb,
    find_system_file,
    link_resolves,
    today_iso,
)

# isort: on

LOG_HEADER = """# KB log

Append-only journal of every KB operation. Entries are written by
`kb_log.py` (kmd-ingest / kmd-lint skills) — never by hand.
"""


class LogAction(StrEnum):
    """Operation kinds a log entry can record."""

    INGEST = "ingest"
    EDIT = "edit"
    LINT = "lint"
    QUERY = "query"
    SKIP = "skip"


class LogArgumentError(Exception):
    """A flag names something that does not exist in the KB."""


def _wikilink(name: str) -> str:
    """Render a page reference as [[Title]] (strip dirs and .md)."""
    cleaned = name.strip()
    stem = Path(cleaned).stem if cleaned.endswith(".md") else cleaned
    return f"[[{Path(stem).name}]]"


def format_entry(args: argparse.Namespace) -> str:
    """Render one canonical log entry (the exact shape lint parses)."""
    lines = [f"## [{today_iso()}] {args.action} | {args.title}"]

    if args.source:
        lines.append(f"- Source: `{args.source}`")
    if args.summary:
        lines.append(f"- Summary: {_wikilink(args.summary)}")
    if args.created:
        lines.append(
            "- Pages created: " + ", ".join(_wikilink(p) for p in args.created)
        )
    if args.updated:
        lines.append(
            "- Pages updated: " + ", ".join(_wikilink(p) for p in args.updated)
        )
    if args.insight:
        lines.append(f"- Key insight: {args.insight}")
    lines.append(f"- By: {args.agent}")

    return "\n".join(lines)


def check_page_refs(kb: KB, args: argparse.Namespace) -> None:
    """Raise LogArgumentError unless every page flag names an existing file."""
    link_index = build_link_index(kb)
    refs = [("summary", args.summary)] if args.summary else []
    refs += [("created", p) for p in args.created]
    refs += [("updated", p) for p in args.updated]
    for flag, ref in refs:
        if not link_resolves(ref, link_index):
            raise LogArgumentError(
                f"--{flag} '{ref}' is not an existing page — page flags take "
                "titles or paths; put prose in --insight"
            )


def normalize_skip_source(kb: KB, source: str | None) -> str:
    """The KB-relative path of the source a skip entry closes."""
    if not source:
        raise LogArgumentError("--action skip requires --source")
    path = Path(source)
    candidates = [path] if path.is_absolute() else [kb.root / path, Path.cwd() / path]
    sources_dir = (kb.root / "sources").resolve()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file() and resolved.is_relative_to(sources_dir):
            return resolved.relative_to(kb.root.resolve()).as_posix()
    raise LogArgumentError(f"--source '{source}' is not a file under sources/")


def resolve_log_path(kb: KB) -> Path:
    """The KB's log file, migrating an uppercase LOG.md to log.md on touch."""
    existing = find_system_file(kb.root, "log.md")
    canonical = kb.root / "log.md"

    if existing is not None and existing.name != "log.md":
        existing.rename(canonical)
        return canonical
    return existing or canonical


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", required=True, choices=[a.value for a in LogAction])
    parser.add_argument(
        "--title",
        required=True,
        help="what happened — for ingests, usually the source title",
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="author identity (your name, or the agent id in org installations)",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="KB-relative source path (e.g. sources/foo.md); required for skip",
    )
    parser.add_argument(
        "--summary",
        default=None,
        help="the primary page for this operation (wikilinked)",
    )
    parser.add_argument(
        "--created",
        nargs="*",
        default=[],
        help="pages created (titles or paths; wikilinked)",
    )
    parser.add_argument(
        "--updated",
        nargs="*",
        default=[],
        help="pages updated (titles or paths; wikilinked)",
    )
    parser.add_argument("--insight", default=None, help="one sentence on what is new")
    parser.add_argument("--kb", default=None, help="KB root or workspace path")
    args = parser.parse_args()

    # CLI boundary: discovery/config failures become exit messages here.
    try:
        kb = find_kb(args.kb)
    except KBError as exc:
        sys.exit(f"error: {exc}")

    try:
        check_page_refs(kb, args)
        if args.action == LogAction.SKIP:
            args.source = normalize_skip_source(kb, args.source)
    except LogArgumentError as exc:
        sys.exit(f"error: {exc}")

    log_path = resolve_log_path(kb)
    entry = format_entry(args)

    if not log_path.exists():
        log_path.write_text(LOG_HEADER + "\n" + entry + "\n", encoding="utf-8")
    else:
        existing = log_path.read_text(encoding="utf-8")
        separator = "" if existing.endswith("\n") else "\n"
        log_path.write_text(existing + separator + entry + "\n", encoding="utf-8")

    print(f"appended to {kb.rel(log_path)}:")
    print(entry)


if __name__ == "__main__":
    main()
