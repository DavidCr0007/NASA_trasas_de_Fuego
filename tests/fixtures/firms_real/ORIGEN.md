# Origen de los CSV reales FIRMS

Recortes con la cabecera y las 25 primeras filas, copiados byte a byte (`head -26`) de los
archivos públicos de 24 h de FIRMS para South America. Esos archivos no requieren clave.

- Descarga: 2026-11-13 22:54 UTC. Calidad: **NRT** (preliminar).
- Base: `https://firms.modaps.eosdis.nasa.gov/data/active_fire/`
- Archivos completos (no versionados): `data/raw/firms_24h_south_america/20261113/`,
  con `manifest.jsonl`.

| recorte | URL (relativa a la base) | sha256 archivo completo | sha256 recorte |
|---|---|---|---|
| `MODIS_C6_1_South_America_24h_head.csv` | `modis-c6.1/csv/MODIS_C6_1_South_America_24h.csv` | `563090e8e81d6c9c5e5f896d5c8c7dba4434dfaae61ebf4b9681860747f8fc30` | `8e776b3d23bfcfe54f34c6faefbcfde36ee3767ca512610418a0224a9e9789d7` |
| `J1_VIIRS_C2_South_America_24h_head.csv` | `noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_America_24h.csv` | `2f922790001ef2de348aa8143ed893c9698f2bffd80e611592568da08e8f1741` | `b09bec849955ab4b1230134c678d265c4f12409480c4909c610484bbb64ef209` |
| `J2_VIIRS_C2_South_America_24h_head.csv` | `noaa-21-viirs-c2/csv/J2_VIIRS_C2_South_America_24h.csv` | `2788337f617ba4a54d1f3a2a9c5208d8872ae1c1626207eb922bfa6ccbbc952e` | `86b687cf13244e576e49b8dee8423e047c156c433dabdf79019f775a4596e178` |

El archivo de Suomi NPP (`suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_24h.csv`,
sha256 `fe0401e4…40`) solo trae la cabecera, porque el satélite ya no entrega datos nuevos.
Por eso no tiene recorte.

Cita obligatoria: ver `docs/cita.md`.
