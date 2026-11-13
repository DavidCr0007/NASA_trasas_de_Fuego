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
| MCD14DL (MODIS C6.1) | NRT | por confirmar |
| MCD14ML (MODIS C6.1) | estándar | por confirmar |
| VNP14IMGTDL_NRT (Suomi NPP, solo histórico) | NRT | por confirmar |
| VJ114IMGTDL_NRT (NOAA-20) | NRT | por confirmar |
| VJ214IMGTDL_NRT (NOAA-21) | NRT | por confirmar |
| VIIRS 375 m estándar (SNPP, NOAA-20, NOAA-21) | estándar | por confirmar |

Los DOI no figuraban en las páginas consultadas. Hay que copiarlos de la página de cada
producto (riesgo R-24).

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

## Cómo citar este proyecto

Harmonized Heat Neiva (NASA Space Apps 2026, reto «Harmonization of MODIS and VIIRS Hot
Spots»). Repositorio: <https://github.com/DavidCr0007/NASA_trasas_de_Fuego>. Los datos de
focos de calor provienen de NASA FIRMS; incluya la cita obligatoria de arriba.

## Nota

Herramienta de armonización hecha para un concurso. Los focos son detecciones térmicas, no
incendios confirmados. Los datos se entregan «as is», según el aviso oficial citado arriba, y
no deben usarse como única base para decisiones críticas.
