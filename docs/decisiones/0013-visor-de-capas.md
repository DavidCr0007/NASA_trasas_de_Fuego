# ADR 0013: Visor de capas sobre el lienzo MapLibre

## Estado

ACEPTADA (2026-11-15). Amplía el ADR 0012 (lienzo único MapLibre, globo 3D) y el ADR 0008 (página sin compilación). No cambia las reglas de armonización ni la API de datos.

## Contexto

Se pidió rediseñar el visor combinando dos referencias:

- **NASA FIRMS:** panel de capas agrupado, barra de herramientas y línea de tiempo.
- **Explorador de focos propio:** búsqueda por lugar, tarjeta de resumen, escala de potencia y pie con cita y aviso.

El estilo debía ser minimalista y con un solo color de acento. El pedido suponía un visor Leaflet, con paneles propios y modos de mezcla CSS por capa. Desde el 14-nov el visor es **un único lienzo WebGL de MapLibre** (ADR 0012, «planeta continuo»), y la prueba `test_un_solo_lienzo_y_limites_vectoriales` impide volver a Leaflet. Se resolvieron cuatro conflictos con el responsable antes de programar (C1–C4).

## Decisión

### C1. Se mantiene MapLibre; el pedido se traduce al lienzo único

- **Panel de capas** (`capas.js`), en tres grupos:
  - **Base:** Relieve, Satelital, Hidrografía o Ninguna. Es un *radio*: solo una base activa.
  - **Sobre la base:** Sombreado del relieve; Ríos y lagos.
  - **Focos:** MODIS (Terra y Aqua), VIIRS NOAA-20, VIIRS NOAA-21, VIIRS Suomi NPP rotulado «histórico» y **Armonizados**. Armonizados son las celdas activas de ~1 km de la grilla R1, lo que cuenta el calendario.
  - **Contexto:** Límites de departamento y municipio; Clima (reanálisis), apagado por defecto.

  Cada capa tiene casilla, icono, nombre y un botón «ajustes» (`aria-expanded`) con opacidad y modo de mezcla. Los grupos se pliegan con botones ARIA. Una línea bajo «Capas» resume lo activo, por ejemplo «Relieve · Sombreado · Ríos · 4 satélites · Armonizados · Límites».
- **Preajustes:**
  - **Mapa** (por defecto): relieve, sombreado multiplicado al 45 %, ríos.
  - **Fuego:** satelital, sombreado multiplicado al 70 %, sin ríos.
  - **Agua:** hidrografía, sombreado al 35 %, ríos al 100 %, focos al 60 %, sin armonizados.

  Conservan las casillas de satélites y del clima.
- **Mezcla real sin CSS.** WebGL compone las capas en modo normal. El sombreado ASTER en grises (valor g) se transforma en el navegador (`maplibregl.addProtocol("sombra")`) en píxeles negros con alfa 1 − g. Componerlos en modo normal da base · (1 − α) = base · g, que es exactamente **multiplicar**. «Trama» usa blanco con alfa g: base + g(1 − base). El negro puro (sin dato, mar) queda transparente.

  Las capas en color (satélite, ríos, focos, límites) solo admiten «Normal». Su selector aparece desactivado y explica por qué. No se ofrece una mezcla que el motor no hace.
- **Orden fijo de abajo arriba:** bases → imagen del día → sombreado → lagos y ríos → atenuación de la zona → **límites** (ADM0–2 a demanda y Huila local) → zona resaltada → focos y celdas → área. Los límites locales usan el mismo estilo que ADM1/ADM2, no tienen `minzoom` y su visibilidad solo depende de su casilla, nunca de la base. Las etiquetas (marcadores HTML, sin glifos remotos) son lo único que cambia con el zoom.
- **Estado** en `localStorage` (`hhn-capas`, versión 1), dentro de `try/catch`. Al leerlo se valida contra el catálogo: base, rango de opacidad y mezcla admitida.

### Selección de un foco y umbral de zoom

Al pulsar un foco (o una celda del globo), `zonas.js` calcula **en el cliente** la zona que lo contiene: punto en polígono con huecos, filtrando antes por recuadro.

- **Zoom < `UMBRAL_ZOOM_MUNICIPIO`:** se resalta el **departamento** y se atenúa el resto (máscara mundo-menos-zona al 42 %).
- **Zoom ≥ umbral:** se resalta el **municipio** (máscara al 30 %), con el departamento como contexto (línea discontinua).
- **Fuentes de las zonas:** primero los límites locales del Huila; fuera, los ADM1/ADM2 de geoBoundaries ya descargados para la vista. Si no hay límites cargados, la tarjeta lo dice.

**Umbral = 8** (zoom MapLibre, ≈ 9 de Leaflet). El pedido proponía 9 como valor provisional. La prueba visual (`tools/recorrido_capas.mjs`) midió:

- El Huila (2,29° de alto) solo cabe completo en el mapa de escritorio 1440 × 900 hasta el **zoom 7,55**.
- A zoom 8 el Huila ocupa unos 834 px de alto y ya no cabe; el municipio mediano mide unos 100 px y el menor (Elías) unos 60 px, legibles y fáciles de pulsar.
- Con 9, entre 7,55 y 9 se resaltaría un departamento que no se ve completo.

Capturas: `docs/capturas/visor_capas_20261115/umbral_zoom_7_9.png` y `umbral_zoom_8.png`. Sigue siendo **PROVISIONAL** y está comentado en `zonas.js`.

**Tarjeta de la zona:** nombre, focos en el periodo, focos de confianza alta, origen (real, sintético o mixto) y fecha UTC. El periodo es el mismo que muestra el mapa.

- **Zonas del Huila:** se usa la ruta existente `/calendario?area=huila|mun:<id>` (forma real, sin duplicados, todos los satélites). **No hace falta una ruta nueva.**
- **Fuera del Huila:** se cuenta en el navegador con los focos cargados y visibles, y la tarjeta advierte que puede estar incompleto.

### C2. Búsqueda local primero; el servidor no guarda búsquedas

1. `Zonas.buscarLocal` busca en los 37 municipios y el departamento: sin tildes ni mayúsculas, acepta «Neiva, Huila» y «municipio de …». Un único resultado se abre directamente: ajusta la vista al polígono y resalta la zona.
2. Si no hay coincidencias (o se pulsa «Buscar también en internet»), consulta Nominatim a través de `/buscar-lugares`, solo con conexión (`navigator.onLine`).
   - **Navegador:** caché en la memoria de la pestaña, como máximo 32 consultas, sin `localStorage`; una consulta por segundo como máximo.
   - **Servidor:** se retiró su caché de 24 h. Solo conserva la hora de la última consulta para cumplir el límite de Nominatim de 1 consulta por segundo **por aplicación**.
   - Nominatim devuelve el polígono simplificado (`polygon_geojson`, umbral 0,005°, como máximo 5 000 vértices), que se resalta igual que una zona local.

### C3. Límite departamental: unión de los municipios DANE

Se verificó en la API de geoBoundaries (2026-11-15) que **COL ADM1 existe**: 33 unidades, fuente OpenStreetMap/Wambacher, año 2017. Su licencia es **ODbL 1.0**, que obliga a compartir igual las bases derivadas.

No se redistribuye. `tools/preparar_limites.py` construye `huila_departamento.geojson` como **unión de los 37 municipios** de `huila_municipios.geojson` (DANE, CC BY 4.0). La unión descarta las aristas compartidas; la topología es limpia: 2 769 aristas interiores, 1 363 de contorno, todos los vértices de grado 2. No necesita `shapely`. El ADM1 se sigue usando solo para seleccionar los municipios.

### C4. Color = FRP; confianza = opacidad y borde

Se mantienen las cinco clases fijas de FRP (ADR 0012). La confianza se codifica sin color:

| Confianza | Opacidad | Borde |
|---|---|---|
| Alta | 0,95 | 2 px |
| Nominal | 0,8 | 1 px |
| Baja | 0,5 | 0,5 px |

La leyenda mínima (abajo a la izquierda) muestra ambas cosas. Simulando protanopia, deuteranopia y tritanopia (Machado et al., 2009), clases vecinas de FRP están a ΔE*76 ≥ 12,3; la prueba exige ≥ 10.

### Fuentes de las capas (licencias verificadas el 2026-11-15)

| Capa | Fuente | Licencia y uso | Red |
|---|---|---|---|
| Relieve | NASA GIBS `BlueMarble_ShadedRelief_Bathymetry` (nivel 8) | Datos NASA sin restricciones (CC0); se pide citar a NASA ([EOSDIS Data Use and Citation Guidance](https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance)) | GIBS (ya permitido) |
| Satelital | NASA GIBS `BlueMarble_NextGeneration` (nivel 8) + imagen del día VIIRS/MODIS | Ídem; Blue Marble NG de NASA Earth Observatory | GIBS |
| Sombreado | NASA GIBS `ASTER_GDEM_Greyscale_Shaded_Relief` (nivel 12) | ASTER GDEM V003 (METI/NASA), «openly shared, without restriction» (LP DAAC, doi:10.5067/ASTER/ASTGTM.003) | GIBS |
| Hidrografía (versión inicial, sustituida por ADR 0017) | Natural Earth 1:10m v5.1.2, ríos y lagos recortados a Colombia (`tools/preparar_hidrografia.py`, 149 kB) | Dominio público | Local, sin red |
| Límites | geoBoundaries gbOpen COL ADM2 (DANE) y su unión departamental | CC BY 4.0 | Local, sin red |
| Clima | Open-Meteo (ERA5, C3S/ECMWF) | CC BY 4.0; rotulado «reanálisis» | Open-Meteo (ya permitido) |

Las tres capas GIBS se comprobaron en `WMTSCapabilities.xml` de EPSG:3857 (`best`). **No se añadió ningún proveedor remoto:** `REMOTOS_PERMITIDOS` no cambia, y la prueba de recursos remotos ahora recorre todo el JavaScript propio (`app.js`, `globo.js`, `capas.js`, `zonas.js`, `busqueda.js`), no solo `app.js`.

Actualización del 2026-11-15: el [ADR 0017](0017-hidrografia-mundial.md) sustituye el recorte hidrográfico de Colombia por un respaldo mundial y añade OpenFreeMap como proveedor permitido para el detalle OpenStreetMap. El párrafo anterior describe la implementación inicial de este ADR.

**Descartadas:**

- GIBS `OSM_Land_Water_Map`: a escala regional es una tesela gris sin agua.
- HydroRIVERS: más detalle, pero su licencia menciona restricciones de redistribución que no se revisaron.
- Teselas de elevación de AWS: añadirían un proveedor y unos megabytes al repositorio.

## Consecuencias

- **Sin red** siguen funcionando: base «Ninguna» o «Hidrografía» (países, ríos y lagos locales), límites, focos, búsqueda local y tarjeta. El relieve, el satélite, el sombreado y el clima necesitan internet.
- **Hidrografía gruesa:** a 1:10m, en el Huila solo aparece el Magdalena.
- **Filtros por satélite:** actúan desde el zoom 6. Las celdas del globo (`/global`) no separan satélites; solo la opacidad del grupo se aplica allí.
- **Accesibilidad:** «Capas» abre y cierra el panel (`aria-expanded`). Escape lo cierra y devuelve el foco al botón. El foco visible es el de siempre (`--foco`).
- **Acento único:** `--acento` pasa a verde azulado (#0f766e claro, #2dd4bf oscuro), con contraste ≥ 4,5 sobre tarjeta y fondo en ambos temas. Así no se confunde con la rampa naranja de FRP ni con el azul de los ríos.
- **Pruebas nuevas en `tests/test_interfaz.py`:**
  - capas por defecto y validación del estado guardado;
  - preajustes;
  - límites siempre visibles y su orden;
  - etiquetas por zoom;
  - umbral documentado;
  - municipio contra departamento a ambos lados del umbral;
  - búsqueda local;
  - contraste del acento;
  - daltonismo de la escala FRP;
  - pie;
  - recursos remotos de todo el JavaScript propio.

  En `tests/test_limites.py`, la unión departamental. En `tests/test_lugares.py`, el servidor sin caché, el límite por aplicación y el polígono.
- **Recorrido en navegador:** `node tools/prueba_navegador.mjs URL carpeta chrome capas` da 10/10 y genera las capturas de `docs/capturas/visor_capas_20261115/`.

## Pendiente

- Revisar la licencia de HydroRIVERS (HydroSHEDS) para una hidrografía de detalle municipal.
- Separar satélites en `/global` si se quiere filtrar también en el globo.
- Validar el umbral 8 con usuarios en móvil (en 390 px el Huila cabe solo hasta un zoom menor).
