# Descarga FIRMS por área

El módulo `ingest.firms_download` descarga CSV de la API area de FIRMS para el
bbox configurado del Huila. Requiere Python 3.13 y una clave en la variable de
entorno `FIRMS_MAP_KEY` o en un archivo `.env` local no versionado:

```dotenv
FIRMS_MAP_KEY=
```

La clave se completa únicamente en el `.env` local.

Para inspeccionar las peticiones sin acceder a la red:

```bash
uv run python -m ingest.firms_download --dry-run
```

La salida siempre sustituye la clave por `<MAP_KEY>`. Una descarga con fechas y
fuentes explícitas se ejecuta así:

```bash
uv run python -m ingest.firms_download \
  --sources MODIS_NRT VIIRS_NOAA20_NRT \
  --start 2026-01-01 --end 2026-12-31 \
  --bbox -76.7 1.4 -74.3 3.9 \
  --out data/raw/firms_api --pause 1
```

Sin fechas, se consulta el intervalo inclusivo desde la fecha UTC actual menos
365 días hasta la fecha UTC actual. Las fuentes predeterminadas son las
enumeradas en `FUENTES_API`: MODIS NRT y estándar, VIIRS SNPP solo estándar,
VIIRS NOAA-20 y NOAA-21 NRT y, porque existe en esa tabla, VIIRS NOAA-20
estándar como fuente opcional incluida por defecto.

## Crudo inmutable y manifiesto

Cada respuesta válida se escribe primero en un temporal del directorio de
destino, se mueve al nombre definitivo y se cambia a modo `0444`. Un nombre ya
existente produce un error: el descargador nunca lo sobrescribe. El nombre
incluye fuente, bbox, ventana de fechas y fecha-hora UTC de descarga.

Después de guardar el CSV se añade una línea JSON a
`data/raw/manifest.jsonl`. La entrada contiene la ruta relativa a `data/raw`,
SHA-256, tamaño, fuente, sensor, calidad, colección, fecha de descarga, URL con
`<MAP_KEY>`, bbox, intervalo solicitado y `sintetico=false`. La clave real no se
guarda ni se muestra. Una respuesta que no comienza por la cabecera esperada se
considera un error de API: no se guarda como CSV y se registra, con la clave
oculta, en `data/raw/firms_api/_errores.log`. Una respuesta formada solo por la
cabecera sí es un CSV válido.

`data/raw` es inmutable y está excluido de Git. Para verificar posteriormente
los hashes:

```bash
uv run python -m ingest.manifest verify data/raw/manifest.jsonl
```

## Límites y valores por confirmar

Los límites y la forma de la API están inventariados en
[`esquema_firms.md`](esquema_firms.md). Esa fuente local indica que la plantilla
de URL, las cabeceras, los nombres y colecciones de fuente, el bbox del Huila,
el máximo de días y el límite de transacciones siguen **por confirmar** contra
la documentación oficial y CSV públicos.

Mientras `API_DAY_RANGE_MAX` sea `None`, el módulo usa provisionalmente ventanas
inclusivas de 5 días, la única hipótesis registrada en el esquema. Puede
ajustarse sin cambiar código mediante `FIRMS_API_DAY_RANGE_MAX`. Como
`API_LIMITE_TRANSACCIONES` también es `None`, `--pause` es configurable y vale
un segundo por defecto. El programa emite advertencias para estos supuestos.
Las ventanas son contiguas, sin huecos ni solapes.

No se consulta `data_availability`: su URL figura como «por confirmar» y no hay
un contrato documentado y validado en `esquema_firms.md`. Hasta confirmarlo, el
servidor decide la disponibilidad al atender cada ventana y los errores quedan
en `_errores.log`.

## Bloqueo B-01

Si no existe una clave ni en el entorno ni en `.env`, el comando escribe:

```text
BLOQUEO B-01: falta FIRMS_MAP_KEY en .env (ver .env.example); se continúa con datos sintéticos en data/sample
```

y termina con código 2. En ese caso no intenta la red ni crea archivos crudos;
el trabajo puede continuar offline con los datos sintéticos de `data/sample`.
