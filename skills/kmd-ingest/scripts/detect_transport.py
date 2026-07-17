#!/usr/bin/env python3
"""Detect and record the KB's page-transport: Obsidian CLI or filesystem.

kmd reads and writes pages through one of two transports:

  obsidian-cli  the CLI shipped with Obsidian 1.12+ — preferred when the
                workspace is a registered vault, because writes go through
                Obsidian itself (link updates, file watchers, sync all see
                them immediately)
  filesystem    plain file reads/writes — always available

Detection is deliberately strict about vault identity: `obsidian-cli`
silently falls back to the ACTIVE vault when the requested vault name is
unknown, so a naive "binary exists" check could route writes into the wrong
vault. A vault only qualifies here when Obsidian resolves it to exactly the
KB's workspace path.

The result is written into `.kmd.json` as:

    "transport": {"preferred": "obsidian-cli", "vault": "my-vault",
                  "detected": "2026-07-16"}

Skills read that key before touching pages; when it is missing they run
this script once. Re-run with no flags after installing/removing Obsidian.

Typical usage example:

  python3 detect_transport.py --kb ~/vault/kb          # detect + record
  python3 detect_transport.py --kb ~/vault/kb --check  # show, don't write
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# isort: off
from kb_common import CONFIG_FILENAME, KB, KBError, find_kb, today_iso  # noqa: E402

# isort: on

CLI_TIMEOUT_SECONDS = 15
"""The CLI answers from the running Obsidian app; slow means broken."""


def _cli_vault_path(vault_name: str) -> Path | None:
    """Ask Obsidian to resolve `vault_name`; return the path it reports.

    Returns None when the CLI is unavailable, errors, or the app is not
    running. The caller compares the returned path against the workspace —
    never trust the name match alone (silent active-vault fallback).
    """
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, trusted constant command
            ["obsidian-cli", "vault", f"vault={vault_name}"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("path\t"):
            return Path(line.split("\t", 1)[1].strip())
    return None


def detect(kb: KB) -> dict[str, str]:
    """Run the detection and return the transport record."""
    fallback = {"preferred": "filesystem", "detected": today_iso()}

    if shutil.which("obsidian-cli") is None:
        return fallback

    vault_name = kb.workspace.name
    resolved = _cli_vault_path(vault_name)
    if resolved is None or resolved.resolve() != kb.workspace:
        # Binary present but this workspace is not the vault Obsidian
        # resolves for that name — the silent-fallback hazard. Filesystem it is.
        return fallback

    return {
        "preferred": "obsidian-cli",
        "vault": vault_name,
        "detected": today_iso(),
    }


def record(kb: KB, transport: dict[str, str]) -> Path:
    """Merge the transport record into `.kmd.json`, preserving other keys."""
    config_path = kb.workspace / CONFIG_FILENAME
    config: dict[str, object] = {}
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))

    config["transport"] = transport
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return config_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb", default=None, help="KB root or workspace path")
    parser.add_argument(
        "--check",
        action="store_true",
        help="print the current/detected transport without writing .kmd.json",
    )
    args = parser.parse_args()

    # CLI boundary: discovery/config failures become exit messages here.
    try:
        kb = find_kb(args.kb)
    except KBError as exc:
        sys.exit(f"error: {exc}")

    recorded = kb.config.get("transport")
    if args.check:
        if isinstance(recorded, dict):
            print(f"recorded: {json.dumps(recorded)}")
        print(f"detected: {json.dumps(detect(kb))}")
        return

    transport = detect(kb)
    config_path = record(kb, transport)
    print(
        f"transport: {transport['preferred']}"
        + (f" (vault: {transport['vault']})" if "vault" in transport else "")
        + f" — recorded in {config_path}"
    )


if __name__ == "__main__":
    main()
