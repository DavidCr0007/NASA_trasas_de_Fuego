.PHONY: help sync test demo api real api-real download secrets verify-raw

help:
	@echo "Objetivos: sync test demo api real api-real download secrets verify-raw"

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

# Ruta pública temporal sin MAP_KEY (ADR 0009): archivo anual por país, calidad estándar.
# Requiere red la primera vez; los crudos se reutilizan si ya están en data/raw.
real:
	uv run python -m ingest.firms_publico --pais Colombia --desde 2016 --hasta 2025 --salida data/processed/recortes_pais/huila
	uv run python -m harmonize.pipeline --input data/processed/recortes_pais/huila --output data/processed/huila_real

api-real:
	uv run python -m api --datos data/processed/huila_real

download:
	uv run python -m ingest.firms_download

secrets:
	uv run python tools/scan_secrets.py

verify-raw:
	uv run python -m ingest.manifest verify data/raw/manifest.jsonl
