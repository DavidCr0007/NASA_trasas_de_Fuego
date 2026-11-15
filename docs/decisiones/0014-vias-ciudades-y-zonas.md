# ADR 0014: Vías e infraestructura, ciudades y zonas en cualquier escala

## Estado

ACEPTADA (2026-11-15). Amplía el ADR 0013 (visor de capas). Revierte en parte el ADR 0012, que había retirado OpenStreetMap del mapa: vuelve como **una base opcional**, no como fondo por defecto.

## Contexto

Se pidió:

1. Al seleccionar un foco, ver el contorno del **municipio, departamento o ciudad** al que pertenece.
2. Al acercarse, ver **el municipio o la ciudad completos**, con sus vías, separaciones y nombre.
3. Una capa **mínima** donde destaquen los colores de los focos o se vean las vías y la infraestructura de la zona.

Situación de partida:

- El ADR 0013 resaltaba municipio o departamento solo con los límites del Huila o con los ADM ya descargados para la vista. Desde el globo, fuera del Huila, respondía «Fuera de los límites cargados».
- No había nivel de ciudad ni ninguna capa de vías.

## Decisión

### Vías e infraestructura: OpenStreetMap en grises

- Se revisaron las capas de referencia de NASA GIBS (`Reference_Features`, `Reference_Labels` y sus versiones de 15 m) el 2026-11-15.
  - `Reference_Features` solo trae fronteras y costas.
  - Las versiones de 15 m devuelven teselas vacías o error 500 a escala municipal.
  - **GIBS no ofrece vías.**
- Se usa `https://tile.openstreetmap.org/{z}/{x}/{y}.png`. Este proveedor **ya estaba en `REMOTOS_PERMITIDOS`** desde el ADR 0008, así que la lista no cambia.
  - La prueba `test_globo_solo_carga_remotos_de_nasa_gibs` (`tests/test_global.py`) se amplía explícitamente a GIBS + esa única URL de OSM.
- **Base «Vías e infraestructura» (nota «mínima»):** OSM con `raster-saturation: -1` y los negros algo aclarados. Muestra vías, separaciones, nombres de barrios y calles, aeropuertos y edificios en grises, de modo que solo destacan la escala FRP, las celdas armonizadas y la zona resaltada.
  - Va bajo el sombreado, el agua y los **límites**, que siguen encima.
  - Es fija en ambos temas, como el resto del mapa.
- **Preajuste «Vías»:** base mínima, sin sombreado ni ríos, con focos, armonizados y límites.
- **Licencia y uso:**
  - Datos © OpenStreetMap contributors (ODbL 1.0). Crédito visible en el mapa (atribución de la fuente) y en el pie.
  - La [política de uso de teselas](https://operations.osmfoundation.org/policies/tiles/) se cumple: crédito visible, sin precarga ni descarga masiva, caché del navegador y peticiones con el Referer de la página.
  - Para un despliegue público hace falta un proveedor propio (R-30, ya registrado en el ADR 0008).

### Tres niveles de zona según el zoom

`zonas.js` define dos umbrales PROVISIONALES medidos con prueba visual (`tools/recorrido_capas.mjs`) en 1440 × 900:

| Zoom MapLibre | Se resalta | Contexto | Medida |
|---|---|---|---|
| < 8 | Departamento | — | El Huila solo cabe completo hasta 7,55 |
| 8 a < 11 | Municipio | Departamento | El municipio de Neiva (0,68°) cabe hasta 9,58 |
| ≥ 11 | Ciudad (área urbana), si el punto cae en una | Municipio | El área urbana de Neiva mide unos 130 px a zoom 11 |

- Si falta el nivel pedido, se baja al siguiente. Un punto rural a zoom 12 resalta su municipio.
- El punto del foco elegido se recuerda. Al **acercarse o alejarse** y cruzar un umbral (`zoomend`), la zona cambia de nivel sola. Las zonas elegidas con la búsqueda no cambian.
- **Ciudades:** `tools/preparar_ciudades.py` toma las áreas urbanas de Natural Earth 1:10m (dominio público) que tocan Colombia. A cada una le asigna el nombre del centro poblado más poblado que contiene (o el más cercano, a menos de 0,1°).
  - Resultado: `datos/ciudades_colombia.geojson`, 55 ciudades, 108 kB, sin red.
  - Incluye Bogotá, Medellín, Cali, Neiva e Ibagué, además de ciudades de los países vecinos dentro del recuadro.
- **Fuera del Huila y sin límites cargados** (por ejemplo, al pulsar desde el globo):
  1. El país del punto se busca en `mundo_paises.geojson` (local).
  2. Se piden sus ADM1 y ADM2 a la ruta existente `/limites/{ISO3}/{nivel}` (geoBoundaries, con caché en servidor y navegador).
  3. Sin red o sin límites publicados, la tarjeta lo explica.
- **Nombre:**
  - La zona resaltada lleva su nombre sobre el mapa (`.etiqueta-zona`).
  - Los ADM1 o ADM2 descargados para la vista también muestran su nombre según el zoom: como máximo 60, solo los que caen en pantalla, sin duplicar los del Huila local. Son marcadores HTML, sin glifos remotos.
- **«Ver zona completa»** (tarjeta): encuadra el polígono entero de la zona para verla con sus vías, límites y nombre.

### Lo que no cambia

La API, las reglas de armonización y la búsqueda (ADR 0013). Los conteos de las zonas del Huila siguen saliendo de `/calendario?area=…`. Las ciudades y las zonas fuera del Huila se cuentan en el navegador con los focos cargados, y la tarjeta lo advierte.

## Alternativas descartadas

- **Teselas vectoriales (OpenFreeMap, Protomaps):** permitirían un estilo de vías propio. Añaden un proveedor nuevo, glifos remotos para los nombres y un estilo que mantener.
- **CARTO Positron:** ya es mínimo, pero es un proveedor nuevo con límite de visitas para uso no comercial.
- **Geocodificación inversa con Nominatim para la ciudad:** sí daría polígonos en todo el mundo. Enviaría cada clic a un servicio externo y comparte el límite de una consulta por segundo de la búsqueda.
- **GIBS `Landsat_Human_Built-up_And_Settlement_Extent`:** es un ráster sin nombres ni polígonos.

## Consecuencias

- **Ciudades a 1:10m:** solo las de huella urbana grande. En el Huila, solo Neiva. Su polígono es aproximado (MODIS 2002) y no coincide con el perímetro urbano oficial. Donde no hay área urbana se resalta el municipio.
- **Sin red:** la base de vías y los límites fuera del Huila no cargan. El resto del visor sigue igual que en el ADR 0013.
- **Pruebas:**
  - `tests/test_interfaz.py`: base mínima en grises y su orden; preajuste Vías; tres niveles de zona (incluido el punto rural sin ciudad); umbral de ciudad documentado; recálculo por zoom y consulta del país; licencia de las ciudades; crédito de OSM en el pie.
  - `tests/test_global.py`: lista de remotos del globo ampliada a OSM.
- **Recorrido en navegador:** `tools/recorrido_capas.mjs` da 15/15. Comprueba:
  - el cambio de nivel al acercarse;
  - el nombre en el mapa;
  - el Tolima resaltado desde zoom 6,5 con límites pedidos a geoBoundaries;
  - la base mínima.

  Capturas: `vias_municipio.png`, `vias_ciudad.png` y `umbral_zoom_11.png`.

## Pendiente

- Perímetros urbanos oficiales (DANE, Marco Geoestadístico Nacional, clase 1 «cabecera municipal») si su licencia permite redistribuirlos; darían todas las cabeceras del Huila.
- Proveedor de teselas propio antes de un despliegue público (R-30).
