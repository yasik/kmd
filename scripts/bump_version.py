#!/usr/bin/env python3
"""Bump (or verify) the kmd version across every manifest that carries it.

The version is duplicated by necessity — each plugin ecosystem reads its own
manifest — so this script is the single place that knows every location.
When a new manifest gains a version field, add it to `TARGETS` below; the
`--check` mode (wired into `make lint`) then guards it against drift.

Locations: the four plugin manifests (Claude, Codex, Cursor, Grok), the Grok
marketplace entry, the installer's package.json, both SKILL.md frontmatters,
and the README version badge.

Typical usage example:

  python3 scripts/bump_version.py 0.2.0   # set everywhere
  python3 scripts/bump_version.py --check # verify all locations agree
"""

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parent.parent

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

type Reader = Callable[[Path], str]
type Writer = Callable[[Path, str], None]


def _json_version_path(*keys: str | int) -> tuple[Reader, Writer]:
    """Build reader/writer for a version stored at a key path in a JSON file."""

    def read(path: Path) -> str:
        node: object = json.loads(path.read_text(encoding="utf-8"))
        for key in keys:
            if isinstance(key, int):
                if not isinstance(node, list):
                    raise KeyError(f"{path}: cannot index {key!r} into a non-list")
                node = cast(list[object], node)[key]
                continue

            if not isinstance(node, dict):
                raise KeyError(f"{path}: cannot descend into {key!r}")
            node = cast(dict[str, object], node)[key]

        if not isinstance(node, str):
            raise ValueError(f"{path}: version at {keys!r} is not a string")
        return node

    def write(path: Path, version: str) -> None:
        # Surgical line replacement instead of re-serializing: a version
        # bumper must not reformat manifests (array wrapping, escapes, key
        # order). The reader re-parse below verifies the regex hit the key
        # this target actually owns.
        text = path.read_text(encoding="utf-8")
        updated, count = re.subn(
            r'("version":\s*)"[^"]*"', rf'\g<1>"{version}"', text, count=1
        )
        if count != 1:
            raise ValueError(f'{path}: no "version" field found')
        path.write_text(updated, encoding="utf-8")

        if read(path) != version:
            raise ValueError(
                f'{path}: replaced a "version" field, but not the one at '
                f"{keys!r} — fix TARGETS or the file"
            )

    return read, write


def _regex_version(pattern: str, template: str) -> tuple[Reader, Writer]:
    """Build reader/writer for a version embedded in text via one regex group."""
    compiled = re.compile(pattern, re.M)

    def read(path: Path) -> str:
        match = compiled.search(path.read_text(encoding="utf-8"))
        if match is None:
            raise ValueError(f"{path}: version pattern not found ({pattern})")
        return match.group(1)

    def write(path: Path, version: str) -> None:
        text = path.read_text(encoding="utf-8")
        updated, count = compiled.subn(template.format(version=version), text, count=1)
        if count != 1:
            raise ValueError(f"{path}: version pattern not found ({pattern})")
        path.write_text(updated, encoding="utf-8")

    return read, write


@dataclass(frozen=True)
class Target:
    """One file location that carries the kmd version."""

    path: str
    """Repo-relative path."""

    reader: Reader
    writer: Writer


_JSON_VERSION = _json_version_path("version")
_GROK_MARKETPLACE = _json_version_path("plugins", 0, "version")
_SKILL_FRONTMATTER = _regex_version(r"^version: (\S+)$", "version: {version}")
_README_BADGE = _regex_version(
    r"badge/version-(.+?)-blue", "badge/version-{version}-blue"
)

TARGETS: tuple[Target, ...] = (
    Target(".claude-plugin/plugin.json", *_JSON_VERSION),
    Target(".codex-plugin/plugin.json", *_JSON_VERSION),
    Target(".cursor-plugin/plugin.json", *_JSON_VERSION),
    Target(".grok-plugin/plugin.json", *_JSON_VERSION),
    Target(".grok-plugin/marketplace.json", *_GROK_MARKETPLACE),
    Target("installer/package.json", *_JSON_VERSION),
    Target("skills/kmd-ingest/SKILL.md", *_SKILL_FRONTMATTER),
    Target("skills/kmd-lint/SKILL.md", *_SKILL_FRONTMATTER),
    Target("README.md", *_README_BADGE),
)


def read_versions() -> dict[str, str]:
    """Current version per target path (raises if any location is unreadable)."""
    return {t.path: t.reader(REPO_ROOT / t.path) for t in TARGETS}


def check() -> int:
    """Verify all locations agree; report drift. Returns a process exit code."""
    versions = read_versions()
    distinct = sorted(set(versions.values()))

    if len(distinct) == 1:
        print(f"version {distinct[0]} — consistent across {len(versions)} locations")
        return 0

    print(f"VERSION DRIFT — {len(distinct)} distinct versions found:")
    for path, version in versions.items():
        print(f"  {version:12} {path}")
    print("fix with: make bump-version VERSION=<x.y.z>")
    return 1


def bump(version: str) -> int:
    """Set `version` in every location. Returns a process exit code."""
    if not SEMVER_RE.match(version):
        print(f"error: '{version}' is not a semver version (x.y.z)")
        return 1

    before = read_versions()
    for target in TARGETS:
        target.writer(REPO_ROOT / target.path, version)
        marker = "·" if before[target.path] == version else "✔"
        print(f"  {marker} {target.path}  {before[target.path]} → {version}")

    print(f"version set to {version} in {len(TARGETS)} locations")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "version",
        nargs="?",
        default=None,
        help="new semver version (omit with --check)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify all locations agree; exit 1 on drift",
    )
    args = parser.parse_args()

    if args.check == (args.version is not None):
        parser.error("pass exactly one of: a version, or --check")

    # CLI boundary: unreadable/missing manifests surface as exit messages here.
    try:
        sys.exit(check() if args.check else bump(args.version))
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()
