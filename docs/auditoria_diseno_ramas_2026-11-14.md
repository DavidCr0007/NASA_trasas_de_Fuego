# Auditoría de diseño: `main` y `feat/globo-global`

**Fecha:** 14 de noviembre de 2026  
**Versiones:** `main` (`1368e89`) y `feat/globo-global` (`4137427`)  
**Objeto:** interfaz, experiencia de uso, accesibilidad y comunicación de los datos. No es una auditoría de la metodología científica.

**Estado posterior:** los siete hallazgos se atendieron en `feat/globo-global`; ver [cierre de la auditoría](#cierre-de-la-auditoría-14-de-noviembre-de-2026). Las capturas y comparaciones iniciales de este documento se conservan como línea de base.

**Nueva iteración:** la reorganización con globo inicial, panel lateral, círculos uniformes y guía térmica está documentada en [reestructuración visual y validación](reestructuracion_visual_2026-11-14.md).

## Método y evidencia

- Comparé `index.html`, `styles.css`, `app.js` y la lógica nueva de `globo.js` en ambas versiones. Ejecuté cada interfaz en Chrome a 1440 × 900 con el mismo conjunto local `data/processed/global_nrt`. La captura de `main` procede de una exportación temporal del commit, sin cambiar la rama de trabajo.
- Recorrí en `feat/globo-global` mapa regional → globo → país → zona explorada → día → tema claro → móvil (390 × 844). El recorrido obtuvo **12/12 comprobaciones correctas**, sin errores de consola ni desborde horizontal. `tests/test_interfaz.py` y `tests/test_global.py`: **125 pruebas correctas**.
- Capturas: [main, escritorio](capturas/auditoria_globo_20261114/00_main_escritorio.png), [rama nueva, mapa regional](capturas/auditoria_globo_20261114/01_regional.png), [globo oscuro](capturas/auditoria_globo_20261114/02_globo.png), [globo claro](capturas/auditoria_globo_20261114/06_globo_claro.png), [móvil](capturas/auditoria_globo_20261114/07_movil_regional.png). Las demás etapas del recorrido están en la misma carpeta.
- La comprobación con datos reales se hizo sobre NRT del 8 al 14 de noviembre de 2026. El resultado visual puede variar con otras densidades, periodos y tamaños de pantalla. No hice una prueba con usuarios ni una auditoría formal de lectores de pantalla.

## Comparación

| Aspecto | `main` | `feat/globo-global` | Evaluación |
|---|---|---|---|
| Jerarquía inicial | Resumen y aviso de seguridad antes del mapa; mapa y análisis en columnas. | Mapa de ancho completo; resumen y leyenda sobre el mapa; análisis debajo. | La rama nueva favorece la exploración espacial. `main` comunica mejor el contexto y la limitación de uso al entrar. |
| Cobertura | Consulta regional centrada en Huila y calendario histórico. | Añade globo mundial NRT, clasificación por FRP, países y transición por zoom. | Avance claro para explorar fuera del Huila, sujeto a la cobertura del conjunto regional. |
| Interpretación del mapa | La leyenda visible identifica sensores, pero la densidad anual por color carece de cortes numéricos junto al mapa. | Leyendas numéricas para densidad y FRP; forma del punto para el sensor. | La rama nueva explica mejor la simbología. |
| Tema y respuesta | Claro/oscuro y disposición de dos columnas en escritorio. | Conserva los temas y usa tarjetas adaptables; sin desborde a 390 px. | Correcto en la muestra; la primera pantalla móvil sigue dominada por controles. |
| Acceso sin red | Mapa regional y calendario operativos; teselas opcionales. | Países locales como fondo alternativo del globo; WebGL requerido. | La degradación está prevista, aunque los datos globales deben estar preparados localmente. |

## Hallazgos priorizados

### 1. Alta — El aviso de seguridad queda fuera de la primera vista

En `main`, el aviso «No usar para proteger vidas ni bienes» se ve antes del mapa. En la rama nueva aparece después de una escena de aproximadamente el 73 % de la altura de la ventana: no entra en la captura inicial de escritorio ni en la primera pantalla móvil. Esto debilita una advertencia esencial para un producto que muestra focos de calor.

**Evidencia:** [main](capturas/auditoria_globo_20261114/00_main_escritorio.png) frente a [rama nueva](capturas/auditoria_globo_20261114/01_regional.png); `index.html` sitúa `#aviso-emergencia` después de `.mapa-tarjeta` y `styles.css` define la altura de `.mapa-escena`.

**Acción:** mostrar una advertencia breve, visible y persistente cerca del título o de los datos de calidad; dejar el texto y la cita completos en su bloque actual. El aviso debe verse antes de interactuar con cualquiera de los mapas.

### 2. Alta — Los controles regionales parecen gobernar el globo

En vista mundial siguen arriba «Área: Huila», «Año: 2026» y las dos descargas CSV. El panel flotante tiene su propio selector «Últimas 48 h». Los controles superiores siguen consultando el área y el calendario regionales, mientras que el globo representa otro alcance y periodo. La interfaz no distingue explícitamente ambos contextos, por lo que una descarga puede interpretarse como la de los focos visibles en el globo.

**Evidencia:** [globo oscuro](capturas/auditoria_globo_20261114/02_globo.png), `index.html` (controles fuera de `#mapa-escena`), `app.js` (`mostrarGlobo`) y `globo.js` (`montarPanel`).

**Acción:** separar visualmente «Consulta regional» y «Vista mundial», rotular el alcance de cada CSV y hacer que los controles pertinentes al globo sean los únicos activos o visibles durante esa vista. Mostrar junto al título mundial el rango UTC efectivo de los datos.

### 3. Alta, condicionada a la configuración — El acercamiento puede prometer detalles que no existen

El globo puede leer `--datos-global` mientras el mapa regional lee `--datos`. Si el primero contiene NRT mundial y el segundo solo historia del Huila, acercarse desde un país distinto abre una zona regional sin las detecciones que el usuario acaba de ver agrupadas. El propio ADR 0012 reconoce esa limitación. Con `make api-global`, que usa un mismo conjunto mundial, el recorrido sí encontró focos al acercarse en Brasil.

**Evidencia:** [zona explorada con `make api-global`](capturas/auditoria_globo_20261114/04_zona_explorada.png), `src/api/app.py` (selección separada de `datos` y `datos_global`), `app.js` (`explorarZona`) y [ADR 0012](decisiones/0012-globo-3d-y-vista-global.md).

**Acción:** indicar la cobertura real disponible para el detalle antes de pasar de vista. Si no existe, ofrecer una explicación contextual y una ruta al visor FIRMS; para la experiencia completa, servir una fuente regional que cubra la zona explorada.

### 4. Media — La primera pantalla móvil está ocupada por filtros y descargas

La cuadrícula de dos columnas mejora la compactación respecto a `main`, pero a 390 px el mapa empieza después de la cabecera, siete controles y el bloque avanzado. La opción «Zona explorada en el globo» queda cortada en el selector. No hay desborde horizontal; el problema es de prioridad visual y lectura.

**Evidencia:** [captura móvil](capturas/auditoria_globo_20261114/07_movil_regional.png); reglas `@media (max-width: 480px)` de `styles.css`.

**Acción:** dejar Área, Año y cambio de mapa a la vista; mover descargas y Tema a un menú o bloque desplegable claramente rotulado. Abreviar la opción del área y mostrar su nombre completo en un texto de apoyo.

### 5. Media — Los focos del globo no tienen una vía equivalente de selección por teclado

Los círculos se abren mediante el evento `click` de MapLibre sobre el lienzo. El panel ofrece botones para los ocho países con más focos, pero no una lista o búsqueda de celdas que permita abrir una celda arbitraria sin apuntar sobre el mapa. El lienzo tiene nombre accesible; ese nombre no comunica los valores individuales.

**Evidencia:** `globo.js` (`mapa.on("click", "focos", ...)`, `pintarPanel` y `montarPanel`). Es un hallazgo de inspección del código, pendiente de validación con usuarios de teclado y lector de pantalla.

**Acción:** añadir una alternativa textual operable: búsqueda de país o zona y lista de celdas visibles con cantidad, FRP y acción «Explorar». Mantener el foco y anunciar el cambio de vista.

### 6. Media — «Últimas 24/48 h» puede significar «últimos días del archivo»

La API termina el periodo en el último dato almacenado, no necesariamente en la fecha actual, y `dias=2` abarca dos fechas UTC completas, no una ventana móvil exacta de 48 horas. El panel sí muestra las fechas efectivas, pero los nombres «Últimas 24 h» y «Últimas 48 h» sugieren una duración y actualidad que el archivo puede no tener. El ADR 0012 registra que la actualización programada está pendiente.

**Evidencia:** `globo.js` (`PERIODOS` y `pintarPanel`) y `src/api/app.py` (`get_global`, `fin = hi` cuando no se indica `hasta`).

**Acción:** usar «1/2/7 días hasta el último dato» o «24/48 h del archivo» y mostrar de forma destacada «Actualizado hasta: fecha y hora UTC». Si el conjunto supera el umbral de vigencia definido por el proyecto, marcarlo como desactualizado.

### 7. Baja — Se retiró el anuncio de dos paneles que cambian con la consulta

`main` marca `#mes-reciente` y `#meteo` con `aria-live="polite"`; la rama nueva lo retira. Cuando se cambia el área o el día, sus resultados pueden actualizarse sin anuncio específico. Conviene comprobar el flujo completo con lector de pantalla antes de decidir si el anuncio global de estado es suficiente.

**Evidencia:** diferencia de `src/ui/static/index.html` entre ambas ramas.

**Acción:** restaurar anuncios breves en esos paneles o concentrar sus cambios en una única región de estado que describa qué resultado se actualizó.

## Recomendación de diseño

Usar `feat/globo-global` como base de la siguiente iteración: mejora el alcance, la lectura de densidad y FRP, y pasó el recorrido de navegador. Antes de presentarla como experiencia global completa, resolver los hallazgos **1 a 3**. Conservar de `main` la visibilidad inicial de la advertencia y la separación clara entre resumen, mapa y análisis. Después atender los problemas móviles y de acceso por teclado.

## Cierre de la auditoría (14 de noviembre de 2026)

| Hallazgo | Cambio aplicado |
|---|---|
| 1. Aviso | Advertencia breve junto al título, visible antes del mapa en escritorio y móvil. El aviso completo y su cita permanecen debajo del mapa. |
| 2. Alcance | La barra distingue consulta regional y vista mundial. En el globo se ocultan área, año, descargas e insignias regionales; el panel mundial muestra su propio origen, calidad, periodo y actualización. Los CSV están rotulados como regionales. |
| 3. Cobertura | `/global` indica si ambos mapas leen el mismo conjunto. Con conjuntos separados, el globo impide la transición automática a un supuesto detalle, muestra el límite de cobertura y ofrece el visor oficial FIRMS. Con un mismo conjunto mundial se conserva la transición. |
| 4. Móvil | Área, Año y cambio de mapa quedan visibles. Dibujo, descargas, Tema, rango y coordenadas están en «Opciones y descargas». La opción «Zona explorada» muestra su nombre completo debajo. |
| 5. Teclado | El panel mundial ofrece un selector de país y una lista paginada de todas las celdas del periodo, con cantidad, FRP y coordenadas. Cada celda abre su ficha mediante un botón; al cambiar de vista se conserva un foco de teclado visible. |
| 6. Vigencia | Los periodos se nombran por días del archivo. Se muestra el rango UTC y la última detección; si supera 48 horas de antigüedad aparece una alerta. |
| 7. Anuncios | `#mes-reciente` y `#meteo` recuperan `aria-live="polite"`. |

**Verificación posterior:** suite completa **449 pruebas correctas**; recorrido Chrome con un mismo conjunto mundial **17/17** y con conjuntos regional/global separados **4/4**, sin errores de consola. Capturas posteriores: [mapa regional](capturas/diseno_aplicado_20261114/01_regional.png), [globo](capturas/diseno_aplicado_20261114/02_globo.png), [móvil](capturas/diseno_aplicado_20261114/07_movil_regional.png) y [fuentes separadas](capturas/diseno_aplicado_20261114/08_globo_fuentes_separadas.png).

**Límite de la solución:** cuando los mapas usan conjuntos separados, se bloquea el paso automático al detalle de esas detecciones aunque ambos archivos puedan solaparse parcialmente. El detalle mundial completo se obtiene al servir el mismo conjunto global en ambos mapas (`make api-global`). La lista de celdas mejora el acceso por teclado; sigue pendiente una evaluación práctica con lectores de pantalla.
