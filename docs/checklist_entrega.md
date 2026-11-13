# Lista de verificación de entrega

Revisada el 2026-11-13 sobre `main` con reglas `armonizacion-0.3.1`.
Leyenda: [x] hecho y verificado · [ ] pendiente · [!] bloqueado (motivo indicado).

## Entregables (§9)

- [x] Repositorio con README: instalación, uso, datos, citación y limitaciones. Ver `README.md`.
- [x] Demo ejecutable con datos locales y sin red: `make demo` y `make api`. Dos ejecuciones dan los mismos hashes.
- [x] Documento de metodología completo: `docs/metodologia.md` (flujo, R1 a R5, API, interfaz, validación cruzada y bibliografía).
- [ ] Capturas de respaldo en `docs/capturas/` (H5-03). Pendientes: el panel del navegador estaba oculto durante la sesión.
- [x] Pitch de 2 minutos: `docs/pitch.md`, sincronizado con el código (`tests/test_documentos.py`).
- [x] Esta lista, marcada antes de enviar.

## Datos FIRMS (§2)

- [x] Productos y colecciones verificados: MODIS C6.1 y VIIRS colección 2 (NRT). Ver `docs/esquema_firms.md`.
- [x] Suomi NPP documentado como solo histórico; su CSV de 24 h llega vacío.
- [x] Incertidumbre espacial (centro de píxel) en la API (`semilado_nominal_m`) y en el mapa (círculo del tamaño de la huella).
- [x] Calidad NRT o estándar etiquetada en cada registro, día y exportación.
- [x] Credenciales fuera del repositorio: `.env` en `.gitignore` y `.env.example` vacío.
- [x] Cita de FIRMS + LANCE + ESDIS y aviso «as is» literales en la app, la exportación y el README.
- [x] Tablas de atributos consultadas antes del lector; escala de confianza VIIRS y códigos de satélite confirmados.
- [!] Muestra real de varios años del Huila en `data/raw`: **bloqueado por B-01** (falta `FIRMS_MAP_KEY`). Hay muestra real de 24 h de Sudamérica (NRT).

## Reglas (§3)

- [x] R1 grilla de ~1 km y celda-día (corregida en 0.3.1: ninguna detección original se pierde).
- [x] R2 tres clases de confianza; umbrales MODIS 30/80 PROVISIONALES (ADR 0002).
- [x] R3 deduplicación de 3 h conservando VIIRS; la limitación voraz está documentada.
- [x] R4 satélite, hora UTC y calidad en cada registro.
- [x] R5 climatología por día del año con P95 y mínimo de 5 años; «base insuficiente» si no se alcanza.
- [x] Versión de reglas incrementada con cada cambio: 0.1.0 → 0.2.0 → 0.3.0 → 0.3.1.

## Requisitos de software (§4)

- [x] D-01 Trazabilidad: sensor, satélite, colección, hora UTC, fecha de descarga y hash de la fuente.
- [x] D-02 Calidad visible y marca de preliminar.
- [x] D-03 Validación de esquema y rangos.
- [x] D-04 Cuarentena con motivo; se cumple entrada = aceptados + cuarentena + deduplicados.
- [x] D-05 Versión de reglas en cada resultado.
- [x] D-06 Reproducibilidad por hash.
- [x] D-07 Metadatos de incertidumbre en la API.
- [x] D-08 Mínimo de años para la línea base.
- [x] D-09 Sin datos personales.
- [x] D-10 Cita en el mapa, las exportaciones y el README.
- [x] D-11 Escaneo de secretos sin hallazgos (`make secrets`, 2026-11-13).

## Validación de veracidad (§8)

- [x] Conteo independiente frente al pipeline con datos reales: diferencia 0 en el Huila y en Colombia (`docs/metodologia.md` §10.1).
- [ ] Comparación con el **visor** de FIRMS para un día y un área: procedimiento listo y conteos por registrar (H5-02). Requiere una persona frente al visor.
- [x] Limitaciones declaradas: detecciones térmicas, centro de píxel, saturación VIIRS, sesgo horario de Terra y NRT (`docs/limitaciones.md` §10).
- [x] Bibliografía de validación (`docs/metodologia.md` §11 y `docs/cita.md`).
- [ ] DOI de cada producto (R-24).

## Antes de enviar

- [x] `make test`: todas las pruebas pasan.
- [x] `make demo` y `make api` funcionan sin red.
- [x] `make secrets` sin hallazgos.
- [x] `git ls-files` no incluye `data/raw`, `data/processed` ni `.env`.
- [ ] Confirmar con los organizadores la duración del evento local y el formato de envío.
