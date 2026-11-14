# ADR 0008: Frontend con JavaScript sin compilación y Leaflet incluido

## Estado

ACEPTADA (2026-11-13), H4.

## Contexto

El prompt del proyecto propone React con Leaflet, o la alternativa que se documente aquí. La demo debe correr con un único comando, con datos locales y **sin internet**. Un proyecto React necesita Node, un `npm install` con red y un paso de compilación, o bien cargar React desde un CDN, lo que rompe el modo sin red.

## Decisión

- Página estática en `src/ui/static/` (`index.html`, `app.js`, `styles.css`), escrita en JavaScript sin compilación.
- Leaflet 1.9.4 va incluido en `src/ui/static/vendor/leaflet/` con su licencia BSD-2. Su SHA-256 coincide con el SRI publicado en leafletjs.com:
  - `leaflet.js`: `sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=`
  - `leaflet.css`: `sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=`
- FastAPI sirve la página en `/ui/`; `/` redirige allí. Un solo proceso (`make api`).
- Las teselas base de OpenStreetMap son **opcionales**: sin red, el mapa queda con fondo neutro y los focos, el área y el calendario siguen funcionando.
- El calendario y la climatología se dibujan en SVG y CSS propios, sin librería de gráficos.

## Alternativas

1. **React + Vite.** Mejor para crecer, pero exige Node y compilación, y obliga a gestionar dependencias. Se descarta para el MVP del hackatón.
2. **React desde un CDN.** No funciona sin internet.
3. **Streamlit o Dash.** Permite iterar rápido en Python, pero es más difícil controlar la interacción del mapa y el calendario.

## Consecuencias

- Nada que compilar: `make api` basta.
- Si la interfaz crece, migrar a React reutiliza la misma API.
- Las teselas de OpenStreetMap siguen su política de uso. Para un despliegue público hay que usar un proveedor propio (R-30).

## Actualización 2026-11-13 (H6): tema claro y oscuro

Decisión:

- Los colores son tokens CSS en `:root`. Se redefinen en `@media (prefers-color-scheme: dark)` y en `:root[data-tema="oscuro"]`.
- El selector «Tema» ofrece «Sistema», «Claro» y «Oscuro». La elección se guarda en `localStorage` con la clave `hhn-tema`, dentro de `try/catch`. Un script en línea en `<head>` aplica el tema guardado antes de cargar las hojas de estilo, para evitar el destello.
- Los colores de Leaflet y del calendario se asignan con clases y variables CSS, sin colores en JavaScript.
- Las teselas se oscurecen con `filter` CSS solo en el tema oscuro.
- No se añaden librerías ni recursos remotos.

Alternativas:

1. **Una hoja de estilos separada por tema.** Duplica reglas y es más difícil mantener el contraste sincronizado. Se descarta.
2. **Solo `prefers-color-scheme`.** No permite forzar el tema para una captura, una demostración o un usuario que lo necesite. Se descarta como única vía.
3. **Teselas oscuras de un proveedor externo.** Requiere red y una clave o política de uso adicional, y rompe el modo sin internet. Se descarta.

Consecuencias:

- El contraste WCAG AA (texto ≥ 4,5:1; gráficos y foco ≥ 3:1) se calcula en `tests/test_interfaz.py` para ambos temas.
- El filtro CSS altera los colores de las teselas de OpenStreetMap en el tema oscuro. Es una aproximación visual, no un mapa oscuro de origen.
- Las capturas de la interfaz H6 con datos reales en claro, oscuro y 375 px están en `docs/capturas/` (`05`–`08`). Las de la demo sintética en ambos temas siguen pendientes (`docs/capturas/LEEME.md`).
