.PHONY: install lint test ingest eda all

install:
	uv sync
	# En macOS, `uv sync` puede dejar los .pth de site-packages con el flag
	# BSD "hidden" puesto; Python 3.11.16 salta los .pth ocultos al arrancar,
	# lo que rompe el install editable (`import calidad_aire` falla incluso
	# con `uv run`). Ver CLAUDE.md §14 -- es un problema de esta plataforma,
	# no del código.
	chflags -R nohidden .venv/lib/*/site-packages/*.pth 2>/dev/null || true

lint:
	uv run ruff format --check .
	uv run ruff check .

test:
	uv run pytest

ingest:
	uv run caq ingest

eda:
	uv run caq eda

all: install lint test ingest eda
