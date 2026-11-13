.PHONY: help sync test demo download secrets verify-raw

help:
	@echo "Objetivos: sync test demo download secrets verify-raw"

sync:
	uv sync

test:
	uv run pytest -q

demo:
	uv run python -m harmonize.pipeline --input data/sample --output data/processed/demo

download:
	uv run python -m ingest.firms_download

secrets:
	uv run python tools/scan_secrets.py

verify-raw:
	uv run python -m ingest.manifest verify data/raw/manifest.jsonl
