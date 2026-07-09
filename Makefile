.PHONY: init sync sync-upgrade
.PHONY: format format-python format-ts
.PHONY: lint lint-python lint-static lint-ts
.PHONY: mypy pyright typecheck tests tree bump-version check-version

# The installer is the only JS package; skill/hook scripts are loose Python
# files, dependency-free by design (tooling lives in the uv dev group only).
INSTALLER_DIR := installer
PY_DIRS := skills/kmd-ingest/scripts skills/kmd-lint/scripts hooks/scripts scripts

init:
	$(MAKE) sync

sync:
	uv sync --all-extras
	cd $(INSTALLER_DIR) && bun install

sync-upgrade:
	uv lock --upgrade
	uv sync --all-extras
	cd $(INSTALLER_DIR) && bun update

format: format-python format-ts

format-python:
	uv run isort $(PY_DIRS)
	uv run black $(PY_DIRS)

format-ts:
	cd $(INSTALLER_DIR) && bun run format

lint: lint-python lint-ts lint-static

lint-python:
	uv run isort --check-only $(PY_DIRS)
	uv run black --check $(PY_DIRS)
	uv run ruff check $(PY_DIRS)
	uv run pyright

lint-static:
	uv run yamllint -c .yamllint.yaml .
	uv run python scripts/bump_version.py --check
	@if command -v markdownlint >/dev/null 2>&1; then \
		markdownlint "**/*.md" --config .markdownlint.yaml \
			--ignore fixtures --ignore "**/node_modules/**" --ignore .venv; \
	else \
		echo "markdownlint not installed; skipping markdown lint (npm i -g markdownlint-cli)"; \
	fi

lint-ts:
	cd $(INSTALLER_DIR) && bun run lint

# kb_common.py / kb_log.py exist as identical copies in both skills (skills
# must stay standalone), so mypy runs per directory to avoid duplicate-module
# errors. The hook scripts resolve kb_common through the plugin's skills
# symlink at runtime; MYPYPATH mirrors that for type checking.
mypy:
	uv run mypy skills/kmd-ingest/scripts
	uv run mypy skills/kmd-lint/scripts
	uv run mypy scripts
	MYPYPATH=skills/kmd-ingest/scripts uv run mypy hooks/scripts

pyright:
	uv run pyright --project pyrightconfig.json

# The version is duplicated across plugin manifests, SKILL frontmatters, and
# the README badge by necessity; this keeps them in lockstep (and `make lint`
# fails on drift via check-version).
bump-version:
	@test -n "$(VERSION)" || { echo "usage: make bump-version VERSION=x.y.z"; exit 1; }
	uv run python scripts/bump_version.py $(VERSION)

check-version:
	uv run python scripts/bump_version.py --check

typecheck:
	@set -eu; \
	mypy_pid=''; \
	pyright_pid=''; \
	trap 'test -n "$$mypy_pid" && kill $$mypy_pid 2>/dev/null || true; test -n "$$pyright_pid" && kill $$pyright_pid 2>/dev/null || true' EXIT INT TERM; \
	echo "Running make mypy and make pyright in parallel..."; \
	$(MAKE) mypy & mypy_pid=$$!; \
	$(MAKE) pyright & pyright_pid=$$!; \
	wait $$mypy_pid; \
	wait $$pyright_pid; \
	trap - EXIT

tests:
	@if [ -d tests ]; then uv run pytest; else echo "no python tests yet"; fi

tree:
	find . -maxdepth 4 -type d -not -path "*/node_modules*" -not -path "*/.venv*" -not -path "*/.git*" | sort
