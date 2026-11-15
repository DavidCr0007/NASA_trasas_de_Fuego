# Harmonized Heat Neiva

[Español](README.md) · **English** · [Français](README.fr.md)

A NASA Space Apps 2026 project exploring MODIS and VIIRS thermal detections from NASA FIRMS, with a globe, local boundaries and harmonized activity calendars. A detection is not a confirmed wildfire. **Do not use this tool to protect life or property.**

## Run locally

Use PowerShell from the repository root. Install Python and dependencies with uv:

```powershell
uv python install 3.13
uv sync --locked
```

Create and start a synthetic demonstration:

```powershell
uv run python tools/generar_historico.py data/sample_historica
uv run python -m harmonize.pipeline --input data/sample_historica --output data/processed/demo_historica
uv run python -m api --datos data/processed/demo_historica --puerto 8000
```

Open **http://127.0.0.1:8000/ui/**. Choose **Language → English**. The application also supports Spanish and French, or a direct URL such as `/ui/?lang=en`. It remembers the chosen language without recreating the map or changing scientific data.

## Encrypted FIRMS key and real data on Vercel

The local `.env` file is private and is not uploaded to Vercel. The key is used only by the Python server. To encrypt a plaintext `FIRMS_MAP_KEY` already entered in the local file:

```powershell
uv run python tools/cifrar_clave_firms.py --archivo .env
```

The tool replaces the plaintext value with `FIRMS_MAP_KEY_ENCRYPTED` and `FIRMS_SECRET_KEY`, using authenticated Fernet encryption. It does not print their values. The decryption key must also remain private.

In Vercel **Project → Settings → Environment Variables**, configure the following for **Production**:

| Name | Type | Value |
|---|---|---|
| `FIRMS_MAP_KEY_ENCRYPTED` | Secret | Copy its value from the private local `.env`. |
| `FIRMS_SECRET_KEY` | Secret | Copy its value from `.env`. |
| `HHN_MODO_DATOS` | Config | `firms` |
| `FIRMS_NRT_DIAS` | Config, optional | `1` by default; accepts `1`–`3`. |

Leave `HHN_DATOS` unset to use the real dataset built by this mode. A custom data path takes precedence. Publish the changes and redeploy after setting the variables. The build downloads MODIS NRT, VIIRS NOAA-20 NRT and VIIRS NOAA-21 NRT for the configured number of completed UTC days before the build, then runs the harmonization pipeline.

The real-data mode fails explicitly if configuration or ingestion fails; it does not silently substitute synthetic observations. `HHN_MODO_DATOS=demo` deliberately keeps the synthetic demonstration. Real data are a deployment-time snapshot; rebuilding refreshes the period, and NRT observations remain preliminary.

Open **Validate data and method** or `/estado-servicios` to see sanitized connection status. This endpoint reports whether the key is configured and encrypted, the active dataset mode and ingestion dates. It never returns credentials. A configured key alone does not change an already built synthetic dataset.

For a real dataset already processed locally:

```powershell
uv run python -m api --datos data/processed/vercel_firms --puerto 8000
```

## Method, provenance and limitations

Rules version: `armonizacion-0.3.1`. Default indicator: equivalent active cells, `celdas-eq-1.1.0`; it is not a sum of MODIS and VIIRS pixel counts. Source files, checksums, acquisition and download dates, processing rules and dataset identifiers remain traceable in JSON, CSV and record popups. The API field names remain stable across languages.

Read `/metodologia?idioma=en`, `/limitaciones?idioma=en` and `/procedencia`. The baseline uses the historical 95th percentile in a ±7-day window, excluding the evaluated year and requiring five reference years. Recent NRT data without sufficient history do not support unusual-day thresholds. Coverage gaps, zero filling, empirical calibration, pixel footprints and brightness-temperature saturation remain limitations; scientific accuracy is not certified.

## Verify

```powershell
uv run pytest -q
uv run python tools/scan_secrets.py
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/languages "C:/Program Files/Google/Chrome/Application/chrome.exe" idiomas
```

The browser check requires Node.js and Chrome. NASA imagery, remote boundaries, weather and remote place search require internet; synthetic data and local boundaries remain available locally. The GitHub Pages demonstration has no Python server and cannot use a production FIRMS secret.

Sources: NASA FIRMS (LANCE / ESDIS), NASA GIBS, geoBoundaries/DANE, Natural Earth, OpenStreetMap/Nominatim and Open-Meteo. Source attribution and scientific warnings remain visible in the application.
