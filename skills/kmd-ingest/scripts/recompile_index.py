#!/usr/bin/env python3
"""Regenerate the KB's INDEX.md from page files — the routing layer.

INDEX.md lists every page with its type, updated date, and a one-line
snippet, grouped by directory. It is script-owned: agents and humans never
hand-edit it (the kmd guard hook denies such writes), they run this instead —
typically as the last step of every ingest and alongside scheduled hygiene.

Output is deterministic (sorted, no timestamps), so kmd-lint can detect a
stale index by comparing the file against a fresh render.

Typical usage example:

  python3 recompile_index.py --kb ~/vault/kb

Exit code 0 on success; prints whether the index was created, updated, or
already current.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# isort: off
from kb_common import KBError, find_kb, index_status, render_index  # noqa: E402

# isort: on


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
        return

    (kb.root / "INDEX.md").write_text(render_index(kb), encoding="utf-8")
    print(
        f"INDEX.md {'created' if status == 'missing' else 'updated'} "
        f"({kb.rel(kb.root / 'INDEX.md')})"
    )


if __name__ == "__main__":
    main()
