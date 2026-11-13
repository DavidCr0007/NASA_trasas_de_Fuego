# Capturas de respaldo

Tomadas el 2026-11-13 con `make api`, reglas `armonizacion-0.3.1`, en una ventana de 1280×900 (exportadas a 800 px de ancho).
Los datos son **sintéticos**: muestra histórica 2020–2026 con una anomalía inyectada en agosto de 2026. No son observaciones reales del Huila.

| archivo | qué muestra |
|---|---|
| `01_vista_general.jpg` | Área Huila, año 2026: mapa de focos, 28 días inusuales, temporada con meses pico (agosto, julio, septiembre), periodos críticos (el principal va del 2026-08-10 al 2026-08-15) e insignia PRELIMINAR (NRT). |
| `02_calendario.jpg` | Calendario de actividad 2026 con días inusuales (borde violeta), días NRT (punto blanco), incertidumbre y cita de FIRMS en el pie. |
| `03_dia_seleccionado_huella.jpg` | Día 2026-08-12 seleccionado (24 focos). Con zoom se ve la huella nominal de MODIS (1 km) frente a la de VIIRS (375 m), y la ventana de un foco Terra marcado como preliminar. |
| `04_base_insuficiente.jpg` | Muestra de 3 días (`data/processed/demo`): la línea base responde «Base insuficiente» (1 año frente a los 5 requeridos) y no marca días inusuales. |

Para regenerarlas: `make api` y abrir http://127.0.0.1:8000. Para la cuarta: `uv run python -m api --datos data/processed/demo --puerto 8001`.
