# Harmonization methodology

Harmonized Heat Neiva · rules `armonizacion-0.3.1` · metric `celdas-eq-1.1.0`.

## Data and provenance

NASA FIRMS MODIS C6.1 and VIIRS 375 m detections retain their product, collection, platform, UTC acquisition time, confidence, FRP, brightness temperature, source file, SHA-256 checksum, download time and CSV record number. Near-real-time (NRT) observations are preliminary. Standard-quality data and synthetic demonstration data remain explicitly identified.

`/procedencia` describes the analysis and global datasets separately. Each response and CSV includes a reproducible dataset identifier. These are declared provenance records, not independent scientific certification. Record numbers start at 1 after the CSV header; they are not necessarily physical line numbers for multiline fields.

## Processing rules

1. **R1: grid.** Detections use a fixed 0.009° grid in geographic coordinates, with origin latitude −90°, longitude −180°. The nominal cell size is about 1 km near the reference study area. Its physical width varies with latitude; it is not an equal-area grid.
2. **R2: confidence.** MODIS values are mapped into low, nominal and high classes with provisional thresholds 30 and 80. VIIRS confidence classes are normalized. Confidence is not temperature uncertainty.
3. **R3: deduplication.** Detections in one cell are grouped within three hours of the earliest anchor, using deterministic ordering and representative selection. The relation is not transitive. Both cross-sensor and same-sensor detections may merge. Absorbed records are retained in a separate table with the representative identifier.
4. **R4: lineage.** Raw inputs are immutable and registered by SHA-256. Invalid records are quarantined with reasons. No input record is silently deleted: input = representatives + deduplicated + quarantined records.
5. **Aggregation.** Cell-day tables retain representative counts, original counts, sensor counts and FRP statistics. Original detections are assigned to their own UTC day, including when their representative falls on a neighboring day.

## Harmonized indicator

The default indicator is **equivalent active cells**, rather than the sum of MODIS and VIIRS pixels. It reconstructs daily distinct cells from representatives and deduplicated records.

The reference constellation is MODIS (Terra and Aqua) ∪ Suomi NPP. Before that reference era, MODIS cells are multiplied by monthly overlap factors. After Suomi NPP, MODIS ∪ NOAA-20 cells are divided by their overlap factor. Factors are estimated from the processed dataset and disclosed in the API; they remain empirical assumptions.

If Suomi NPP reference observations are absent, the method is labeled **uncalibrated** and counts active cells from all available constellations. This does not establish comparability between years. `metrica=n_brutas` explicitly requests original counts instead.

## R5: baseline and unusual days

The default threshold is the historical 95th percentile for the same day of year within a ±7-day window, excluding the evaluated year. At least five reference years are required for a daily threshold. Insufficient reference data produce null thresholds and no unusual-day classification.

The coverage interval comes from the dataset’s first and last detected dates. Gaps inside that interval are filled with zero. This is not a mask of valid satellite observations, cloud cover or sensor availability; zero detections do not prove absence of fire. Partial years and zero-heavy references require additional validation. An unusual day is a statistical comparison, not an emergency alert.

## Spatial definitions and interpretation

For supported administrative polygons, cells are selected by whether their centers lie within the polygon. Bounding-box queries use their four coordinates. Map points use detection coordinates. Small differences near boundaries must be interpreted using these definitions. World circles aggregate detections and use maximum FRP for color and count for size; they do not represent burned area.

FRP is expressed in MW and has no direct conversion to °C. Brightness temperature, when available, is converted using °C = K − 273.15. It combines fire and background signals; it is not flame or air temperature. MODIS and VIIRS nominal resolutions are 1,000 m and 375 m; pixel footprints grow toward the scan edge. The file does not provide individual ±°C uncertainty.

## Reproduction and verification

With dependencies pinned in `uv.lock`:

```powershell
uv run python -m harmonize.pipeline --input data/sample --output data/processed/demo
uv run pytest -q
uv run python tools/auditar_plataforma.py --datos data/processed/global_nrt --crudos data/raw/global --salida docs/evidencias/check.json
```

Deterministic schemas, row ordering and Parquet settings make the same inputs and configuration reproducible under the same dependency versions. `/procedencia` publishes declared checksums; the audit tool verifies locally available files and compares JSON with CSV. Synthetic tests verify execution and consistency, not empirical satellite accuracy.

Sources: NASA FIRMS (LANCE / ESDIS); see `/limitaciones?idioma=en` for remaining uncertainties. Do not use this tool for the preservation of life or property.
