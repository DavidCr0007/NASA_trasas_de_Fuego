# Clave cifrada, datos FIRMS reales e interfaz en tres idiomas

15 de noviembre de 2026.

## Resultado

La clave local se cifró con Fernet, el formato de cifrado autenticado de `cryptography`. El archivo `.env` conserva `FIRMS_MAP_KEY_ENCRYPTED` y `FIRMS_SECRET_KEY`; se retiró su valor en texto plano. El descifrado ocurre en Python, exclusivamente en el servidor. La configuración local sigue excluida de Git y ahora también del paquete de Vercel.

La comprobación contra el endpoint oficial de disponibilidad de NASA FIRMS aceptó la credencial. La misma construcción que usará Vercel descargó MODIS NRT, VIIRS NOAA-20 NRT y VIIRS NOAA-21 NRT para el **14 de noviembre de 2026**: **91.641 registros de entrada, 56.084 representantes y 35.557 deduplicados**, sin cuarentena. El conjunto pasó **18/18 criterios de auditoría** de JSON, CSV, linaje y Parquet. Los crudos de esta construcción temporal no forman parte del paquete publicado.

La interfaz permite español, inglés y francés. El cambio conserva el mapa, los controles y los datos, y recuerda la preferencia en el navegador. Traduce controles, mensajes, leyendas, calendarios, etiquetas accesibles, fichas, guías y documentos de método y limitaciones. Los identificadores de la API, los nombres oficiales de lugares, los productos y las columnas de CSV conservan su forma original. Las citas oficiales se mantienen en su idioma de origen con advertencias explicativas traducidas.

## Configurar Vercel

El archivo local `.env` no se transfiere automáticamente a Vercel. En **Project → Settings → Environment Variables**, seleccionar **Production** y crear:

| Variable | Tipo | Valor |
|---|---|---|
| `FIRMS_MAP_KEY_ENCRYPTED` | **Secret** | Copiar el valor de esa variable desde `.env`, sin las comillas ni el nombre. |
| `FIRMS_SECRET_KEY` | **Secret** | Copiar el valor de esa variable desde `.env`. Es la clave que permite descifrar. |
| `HHN_MODO_DATOS` | Config | `firms` |
| `FIRMS_NRT_DIAS` | Config, opcional | `1` por defecto; admite de `1` a `3` días UTC completos anteriores a la construcción. |

Dejar `HHN_DATOS` sin configurar para que el modo seleccione `data/processed/vercel_firms`. Si se mantiene una ruta personalizada, esa ruta prevalece y debe contener el conjunto deseado. Si se usa la pareja cifrada, se puede retirar la variable antigua `FIRMS_MAP_KEY` de Vercel.

Publicar estos cambios y ejecutar **Redeploy** después de configurar las variables. Se necesitan en la construcción y en la función de producción. Vercel permite crear variables de tipo [Secret](https://vercel.com/changelog/environment-variables-now-use-config-and-secret-types), cuyos valores permanecen disponibles para los despliegues y no se pueden volver a consultar desde el panel tras guardarlos.

La construcción descarga el periodo reciente y ejecuta el pipeline. Si falta la clave, no puede descifrarse o FIRMS falla, el modo real falla explícitamente y no genera una demo como sustitución. El modo `demo` sigue disponible para una demostración sintética deliberada.

## Verificar la carga

`GET /estado-servicios` informa únicamente si la credencial está configurada, si está cifrada, el modo efectivo, el origen del conjunto y las fechas de la última ingesta. No devuelve la clave, su clave de descifrado ni el texto cifrado.

En la interfaz, abrir **Validar datos y método** para revisar el estado de conexión. Para una construcción real se esperan:

- `firms.configurada = true` y `firms.cifrada = true`;
- `firms.modo = firms` y `firms.origen_datos = real`;
- productos y fechas en `firms.ultima_ingesta`;
- origen real y calidad NRT en los paneles del mapa.

Una credencial configurada no implica por sí sola que el conjunto activo sea real: el modo y la procedencia también se comprueban. El conjunto es una instantánea generada al construir; un nuevo despliegue actualiza el periodo. La interfaz conserva el aviso de antigüedad de los datos. NRT es preliminar, y un conjunto reciente no proporciona años suficientes para una línea base.

## Cifrar otra clave local

Introducir una nueva clave en `FIRMS_MAP_KEY` dentro del archivo local y ejecutar:

```powershell
uv sync --locked
uv run python tools/cifrar_clave_firms.py --archivo .env
```

La herramienta conserva otras variables, reemplaza el valor plano por la pareja cifrada y no imprime los secretos. Repetirla sobre una pareja ya cifrada la verifica y mantiene sus valores. Mantener la clave de descifrado en almacenamiento privado; el cifrado necesita esa clave para recuperar la credencial. No subir `.env` al repositorio ni pegar sus valores en el chat.

Fernet protege la confidencialidad y autenticidad del valor cifrado ([documentación de cryptography](https://cryptography.io/en/latest/fernet/)). El acceso al archivo local que contiene ambos valores permite descifrarlo; en producción se almacenan como secretos administrados.

## Idiomas

El selector **Idioma / Language / Langue** está en la barra principal. También se puede abrir `/ui/?lang=es`, `/ui/?lang=en` o `/ui/?lang=fr`. Sin preferencia previa, el idioma es español. El cambio de idioma no vuelve a cargar el mapa ni modifica filtros, posiciones o valores científicos. Los números y fechas de presentación se localizan; los datos JSON y CSV mantienen su contrato.

Documentos públicos:

- `/metodologia?idioma=es`, `en` o `fr`;
- `/limitaciones?idioma=es`, `en` o `fr`.

La búsqueda remota transmite `idioma` a Nominatim y mantiene su caché separada por idioma. La demo estática de GitHub Pages conserva los idiomas y documentos, pero informa que no tiene servidor FIRMS ni admite secretos de producción.

## Verificación realizada

- **562 pruebas correctas** con pytest, incluidas precedencia de secretos, cifrado inválido sin sustitución, idempotencia, errores sin valores de credenciales, construcción real simulada, rutas documentales, localización y búsqueda por idioma.
- **17/17 comprobaciones en Chrome con la demo** y **17/17 con el conjunto real**: títulos, origen, atributos de idioma, mismo mapa y filtros, actualizaciones, búsqueda, móvil, persistencia, enlaces directos y retorno al español.
- Construcción real completada con la credencial cifrada; **18/18 criterios** del conjunto generado.
- Escaneo del repositorio sin credenciales detectadas. `.env` permanece ignorado.

Evidencia sin secretos: [validación de clave](evidencias/clave_idiomas_20261115/validacion_clave.json), [arranque del punto de entrada de Vercel con datos reales](evidencias/clave_idiomas_20261115/arranque_vercel.json), [auditoría del conjunto real](evidencias/clave_idiomas_20261115/conjunto_real_vercel.json), [inglés con datos reales](capturas/idiomas_reales_20261115/01_en_escritorio.png), [francés](capturas/idiomas_reales_20261115/01_fr_escritorio.png), [móvil en francés](capturas/idiomas_reales_20261115/02_fr_movil.png).

Repetir el recorrido con una API local en marcha:

```powershell
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/idiomas_local "C:/Program Files/Google/Chrome/Application/chrome.exe" idiomas
```

La configuración de secretos en Vercel corresponde al administrador del proyecto. Esta ejecución no tuvo una sesión conectada al panel ni escribió variables remotas.
