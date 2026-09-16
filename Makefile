.PHONY: install lint test ingest all

install:
	uv sync

lint:
	uv run ruff format --check .
	uv run ruff check .

test:
	uv run pytest

ingest:
	uv run caq ingest

all: install lint test ingest
