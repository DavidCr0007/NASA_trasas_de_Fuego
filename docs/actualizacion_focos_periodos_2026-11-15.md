# Actualización de focos por día y periodo

Fecha: 2026-11-15.

## Causas comprobadas

El despliegue público contenía solo el **14 de noviembre de 2026**. Al consultar `/global` con `dias=1`, `2` y `7`, los tres resultados devolvían **56.084 detecciones**, con la misma cobertura de un día. Un filtro no puede recuperar observaciones que no se descargaron.

Además, el calendario, el rango y el selector mundial mantenían estados temporales independientes. Cambiar el selector podía dejar activo el día anterior en el detalle regional. Una tercera causa permitía que una respuesta antigua volviera a pintar el mapa: `iniciarCarga()` comparaba el contador mutable del mismo objeto consigo mismo, en lugar de conservar el número de la solicitud que había iniciado.

## Cambios

- La construcción FIRMS descarga **7 días UTC completos por defecto**. `FIRMS_NRT_DIAS` admite de 1 a 10; la descarga se divide en ventanas de hasta 5 días, respetando la [API de área de FIRMS](https://firms.modaps.eosdis.nasa.gov/api/area/). Una semana requiere dos ventanas por producto, seis peticiones para los tres productos. Se comprueba que lleguen todas las ventanas.
- El selector se llama **Periodo de los focos**. El calendario y el rango aparecen como **Fechas seleccionadas** en ese selector y aplican las mismas fechas al globo y al detalle. Elegir 1, 2 o 7 días sustituye el día y el rango anteriores.
- `/global` acepta `desde` y `hasta`, además del periodo reciente. Las fechas sin detecciones devuelven cero y vacían los puntos; no reutilizan el último día disponible.
- El cambio de periodo cancela las consultas anteriores del área y del visor. Se conservan el número de cada solicitud y el mismo mapa; una respuesta tardía no puede restituir los focos anteriores. Los datos anteriores se retiran mientras se carga el nuevo periodo, con carga localizada en el mapa y el resumen.
- La interfaz muestra la cobertura real y desactiva periodos mayores que la extensión del archivo. Si solo existe un día, no presenta 2 o 7 como opciones disponibles. No se interpreta como ausencia de incendios una fecha sin observaciones del archivo.
- La demo estática filtra y agrega las fechas seleccionadas desde sus detecciones exportadas, en vez de devolver siempre la última semana precalculada. Una prueba compara sus resultados con la API.
- Los CSV de detecciones, la fecha mostrada y el enlace de consulta FIRMS siguen el periodo seleccionado. Las observaciones y sus valores científicos no se modifican.

## Validación con datos reales

Se reconstruyó localmente el conjunto FIRMS y se comprobaron estos resultados:

| Selección | Fechas UTC | Detecciones mundiales |
|---|---|---:|
| 1 día | 14 nov 2026 | 55.683 |
| 2 días | 13–14 nov 2026 | 114.235 |
| 7 días | 8–14 nov 2026 | 470.686 |

El número del resumen coincide con la suma de detecciones representadas por los círculos del globo. En Huila, seleccionar el **10 de noviembre** mostró **19 detecciones**, y el **9 de noviembre**, **7**. Se comprobó la fecha de cada registro y se retrasó deliberadamente la respuesta del primer día para verificar que no reemplazara al segundo. También se verificaron el rango de fechas, una fecha sin datos y una simulación del archivo de un solo día.

Estas cifras corresponden a la reconstrucción local de esta validación. NRT es preliminar y puede corregirse; no se promete que futuras descargas produzcan cantidades idénticas.

- **575 pruebas correctas**, incluidas ingesta semanal en ventanas válidas, fechas explícitas de la API y equivalencia de la demo estática.
- **14/14 comprobaciones de periodos en Chrome** y **17/17 de idiomas**, manteniendo el mismo mapa.
- **18/18 criterios** de auditoría del conjunto real generado.
- Escaneo de secretos sin hallazgos. Se conserva una advertencia de deprecación de Starlette/HTTPX, ajena a este cambio.

Evidencia: [cantidades verificadas](capturas/periodos_focos_20261115/resultados.json), [respuesta tardía descartada](capturas/periodos_focos_20261115/carrera.json), [semana](capturas/periodos_focos_20261115/01_semana.png), [fecha sin datos](capturas/periodos_focos_20261115/02_fecha_sin_datos.png), [archivo de un día](capturas/periodos_focos_20261115/03_cobertura_insuficiente.png), [auditoría del conjunto](evidencias/periodos_focos_20261115/conjunto_real.json).

## Activarlo en Vercel

En **Project → Settings → Environment Variables → Production**, establecer **`FIRMS_NRT_DIAS=7`**. Si ya existe con valor `1`, actualizarlo: ese valor explícito prevalece sobre el nuevo valor predeterminado. Mantener `HHN_MODO_DATOS=firms` y las dos variables privadas de la clave.

Publicar el código y ejecutar **Redeploy** para construir el nuevo archivo. La construcción sigue siendo una instantánea: cambiar el selector consulta el archivo disponible y no realiza una descarga FIRMS por cada clic. Un nuevo despliegue actualiza la instantánea. Esta ejecución verificó la construcción local y no cambió variables remotas ni publicó un despliegue.

Para repetir con una API local que sirva el conjunto real:

```powershell
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/periodos_focos "C:/Program Files/Google/Chrome/Application/chrome.exe" periodos
```
