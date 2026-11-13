.PHONY: help sync test demo api download secrets verify-raw

help:
	@echo "Objetivos: sync test demo api download secrets verify-raw"

sync:
	uv sync

test:
	uv run pytest -q

demo:
	uv run python -m harmonize.pipeline --input data/sample --output data/processed/demo
	uv run python tools/generar_historico.py data/sample_historica
	uv run python -m harmonize.pipeline --input data/sample_historica --output data/processed/demo_historica

api: demo
	uv run python -m api --datos data/processed/demo_historica

download:
	uv run python -m ingest.firms_download

secrets:
	uv run python tools/scan_secrets.py

verify-raw:
	uv run python -m ingest.manifest verify data/raw/manifest.jsonl
