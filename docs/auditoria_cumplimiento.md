# Auditoría de cumplimiento frente al reto oficial (2026-11-14)

**Referencia:** texto oficial del reto «Harmonization of MODIS and VIIRS Hot Spots» (NASA Space Apps 2026), entregado por el equipo el 2026-11-14.
**Estado auditado:** `main` `cdd15f5`, con reglas `armonizacion-0.3.1` y R5 `r5-1.1.0`; 410 pruebas en verde.
**Evidencia:** datos reales del archivo por país de FIRMS (calidad estándar, 2016–2025), filtrados por la forma real del Huila (`area=huila`).

Leyenda: ✅ cumple · 🟡 parcial · ❌ no cumple.

## Objetivos del reto

| # | requisito del reto | estado | evidencia | brecha |
|---|---|---|---|---|
| O1 | Aplicación web con un **calendario de actividad de quema** basado en focos activos | ✅ | Calendario diario por año, mapa, panel, API y `make api-real` | — |
| O2 | **Armonizar** MODIS y VIIRS de modo que «el sensor de origen ya no importe» y la serie sea consistente | 🟡 | R1–R4: grilla de 1 km, confianza en tres clases, deduplicación de 3 h y procedencia por registro | **Alta.** La serie anual del Huila cambia de nivel al entrar NOAA-20 (2018): 663 y 577 detecciones en 2016–2017 frente a 1 207 y 1 410 en 2019–2020, con NOAA-20 aportando 598–615. La métrica `n_brutas` crece con el número de satélites. Falta una **métrica armonizada** insensible a cuántos sensores observan, más una **intercalibración** MODIS↔VIIRS en el periodo en que ambos coinciden. |
| O3 | Serie **desde inicios de los 2000** hasta el **presente** | 🟡 | Historia real 2016–2025 (`make real`) | **Alta.** El archivo por país tiene MODIS desde 2000 y Suomi NPP desde 2012, pero solo se descargó 2016–2025. 2026 (el presente) falta: solo existe en NRT y requiere la MAP_KEY (B-01) o los archivos de 7 días. |
| O4 | El usuario elige **región** y **rango de fechas** y **descarga analíticas y visualizaciones** | 🟡 | Región: Huila, 37 municipios, dibujo y Neiva. Descarga: CSV diario con cita y versión | **Media.** La interfaz solo elige **año**, no un rango libre (la API sí lo acepta). No se pueden descargar las visualizaciones (PNG/SVG). |
| O5 | Ver **qué periodos del año** tienen más fuego | ✅ | Climatología mensual y meses pico (Huila: septiembre, octubre y febrero) | — |
| O6 | Ver **qué años** tuvieron más actividad | 🟡 | Resumen y selector por año | **Media.** Falta una vista de **totales anuales** que compare todos los años de un vistazo. |
| O7 | Comparar el **mes actual con la mediana histórica** y un fuego actual con los anteriores | 🟡 | Días inusuales (P95 por día del año ± 7, ADR 0004) y comparación mensual con la **media** | **Media.** El reto pide **mediana**; falta la anomalía del mes en curso (porcentaje sobre la mediana). |
| O8 | **Rampas de color** que muestren diferencias **entre meses** (y años) | 🟡 | Rampa secuencial con contraste AA y leyenda numérica en el calendario diario | **Media.** Falta el «calendario de quema» clásico: una matriz **año × mes** coloreada, que es la vista más directa para O5, O6 y O8. |
| O9 | **CSV descargable de los focos** detectados en la búsqueda | ❌ | Solo se exporta el agregado diario (`/calendario.csv`) | **Media y fácil.** Falta `/detecciones.csv`: lista de focos con coordenadas, satélite, hora, confianza, calidad, cita y versión. |

## Consideraciones opcionales

| # | consideración | estado | evidencia y brecha |
|---|---|---|---|
| C1 | Público: alerta temprana, respondedores, científicos, gestores, bomberos | ✅ | Resumen en lenguaje sencillo, explicaciones, aviso «no usar para proteger vidas ni bienes» y tema claro/oscuro |
| C2 | Mapa para **dibujar** el área u opción de **latitud/longitud** | 🟡 | Dibujo ✅. Falta **ingresar coordenadas** (W, S, E, N o punto con radio). |
| C3 | **Rampas de color accesibles** | 🟡 | Contraste AA en ambos temas, comprobado con pruebas. No se ha comprobado la distinción para daltonismo; la rampa naranja secuencial debería resistirla, pero está sin verificar. |
| C4 | Representar un **calendario de quema** | ✅ | Calendario diario (ver O8 para la matriz año × mes) |
| C5 | Índices clave: comparaciones históricas, **anomalías frente a promedios plurianuales**, número de focos | 🟡 | Número de focos ✅; días inusuales ✅; anomalía mensual frente a la media o mediana plurianual ❌ (ver O7) |
| C6 | Usar **NASA Earthdata FIRMS** y combinar MODIS (histórico) con VIIRS (detalle) | ✅ | Esquema verificado, ruta pública, conexión con el visor FIRMS, DOI y cita |

## Requisitos propios del proyecto (resumen)

R1–R5, D-01 a D-11 y los entregables §9 se cumplen; ver `docs/checklist_entrega.md`. Siguen abiertos:

- H5-02: comparación manual con el visor de FIRMS. El enlace directo ya está en la interfaz.
- B-01: la MAP_KEY de la API area.
- Confirmar con los organizadores la sede en Neiva y el formato de envío (R-38).

## Hallazgos de esta jornada que afectan la presentación

- **R-41 (corregido):** hasta hoy se presentaron cifras del **recuadro** como «Huila». El departamento ocupa solo el 25 % del recuadro. Cifras corregidas: **14 280** focos 2016–2025 dentro del Huila (no 83 519), con meses pico **septiembre, octubre y febrero** (no febrero, enero y septiembre). Ver `docs/metodologia.md` §10.3.
- **Sesgo de Terra:** en 2025 Terra aporta 19 detecciones en el Huila (153 en 2024). Coincide con el sesgo horario por la deriva y el fin de Terra declarado en limitaciones §10.

## Plan de cierre de brechas (por impacto sobre esfuerzo)

| prioridad | brecha | propuesta | esfuerzo |
|---|---|---|---|
| 1 | O2 armonización | Métrica armonizada **celdas activas por día**: celdas de 1 km con al menos un foco, independiente de cuántos satélites las ven. Más un **factor de intercalibración** MODIS→VIIRS estimado en el periodo en que ambos coinciden (2012–2025), para extender la serie a la era solo-MODIS. Documentar en un ADR, con pruebas y una nueva `RULES_VERSION`. | alto |
| 2 | O3 serie larga | `make real --desde 2001` (MODIS 2001–2011 y Suomi NPP desde 2012), con la métrica de la prioridad 1 | bajo (datos), depende de 1 |
| 3 | O8, O6 | Matriz **año × mes** coloreada (el «burn calendar») con totales anuales | medio |
| 4 | O9 | `/detecciones.csv` con cita, versión, calidad y área | bajo |
| 5 | O7, C5 | Mediana mensual plurianual y anomalía (%) del mes en curso frente a la mediana | bajo a medio |
| 6 | O4, C2 | Rango de fechas libre y entrada de coordenadas | bajo a medio |
| 7 | O4 | Descarga de las visualizaciones (SVG del calendario y la matriz) | bajo |
| 8 | C3 | Verificar la rampa con simulación de daltonismo | bajo |

## Seguimiento: cierre de brechas (H8, 2026-11-14)

| # | antes | ahora | evidencia |
|---|---|---|---|
| O2 | 🟡 | ✅ | Métrica «celdas activas equivalentes» (ADR 0011). Con datos reales del Huila, el salto de 2018 pasa de × 1,7 a × 1,00 y el de 2012, de × 7,4 a × 1,3. Factores publicados: k_M ≈ 4,34 y k_N20 ≈ 1,00. |
| O3 | 🟡 | 🟡 | Serie 2001–2025 (131 021 detecciones en el recuadro, 0 en cuarentena). **2026 sigue pendiente** de la MAP_KEY (R-43); la calibración con NOAA-20 está lista. |
| O4 | 🟡 | ✅ | Rango de fechas libre (mapa y descargas), CSV del calendario, CSV de focos y SVG del calendario y de la matriz |
| O6 | 🟡 | ✅ | Totales anuales en la matriz; años con más actividad en el Huila: 2024, 2023 y 2020 |
| O7 | 🟡 | ✅ | Mes reciente frente a la mediana: diciembre de 2025, +78 % (Huila por forma) y +91 % (recuadro de Neiva por coordenadas), con 24 años de referencia |
| O8 | 🟡 | ✅ | Matriz año × mes 2001–2025 con rampa accesible y leyenda numérica |
| O9 | ❌ | ✅ | `/detecciones.csv`: una fila por foco, con cita y procedencia (`tests/test_api.py`) |
| C2 | 🟡 | ✅ | Entrada de coordenadas validada |
| C3 | 🟡 | ✅ | Rampa monótona y con pasos de al menos 5 L* bajo protanopía, deuteranopía y tritanopía. La simulación encontró un paso débil en el tema oscuro, que se corrigió |
| C5 | 🟡 | ✅ | Anomalía frente a la mediana plurianual y días inusuales por P95 |

**Queda abierto:** el año en curso (2026) en la serie (R-43 y B-01), y la comparación manual con el visor de FIRMS (H5-02), que ya tiene enlace directo desde la interfaz.
