#!/usr/bin/env python3
"""Regenerate the KB's INDEX.md from page files — the routing layer.

INDEX.md lists every page with its type, updated date, and a one-line
snippet, grouped by directory. It is script-owned: agents and humans never
hand-edit it (the kmd guard hook denies such writes), they run this instead —
typically as the last step of every ingest and alongside scheduled hygiene.

Output is deterministic (sorted, no timestamps), so kmd-lint can detect a
stale index by comparing the file against a fresh render.

When qmd is installed, this script can also refresh qmd's search index so
new pages become searchable immediately. That is opt-in
(`"qmd_update_on_ingest": true` in `.kmd.json`) because `qmd update` has no
per-collection scope: it re-indexes every configured collection and runs
each collection's update command (e.g. `git pull`) — kmd never triggers
that silently. Without the opt-in, a one-line note keeps the freshness
model visible.

Typical usage example:

  python3 recompile_index.py --kb ~/vault/kb

Exit code 0 on success; prints whether the index was created, updated, or
already current.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# isort: off
from kb_common import KB, KBError, find_kb, index_status, render_index  # noqa: E402

# isort: on

QMD_UPDATE_TIMEOUT_SECONDS = 600
"""Generous ceiling: `qmd update` is incremental, but first runs index everything."""


def refresh_qmd(kb: KB) -> None:
    """Best-effort qmd search-index refresh after KB content changed.

    qmd has no file watcher — its index only moves when `qmd update` runs,
    and that command touches every collection plus their update commands,
    so it runs only with the explicit `.kmd.json` opt-in. Failures are
    reported but never fail the ingest: a stale search index is a
    degradation, not an error.
    """
    if shutil.which("qmd") is None:
        return

    if kb.config.get("qmd_update_on_ingest") is not True:
        print(
            "note: qmd is installed but its index refreshes on your schedule "
            "(`qmd update`) — new pages are searchable after the next run. "
            'Set "qmd_update_on_ingest": true in .kmd.json to refresh on '
            "every ingest (it re-indexes ALL your qmd collections)."
        )
        return

    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, trusted constant command
            ["qmd", "update"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=QMD_UPDATE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"qmd update failed ({exc}) — search index may be stale")
        return

    if result.returncode == 0:
        print("qmd index refreshed")
        return
    print(
        f"qmd update exited {result.returncode} — search index may be stale; "
        "run `qmd update` manually to see why"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb", default=None, help="KB root or workspace path")
    parser.add_argument(
        "--check",
        action="store_true",
        help="report status without writing (exit 1 unless current)",
    )
    args = parser.parse_args()

    # CLI boundary: discovery/config failures become exit messages here.
    try:
        kb = find_kb(args.kb)
    except KBError as exc:
        sys.exit(f"error: {exc}")

    status = index_status(kb)
    if args.check:
        print(f"INDEX.md is {status}")
        sys.exit(0 if status == "current" else 1)

    if status == "current":
        print("INDEX.md already current")
    else:
        (kb.root / "INDEX.md").write_text(render_index(kb), encoding="utf-8")
        print(
            f"INDEX.md {'created' if status == 'missing' else 'updated'} "
            f"({kb.rel(kb.root / 'INDEX.md')})"
        )

    # Page bodies can change without the index changing, so the search
    # refresh runs regardless of INDEX.md status.
    refresh_qmd(kb)


if __name__ == "__main__":
    main()
