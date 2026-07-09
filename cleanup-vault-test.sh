#!/bin/bash
# Cleanup for the 2026-07-09 end-to-end test of kmd on the real Obsidian vault.
#
# Removes EXACTLY ONE directory — the test KB — and nothing else:
#   /Users/yasik/Library/Mobile Documents/iCloud~md~obsidian/Documents/yasik.main/kb_test
#
# The test made no other changes anywhere in the vault:
#   - Raw/ was read-only (verified: 33/33 file checksums identical before/after)
#   - no .kmd.json was created, no git repo initialized, no qmd collection added
#
# Run with:  bash cleanup-vault-test.sh --confirm
set -euo pipefail

KB_TEST="/Users/yasik/Library/Mobile Documents/iCloud~md~obsidian/Documents/yasik.main/kb_test"

if [ "${1:-}" != "--confirm" ]; then
  echo "dry run — would remove: $KB_TEST"
  echo "contents that would be deleted:"
  find "$KB_TEST" -type f 2>/dev/null | sed 's/^/  /' || echo "  (already gone)"
  echo ""
  echo "re-run with --confirm to actually delete"
  exit 0
fi

# Safety: refuse unless the directory looks exactly like the test KB we built
# (schema marker + lint report present), so a typo'd path can never nuke
# anything else.
if [ ! -f "$KB_TEST/SCHEMA.md" ] || [ ! -d "$KB_TEST/.lint" ]; then
  echo "refusing: $KB_TEST does not look like the kmd test KB (SCHEMA.md + .lint/ expected)"
  exit 1
fi

/bin/rm -rf "$KB_TEST"
echo "removed $KB_TEST — vault back to its pre-test state"
