"""Constantes del esquema FIRMS. Solo datos, sin lógica.

Verificado el 2026-11-13 contra:
  [A] Tabla oficial de atributos MODIS/VIIRS (URL_FUENTES["atributos_firms"]).
  [C] CSV reales públicos 24 h South America, descargados 2026-11-13 (calidad NRT);
      recortes en tests/fixtures/firms_real/ (ver ORIGEN.md).
  [P] Documentación de la API area (URL_FUENTES["api_area"]).
Lo que no figura en esas fuentes sigue marcado "por confirmar". Ver docs/esquema_firms.md.
"""

ESTADO_GLOBAL = "verificado parcialmente (2026-11-13)"
URL_FUENTES = {
    "atributos_firms": "https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs",
    "faq_firms": "https://www.earthdata.nasa.gov/data/tools/firms/faq",
    "api_area": "https://firms.modaps.eosdis.nasa.gov/api/area/",
    "api_data_availability": "https://firms.modaps.eosdis.nasa.gov/api/data_availability/",
    "descargas_24h": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/",
}

# Nombre de fuente API -> metadatos. Nombres confirmados en [P].
# Colección: MODIS 6.1 ([A] y version "6.1NRT" en [C]); VIIRS 2 (version "2.0NRT" y
# nombre de archivo "VIIRS_C2" en [C]). La colección de los productos SP de VIIRS
# (archivo estándar) queda por confirmar ([A] aún menciona "1.0").
FUENTES_API = {
    "MODIS_NRT": {"sensor": "MODIS", "satelite": ("Terra", "Aqua"), "calidad": "NRT",
                  "coleccion": "6.1", "confirmado": True, "fuente": "P,A,C"},
    "MODIS_SP": {"sensor": "MODIS", "satelite": ("Terra", "Aqua"), "calidad": "estandar",
                 "coleccion": "6.1", "confirmado": True, "fuente": "P,A"},
    # Suomi NPP ya no entrega datos nuevos ([A]); solo histórico.
    "VIIRS_SNPP_NRT": {"sensor": "VIIRS", "satelite": ("Suomi NPP",), "calidad": "NRT",
                       "coleccion": "2", "confirmado": True, "fuente": "P,C",
                       "solo_historico": True},
    "VIIRS_SNPP_SP": {"sensor": "VIIRS", "satelite": ("Suomi NPP",), "calidad": "estandar",
                      "coleccion": "por confirmar", "confirmado": True, "fuente": "P",
                      "solo_historico": True},
    "VIIRS_NOAA20_NRT": {"sensor": "VIIRS", "satelite": ("NOAA-20",), "calidad": "NRT",
                         "coleccion": "2", "confirmado": True, "fuente": "P,C"},
    "VIIRS_NOAA20_SP": {"sensor": "VIIRS", "satelite": ("NOAA-20",), "calidad": "estandar",
                        "coleccion": "por confirmar", "confirmado": True, "fuente": "P"},
    "VIIRS_NOAA21_NRT": {"sensor": "VIIRS", "satelite": ("NOAA-21",), "calidad": "NRT",
                         "coleccion": "2", "confirmado": True, "fuente": "P,C"},
    "VIIRS_NOAA21_SP": {"sensor": "VIIRS", "satelite": ("NOAA-21",), "calidad": "estandar",
                        "coleccion": "por confirmar", "confirmado": True, "fuente": "P"},
}

# Cabeceras exactas de los CSV 24 h [C]. No existe columna "instrument".
# La API area usa, según [P], el mismo formato CSV; su cabecera exacta queda por
# confirmar con la primera descarga con MAP_KEY (el lector tolera columnas extra).
_COLS_VIIRS = ("latitude", "longitude", "bright_ti4", "scan", "track", "acq_date",
               "acq_time", "satellite", "confidence", "version",
               "bright_ti5", "frp", "daynight")
_COLS_MODIS = ("latitude", "longitude", "brightness", "scan", "track", "acq_date",
               "acq_time", "satellite", "confidence", "version",
               "bright_t31", "frp", "daynight")
COLUMNAS_REQUERIDAS = {
    ("MODIS", "api_nrt"): _COLS_MODIS,
    ("MODIS", "api_sp"): _COLS_MODIS,
    ("MODIS", "24h"): _COLS_MODIS,
    ("VIIRS", "api_nrt"): _COLS_VIIRS,
    ("VIIRS", "api_sp"): _COLS_VIIRS,
    ("VIIRS", "24h"): _COLS_VIIRS,
}
COLUMNAS_ESTADO = {
    "24h": "confirmado [C]",
    "api_nrt": "por confirmar (se asume igual a 24h)",
    "api_sp": "por confirmar (MODIS SP puede traer 'type' [A]; se tolera como extra)",
}

# Códigos del campo satellite. Confirmados en [A]; N20, N21, T y A observados en [C].
# Los códigos del prototipo "1"/"2" y los nombres "Terra"/"Aqua" quedan refutados.
SATELITES = {
    "N": {"sensor": "VIIRS", "nombre": "Suomi NPP", "confirmado": True, "fuente": "A"},
    "N20": {"sensor": "VIIRS", "nombre": "NOAA-20", "confirmado": True, "fuente": "A,C"},
    "N21": {"sensor": "VIIRS", "nombre": "NOAA-21", "confirmado": True, "fuente": "A,C"},
    "T": {"sensor": "MODIS", "nombre": "Terra", "confirmado": True, "fuente": "A,C"},
    "A": {"sensor": "MODIS", "nombre": "Aqua", "confirmado": True, "fuente": "A,C"},
}

# Confianza VIIRS: "low", "nominal", "high" ([A], FAQ y [C]).
# "l","n","h" (prototipo) no aparece en ninguna fuente consultada; se acepta solo como
# variante por confirmar de la API area, para no perder filas si la API la usa (R-23).
CONFIANZA_VIIRS_VALORES = ("low", "nominal", "high", "l", "n", "h")
CONFIANZA_VIIRS_CONFIRMADOS = ("low", "nominal", "high")
CONFIANZA_VIIRS_ESTADO = "confirmado (low/nominal/high); l/n/h por confirmar en API"
CONFIANZA_MODIS_RANGO = (0, 100)  # [A] y FAQ: 0 a 100 %
CONFIANZA_MODIS_ESTADO = "confirmado"
# [A] y FAQ dicen que el porcentaje se agrupa en baja/nominal/alta pero NO publican
# los cortes en las páginas consultadas: los umbrales 30/80 siguen PROVISIONALES (ADR 0002).
CLASES_CONFIANZA_FIRMS_DOC = None  # por confirmar

# version: [A] da 6.1URT, 6.1RT, 6.1NRT (MODIS NRT) y 6.1 (estándar); [C] muestra
# 6.1NRT y 2.0NRT. URT y RT son productos aún más preliminares: se tratan como NRT.
PATRONES_VERSION = {
    "NRT": r"^\d+(\.\d+)*(NRT|URT|RT)$",
    "estandar": r"^\d+(\.\d+)*$",
}
PATRONES_VERSION_ESTADO = "confirmado"

# acq_time: 4 dígitos HHMM UTC con ceros a la izquierda en [C] (p. ej. "0017").
ACQ_TIME_FORMATO = "HHMM UTC, 4 dígitos (confirmado [C])"

API_AREA_URL_PLANTILLA = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/<FUENTE>/<W,S,E,N>/<DAY_RANGE>[/<YYYY-MM-DD>]"
)  # confirmado [P]; con fecha devuelve [fecha, fecha + DAY_RANGE - 1]
API_DAY_RANGE_MAX = 5  # confirmado [P]: 1 a 5
API_LIMITE_TRANSACCIONES = (5000, 600)  # confirmado [P]: 5000 transacciones por 10 min

# Huila, formato (W, S, E, N). Aproximado, NO verificado con IGAC/DANE/geoBoundaries.
HUILA_BBOX = (-76.7, 1.4, -74.3, 3.9)
HUILA_BBOX_CONFIRMADO = False
