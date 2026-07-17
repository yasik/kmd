---
name: kmd-ingest
version: 0.2.0
description: The write protocol for a markdown knowledge base (Obsidian-compatible, the LLM-wiki pattern) — personal or shared. Use for EVERY write into the KB — distilling a new or scraped source, promoting a finished artifact/report/lesson into the KB, filing a durable learning, insight, or query answer, or correcting/updating an existing page, even a one-line fix. If you are about to create or edit any file inside a knowledge base (a directory with schema.md/log.md, a .kmd.json config, or a kb/ folder), use this skill first; there is no free-form edit path to the KB.
---

# kmd-ingest — the KB write protocol

The knowledge base compounds in value only if every write follows the same
discipline: condensed pages, declared provenance, cross-references swept, one
log entry per operation. A single undisciplined write is cheap; a thousand of
them make the KB untrustworthy at query time. This skill is that discipline —
the same whether the KB belongs to one person or an organization of agents.
Permissions are open — any author may create or edit any page. The *manner*
is not: every write, down to a one-line correction, is an ingest.

## The two layers (get this right and the rest follows)

- **`sources/` — append-only evidence.** Raw external material: scraped
  pages, whitepapers, transcripts. You may *add* files here (when new raw
  material is involved in your work); you never edit or delete existing ones.
- **Everything else in the KB — living synthesis.** Pages you write and
  maintain (`entities/`, `concepts/`, `projects/`, …) plus derived artifacts
  in `assets/` (charts, decks — embedded from pages, never pages themselves).

Your own outputs — reports, analyses, lessons — are **never** filed into
`sources/`, no matter how polished or reference-like they feel. Synthesis
recycled as evidence is how hallucinations launder themselves into ground
truth. A finished report becomes a *page* citing the raw material it was
built from.

## Before you write

1. **Locate the KB root** — in order: a path you were given; `$KMD_ROOT`; a
   `.kmd.json` at the workspace root (`{"root": "<dir>"}`); a directory
   containing `schema.md`/`log.md`; the default `kb/` under the workspace.
   The bundled scripts implement exactly this resolution (`--kb` flag).
2. **Pick the transport** — read `.kmd.json`'s `transport` key; if missing,
   run `python3 scripts/detect_transport.py --kb <kb-root>` once. When it
   says `obsidian-cli`, read and write pages through the Obsidian CLI per
   [references/obsidian-cli-transport.md](references/obsidian-cli-transport.md);
   otherwise (or whenever a CLI call fails) use plain filesystem tools.
3. **Read `schema.md`** at the KB root — the single source of truth for
   taxonomy, writing style, and conventions; its Extensions section may add
   page types and hierarchies beyond the defaults, and it overrides anything
   here that conflicts. If the KB has no schema.md yet, bootstrap it from
   [references/schema-template.md](references/schema-template.md) —
   stripping the `<!-- kmd:template-note -->` block, and the org-extension
   block unless this is an org installation.
4. **Check for the org extension** — if `.kmd.json` declares an `"org"` key
   or the workspace has a charter with an `ORG.md`, read
   [references/org-extension.md](references/org-extension.md) first (it adds
   ownership routing and org-specific provenance origins). Otherwise ignore.

For Obsidian formatting specifics (callouts, embeds, properties), the
`obsidian-markdown` skill from
[kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) is the
authoritative reference when installed.

## The ingest checklist

Steps 2–6 are judgment — yours. Steps 7–9 are mechanics — the scripts'.

### 1. Classify — and decide save vs. skip

Triggers: new raw source to distill · finished artifact to promote · durable
learning or query answer to file · correction to an existing page.

Worth saving: non-obvious insights or synthesis, decisions with rationale,
analyses that took real effort, comparisons likely to be referenced again,
research findings. **Skip**: mechanical Q&A, setup steps documented
elsewhere, debugging sessions with no lasting insight, anything already in
the KB (update the existing page instead). Filed-back query answers are the
compounding loop — when an answer is durable and reusable, it becomes a
page, and the next question gets cheaper.

### 2. File raw material (if any)

If new external material is involved — a page you fetched, a document you
were given — save it under `sources/` first (a short natural-language
filename; material dropped by others keeps the name it arrived with),
verbatim or minimally cleaned. This is what your page will cite; a citation
into your context window is unverifiable the moment the session ends. For
web research: anything your page *substantively relies on* gets fetched and
filed; incidental facts may carry bare URL citations at lower `confidence`.

### 3. Dedup gate — search before writing

Search the KB for existing pages on the topic. Use qmd if available, but
**always check `index.md` too**: the index is regenerated on every ingest,
while qmd's search index only moves when `qmd update` runs. Never conclude
a page doesn't exist from qmd results alone. This decides **new page vs.
edit**: a new page only for a distinct, linkable concept other pages will
reference; otherwise improve the existing page. Point-in-time outputs go to
`reports/`; living knowledge belongs in `concepts/`.

### 4. Write the page — condense, don't mirror

A page condenses facts scattered across sources into the shortest faithful
synthesis. Style (schema.md's rules, in brief): **declarative, present
tense — write the knowledge, not the conversation** ("X works by doing Y",
never "the user asked about X and…"); context-complete, readable cold by a
future session; **every mentioned concept, entity, or page gets a
[[wikilink]]** — dense links are how topics self-organize into a graph.

**The filename is the title** (natural language, `GPU memory math for
LLMs.md`). Frontmatter as below; the body starts on the very next line
after the closing `---` (no blank line), beginning with the H1:

```yaml
---
type: entity | concept | project | decision | report   # + schema extensions
created: <today, YYYY-MM-DD>
updated: <today, YYYY-MM-DD>   # bump on every edit
author: <your-name-or-agent-id>
confidence: high | medium | low  # epistemic marker — see schema.md
sources: ["[[sources/raft-paper]]"]   # provenance — see rule below
tags: []
---
```

**Provenance rule** (the `sources:` field): every page declares where its
content came from — external claims point into `sources/`, internal
artifacts at their origin (another page, a dated note, the work that
produced them). When promoting an artifact, cite what it was *built from*,
never the draft itself.

### 5. Enrich — derived outputs when they earn their place

- A structure or flow that a diagram explains better than prose → embed a
  ` ```mermaid ` block right in the page (Obsidian renders it).
- Data that wants plotting → generate the chart (matplotlib or similar)
  into `assets/`, embed with `![[assets/<name>.png]]`.
- A topic that warrants presenting → a Marp deck in `assets/decks/`,
  linked from its page.

These are *exports from* pages — prefer inline (mermaid) over separate
files, and never let an artifact substitute for the page itself.

### 6. Sweep related pages — and mark contradictions

Add cross-references from related pages, bump project status, link the new
page where future readers will come from — every touched page is part of
this ingest (bump its `updated`/`author`). If the new information
**contradicts** an existing page, do not pick a side silently: add the
`> [!contradiction]` callout on *both* pages per schema.md's framework
(what each side claims, what would resolve it). Lint tracks open
contradiction callouts until someone resolves them.

### 7. Validate

```bash
python3 scripts/validate_page.py --kb <kb-root> <every page you wrote or edited>
```

Fix anything it reports and re-run until clean.

### 8. Log — one entry per operation

```bash
python3 scripts/kb_log.py --kb <kb-root> --action ingest \
    --title "<source or operation title>" --agent <your-name-or-agent-id> \
    --source "sources/<file>.md" --summary "<primary page>" \
    --created "<Page 1>" "<Page 2>" --updated "<Page 3>" \
    --insight "<one sentence on what is new>"
```

Emits the canonical entry (header + Source/Summary/Pages/Key insight/By
bullets — omit flags that don't apply). `--action edit` for small
corrections; a batch drained in one sitting is one operation and one entry.
Never write log.md by hand — lint checks the canonical format.

### 9. Regenerate the index

```bash
python3 scripts/recompile_index.py --kb <kb-root>
```

`index.md` is the routing layer other agents search before reading pages —
script-owned (the guard hook enforces it), and lint flags it when missing
or stale. If qmd is installed the script also handles search freshness per
`.kmd.json` (see its output).

## What you never do

- Edit or delete anything under `sources/` (append-only; git catches this)
- Hand-write `index.md` — regenerate it with `recompile_index.py`
- Edit `schema.md` (owner-controlled; propose changes instead)
- File your own synthesis into `sources/`
- Skip the log entry or the validation, however small the edit

## Done looks like

Sources filed (if any) → no duplicate created → page(s) condensed in
declarative style with valid frontmatter → enriched where it earns it →
related pages swept, contradictions marked → `validate_page.py` clean → one
log entry → `index.md` regenerated. If you were interrupted mid-ingest, the
log entry comes before the index step precisely so an unlogged half-ingest
is detectable by lint.
