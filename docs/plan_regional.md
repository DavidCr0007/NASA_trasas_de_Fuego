# Plan: cobertura regional LatAm + Europa (continuación)

Estado al 2026-11-14. Trabajo validado en esta sesión; la implementación queda pendiente.

## Decisiones del usuario
- Alcance: **toda Latinoamérica y Europa**, historia completa.
- Base de datos «recién liberada» de la NASA: el usuario pasará el enlace para validar su acceso (pendiente).

## Claves (validado)
- La `MAP_KEY` de FIRMS es **gratuita**, se pide solo con un correo en
  <https://firms.modaps.eosdis.nasa.gov/api/map_key/>; no hay acceso anónimo a la API.
- **No se extraen claves de ningún sistema.** Los 4 repositorios propuestos **no contienen** ninguna MAP_KEY.
- No hace falta clave: los archivos **por país** son públicos (calidad estándar, 2001–2025).
- 2026 aún no está en el archivo por país (404).

## Recursos (medido)
- Disco libre: 316 GB (sobra). Memoria: ~3 GB libres → **el pipeline Python no escala**; usar **DuckDB nativo** (streaming desde disco, límite 12 GiB, memoria acotada).
- Tamaño por país y año (2024): Colombia MODIS 1,9 MB / VIIRS 8 MB; **Brasil VIIRS 155 MB (2 M filas)**.
  Estimación LatAm+Europa, historia completa: **decenas de GB, cientos de millones de filas**.

## Ancla de correctitud (validado)
Una agregación **en SQL (DuckDB)** sobre los mismos recortes reproduce el `celda_dia` del pipeline
Python **exactamente**: 99 034 celda-día, 131 021 `n_brutas`, **0 diferencias**, en 2,7 s.
Grilla: `cell_fila=floor((lat+90)/0.009)`, `cell_col=floor((lon+180)/0.009)`, `cell_id='f'||fila||'_c'||col`.
Validación: lat∈[-90,90], lon∈[-180,180]; MODIS sat∈{T,A,Terra,Aqua} y `try_cast(conf as INT)∈[0,100]`;
VIIRS sat∈{N,N20,N21} y conf∈{low,nominal,high,l,n,h}. (Usar `try_cast`, no `::INT`: DuckDB no corta el AND.)

## Países FIRMS validados (HTTP 200, archivo MODIS 2024)
- **LatAm (26):** Argentina, Belize, Bolivia, Brazil, Chile, Colombia, Costa_Rica, Cuba,
  Dominican_Republic, Ecuador, El_Salvador, French_Guiana, Guatemala, Guyana, Haiti, Honduras,
  Mexico, Nicaragua, Panama, Paraguay, Peru, Puerto_Rico, Suriname, Trinidad_and_Tobago, Uruguay, Venezuela.
- **Europa (37):** Albania, Austria, Belarus, Belgium, Bosnia_and_Herzegovina, Bulgaria, Croatia,
  Czech_Republic, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Iceland, Ireland,
  Italy, Kosovo, Latvia, Lithuania, Luxembourg, Moldova, Montenegro, Netherlands, Norway, Poland,
  Portugal, Romania, Serbia, Slovakia, Slovenia, Spain, Sweden, Switzerland, Ukraine, United_Kingdom.

## Pasos pendientes (en orden)
1. `src/ingest/celda_dia_sql.py`: builder DuckDB-nativo que produce `celda_dia.parquet` (contrato actual
   + banderas por celda-día para la métrica armonizada: `has_ref`=MODIS∪Suomi NPP, `has_modis`, `has_mn20`,
   `has_snpp`, `has_n20`). Prueba que compara con el pipeline Python (0 diferencias).
2. `firms_publico.py`: presets de región (`--region latam|europa`) con las listas de arriba; descarga por país
   (crudo inmutable con SHA-256, reanudable); **sin recorte** (el builder SQL filtra por bbox/área al consultar).
3. Métrica armonizada por región: los factores de intercalibración (ADR 0011) se estiman **por conjunto regional**.
   La API calcula la serie desde las banderas de `celda_dia` cuando existan (no desde las detecciones crudas),
   para escalar; mantener la vía actual como respaldo (demo/Huila) y tests verdes.
4. A escala continental **no** se generan `detecciones`/`deduplicados` completas; el detalle por foco y la
   imagen GIBS del día quedan para un área pequeña seleccionada.
5. UI: selector de **región/país/coordenadas** e **imagen GIBS global con campo de fecha propio** (ver imágenes
   fuera del Huila sin depender del calendario). Las regiones filtran por **recuadro**; países del Huila por polígono.
6. `make` targets: `region-latam`, `region-europa` (descarga + build SQL). Documentar tamaño/tiempo y el aviso de
   factores por región. Ejecutar como trabajo largo reanudable.
7. Validar la base NASA del enlace que pase el usuario.

## Riesgos nuevos a registrar
- La descarga completa son decenas de GB y horas; es reanudable (se omite lo ya bajado).
- Los factores de armonización son por región; no mezclar regiones en un mismo conjunto.
- La métrica cuenta celdas activas, no incendios; a escala continental no hay detalle por foco.
