"""Constantes del esquema FIRMS. Solo datos, sin lógica.

REGLA: nada aquí está confirmado contra fuente oficial en esta sesión (el
trabajador no tuvo acceso a red ni a shell). Todo valor lleva confirmado=False
y estado "por confirmar". Los valores marcados "hipotesis_recordada" provienen
de memoria del redactor, NO de una fuente consultada: verificar antes de usar.
Ver docs/esquema_firms.md.
"""

ESTADO_GLOBAL = "por confirmar"
URL_FUENTES = {
    "atributos_firms": "https://www.earthdata.nasa.gov/data/tools/firms",  # por confirmar URL exacta
    "api_area": "https://firms.modaps.eosdis.nasa.gov/api/area/",
    "api_data_availability": "https://firms.modaps.eosdis.nasa.gov/api/data_availability/",  # por confirmar
    "descargas_24h": "https://firms.modaps.eosdis.nasa.gov/active_fire/",
}

# Nombre de fuente API -> metadatos. Nombres según recuerdo; por confirmar.
FUENTES_API = {
    "MODIS_NRT": {"sensor": "MODIS", "satelite": ("Terra", "Aqua"), "calidad": "NRT",
                  "coleccion": "6.1", "confirmado": False},
    "MODIS_SP": {"sensor": "MODIS", "satelite": ("Terra", "Aqua"), "calidad": "estandar",
                 "coleccion": "6.1", "confirmado": False},
    "VIIRS_SNPP_NRT": {"sensor": "VIIRS", "satelite": ("Suomi NPP",), "calidad": "NRT",
                       "coleccion": "por confirmar", "confirmado": False},
    "VIIRS_SNPP_SP": {"sensor": "VIIRS", "satelite": ("Suomi NPP",), "calidad": "estandar",
                      "coleccion": "por confirmar", "confirmado": False},
    "VIIRS_NOAA20_NRT": {"sensor": "VIIRS", "satelite": ("NOAA-20",), "calidad": "NRT",
                         "coleccion": "por confirmar", "confirmado": False},
    "VIIRS_NOAA20_SP": {"sensor": "VIIRS", "satelite": ("NOAA-20",), "calidad": "estandar",
                        "coleccion": "por confirmar", "confirmado": False},
    "VIIRS_NOAA21_NRT": {"sensor": "VIIRS", "satelite": ("NOAA-21",), "calidad": "NRT",
                         "coleccion": "por confirmar", "confirmado": False},
}

# Columnas hipótesis (orden recordado, NO verificado con CSV real). Por confirmar.
_COLS_VIIRS = ("latitude", "longitude", "bright_ti4", "scan", "track", "acq_date",
               "acq_time", "satellite", "instrument", "confidence", "version",
               "bright_ti5", "frp", "daynight")
_COLS_MODIS = ("latitude", "longitude", "brightness", "scan", "track", "acq_date",
               "acq_time", "satellite", "instrument", "confidence", "version",
               "bright_t31", "frp", "daynight")
COLUMNAS_REQUERIDAS = {
    ("MODIS", "api_nrt"): _COLS_MODIS,
    ("MODIS", "api_sp"): _COLS_MODIS,
    ("MODIS", "24h"): _COLS_MODIS,
    ("VIIRS", "api_nrt"): _COLS_VIIRS,
    ("VIIRS", "api_sp"): _COLS_VIIRS,
    ("VIIRS", "24h"): _COLS_VIIRS,
}
COLUMNAS_ESTADO = "por confirmar"

# Códigos del prototipo: ninguno confirmado. Hipótesis alterna recordada (no verificada):
# el campo satellite de VIIRS usaría "N", "N20", "N21"; el de MODIS "Terra"/"Aqua" o "T"/"A".
SATELITES = {
    "N": {"sensor": "VIIRS", "nombre": "Suomi NPP", "confirmado": False,
          "nota": "código del prototipo; por confirmar con CSV real"},
    "1": {"sensor": "VIIRS", "nombre": "NOAA-20", "confirmado": False,
          "nota": "código del prototipo; sospechoso (hipótesis alterna: 'N20'); por confirmar"},
    "2": {"sensor": "VIIRS", "nombre": "NOAA-21", "confirmado": False,
          "nota": "código del prototipo; sospechoso (hipótesis alterna: 'N21'); por confirmar"},
    "N20": {"sensor": "VIIRS", "nombre": "NOAA-20", "confirmado": False,
            "nota": "hipotesis_recordada; por confirmar"},
    "N21": {"sensor": "VIIRS", "nombre": "NOAA-21", "confirmado": False,
            "nota": "hipotesis_recordada; por confirmar"},
    "T": {"sensor": "MODIS", "nombre": "Terra", "confirmado": False,
          "nota": "código del prototipo; por confirmar"},
    "A": {"sensor": "MODIS", "nombre": "Aqua", "confirmado": False,
          "nota": "código del prototipo; por confirmar"},
    "Terra": {"sensor": "MODIS", "nombre": "Terra", "confirmado": False,
              "nota": "hipotesis_recordada; por confirmar"},
    "Aqua": {"sensor": "MODIS", "nombre": "Aqua", "confirmado": False,
             "nota": "hipotesis_recordada; por confirmar"},
}

CONFIANZA_VIIRS_VALORES = ("l", "n", "h")  # por confirmar (prototipo + recuerdo)
CONFIANZA_VIIRS_ESTADO = "por confirmar"
CONFIANZA_MODIS_RANGO = (0, 100)  # por confirmar
CONFIANZA_MODIS_ESTADO = "por confirmar"
# Clases que la documentación FIRMS daría para MODIS (low/nominal/high con cortes
# propios): no copiadas porque no se verificó la fuente.
CLASES_CONFIANZA_FIRMS_DOC = None  # por confirmar

# Patrones de version (NRT vs estándar). Hipótesis: sufijo "NRT" => casi tiempo real.
PATRONES_VERSION = {
    "NRT": r".*NRT$",          # por confirmar
    "estandar": r"^\d+(\.\d+)*$",  # por confirmar
}
PATRONES_VERSION_ESTADO = "por confirmar"

API_AREA_URL_PLANTILLA = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/<FUENTE>/<W,S,E,N>/<DAY_RANGE>[/<YYYY-MM-DD>]"
)  # por confirmar
API_DAY_RANGE_MAX = None  # por confirmar (recuerdo no verificado: 5)
API_LIMITE_TRANSACCIONES = None  # por confirmar (recuerdo no verificado: 5000 por 10 min)

# Huila, formato (W, S, E, N). Aproximado, NO verificado con IGAC/DANE/geoBoundaries.
HUILA_BBOX = (-76.7, 1.4, -74.3, 3.9)
HUILA_BBOX_CONFIRMADO = False
