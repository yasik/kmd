# Page transport: Obsidian CLI first, filesystem fallback

kmd reads and writes pages through one of two transports. Prefer the
**Obsidian CLI** (ships with Obsidian 1.12+) when available: writes go
through Obsidian itself, so link resolution, file watchers, and sync see
them immediately. Fall back to **direct filesystem** tools otherwise —
everything in the protocol works either way.

(Adapted from the transport approach in
[claude-obsidian's wiki-cli skill](https://github.com/AgriciDaniel/claude-obsidian);
command grammar verified against the real CLI. For the canonical, complete
CLI reference, install
[kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) — its
`obsidian-cli` skill is authoritative and this file defers to it.)

## The decision tree

```
need to read/write a page
  → read .kmd.json
      transport key present?
        preferred = obsidian-cli → use the CLI recipes below
        preferred = filesystem   → use Read/Write/Edit tools
      transport key missing?
        → python3 scripts/detect_transport.py --kb <kb-root>
          (detects, records into .kmd.json, then follow it)
```

If a CLI call fails mid-session (Obsidian quit, vault closed), fall back to
filesystem for that operation and continue — transport is a preference, not
a dependency.

## Two hazards the detection guards against

1. **Silent wrong-vault fallback.** `vault=<name>` with an unknown or
   deleted vault name silently targets the *active* vault instead of
   erroring. `detect_transport.py` therefore verifies that Obsidian
   resolves the vault name to exactly the KB's workspace path before ever
   preferring the CLI. Never pass `vault=` names it didn't verify.
2. **The CLI needs the app.** The binary talks to the running Obsidian
   process; app closed means CLI dead. Detection runs a real command, not a
   binary-existence check — and runtime failures fall back per above.

## Command grammar

`obsidian-cli <command> key=value ...` — `path=` is exact and
vault-relative (`kb/concepts/Foo.md`), `file=` resolves by name like a
wikilink. Quote values with spaces. Always pass the verified
`vault=<name>` from `.kmd.json`'s transport record.

## Recipes (CLI form; filesystem fallback in parentheses)

```bash
# read a page                          (fallback: Read tool)
obsidian-cli read vault=$V path="kb/concepts/Foo.md"

# create a page                        (fallback: Write tool)
obsidian-cli create vault=$V path="kb/concepts/Foo.md" content="..."

# append / prepend                     (fallback: Read + Write)
obsidian-cli append vault=$V path="kb/log-notes.md" content="..."

# set a frontmatter property           (fallback: Edit tool)
obsidian-cli property:set vault=$V path="kb/concepts/Foo.md" updated "2026-07-16"

# search (Obsidian's own ranking)      (fallback: qmd / grep)
obsidian-cli search vault=$V "loop engineering"
obsidian-cli search:context vault=$V "loop engineering"

# graph questions — useful in lint     (fallback: lint_mechanical.py)
obsidian-cli backlinks vault=$V path="kb/concepts/Foo.md"
obsidian-cli links vault=$V path="kb/concepts/Foo.md"
obsidian-cli orphans vault=$V
obsidian-cli unresolved vault=$V
```

Multi-line `content=` uses `\n` escapes; for whole-page writes of any real
length, the filesystem Write tool is often the more reliable choice even in
CLI mode — the transport preference matters most for reads, appends,
property edits, and search, where Obsidian's own view of the vault adds
value.

## What never changes with transport

The guard hook, validation, logging, and index regeneration are
transport-independent — `index.md`, `log.md`, and `sources/` rules hold no
matter how bytes reach disk.
