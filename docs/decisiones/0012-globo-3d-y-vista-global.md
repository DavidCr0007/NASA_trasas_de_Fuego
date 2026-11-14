# ADR 0012: Vista global con globo 3D (MapLibre) y focos NRT de todo el mundo

## Estado

ACEPTADA (2026-11-14). Complementa el ADR 0008 (Leaflet + Canvas, que sigue siendo el mapa regional) y amplía el ADR 0009 (con la MAP_KEY ya validada, B-01 queda resuelto para la ruta NRT).

## Contexto

- La `FIRMS_MAP_KEY` quedó validada el 2026-11-14: `mapkey_status` informa 5 000 transacciones cada 10 minutos. La API área acepta el recuadro mundial `-180,-90,180,90`.
- Se pidió confirmar que el sistema funciona **fuera del Huila**, a escala global, y que el mapa sea la pieza central: al alejarse hasta la vista de país debe aparecer un **globo terráqueo 3D**, y al acercarse, el detalle de cada foco.
- Restricciones vigentes: sin paso de compilación, sin CDN, la demo funciona sin red, citas D-10 visibles y contraste AA.

## Decisión

1. **Dos motores en la misma escena, con histéresis.**
   - **Mapa regional (Leaflet 1.9.4):** cada foco, la rejilla de densidad, el área y los municipios. Aplica desde el zoom 6 hacia adentro.
   - **Globo 3D (MapLibre GL JS 5.24.0, proyección `globe`):** la vista mundial y de país.
   - **Cambio de vista:** se entra al globo al **alejarse** hasta el zoom Leaflet ≤ 5 (vista de país). Se vuelve al mapa regional al **acercarse** hasta el zoom MapLibre ≥ 5,2 (≈ Leaflet 6,2), en el mismo punto.
   - El cambio solo ocurre por zoom del usuario. Los encuadres programáticos (elegir un área, volar a un país) no lo disparan. También hay un botón «Ver el globo 3D» y el enlace directo `…/ui/#globo`.
2. **MapLibre incluido en `vendor/maplibre/`**, versión 5.24.0, obtenida con `npm pack`. Integridad del paquete: `sha512-ALyFxgtd5R+65UqZ/++lOqwWcC0SNho9c27fYSyLmG7AfnAul2o46F05aDJGPbFU57wos9dgcIySHs0Xe6ia3A==`. Licencia BSD-3 en `vendor/maplibre/LICENSE`. No hay plugins.
3. **Fondo del globo: NASA GIBS, opcional.** Usa Blue Marble (relieve sombreado y batimetría) en el tema claro y Black Marble (VIIRS, luces nocturnas) en el oscuro. Sin red, se ven los países de **Natural Earth 1:110m** (dominio público), servidos localmente. Ese archivo, de 181 kB, se genera con `tools/preparar_mundo.py` desde el crudo en `data/raw/natural_earth/20261114/`.
4. **Endpoint `/global?dias=1..31&res=0.25|0.5|1`.** Agrega las detecciones, ya sin duplicados, en celdas de `res` grados. Por celda devuelve: n, FRP máx./suma, n de confianza alta, n VIIRS, último paso y país. También devuelve el ranking de países y la serie diaria. Tarda menos de 0,5 s con 456 000 detecciones.
   - Puede leer un conjunto aparte con `--datos-global`, por ejemplo el NRT global reciente, mientras `--datos` sigue siendo la historia del Huila.
   - El país se asigna por punto en polígono en el centro de masa de la celda. A 1:110m, un foco en una costa o en una isla pequeña puede quedar «fuera de país»; no se adivina.
5. **Descarga global con su propio manifiesto**: `firms_download --manifest data/raw/global/manifest.jsonl`. Así el pipeline global no mezcla los crudos del Huila.
6. **Simbología común en el globo y en el mapa regional.**
   - Clases fijas de FRP: < 5, 5–20, 20–100, 100–500 y ≥ 500 MW. Usan los tokens `--f1…--f5`.
   - Mapa regional: tamaño y color = FRP; opacidad = confianza; forma = sensor (círculo MODIS, rombo VIIRS); borde punteado = preliminar (NRT); la huella del píxel aparece desde el zoom 11.
   - Globo: color = FRP máximo de la celda; tamaño = √n.
7. **Métrica armonizada 1.1.0.** Si el conjunto no tiene era de Suomi NPP (por ejemplo, solo NRT reciente), no hay con qué calibrar. Entonces el día vale las celdas de **todas** las constelaciones, con el método «sin calibrar». Antes se contaba solo MODIS con k = 1, y los días con focos solo de VIIRS valían 0.

## Consecuencias

- **Mapa como protagonista.** Ocupa el ancho completo y ~73 % del alto de la ventana a 1440 × 900. El resumen, la leyenda numérica y el panel mundial flotan sobre él. En móvil, los paneles pasan debajo del mapa.
- **Funcionamiento fuera del Huila.** Desde el globo, acercarse a cualquier punto consulta esa zona («Zona explorada en el globo»). Para ver focos individuales fuera del Huila, el conjunto principal debe cubrir esa zona; por ejemplo, `make api-global` sirve el NRT global como conjunto principal.
- **Requiere WebGL.** Sin WebGL, el botón informa del problema y el mapa regional sigue funcionando.
- **Prueba de uso de punta a punta.** `tools/prueba_navegador.mjs` usa Chrome sin interfaz gráfica, sin dependencias. Recorre el mapa regional → el globo → un país → acercar con la rueda → la zona explorada → un día → el tema claro → el móvil. Falla si hay errores en la consola.

## Pendiente

- Combinar en un solo conjunto la historia del Huila 2001–2025 y el NRT global: hoy son dos directorios.
- Actualizar el NRT global de forma programada; la API lo sirve tal como esté en disco.
- Rehacer las capturas de `docs/capturas/` con la nueva interfaz (R-35).
