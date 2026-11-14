# Cita y reconocimiento

Textos copiados literalmente el 2026-11-13 de la página oficial de FIRMS en Earthdata:
<https://www.earthdata.nasa.gov/data/tools/firms>. Este bloque debe aparecer en la app
(mapa), en cada exportación y en el README (D-10).

## Cita obligatoria (FIRMS, LANCE y ESDIS)

> We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource
> Management System (FIRMS) (https://www.earthdata.nasa.gov/data/tools/firms), part of NASA's
> Land, Atmosphere Near real-time Capability for Earth observations (LANCE) and NASA's Earth
> Science Data and Information System (ESDIS).

Fuente: página de FIRMS en Earthdata (consultada el 2026-11-13). La página enlaza «FIRMS» y
«LANCE» a sus páginas; las URL de LANCE y ESDIS se añadirán al integrar la cita en la interfaz.

Variante corta para pies de imagen, según la FAQ de FIRMS
(<https://www.earthdata.nasa.gov/data/tools/firms/faq>): «NASA FIRMS», con enlace directo a
la imagen cuando sea posible.

## Aviso «as is»

> The information presented through LANCE, GIBS, Worldview, and FIRMS are provided "as is"
> and users bear all responsibility and liability for their use of data.

Fuente: página de FIRMS en Earthdata (consultada el 2026-11-13). Traducción informativa: la
información se entrega «tal cual» y los usuarios asumen toda la responsabilidad por su uso.

## DOI por producto

| producto | calidad | DOI |
|---|---|---|
| MCD14DL (MODIS C6.1) | NRT | 10.5067/FIRMS/MODIS/MCD14DL.NRT.0061 |
| VNP14IMGTDL_NRT (Suomi NPP, solo histórico) | NRT | 10.5067/FIRMS/VIIRS/VNP14IMGT_NRT.002 |
| VJ114IMGTDL_NRT (NOAA-20) | NRT | 10.5067/FIRMS/VIIRS/VJ114IMGT_NRT.002 |
| VJ214IMGTDL_NRT (NOAA-21) | NRT | 10.5067/FIRMS/VIIRS/VJ214IMGT_NRT.002 |
| MCD14ML (MODIS C6.1) | estándar | 10.5067/FIRMS/MODIS/MCD14ML (resuelve a la página de FIRMS; versión por confirmar) |
| VIIRS 375 m estándar (SNPP, NOAA-20) | estándar | por confirmar |

Los cuatro DOI NRT se copiaron el 2026-11-13 de la página de cada producto en
<https://modaps.modaps.eosdis.nasa.gov/services/about/products/> (`c61-nrt/MCD14DL-NRT.html`,
`viirs-land-c2-nrt/vnp14imgtdl_nrt.html`, `vj114imgtdl_nrt.html` y `vj214imgtdl_nrt.html`).
Los cuatro resuelven en doi.org al catálogo de Earthdata. El DOI de los productos VIIRS
estándar sigue pendiente (R-24).

## Estudios de validación citados por FIRMS

La FAQ de FIRMS cita estos trabajos. Las referencias completas se transcriben aquí y deben
cotejarse con la FAQ antes de la entrega.

- Justice, C. O., et al. (2002). The MODIS fire products. *Remote Sensing of Environment*, 83, 244–262.
- Morisette, J. T., Giglio, L., Csiszar, I., & Justice, C. O. (2005). Validation of the MODIS active fire product over Southern Africa with ASTER data. *International Journal of Remote Sensing*, 26(19), 4239–4264.
- Morisette, J. T., et al. (2005). Validation of MODIS active fire detection products derived from two algorithms. *Earth Interactions*, 9(9), 1–25.
- Csiszar, I., Morisette, J. T., & Giglio, L. (2006). Validation of active fire detection from moderate-resolution satellite sensors: the MODIS example in Northern Eurasia. *IEEE Transactions on Geoscience and Remote Sensing*, 44(7), 1757–1764.
- Csiszar, I., et al. (2014). Active fires from the Suomi NPP Visible Infrared Imaging Radiometer Suite: product status and first evaluation results. *Journal of Geophysical Research: Atmospheres*, 119, 803–816.

También es la referencia del algoritmo VIIRS de 375 m, aunque la FAQ no lo cita como estudio
de validación:

- Schroeder, W., Oliva, P., Giglio, L., & Csiszar, I. (2014). The New VIIRS 375 m active fire detection data product: Algorithm description and initial assessment. *Remote Sensing of Environment*, 143, 85–96.

## Fuentes complementarias de la interfaz (H7, ADR 0010)

**NASA GIBS**: imagen de color real del día. Reconocimiento solicitado en la documentación de la API de GIBS (<https://nasa-gibs.github.io/gibs-api-docs/>, consultada el 2026-11-14):

> We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse
> Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).

**Open-Meteo**: clima histórico. Los datos de la API se publican con licencia CC BY 4.0 (<https://open-meteo.com/en/terms>). La API histórica se basa en los reanálisis ERA5 y ERA5-Land y en el modelo IFS de ECMWF (<https://open-meteo.com/en/docs/historical-weather-api>). En la interfaz figura «Datos meteorológicos: Open-Meteo.com (CC BY 4.0)». El texto exacto de crédito que pide Open-Meteo y el crédito adicional de Copernicus/ECMWF siguen **por confirmar**: su página de licencia redirigía el 2026-11-14 y no se pudo leer (R-39).

**geoBoundaries**: límites municipales del Huila (ADM2, fuente DANE 2020, CC BY 4.0). El ADM1 (OpenStreetMap, ODbL 1.0) solo se usa para seleccionar los municipios y no se redistribuye.

- Runfola, D., et al. (2020). geoBoundaries: A global database of political administrative boundaries. *PLoS ONE*, 15(4), e0231866.

## Cómo citar este proyecto

Harmonized Heat Neiva (NASA Space Apps 2026, reto «Harmonization of MODIS and VIIRS Hot
Spots»). Repositorio: <https://github.com/DavidCr0007/NASA_trasas_de_Fuego>. Los datos de
focos de calor provienen de NASA FIRMS; incluya la cita obligatoria de arriba.

## Nota

Herramienta de armonización hecha para un concurso. Los focos son detecciones térmicas, no
incendios confirmados. Los datos se entregan «as is», según el aviso oficial citado arriba, y
no deben usarse como única base para decisiones críticas.
