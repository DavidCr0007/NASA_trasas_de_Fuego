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
