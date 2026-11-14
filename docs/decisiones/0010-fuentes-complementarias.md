# ADR 0010: Fuentes complementarias para la presentación (H7)

## Estado

ACEPTADA (2026-11-14). La evaluación completa está en `docs/fuentes_complementarias.md`.

## Contexto

Para que el calendario sea más entendible hacía falta contexto: dónde están los límites reales del departamento, cómo se veía el cielo ese día y qué tiempo hacía. Se evaluaron cuatro repositorios propuestos (Meteomatics y Microsoft Planetary Computer) y varias alternativas. Las condiciones eran tres: la demo sin red no puede romperse, no puede haber credenciales en el repositorio y las licencias deben permitir citar los datos.

## Decisión

| fuente | uso | red | licencia y crédito |
|---|---|---|---|
| geoBoundaries ADM2 (DANE) | Límites de los 37 municipios del Huila en el mapa y selector por municipio | **no** (GeoJSON versionado en `src/ui/static/datos/`) | CC BY 4.0; Runfola et al. (2020) |
| geoBoundaries ADM1 (OpenStreetMap) | Solo para **seleccionar** qué municipios son del Huila; no se redistribuye | no (crudo fuera de git) | ODbL 1.0 |
| NASA GIBS | Imagen de color real del día elegido (VIIRS NOAA-20 o MODIS Terra) | sí, opcional | Reconocimiento de GIBS (ver `docs/cita.md`) |
| Open-Meteo, archivo histórico | Clima del día elegido (±3 días) o del periodo crítico principal | sí, opcional | CC BY 4.0; reanálisis ERA5 y ERA5-Land, e IFS de ECMWF |

Restricciones de diseño:

- **La imagen va en su propio panel de Leaflet**, fuera de `.leaflet-tile-pane`, para que el filtro del tema oscuro no la invierta.
- **El área y los límites se dibujan en SVG.** Los focos van en Canvas (auditoría UI/UX), pero Canvas ignora las clases CSS y estas figuras necesitan los colores del tema.
- **El clima se rotula «reanálisis, no observación»** y sus fallos solo muestran un aviso.
- **Las consultas de clima solo envían el centro del área.** No incluyen datos personales.

## Descartadas

- **Meteomatics (Python y R):** la API pide credenciales y el precio depende del uso; Open-Meteo cubre la misma necesidad gratis.
- **`planetary-computer-apis`:** es el código del servidor y no hace falta desplegarlo.
- **`PlanetaryComputerDataCatalog`:** está archivado.
- **Para después del hackatón:** MCD64A1 (área quemada) y la cobertura del suelo LULC, por el procesamiento ráster que exigen.

## Consecuencias

- R-06 queda resuelto. El recuadro aproximado del Huila (−76,7; 1,4; −74,3; 3,9) **contiene** el límite oficial (−76,62; 1,55; −74,41; 3,84) con un margen de 0,05 a 0,15°. Ese margen incluye franjas de los departamentos vecinos (R-40).
- Dos capas dependen de servicios externos sin acuerdo de servicio. Open-Meteo gratuito es solo para uso no comercial (R-39).
- La imagen GIBS puede salir negra en franjas donde el satélite no pasó ese día. Ejemplo comprobado: MODIS Terra del 2024-09-15 sobre el Huila es un 49 % negra, frente al 0 % de VIIRS NOAA-20.
