# Lista de verificación de entrega

Revisada el 2026-11-14 sobre `main` (0a0d3c7) con reglas `armonizacion-0.3.1`; sección «Visor de capas» añadida el 2026-11-15 en `feat/globo-global`.
Leyenda: [x] hecho y verificado · [ ] pendiente · [!] bloqueado (motivo indicado).

## Entregables (§9)

- [x] Repositorio con README: instalación, uso, datos, citación y limitaciones. Ver `README.md`.
- [x] Demo ejecutable con datos locales y sin red: `make demo` y `make api`. Dos ejecuciones dan los mismos hashes.
- [x] Documento de metodología completo: `docs/metodologia.md` (flujo, R1 a R5, API, interfaz, validación cruzada y bibliografía).
- [x] Capturas de respaldo en `docs/capturas/` (H5-03): vista general, calendario, día seleccionado con huella y base insuficiente. Ver `docs/capturas/LEEME.md`. Con datos reales (ADR 0009) e interfaz H6 en claro, oscuro y 375 px: `05`–`08`.
- [x] Interfaz H6: tema claro/oscuro con contraste AA calculado, insignia de origen de los datos, resumen en lenguaje sencillo y calendario accesible (`tests/test_interfaz.py`). Auditoría UI/UX corregida: mapa en Canvas con rejilla de densidad, leyenda numérica y celdas táctiles de 24 px (`docs/auditoria_ui_ux.md`).
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
- [x] Muestra real de varios años del Huila en `data/raw`: Colombia 2016–2025 por la ruta pública por país (ADR 0009, `make real`), calidad estándar: 84 833 detecciones en el recuadro y 14 280 dentro del Huila por forma real (`docs/metodologia.md` §10.3). La API area con MAP_KEY sigue pendiente (B-01) y no hay datos de 2026.

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
- [x] D-11 Escaneo de secretos sin hallazgos (`make secrets`, 2026-11-14).

## Validación de veracidad (§8)

- [x] Conteo independiente frente al pipeline con datos reales (NRT de 24 h y estándar 2016–2025): diferencia sin explicar 0; el efecto de borde se informa aparte (`docs/metodologia.md` §10.1).
- [ ] Comparación con el **visor** de FIRMS para un día y un área: procedimiento listo y conteos por registrar (H5-02). Requiere una persona frente al visor.
- [x] Limitaciones declaradas: detecciones térmicas, centro de píxel, saturación VIIRS, sesgo horario de Terra y NRT (`docs/limitaciones.md` §10).
- [x] Bibliografía de validación (`docs/metodologia.md` §11 y `docs/cita.md`).
- [x] DOI verificados en doi.org: cuatro productos NRT y los productos VIIRS estándar de origen (`docs/cita.md`).

## Antes de enviar

- [x] `make test`: todas las pruebas pasan.
- [x] `make demo` y `make api` funcionan sin red.
- [x] `make secrets` sin hallazgos.
- [x] `git ls-files` no incluye `data/raw`, `data/processed` ni `.env`.
- [ ] Confirmar con los organizadores la sede en Neiva, la duración y el formato de envío. Dato público: el hackatón global es el 14 y 15 de noviembre de 2026 (R-38).

## Reto oficial (auditoría de cumplimiento, 2026-11-14)

- [x] O1 Calendario de quema en una aplicación web.
- [x] O2 Armonización: métrica que no cambia al sumar satélites (salto de 2018 de × 1,7 a × 1,00; ADR 0011).
- [x] O3 Serie desde 2001 (MODIS calibrado) hasta 2025. [ ] 2026 pendiente de la MAP_KEY (R-43).
- [x] O4 Región, rango de fechas, descarga de CSV y SVG.
- [x] O5, O6, O8 Meses y años con más actividad: matriz año × mes con totales.
- [x] O7 Mes reciente frente a la mediana histórica.
- [x] O9 CSV de los focos de la búsqueda.
- [x] C2 Dibujo del área y entrada de coordenadas.
- [x] C3 Rampa accesible: contraste AA y simulación de daltonismo (`tests/test_interfaz.py`).


## Visor de capas (ADR 0013, 2026-11-15)

- [x] Panel de capas agrupado en Base / Focos / Contexto, con casilla, icono, nombre, opacidad y modo de mezcla; preajustes Mapa, Fuego y Agua (`src/ui/static/capas.js`).
- [x] Mezcla real en el lienzo único: sombreado ASTER multiplicado sobre la base. Las capas en color quedan en modo normal y el selector lo explica.
- [x] Límites de departamento y municipio siempre sobre cualquier base, sin depender del zoom; solo las etiquetas cambian con el zoom.
- [x] Límite departamental como unión de los 37 municipios DANE (CC BY 4.0). ADM1 de geoBoundaries verificado: existe, pero es ODbL 1.0 y no se redistribuye.
- [x] Clic en un foco: resalta el departamento (zoom < 8) o el municipio (zoom ≥ 8, con el departamento como contexto). Tarjeta con nombre, focos del periodo, confianza alta, origen y fecha UTC. Umbral **PROVISIONAL** medido con prueba visual (`tools/recorrido_capas.mjs`).
- [x] Búsqueda: primero municipios y departamento locales; Nominatim solo con conexión, caché en la pestaña y una consulta por segundo. El servidor ya no guarda búsquedas.
- [x] Leyenda mínima: escala FRP distinguible con daltonismo (ΔE ≥ 10) y confianza por opacidad y borde.
- [x] Línea de tiempo: día anterior, día, día siguiente y «Todo el año», en UTC.
- [x] Pie con cita FIRMS, «No usar para proteger vidas ni bienes», «detecciones térmicas, no incendios confirmados», fechas en UTC y advertencia visible con datos sintéticos o mixtos.
- [x] Licencias verificadas (GIBS Blue Marble, Blue Marble NG y ASTER GDEM: NASA sin restricciones; Natural Earth: dominio público). Sin proveedores remotos nuevos.
- [x] Capturas de escritorio y móvil, claro y oscuro: `docs/capturas/visor_capas_20261115/`.
- [x] Recorrido en Chrome: `node tools/prueba_navegador.mjs URL carpeta chrome capas` da 10/10; el recorrido `normal` sigue en 18/18.
- [ ] Recorrido `busqueda` (`tools/recorrido_busqueda.mjs`): 2/4. Falla igual en el commit anterior (b4b447a); no lo introduce este cambio.
- [ ] Hidrografía de detalle municipal: pendiente de revisar la licencia de HydroRIVERS.

## Vías, ciudades y zonas (ADR 0014, 2026-11-15)

- [x] Base mínima «Vías e infraestructura»: OpenStreetMap en grises para que destaquen los focos. Preajuste «Vías». El proveedor ya estaba permitido; la prueba del globo se amplió explícitamente.
- [x] Al elegir un foco: departamento (zoom < 8), municipio (8 a < 11) o ciudad (≥ 11, si el punto cae en un área urbana). La zona cambia de nivel sola al acercarse o alejarse. Umbrales PROVISIONALES medidos con prueba visual.
- [x] Nombre de la zona sobre el mapa, nombres de ADM1/ADM2 cargados y botón «Ver zona completa».
- [x] Fuera del Huila y desde el globo: el país se busca en local y sus ADM1/ADM2 se piden a `/limites` (comprobado con el Tolima).
- [x] Ciudades: 55 áreas urbanas con nombre de Natural Earth 1:10m (dominio público), `tools/preparar_ciudades.py`.
- [x] Recorrido en Chrome (`capas`): 15/15; `normal`: 18/18.
- [ ] Perímetros urbanos oficiales del DANE (todas las cabeceras del Huila): pendiente de revisar su licencia.
- [ ] Proveedor de teselas propio antes de un despliegue público (R-30).
