# Evaluación de fuentes complementarias (2026-11-14)

**Pregunta:** ¿cuáles de los repositorios propuestos sirven al proyecto y qué otras fuentes mejorarían la experiencia y la presentación de los datos?

**Criterios:**
1. Cubre el Huila.
2. Acceso sin pago, con licencia que permita citar.
3. Aporta algo que FIRMS no da.
4. Esfuerzo compatible con el hackatón.
5. No compromete la demo sin red: toda fuente nueva debe ser una capa opcional.

Todo lo de este documento se comprobó el 2026-11-14 con consultas reales.

## Repositorios propuestos

Ninguno de los cuatro es de NASA: dos son de Meteomatics (empresa privada de meteorología) y dos de Microsoft Planetary Computer.

| repositorio | qué es | estado (GitHub, 2026-11-14) | veredicto |
|---|---|---|---|
| `meteomatics/python-connector-api` | Cliente Python de la API meteorológica de Meteomatics | activo, MIT | **No incorporar ahora.** La API pide usuario y contraseña y su página dice que el precio varía según el uso; no encontré un plan gratuito para la API. En la página consultada no figura un índice de peligro de incendio. Open-Meteo cubre el mismo contexto gratis y sin clave. |
| `meteomatics/R-connector-api` | Cliente R de la misma API | activo, licencia no declarada (NOASSERTION) | **No.** Mismo motivo; además el proyecto está en Python y la licencia es incierta. |
| `microsoft/planetary-computer-apis` | Código **servidor** de la API STAC y del servicio de teselas de Planetary Computer | activo, MIT | **No como dependencia.** No hace falta desplegar ese servidor: basta con **consumir la API pública** (`planetarycomputer.microsoft.com/api/stac/v1`), que funciona sin cuenta y con token SAS anónimo. |
| `microsoft/PlanetaryComputerDataCatalog` | Sitio web del catálogo de datos | **archivado** | **No.** Está archivado y es la interfaz del catálogo, no los datos. |

**Conclusión:** de estos repositorios solo sirve, de forma indirecta, la **API pública de Planetary Computer**, que da acceso a varios datos útiles (ver abajo).

## Datos útiles comprobados

| fuente | qué aporta a la presentación | comprobación (2026-11-14) | licencia y acceso | esfuerzo |
|---|---|---|---|---|
| **NASA GIBS**: imagen de color real MODIS y VIIRS del día | Al elegir un día, ver la imagen satelital (humo, nubes) bajo los focos. Es de NASA. | Teselas WMTS del 2024-09-15 de MODIS Terra y VIIRS NOAA-20: HTTP 200 | NASA, sin clave; requiere red | **Bajo**: una capa de Leaflet opcional |
| **Open-Meteo** (archivo histórico, reanálisis) | Explicar los días inusuales: calor, sequedad, lluvia y viento | Neiva, 10–16 sep 2024: máx. 38,3–40,1 °C, humedad mín. 19–24 %, lluvia 0–0,2 mm | Gratuito y sin clave para uso no comercial; datos CC BY 4.0. Son datos **modelados** (reanálisis), no observaciones | **Bajo**: una consulta JSON por día o por rango |
| **geoBoundaries** (límites de Colombia) | Límite real del Huila en lugar del bbox aproximado (R-06) y agregación por municipio (Neiva y otros) | ADM1 (ODbL 1.0) y ADM2 (CC BY 4.0, 1 122 unidades), descargables | Sin clave | **Bajo a medio**: el polígono es estático y se puede incluir en el repositorio para la demo sin red |
| **MODIS MCD64A1** (área quemada mensual, 500 m) en Planetary Computer | Contrastar focos con superficie realmente quemada: responde a la limitación de que los focos no son incendios confirmados | Septiembre de 2024 sobre el Huila: 1 escena (`h10v08`), con `tilejson` para pintarla como capa | NASA LP DAAC, vía Planetary Computer con token anónimo | **Medio**: la capa por `tilejson` es fácil; cruzarla con los focos requiere procesar el HDF |
| **Esri/IO LULC anual v02** (cobertura del suelo 10 m, 2017–2023) | Clasificar focos por cobertura (cultivo, pasto, bosque): «¿qué se quema?» | Colección activa en Planetary Computer, cobertura global, CC BY 4.0 | Token anónimo | **Medio a alto**: requiere procesar ráster |
| **Sentinel-3 SLSTR FRP** | Un tercer sensor de potencia del fuego | Septiembre de 2024 sobre el Huila: 1 escena | Copernicus, vía Planetary Computer | **Alto** y fuera del alcance del reto (MODIS y VIIRS) |

**No aplican al Huila:** Daymet, gridMET y MTBS (solo cubren EE. UU.). Tampoco ERA5 en Planetary Computer: la búsqueda de septiembre de 2024 no devolvió datos. En su lugar se usa Open-Meteo.

## Recomendación para el hackatón

Por orden de impacto sobre esfuerzo:

1. **Imagen NASA GIBS del día seleccionado:** una capa opcional en el mapa con selector MODIS o VIIRS.
2. **Contexto meteorológico de Open-Meteo:** temperatura, humedad y lluvia en el resumen del periodo crítico y en el detalle del día, etiquetado como «reanálisis, no observación».
3. **Límite del Huila con geoBoundaries:** se versiona como GeoJSON para que funcione sin red y resuelve R-06.

Para después del hackatón: MCD64A1 (área quemada) y LULC (cobertura), que requieren procesar ráster.

Cada fuente nueva debe registrarse en `docs/cita.md` con su crédito y en un ADR propio, y no puede romper la demo sin red.
