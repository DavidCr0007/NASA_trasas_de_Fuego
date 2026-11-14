/* Harmonized Heat Neiva: mapa y calendario de actividad (H4, H6).
 * Sin paso de compilación y sin dependencias remotas: Leaflet va incluido en vendor/.
 * Las teselas base de OpenStreetMap son opcionales; sin internet el mapa queda en gris.
 * Los colores viven en styles.css (variables por tema); aquí solo se asignan clases.
 */
"use strict";

const AREAS = {
  huila: [-76.7, 1.4, -74.3, 3.9], // firms_schema.HUILA_BBOX: contiene el límite oficial (geoBoundaries) con 0,05-0,15° de margen
  neiva: [-75.53, 2.68, -75.03, 3.18], // Neiva (2,93; -75,28) ± 0,25°
};
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const CLAVE_TEMA = "hhn-tema";

// area: "huila" o "mun:<id>" filtra por la forma real (R-40); null usa solo el recuadro bbox.
// rango: {desde, hasta} opcional para el mapa y las descargas (H8-05).
const estado = { bbox: AREAS.huila, area: "huila", anio: null, dia: null, calendario: null, rango: null, resumen: null };

const $ = (id) => document.getElementById(id);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (n, d = 0) => (n == null ? "—" : Number(n).toLocaleString("es-CO", { maximumFractionDigits: d }));

/** «2026-08-12» → «12 ago 2026», sin Date local (no depende de la zona horaria). */
function fechaLegible(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ""));
  if (!m) return String(iso ?? "—");
  return `${Number(m[3])} ${MESES[Number(m[2]) - 1]} ${m[1]}`;
}
/** Fecha legible con la ISO entre paréntesis, para quien necesita precisión. */
const fechaPrecisa = (iso) => `${fechaLegible(iso)} (${String(iso).slice(0, 10)})`;
/** «2026-08-12T15:42:00Z» → «12 ago 2026, 15:42 UTC». */
function fechaHoraLegible(iso) {
  const m = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/.exec(String(iso ?? ""));
  return m ? `${fechaLegible(m[1])}, ${m[2]} UTC` : String(iso ?? "—");
}

function mensajeDe(err) {
  return err && err.message ? err.message : String(err);
}
const esAborto = (err) => err && err.name === "AbortError";

/** Lee la respuesta UNA sola vez como texto y la interpreta como JSON si es posible. */
async function pedir(ruta, señal) {
  let r, texto;
  try {
    r = await fetch(ruta, { signal: señal });
    texto = await r.text();
  } catch (err) {
    if (esAborto(err)) throw err;
    throw new Error("No se pudo conectar con el servidor. Compruebe que la API esté en marcha.");
  }
  let cuerpo = null;
  try { cuerpo = JSON.parse(texto); } catch { /* cuerpo no JSON */ }
  if (!r.ok) {
    let detalle = cuerpo && (cuerpo.detail ?? cuerpo.detalle);
    if (detalle != null && typeof detalle !== "string") detalle = JSON.stringify(detalle);
    detalle = detalle || r.statusText || texto.slice(0, 120) || "error desconocido";
    if (r.status === 503) detalle += " (faltan datos procesados; ejecute make demo)";
    throw new Error(`${r.status}: ${detalle}`);
  }
  if (cuerpo === null) throw new Error("La respuesta del servidor no tiene el formato esperado.");
  return cuerpo;
}

// ------------------------------------------------------------------ tema
function aplicarTema(valor) {
  const raiz = document.documentElement;
  if (valor === "claro" || valor === "oscuro") raiz.setAttribute("data-tema", valor);
  else raiz.removeAttribute("data-tema");
}

function iniciarTema() {
  let guardado = "sistema";
  try {
    const v = localStorage.getItem(CLAVE_TEMA);
    if (v === "claro" || v === "oscuro") guardado = v;
  } catch { /* almacenamiento no disponible */ }
  const sel = $("sel-tema");
  sel.value = guardado;
  aplicarTema(guardado);
  sel.addEventListener("change", () => {
    const v = sel.value;
    try {
      if (v === "sistema") localStorage.removeItem(CLAVE_TEMA); else localStorage.setItem(CLAVE_TEMA, v);
    } catch { /* se aplica igual, solo que no se recordará */ }
    aplicarTema(v);
    repintarTema();
  });
}

/** Tema efectivo: el elegido en el selector o, en «Sistema», la preferencia del sistema. */
function temaOscuro() {
  const elegido = document.documentElement.getAttribute("data-tema");
  return elegido ? elegido === "oscuro" : window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Vuelve a pintar lo que se dibuja en JS; los colores salen de CSS, así que basta con repintar. */
function repintarTema() {
  if (ultimosFocos) pintarFocos(ultimosFocos);
  if (globo) globo.repintar();
  const c = estado.calendario;
  if (!c || !c.dias || !c.dias.length) return;
  pintarCalendario(c);
  if (typeof pintarComparacion === "function") pintarComparacion(c);
}
window.repintarTema = repintarTema;
window.matchMedia("(max-width: 600px)").addEventListener("change", () => {
  const c = estado.calendario;
  if (c && c.dias && c.dias.length) pintarCalendario(c);
});

// ------------------------------------------------------------------ mapa
// Canvas: con miles de focos, SVG genera un elemento por círculo y vuelve lenta la interfaz
// (auditoría UI/UX, hallazgo 2). Canvas no admite estilos por clase: los colores se leen de
// las variables CSS del tema y se repintan al cambiarlo.
const lienzo = L.canvas({ padding: 0.3 });
// El zoom va arriba a la derecha: arriba a la izquierda flota el resumen.
const mapa = L.map("mapa", { zoomControl: false, attributionControl: true, preferCanvas: true, renderer: lienzo, minZoom: 4 }).setView([2.6, -75.5], 8);
L.control.zoom({ position: "topright" }).addTo(mapa);
const token = (nombre) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
let ultimosFocos = null;
mapa.attributionControl.setPrefix(false);

// ------------------------------------------------------------------ globo 3D (ADR 0012)
// Vista de país o más lejos = globo (MapLibre, focos de todo el mundo agregados en celdas);
// más cerca = mapa regional (Leaflet, cada foco). El cambio solo ocurre por zoom del usuario
// (no al encuadrar un área) y con histéresis: se entra al globo en zoom Leaflet ≤ 5 alejándose
// y se vuelve al mapa regional en zoom MapLibre ≥ 5,2 (≈ Leaflet 6,2) acercándose.
const UMBRAL_GLOBO = 5;
const UMBRAL_REGIONAL = 5.2;
let vista = "regional";
let globo = null;
let guardaZoom = false;
let zoomPrevio = mapa.getZoom();

/** Encuadre programático: no debe disparar el paso al globo. */
function encuadrar(fn) {
  guardaZoom = true;
  fn();
  const soltar = () => { guardaZoom = false; };
  mapa.once("moveend", soltar);
  setTimeout(soltar, 1500);
}

function hayWebGL() {
  try {
    const c = document.createElement("canvas");
    return Boolean(window.maplibregl && window.Globo && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch { return false; }
}

function dentroDeArea(lon, lat) {
  const [w, s, e, n] = estado.bbox;
  return lon >= w && lon <= e && lat >= s && lat <= n;
}

function mostrarGlobo() {
  if (!hayWebGL()) {
    mostrarEstado("error", "El globo 3D no está disponible: este navegador no tiene WebGL. El mapa regional sigue funcionando.");
    return;
  }
  vista = "globo";
  $("mapa-escena").dataset.vista = "globo";
  $("aviso-truncado").hidden = true;
  const b = $("btn-globo");
  b.textContent = "Volver al mapa regional";
  b.setAttribute("aria-pressed", "true");
  $("mapa-titulo").textContent = "Globo 3D: focos activos en el mundo";
  $("mapa-filtro").textContent = "Arrastre para girar; acérquese a una zona para ver cada foco.";
  $("mapa-modo").textContent = "Vista mundial: cada círculo agrupa los focos de una celda (0,5° lejos, 0,25° cerca). " +
    "Color = FRP máximo de la celda; tamaño = número de focos.";
  if (!globo) {
    globo = window.Globo.crear({
      contenedor: $("globo"), panel: $("globo-panel"), oscuro: temaOscuro, umbralRegional: UMBRAL_REGIONAL,
      alExplorar: (lon, lat, z) => mostrarRegional(lon, lat, Math.max(6, Math.min(10, z))),
      alVolver: () => mostrarRegional(),
    });
  }
  const c = mapa.getCenter();
  globo.mostrar(c.lng, c.lat, Math.max(1.2, Math.min(UMBRAL_REGIONAL - 1.2, mapa.getZoom() - 1)));
}

/** Vuelve al mapa regional. Con coordenadas, se centra allí y, si está fuera del área, la explora. */
function mostrarRegional(lon, lat, zoom) {
  vista = "regional";
  $("mapa-escena").dataset.vista = "regional";
  if (globo) globo.ocultar();
  const b = $("btn-globo");
  b.textContent = "Ver el globo 3D";
  b.setAttribute("aria-pressed", "false");
  $("mapa-titulo").textContent = "Mapa de focos";
  mapa.invalidateSize();
  if (lon == null) {
    const [w, s, e, n] = estado.bbox;
    encuadrar(() => mapa.fitBounds([[s, w], [n, e]], { padding: [10, 10], animate: false }));
    if (ultimosFocos) pintarFocos(ultimosFocos);
    return;
  }
  encuadrar(() => mapa.setView([lat, lon], zoom ?? 7, { animate: false }));
  if (dentroDeArea(lon, lat)) { if (ultimosFocos) pintarFocos(ultimosFocos); return; }
  explorarZona();
}

/** Toma la vista actual del mapa regional como área de consulta (zona elegida en el globo). */
function explorarZona() {
  const b = mapa.getBounds();
  const r = (x) => Math.round(x * 100) / 100;
  estado.bbox = [r(Math.max(-180, b.getWest())), r(Math.max(-90, b.getSouth())), r(Math.min(180, b.getEast())), r(Math.min(90, b.getNorth()))];
  estado.area = null;
  estado.dia = null;
  const opcion = $("sel-area").querySelector('option[value="dibujo"]');
  opcion.disabled = false;
  opcion.textContent = "Zona explorada en el globo";
  $("sel-area").value = "dibujo";
  resaltarMunicipio(null);
  cargar({ encuadrarArea: false });
}

mapa.on("zoomstart", () => { zoomPrevio = mapa.getZoom(); });
mapa.on("zoomend", () => {
  const z = mapa.getZoom();
  if (vista === "regional" && !guardaZoom && z < zoomPrevio && z <= UMBRAL_GLOBO) { mostrarGlobo(); return; }
  // La rejilla depende del zoom y la huella del píxel solo se dibuja de cerca: se rehace.
  if (ultimosFocos) pintarFocos(ultimosFocos);
});
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 17,
  className: "teselas-base",
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(mapa);
// D-10: cita de FIRMS en el mapa (forma corta según la FAQ; la completa va en el pie).
mapa.attributionControl.addAttribution(
  'Focos: <a href="https://www.earthdata.nasa.gov/data/tools/firms">NASA FIRMS</a> (LANCE / ESDIS)'
);
// Pocas figuras con estilo del tema (área y límites): en SVG, para que apliquen las clases CSS.
const svgVector = L.svg();
const capaLimites = L.layerGroup().addTo(mapa);
const capaArea = L.layerGroup().addTo(mapa);
const capaFocos = L.layerGroup().addTo(mapa);

function dibujarArea() {
  capaArea.clearLayers();
  const [w, s, e, n] = estado.bbox;
  L.rectangle([[s, w], [n, e]], { renderer: svgVector, className: "area-rect", weight: 1.5, fill: false, dashArray: "4 4", interactive: false }).addTo(capaArea);
}

// ------------------------------------------------------------------ límites (H7-01)
// Municipios del Huila (geoBoundaries ADM2, DANE, CC BY 4.0), servidos localmente: funcionan sin red.
let municipios = [];
let capaMunicipios = null;

async function cargarLimites() {
  try {
    const geo = await pedir("/ui/datos/huila_municipios.geojson");
    municipios = geo.features ?? [];
    capaMunicipios = L.geoJSON(geo, {
      renderer: svgVector, interactive: false,
      style: () => ({ className: "limite-municipio", weight: 1, fill: false }),
    }).addTo(capaLimites);
    const grupo = document.createElement("optgroup");
    grupo.label = "Municipios del Huila (recuadro del municipio)";
    for (const f of municipios) {
      const o = document.createElement("option");
      o.value = `mun:${f.properties.shapeID}`;
      o.textContent = f.properties.shapeName;
      grupo.appendChild(o);
    }
    $("sel-area").appendChild(grupo);
    mapa.attributionControl.addAttribution(
      'Límites: <a href="https://www.geoboundaries.org">geoBoundaries</a> (DANE, CC BY 4.0)'
    );
  } catch {
    // Sin límites la herramienta sigue funcionando: solo no se dibujan los municipios.
  }
}

function resaltarMunicipio(id) {
  if (!capaMunicipios) return;
  capaMunicipios.eachLayer((l) => {
    const el = l.getElement && l.getElement();
    if (el) el.classList.toggle("limite-sel", l.feature?.properties?.shapeID === id);
  });
}

// ------------------------------------------------------------------ imagen del día (H7-02)
// NASA GIBS: color real del día seleccionado. Panel propio fuera de .leaflet-tile-pane para
// que el filtro del tema oscuro no invierta la imagen. Requiere red; es opcional.
mapa.createPane("imagen");
mapa.getPane("imagen").style.zIndex = 250;
const CAPAS_GIBS = {
  modis: "MODIS_Terra_CorrectedReflectance_TrueColor",
  viirs: "VIIRS_NOAA20_CorrectedReflectance_TrueColor",
};
let capaGibs = null;

function actualizarImagen() {
  if (capaGibs) { mapa.removeLayer(capaGibs); capaGibs = null; }
  const sel = $("sel-imagen");
  const nota = $("imagen-nota");
  if (!sel) return;
  sel.disabled = !estado.dia;
  if (!estado.dia) { nota.textContent = "Elija un día en el calendario para ver la imagen satelital de ese día."; return; }
  const capa = CAPAS_GIBS[sel.value];
  if (!capa) { nota.textContent = ""; return; }
  capaGibs = L.tileLayer(
    `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${capa}/default/${estado.dia}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`,
    { pane: "imagen", maxNativeZoom: 9, maxZoom: 17, opacity: 0.92,
      attribution: 'Imagen: <a href="https://www.earthdata.nasa.gov/data/tools/gibs">NASA GIBS</a> (ESDIS)' },
  ).addTo(mapa);
  nota.textContent = `Imagen de color real del ${fechaLegible(estado.dia)} (NASA GIBS). Las nubes pueden ocultar el humo; ` +
    "las franjas negras son zonas por donde el satélite no pasó ese día (pruebe el otro satélite). Requiere internet.";
}

// ------------------------------------------------------------------ conexión NASA FIRMS
// Abre el mismo día y área en el visor oficial (útil para la comparación manual H5-02).
function actualizarEnlaceFirms() {
  const a = $("enlace-firms");
  if (!a) return;
  const [w, s, e, n] = estado.bbox;
  const lat = ((s + n) / 2).toFixed(3), lon = ((w + e) / 2).toFixed(3);
  const p = estado.calendario && estado.calendario.periodos_inusuales ? periodosOrdenados(estado.calendario)[0] : null;
  const dia = estado.dia ?? p?.inicio ?? null;
  const zoom = Math.max(7, Math.min(12, mapa.getZoom()));
  a.href = `https://firms.modaps.eosdis.nasa.gov/map/#${dia ? `d:${dia}..${dia};` : ""}@${lon},${lat},${zoom}.0z`;
  a.textContent = dia ? `Abrir el ${fechaLegible(dia)} en el visor NASA FIRMS` : "Abrir esta área en el visor NASA FIRMS";
}

// ------------------------------------------------------------------ clima (H7-03)
// Open-Meteo, archivo histórico: reanálisis (modelo), no observaciones. Opcional; requiere red.
let meteoGen = 0;
const sumarDias = (iso, n) => new Date(Date.parse(`${iso}T00:00:00Z`) + n * 86400000).toISOString().slice(0, 10);

async function pintarMeteo() {
  const caja = $("meteo");
  if (!caja) return;
  const c = estado.calendario;
  let desde, hasta, titulo;
  if (estado.dia) {
    desde = sumarDias(estado.dia, -3); hasta = sumarDias(estado.dia, 3);
    titulo = `alrededor del ${fechaLegible(estado.dia)}`;
  } else {
    const p = c && c.periodos_inusuales ? periodosOrdenados(c)[0] : null;
    if (!p) { caja.innerHTML = `<p class="tenue">Elija un día en el calendario para ver el clima de esos días.</p>`; return; }
    desde = sumarDias(p.inicio, -2); hasta = sumarDias(p.fin, 2);
    titulo = `del periodo crítico principal (${fechaLegible(p.inicio)} → ${fechaLegible(p.fin)})`;
  }
  const [w, s, e, n] = estado.bbox;
  const lat = ((s + n) / 2).toFixed(2), lon = ((w + e) / 2).toFixed(2);
  const gen = ++meteoGen;
  caja.innerHTML = `<p class="tenue">Consultando el clima ${esc(titulo)}…</p>`;
  const url = `https://archive-api.open-meteo.com/v1/archive?latitude=${lat}&longitude=${lon}` +
    `&start_date=${desde}&end_date=${hasta}&timezone=UTC` +
    "&daily=temperature_2m_max,relative_humidity_2m_min,precipitation_sum,wind_speed_10m_max";
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(10000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = (await r.json()).daily;
    if (gen !== meteoGen) return;
    const inusual = new Set((c?.dias ?? []).filter((x) => x.inusual).map((x) => x.fecha_utc));
    const filas = d.time.map((t, i) => {
      const marcas = [t === estado.dia ? "día elegido" : "", inusual.has(t) ? "inusual" : ""].filter(Boolean).join(", ");
      return `<tr${t === estado.dia ? ' class="fila-sel"' : ""}><th scope="row">${esc(fechaLegible(t))}${marcas ? ` <span class="tenue">(${marcas})</span>` : ""}</th>` +
        `<td>${fmt(d.temperature_2m_max[i], 1)} °C</td><td>${fmt(d.relative_humidity_2m_min[i])} %</td>` +
        `<td>${fmt(d.precipitation_sum[i], 1)} mm</td><td>${fmt(d.wind_speed_10m_max[i], 0)} km/h</td></tr>`;
    }).join("");
    const vals = (k) => d[k].filter((v) => v != null);
    const lluvia = vals("precipitation_sum").reduce((a, b) => a + b, 0);
    caja.innerHTML =
      `<p><strong>Clima ${esc(titulo)}</strong>: máx. ${fmt(Math.max(...vals("temperature_2m_max")), 1)} °C, ` +
      `humedad mín. ${fmt(Math.min(...vals("relative_humidity_2m_min")))} %, lluvia total ${fmt(lluvia, 1)} mm.</p>` +
      `<details><summary>Ver día por día</summary><table class="tabla-cmp"><thead><tr><th scope="col">Día</th>` +
      `<th scope="col">T. máx.</th><th scope="col">Hum. mín.</th><th scope="col">Lluvia</th><th scope="col">Viento máx.</th>` +
      `</tr></thead><tbody>${filas}</tbody></table></details>` +
      `<p class="tenue">Punto central del área (${esc(fmt(Number(lat), 2))}; ${esc(fmt(Number(lon), 2))}). Calor, humedad baja y ausencia de lluvia favorecen las quemas, pero no las causan.</p>`;
  } catch {
    if (gen !== meteoGen) return;
    caja.innerHTML = `<p class="tenue">No se pudo consultar el clima (requiere internet o la fecha aún no está en el archivo, que tiene unos días de retraso). El resto de la herramienta funciona sin él.</p>`;
  }
}

function activarDibujo() {
  const boton = $("btn-dibujar");
  boton.classList.add("activo");
  boton.textContent = "Arrastre sobre el mapa…";
  mapa.dragging.disable();
  let inicio = null;
  let rect = null;
  const abajo = (ev) => { inicio = ev.latlng; };
  const mover = (ev) => {
    if (!inicio) return;
    const b = L.latLngBounds(inicio, ev.latlng);
    if (rect) rect.setBounds(b); else rect = L.rectangle(b, { className: "area-dibujo", weight: 1.5 }).addTo(mapa);
  };
  const arriba = (ev) => {
    if (!inicio) return;
    const b = L.latLngBounds(inicio, ev.latlng);
    mapa.off("mousedown", abajo).off("mousemove", mover).off("mouseup", arriba);
    mapa.dragging.enable();
    if (rect) mapa.removeLayer(rect);
    boton.classList.remove("activo");
    boton.textContent = "Dibujar área en el mapa";
    const r = (x) => Math.round(x * 1000) / 1000;
    if (b.getWest() === b.getEast() || b.getSouth() === b.getNorth()) return;
    estado.bbox = [r(b.getWest()), r(b.getSouth()), r(b.getEast()), r(b.getNorth())];
    estado.area = null;
    const opcion = $("sel-area").querySelector('option[value="dibujo"]');
    opcion.disabled = false;
    $("sel-area").value = "dibujo";
    estado.dia = null;
    cargar();
  };
  mapa.on("mousedown", abajo).on("mousemove", mover).on("mouseup", arriba);
}

// ------------------------------------------------------------------ simbología de los focos
// Tamaño y color = FRP (clases fijas, comparables entre días y regiones; las mismas del globo).
// Opacidad = confianza (la incertidumbre se ve como «menos tinta»). Forma = sensor: círculo
// MODIS, rombo VIIRS. Borde punteado = preliminar (NRT). Huella del píxel solo de cerca.
const CORTES_FRP = [5, 20, 100, 500];
const RADIO_FRP = [3.5, 5, 7, 9.5, 12.5];
const OPACIDAD_CONFIANZA = { alta: 0.95, nominal: 0.78, baja: 0.42 };
const ZOOM_HUELLA = 11;
const claseFrp = (frp) => (frp == null ? 0 : CORTES_FRP.filter((c) => frp >= c).length);
const coloresFrp = () => [token("--f1"), token("--f2"), token("--f3"), token("--f4"), token("--f5")];

/** Rombo en el lienzo Canvas de Leaflet (VIIRS); la detección de clic es la del círculo. */
const Rombo = L.CircleMarker.extend({
  _updatePath() {
    const r = this._renderer;
    if (!r._drawing || this._empty()) return;
    const p = this._point, ctx = r._ctx, s = this._radius * 1.18;
    ctx.beginPath();
    ctx.moveTo(p.x, p.y - s); ctx.lineTo(p.x + s, p.y); ctx.lineTo(p.x, p.y + s); ctx.lineTo(p.x - s, p.y);
    ctx.closePath();
    r._fillStroke(ctx, this);
  },
});

function popupFoco(d) {
  const clase = claseFrp(d.frp);
  const intensidad = ["muy baja", "baja", "moderada", "alta", "muy alta"][clase];
  return `<div class="ficha-foco"><strong>${esc(d.satelite)}</strong> · ${esc(d.sensor)}` +
    `${d.preliminar ? ' <span class="insignia preliminar mini">NRT</span>' : ""}<dl>` +
    `<dt>Fecha</dt><dd>${esc(fechaHoraLegible(d.fecha_hora_utc))}</dd>` +
    `<dt>Intensidad</dt><dd>FRP ${fmt(d.frp, 1)} MW (${intensidad})</dd>` +
    `<dt>Confianza</dt><dd>${esc(d.confianza_clase)} (${esc(d.confianza_raw)})${d.sensor === "MODIS" ? " · cortes MODIS provisionales" : ""}</dd>` +
    `<dt>Calidad</dt><dd>${esc(d.calidad)}${d.preliminar ? " · preliminar, puede corregirse" : ""}</dd>` +
    `<dt>Píxel</dt><dd>±${fmt(d.semilado_nominal_m)} m nominal: el fuego está dentro de ese cuadro</dd>` +
    `<dt>Posición</dt><dd>${fmt(d.lat, 4)}; ${fmt(d.lon, 4)}</dd>` +
    (d.n_fusionados ? `<dt>Fusionados</dt><dd>agrupa ${fmt(d.n_fusionados)} detección(es) casi simultánea(s)</dd>` : "") +
    `</dl></div>`;
}

/** Día o rango corto: cada foco con la simbología de arriba, del menos al más intenso. */
function pintarFocosIndividuales(lista) {
  const colores = coloresFrp();
  const borde = token("--tinta");
  const huella = mapa.getZoom() >= ZOOM_HUELLA;
  const orden = [...lista].sort((a, b) => (a.frp ?? 0) - (b.frp ?? 0));
  for (const d of orden) {
    const k = claseFrp(d.frp);
    const viirs = String(d.sensor).toLowerCase() === "viirs";
    const op = OPACIDAD_CONFIANZA[d.confianza_clase] ?? 0.78;
    if (huella) {
      L.circle([d.lat, d.lon], { renderer: lienzo, radius: d.semilado_nominal_m, color: colores[k], weight: 1,
        fillColor: colores[k], fillOpacity: 0.16, interactive: false }).addTo(capaFocos);
    }
    const Forma = viirs ? Rombo : L.circleMarker;
    const opts = { renderer: lienzo, radius: RADIO_FRP[k], color: borde, weight: 1, opacity: Math.max(0.55, op),
      fillColor: colores[k], fillOpacity: op, dashArray: d.preliminar ? "2 2" : null };
    (viirs ? new Forma([d.lat, d.lon], opts) : Forma([d.lat, d.lon], opts)).bindPopup(popupFoco(d)).addTo(capaFocos);
  }
}

/** Lado de la rejilla de densidad (grados) según el zoom: ~55 km muy lejos, la celda de 1 km de cerca. */
function ladoRejilla() {
  const z = mapa.getZoom();
  return z <= 6 ? 0.5 : z <= 7 ? 0.25 : z <= 8 ? 0.1 : z <= 9 ? 0.05 : z <= 10 ? 0.025 : 0.009;
}

/** Vista del año o de un rango largo: rejilla de densidad con cortes numéricos en la leyenda. */
function pintarCeldas(lista) {
  const lado = ladoRejilla();
  const celdasR = new Map();
  for (const d of lista) {
    const fila = Math.floor(d.lat / lado), col = Math.floor(d.lon / lado);
    const k = `${fila}:${col}`;
    const c = celdasR.get(k) ?? { fila, col, n: 0, modis: 0, viirs: 0, alta: 0, frp: 0, dias: new Set() };
    c.n += 1;
    if (String(d.sensor).toLowerCase() === "viirs") c.viirs += 1; else c.modis += 1;
    if (d.confianza_clase === "alta") c.alta += 1;
    c.frp = Math.max(c.frp, d.frp ?? 0);
    c.dias.add(String(d.fecha_hora_utc).slice(0, 10));
    celdasR.set(k, c);
  }
  const valores = [...celdasR.values()].map((c) => c.n).sort((a, b) => a - b);
  const q = (p) => valores[Math.min(valores.length - 1, Math.floor(p * valores.length))] ?? 1;
  // Cortes por cuantiles de ESTA vista (se muestran con números en la leyenda), siempre crecientes.
  const cortes = [q(0.5), q(0.75), q(0.9)];
  for (let i = 1; i < cortes.length; i++) cortes[i] = Math.max(cortes[i], cortes[i - 1] + 1);
  const escala = [token("--e1"), token("--e2"), token("--e3"), token("--e4")];
  const opacidad = [0.5, 0.64, 0.76, 0.88];
  const borde = token("--tinta");
  const km = Math.round(lado * 111);
  const detalle = mapa.getZoom() >= 10;
  for (const c of celdasR.values()) {
    const nv = c.n <= cortes[0] ? 0 : c.n <= cortes[1] ? 1 : c.n <= cortes[2] ? 2 : 3;
    L.rectangle([[c.fila * lado, c.col * lado], [(c.fila + 1) * lado, (c.col + 1) * lado]], {
      renderer: lienzo, color: borde, weight: detalle ? 0.5 : 0, opacity: 0.35, fillColor: escala[nv], fillOpacity: opacidad[nv],
    }).bindPopup(
      `<strong>${fmt(c.n)} ${c.n === 1 ? "foco" : "focos"}</strong> en este cuadro de ~${fmt(km)} km<br>` +
      `${fmt(c.dias.size)} ${c.dias.size === 1 ? "día" : "días"} con focos · MODIS ${fmt(c.modis)} · VIIRS ${fmt(c.viirs)}<br>` +
      `Confianza alta: ${fmt(c.alta)} · FRP máx. ${fmt(c.frp, 1)} MW<br>` +
      `<span class="tenue">Acerque el mapa para más detalle o elija un día en el calendario para ver cada foco.</span>`,
    ).addTo(capaFocos);
  }
  return { n: celdasR.size, km, cortes };
}

/** Leyenda flotante del mapa regional, con los mismos cortes y formas que se pintan. */
function pintarLeyendaMapa(modo, r) {
  const caja = $("leyenda-mapa");
  if (!caja) return;
  if (modo === "focos") {
    const tramos = ["&lt; 5", "5–20", "20–100", "100–500", "≥ 500"];
    caja.innerHTML = `<strong>FRP (MW)</strong><span class="fila-leyenda">${tramos.map((t, k) =>
      `<span><i class="esc-frp f${k + 1}" style="width:${6 + k * 2.5}px;height:${6 + k * 2.5}px"></i>${t}</span>`).join("")}</span>` +
      `<span class="fila-leyenda"><span><i class="forma circulo"></i>MODIS</span><span><i class="forma rombo"></i>VIIRS</span>` +
      `<span><i class="forma nrt"></i>preliminar</span></span>` +
      `<span class="tenue">Más transparente = menor confianza.${mapa.getZoom() >= ZOOM_HUELLA ? " Círculo claro = huella del píxel." : ""}</span>`;
    return;
  }
  const v = (x) => fmt(x);
  const [a, b, c] = r.cortes;
  const tramos = [["e1", `1–${v(a)}`], ["e2", `${v(a + 1)}–${v(b)}`], ["e3", `${v(b + 1)}–${v(c)}`], ["e4", `más de ${v(c)}`]];
  caja.innerHTML = `<strong>Focos por cuadro de ~${fmt(r.km)} km</strong><span class="fila-leyenda">` +
    tramos.map(([cls, t]) => `<span><i class="esc ${cls}"></i>${esc(t)}</span>`).join("") + `</span>` +
    `<span class="tenue">Cortes de esta vista; cambian con el zoom.</span>`;
}

function pintarFocos(datos) {
  ultimosFocos = datos;
  capaFocos.clearLayers();
  if (vista === "globo") return;
  const lista = datos.detecciones ?? [];
  const n = lista.length;
  // Puntos individuales en un día, o en un rango corto con pocos focos; si no, densidad.
  const rangoCorto = estado.rango && (Date.parse(estado.rango.hasta) - Date.parse(estado.rango.desde)) <= 6 * 86400000;
  const individuales = Boolean(estado.dia) || (rangoCorto && n <= 4000) || mapa.getZoom() >= 12;
  let detalle = "";
  if (individuales) {
    pintarFocosIndividuales(lista);
    pintarLeyendaMapa("focos");
  } else {
    const r = pintarCeldas(lista);
    pintarLeyendaMapa("celdas", r);
    detalle = ` · densidad en cuadros de ~${fmt(r.km)} km`;
  }
  $("mapa-filtro").textContent =
    `${fmt(n)} ${n === 1 ? "foco" : "focos"} ${estado.dia ? `el ${fechaPrecisa(estado.dia)}`
      : estado.rango ? `del ${fechaLegible(estado.rango.desde)} al ${fechaLegible(estado.rango.hasta)}` : `en ${estado.anio}`}${detalle}`;
  const aviso = $("aviso-truncado");
  aviso.hidden = !datos.truncado;
  if (datos.truncado) {
    aviso.textContent = `Se muestran los primeros ${fmt(n)} focos por orden de fecha: faltan los más recientes. ` +
      "Elija un día, acote el rango o un área más pequeña.";
  }
  const modo = $("mapa-modo");
  if (modo) {
    modo.textContent = individuales
      ? "Cada foco: tamaño y color según su intensidad (FRP), forma según el sensor y transparencia según la confianza. " +
        `La huella del píxel aparece desde el zoom ${ZOOM_HUELLA}.`
      : "Densidad: cuadros coloreados según el número de focos del periodo, con los cortes de la leyenda. " +
        "El tamaño del cuadro se ajusta al zoom. Elija un día en el calendario para ver cada foco. Aléjese para ver el globo 3D.";
  }
}

// ------------------------------------------------------------------ panel
const hayDatos = (c) => Array.isArray(c.dias) && c.dias.length > 0 && c.desde != null;

function pintarBase(c) {
  const b = c.linea_base;
  const caja = $("base-estado");
  if (!b) { caja.innerHTML = `<p class="tenue">Sin información de línea base.</p>`; return; }
  if (b.estado !== "suficiente") {
    caja.innerHTML = `<div class="aviso-caja"><strong>Base insuficiente. </strong>` +
      `${fmt(b.anios_disponibles)} año(s) con dato en el área; se requieren ${fmt(b.anios_minimos)}. ` +
      `No se marcan días inusuales.</div>`;
    return;
  }
  const inusuales = (c.dias ?? []).filter((d) => d.inusual).length;
  caja.innerHTML = `<div class="ok-caja"><strong>${fmt(inusuales)} día(s) inusual(es) en ${esc(estado.anio)}. </strong>` +
    `Umbral: P${fmt(b.percentil)} de ${esc(b.metrica)} en los otros años, mismo día del año ± ${fmt(b.ventana_dias)} días ` +
    `(se excluye el año evaluado). Años con dato: ${esc((b.anios_usados ?? []).join(", "))}.</div>` +
    `<p class="tenue">${esc(b.nota_ventana)}</p>`;
}

function pintarClima(c) {
  const caja = $("clima");
  if (!c.climatologia_mensual) {
    caja.innerHTML = `<p class="tenue">Requiere base suficiente.</p>`;
    return;
  }
  const picos = c.meses_pico ?? [];
  const meses = Array.from({ length: 12 }, (_, i) => c.climatologia_mensual[String(i + 1)] ?? { media: 0, anios: 0 });
  const max = Math.max(1, ...meses.map((m) => m.media));
  caja.innerHTML = `<div class="barras">${meses.map((m, i) => {
    const pico = picos.includes(i + 1);
    return `<div class="barra-mes${pico ? " pico" : ""}" title="${MESES[i]}: media ${esc(fmt(m.media, 1))} celdas activas (${esc(fmt(m.anios))} años)">` +
      `<i style="height:${(100 * m.media) / max}%"></i>${MESES[i]}</div>`;
  }).join("")}</div>` +
    `<p class="tenue">Media mensual de ${ETIQUETA_METRICA}. Meses pico: ${esc(picos.map((m) => MESES[m - 1]).join(", ") || "—")}.</p>`;
}

/** Este año (suma mensual de la métrica armonizada) frente al promedio histórico mensual, en SVG propio. */
function pintarComparacion(c) {
  const caja = $("comparacion");
  const dias = c.dias ?? [];
  if (!dias.length) {
    caja.innerHTML = `<p class="tenue">Sin datos para comparar este año con el promedio histórico.</p>`;
    return;
  }
  const anio = estado.anio;
  const suma = Array(12).fill(null);
  const diasMes = Array(12).fill(0);
  dias.forEach((d) => {
    const m = Number(String(d.fecha_utc).slice(5, 7)) - 1;
    if (m >= 0 && m < 12) { suma[m] = (suma[m] ?? 0) + valorDia(d); diasMes[m] += 1; }
  });
  // Un mes es incompleto si el rango cubierto no tiene todos sus días (p. ej. el año en curso).
  const incompleto = diasMes.map((n, i) => n > 0 && n < new Date(Date.UTC(Number(anio), i + 1, 0)).getUTCDate());
  const clim = c.climatologia_mensual || null;
  const media = Array.from({ length: 12 }, (_, i) => {
    const v = clim ? clim[String(i + 1)] : null;
    return v && v.media != null ? Number(v.media) : null;
  });
  const picos = c.meses_pico ?? [];
  const max = Math.max(1, ...suma.filter((v) => v != null), ...media.filter((v) => v != null));
  const W = 360, H = 170, IZQ = 38, DER = 6, ARR = 10, ABA = 34;
  const pw = W - IZQ - DER, ph = H - ARR - ABA, banda = pw / 12, bw = banda * 0.6;
  const yDe = (v) => ARR + ph - (ph * v) / max;
  const p = [`<line class="cmp-eje" x1="${IZQ}" y1="${ARR + ph}" x2="${W - DER}" y2="${ARR + ph}"/>`,
    `<line class="cmp-eje" x1="${IZQ}" y1="${ARR}" x2="${IZQ}" y2="${ARR + ph}"/>`,
    `<text class="cmp-texto" x="${IZQ - 4}" y="${ARR + 8}" text-anchor="end" font-size="9">${esc(fmt(max, max < 10 ? 1 : 0))}</text>`,
    `<text class="cmp-texto" x="${IZQ - 4}" y="${ARR + ph}" text-anchor="end" font-size="9">0</text>`];
  for (let i = 0; i < 12; i++) {
    const x = IZQ + i * banda, cx = x + banda / 2;
    if (suma[i] != null) {
      const y = yDe(suma[i]);
      p.push(`<rect class="cmp-anio${incompleto[i] ? " cmp-incompleto" : ""}" x="${x + (banda - bw) / 2}" y="${y}" width="${bw}" height="${ARR + ph - y}"/>`);
    } else {
      p.push(`<text class="cmp-texto" x="${cx}" y="${ARR + ph - 4}" font-size="7" text-anchor="start" ` +
        `transform="rotate(-90 ${cx + 2} ${ARR + ph - 4})">sin datos</text>`);
    }
    if (media[i] != null) {
      const y = yDe(media[i]);
      p.push(`<line class="cmp-media" x1="${x + 1}" y1="${y}" x2="${x + banda - 1}" y2="${y}" stroke-width="2.5"/>`);
    }
    p.push(`<text class="cmp-texto" x="${cx}" y="${ARR + ph + 13}" font-size="9" text-anchor="middle"` +
      `${picos.includes(i + 1) ? ' font-weight="700"' : ""}>${MESES[i]}</text>`);
  }
  const conDato = suma.filter((v) => v != null);
  const total = conDato.reduce((s, v) => s + v, 0);
  const etiqueta = `Actividad armonizada por mes en ${anio}: ${fmt(total)} celdas activas en total` +
    (clim ? `, frente al promedio histórico mensual (línea). Meses pico: ${picos.map((m) => MESES_LARGOS[m - 1]).join(", ") || "ninguno"}.`
      : ". Sin promedio histórico: base insuficiente.");
  const filas = MESES.map((m, i) =>
    `<tr><th scope="row">${picos.includes(i + 1) ? `<strong>${m}</strong>` : m}</th>` +
    `<td>${suma[i] == null ? "sin datos" : `${esc(fmt(suma[i], 1))} celdas activas${incompleto[i] ? ` (mes incompleto: ${diasMes[i]} días)` : ""}`}</td>` +
    (clim ? `<td>${media[i] == null ? "—" : `${esc(fmt(media[i], 1))} celdas activas`}</td>` : "") + `</tr>`).join("");
  caja.innerHTML =
    `<h3 class="cmp-titulo">Este año frente al promedio histórico</h3>` +
    `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(etiqueta)}" preserveAspectRatio="xMidYMid meet">${p.join("")}</svg>` +
    `<p class="tenue">Barras: ${ETIQUETA_METRICA} de ${esc(anio)} por mes${clim ? ". Línea: promedio histórico mensual" : ""}.` +
    `${incompleto.some(Boolean) ? " Las barras con borde punteado son meses incompletos y no se comparan de igual a igual con el promedio." : ""}</p>` +
    (clim ? `<p class="tenue">El promedio histórico usa los meses completos de todos los años disponibles, incluido este año si el mes está completo.</p>`
      : `<p class="tenue">Sin promedio: base insuficiente.</p>`) +
    `<details><summary>Ver como tabla</summary><table class="tabla-cmp"><thead><tr><th scope="col">Mes</th>` +
    `<th scope="col">${esc(anio)}</th>${clim ? `<th scope="col">Promedio</th>` : ""}</tr></thead><tbody>${filas}</tbody></table></details>`;
}

function periodosOrdenados(c) {
  return [...(c.periodos_inusuales ?? [])].sort((a, b) => b.dias - a.dias || b.maximo - a.maximo);
}

function textoPeriodo(p) {
  return p.fin !== p.inicio ? `${fechaLegible(p.inicio)} → ${fechaLegible(p.fin)}` : fechaLegible(p.inicio);
}

function pintarPeriodos(c) {
  const lista = $("periodos");
  if (!c.periodos_inusuales) { lista.innerHTML = `<li class="tenue">Requiere base suficiente.</li>`; return; }
  if (!c.periodos_inusuales.length) { lista.innerHTML = `<li class="tenue">Sin días inusuales en el año.</li>`; return; }
  const orden = periodosOrdenados(c).slice(0, 6);
  lista.innerHTML = orden.map((p) =>
    `<li><a href="#" data-dia="${esc(p.inicio)}">${esc(textoPeriodo(p))}</a> ` +
    `<span class="tenue">(${esc(p.inicio)}${p.fin !== p.inicio ? ` → ${esc(p.fin)}` : ""})</span>` +
    ` · ${fmt(p.dias)} día(s), máx. ${fmt(p.maximo, 1)} celdas activas en un día</li>`).join("");
  lista.querySelectorAll("a").forEach((a) => a.addEventListener("click", (ev) => {
    ev.preventDefault(); seleccionarDia(a.dataset.dia);
  }));
}

function pintarIncertidumbre(c) {
  const i = c.incertidumbre ?? {};
  const res = i.resolucion_m ?? {};
  const pasadas = Object.entries(i.horario_pasada_utc ?? {})
    .map(([sat, p]) => `${esc(sat)}: ${esc(p.min)}–${esc(p.max)} UTC (${fmt(p.n)} focos)`).join("<br>") || "—";
  const clases = Object.entries(i.clases_confianza ?? {}).map(([k, v]) => `${esc(k)} ${fmt(v)}`).join(" · ") || "—";
  const anios = (i.anios_con_dato ?? []).join(", ");
  $("incertidumbre").innerHTML =
    `<dt>Resolución</dt><dd>MODIS ${fmt(res.MODIS)} m · VIIRS ${fmt(res.VIIRS)} m</dd>` +
    `<dt>Grilla</dt><dd>${fmt(i.grilla_deg, 3)}° (~1 km)</dd>` +
    `<dt>Pasadas UTC</dt><dd>${pasadas}</dd>` +
    `<dt>Confianza</dt><dd>${clases}</dd>` +
    `<dt>Días con dato</dt><dd>${fmt(i.porcentaje_dias_con_dato, 1)} % de ${fmt(i.dias_en_rango)} días</dd>` +
    `<dt>Años con dato</dt><dd>${esc(anios) || "—"}</dd>` +
    `<dt>Reglas</dt><dd>${esc(c.rules_version)}</dd>`;
}

const ORIGENES = {
  sintetico: ["origen-sintetico", "DATOS SINTÉTICOS (demostración)",
    "Datos inventados para la demostración: no describen incendios reales."],
  real: ["origen-real", "Datos reales NASA FIRMS",
    "Detecciones reales del archivo público de NASA FIRMS."],
  mixto: ["origen-mixto", "Datos mixtos: reales y sintéticos",
    "El conjunto de datos cargado mezcla detecciones reales con datos sintéticos de demostración."],
};

function pintarCabecera(c) {
  const insignia = $("insignia-calidad");
  insignia.className = "insignia " + (c.preliminar ? "preliminar" : "estandar");
  insignia.textContent = c.preliminar ? "PRELIMINAR · incluye datos NRT"
    : c.calidad === "estandar" ? "Calidad estándar (definitiva)" : `Calidad ${c.calidad ?? "sin datos"}`;
  insignia.title = c.preliminar
    ? "Incluye datos casi en tiempo real (NRT) que pueden corregirse."
    : "Datos de la versión estándar definitiva.";
  const [clase, texto, ayuda] = ORIGENES[c.origen_datos] ??
    ["origen-desconocido", "Origen de los datos desconocido", "La API no indicó si los datos son reales o sintéticos."];
  const o = $("insignia-origen");
  o.className = `insignia ${clase}`;
  o.textContent = texto;
  o.title = ayuda;
  $("resumen-origen").hidden = c.origen_datos !== "sintetico";
  $("insignia-version").textContent = c.rules_version ?? "";
  $("cita").textContent = c.cita;
  $("aviso").textContent = c.aviso;
}

/** Resumen en lenguaje sencillo, generado SOLO con la respuesta de /calendario. */
function listaY(items) {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

/** Valor del día en la métrica activa (por defecto, celdas activas equivalentes; ADR 0011). */
const valorDia = (d) => (d.valor ?? d.n_brutas ?? 0);
const ETIQUETA_METRICA = "celdas activas (armonizado)";

function resumir(c) {
  const anio = estado.anio;
  if (!hayDatos(c)) return `No hay observaciones para esta área en ${anio}.`;
  const dias = c.dias;
  const primero = dias[0].fecha_utc, ultimo = dias[dias.length - 1].fecha_utc;
  const completo = primero === `${anio}-01-01` && ultimo === `${anio}-12-31`;
  const rango = fechaLegible(primero).replace(/ \d{4}$/, "");
  const finRango = fechaLegible(ultimo).replace(/ \d{4}$/, "");
  const cabeza = completo ? `En ${anio}` : `En ${anio} (del ${rango} al ${finRango})`;
  const total = dias.reduce((s, d) => s + (d.n_brutas || 0), 0);
  const conFocos = dias.filter((d) => d.n_brutas > 0).length;
  const armonizado = dias.reduce((s, d) => s + valorDia(d), 0);
  if (total === 0) return `${cabeza} no se detectaron focos de calor en esta área.` + (c.preliminar ? " Incluye datos preliminares (NRT) que pueden cambiar." : "");
  const partes = [`${cabeza} el área tuvo ${fmt(total)} ${total === 1 ? "foco" : "focos"} de calor en ${fmt(conFocos)} ${conFocos === 1 ? "día" : "días"} ` +
    `(${fmt(armonizado)} celdas activas en la serie armonizada, comparable entre años).`];
  const b = c.linea_base;
  if (b && b.estado !== "suficiente") {
    partes.push(`Todavía no se puede decir qué días fueron inusuales: hay ${fmt(b.anios_disponibles)} ${b.anios_disponibles === 1 ? "año" : "años"} de datos y se necesitan ${fmt(b.anios_minimos)}.`);
  } else {
    const inusuales = dias.filter((d) => d.inusual === true).length;
    if (inusuales === 0) {
      partes.push("Ningún día superó lo habitual.");
    } else {
      let frase = `${fmt(inusuales)} ${inusuales === 1 ? "día estuvo" : "días estuvieron"} fuera de lo normal`;
      const p = periodosOrdenados(c)[0];
      if (p) {
        frase += (p.inicio === p.fin ? `; el día más crítico fue el ${fechaLegible(p.inicio)} `
          : `; el periodo más crítico fue del ${fechaLegible(p.inicio)} al ${fechaLegible(p.fin)} `) +
          `(${fmt(p.dias)} ${p.dias === 1 ? "día" : "días seguidos"}, hasta ${fmt(p.maximo, 1)} celdas activas en un día)`;
      }
      partes.push(frase + ".");
    }
    const picos = (c.meses_pico ?? []).map((m) => MESES_LARGOS[m - 1]).filter(Boolean);
    if (picos.length) partes.push(`Temporada alta: ${listaY(picos)}.`);
  }
  if (c.preliminar) partes.push("Incluye datos preliminares (NRT) que pueden cambiar.");
  return partes.join(" ");
}

// ------------------------------------------------------------------ calendario
function nivel(v, cortes) {
  if (!v) return 0;
  return v <= cortes[0] ? 1 : v <= cortes[1] ? 2 : v <= cortes[2] ? 3 : 4;
}

const DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
let celdas = []; // rect.dia en el orden de c.dias (se rehace en cada pintado)
let diasCal = []; // c.dias del calendario pintado

function descripcionDia(d) {
  const n = d.n_brutas || 0;
  let t = `${fechaLegible(d.fecha_utc)}: ${fmt(valorDia(d), 1)} ${ETIQUETA_METRICA}; ${fmt(n)} ${n === 1 ? "foco" : "focos"} de calor`;
  if (d.inusual) t += d.umbral != null ? `; día inusual (umbral ${fmt(d.umbral, 1)})` : "; día inusual";
  if (d.preliminar) t += "; incluye datos preliminares";
  return t;
}

function ocultarTooltip() {
  const tip = $("tooltip-cal");
  tip.hidden = true;
  celdas.forEach((r) => r.removeAttribute("aria-describedby"));
}

function mostrarTooltip(rect) {
  const d = diasCal[celdas.indexOf(rect)];
  const tip = $("tooltip-cal");
  const tarjeta = tip.closest(".calendario-tarjeta");
  if (!d || !tarjeta) return;
  celdas.forEach((r) => r.removeAttribute("aria-describedby"));
  rect.setAttribute("aria-describedby", "tooltip-cal");
  const n = d.n_brutas || 0;
  let h = `<strong>${esc(fechaLegible(d.fecha_utc))}</strong> <span class="tenue">(${esc(d.fecha_utc)})</span><br>` +
    `<strong>${esc(fmt(valorDia(d), 1))}</strong> ${ETIQUETA_METRICA}${d.metodo && d.metodo !== "referencia" ? ` <span class="tenue">(${esc(d.metodo)})</span>` : ""}<br>` +
    `${esc(fmt(n))} ${n === 1 ? "foco" : "focos"} de calor (${esc(fmt(d.n_detecciones))} tras quitar duplicados)<br>` +
    `MODIS ${esc(fmt(d.n_modis))} · VIIRS ${esc(fmt(d.n_viirs))}`;
  if (d.umbral != null) h += `<br>Lo habitual para esta fecha: hasta ${esc(fmt(d.umbral, 1))} celdas activas`;
  if (d.inusual) h += `<br><strong>Fuera de lo normal</strong>`;
  if (d.preliminar) h += `<br>Preliminar (NRT)`;
  tip.innerHTML = h;
  tip.hidden = false;
  const t = tarjeta.getBoundingClientRect(), r = rect.getBoundingClientRect();
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  const maxIzq = Math.min(t.width, window.innerWidth - t.left) - tw - 4;
  let izq = r.left - t.left + r.width / 2 - tw / 2;
  izq = Math.max(4, Math.min(izq, maxIzq));
  let arriba = r.top - t.top - th - 6;
  if (arriba < 0) arriba = r.bottom - t.top + 6;
  tip.style.left = `${izq}px`;
  tip.style.top = `${arriba}px`;
}

/** Mueve el tabindex itinerante a la celda i y devuelve esa celda. */
function fijarTabindex(i) {
  celdas.forEach((r, k) => r.setAttribute("tabindex", k === i ? "0" : "-1"));
  return celdas[i];
}

function irACelda(i) {
  if (!celdas.length) return;
  const k = Math.max(0, Math.min(celdas.length - 1, i));
  const r = fijarTabindex(k);
  r.focus();
  mostrarTooltip(r);
}

function alternarDia(fecha) {
  seleccionarDia(fecha === estado.dia ? null : fecha);
}

function teclaCelda(ev) {
  const i = celdas.indexOf(ev.currentTarget);
  if (i < 0) return;
  const f = diasCal[i].fecha_utc;
  let destino = null;
  switch (ev.key) {
    case "ArrowUp": destino = i - 1; break;
    case "ArrowDown": destino = i + 1; break;
    case "ArrowLeft": destino = i - 7; break;
    case "ArrowRight": destino = i + 7; break;
    case "Home": destino = 0; break;
    case "End": destino = celdas.length - 1; break;
    case "PageUp":
    case "PageDown": {
      let a = Number(f.slice(0, 4)), m = Number(f.slice(5, 7)) + (ev.key === "PageUp" ? -1 : 1);
      if (m < 1) { m = 12; a -= 1; } else if (m > 12) { m = 1; a += 1; }
      const pref = `${a}-${String(m).padStart(2, "0")}-`;
      const del_mes = diasCal.map((d, k) => [d.fecha_utc, k]).filter(([x]) => x.startsWith(pref));
      if (del_mes.length) destino = del_mes[Math.min(Number(f.slice(8, 10)), del_mes.length) - 1][1];
      else return; // mes fuera de cobertura: no se maneja la tecla
      break;
    }
    case "Enter":
    case " ":
      ev.preventDefault();
      alternarDia(f);
      return;
    case "Escape":
      ev.preventDefault();
      ocultarTooltip();
      if (estado.dia) seleccionarDia(null);
      return;
    default:
      return;
  }
  ev.preventDefault();
  irACelda(destino);
}

/** Leyenda numérica de la escala del calendario, con los mismos cortes que pintan las celdas. */
function pintarLeyendaEscala(cortes, hayValores) {
  const caja = $("leyenda-escala");
  if (!caja) return;
  const [a, b, c] = cortes;
  // La métrica armonizada puede tener decimales (eras calibradas): cortes como «hasta», «–», «más de».
  const v = (x) => fmt(x, x < 10 ? 1 : 0);
  const tramos = hayValores
    ? [["e0", "0"], ["e1", `hasta ${v(a)}`], ["e2", b > a ? `${v(a)}–${v(b)}` : "—"], ["e3", c > b ? `${v(b)}–${v(c)}` : "—"], ["e4", `más de ${v(c)}`]]
    : [["e0", "0"]];
  caja.innerHTML = tramos.filter(([, txt]) => txt !== "—")
    .map(([cls, txt]) => `<span class="tramo"><i class="esc ${cls}"></i>${esc(txt)}</span>`).join("") +
    `<span class="tenue"> ${ETIQUETA_METRICA} por día</span>`;
}

function pintarCalendario(c) {
  const dias = c.dias ?? [];
  const cont = $("calendario");
  celdas = [];
  diasCal = [];
  $("tooltip-cal").hidden = true;
  if (!dias.length) {
    cont.innerHTML = `<p class="tenue">No hay días con datos para mostrar en el calendario.</p>`;
    $("cal-resumen").textContent = "";
    return;
  }
  diasCal = dias;
  const valores = dias.map(valorDia).filter((v) => v > 0).sort((a, b) => a - b);
  const q = (p) => valores.length ? valores[Math.min(valores.length - 1, Math.floor(p * valores.length))] : 1;
  const cortes = [q(0.25), q(0.5), q(0.75)];
  pintarLeyendaEscala(cortes, valores.length > 0);
  // Pantallas táctiles estrechas: celdas de 24 px (WCAG 2.2, 2.5.8); el calendario se
  // desplaza dentro de su tarjeta (auditoría UI/UX, hallazgo 4).
  const tactil = window.matchMedia("(max-width: 600px)").matches;
  const T = tactil ? 24 : 13, G = tactil ? 3 : 2, X0 = 26, Y0 = 18;
  const primero = new Date(dias[0].fecha_utc + "T00:00:00Z");
  const desfase = (primero.getUTCDay() + 6) % 7; // lunes = 0
  const semanas = Math.ceil((dias.length + desfase) / 7);
  const ancho = X0 + semanas * (T + G), alto = Y0 + 7 * (T + G);
  const textos = [];
  ["L", "", "X", "", "V", "", "D"].forEach((t, i) => {
    if (t) textos.push(`<text class="cal-texto" x="0" y="${Y0 + i * (T + G) + 10}" font-size="10" aria-hidden="true">${t}</text>`);
  });
  const filas = Array.from({ length: 7 }, () => []);
  let inicial = dias.findIndex((d) => d.fecha_utc === estado.dia);
  if (inicial < 0) inicial = Math.max(0, dias.findIndex((d) => d.n_brutas > 0));
  dias.forEach((d, k) => {
    const pos = k + desfase, col = Math.floor(pos / 7), fila = pos % 7;
    const x = X0 + col * (T + G), y = Y0 + fila * (T + G);
    const fecha = d.fecha_utc;
    if (fecha.endsWith("-01")) {
      textos.push(`<text class="cal-texto" x="${x}" y="11" font-size="10" aria-hidden="true">${MESES[Number(fecha.slice(5, 7)) - 1]}</text>`);
    }
    const lv = nivel(valorDia(d), cortes);
    const sel = estado.dia === fecha;
    const clases = `dia${d.inusual ? " inusual" : ""}${sel ? " sel" : ""}`;
    filas[fila].push(`<rect class="${clases}" role="gridcell" data-dia="${esc(fecha)}" tabindex="${k === inicial ? 0 : -1}" ` +
      `aria-selected="${sel}" aria-label="${esc(descripcionDia(d))}" x="${x}" y="${y}" width="${T}" height="${T}" rx="2" ` +
      `fill="var(--e${lv})"/>`);
    if (d.preliminar && d.n_brutas > 0) {
      filas[fila].push(`<circle class="nrt-punto" cx="${x + T / 2}" cy="${y + T / 2}" r="1.6" pointer-events="none"/>`);
    }
  });
  const grupos = filas.map((f, i) => `<g role="row" aria-label="${DIAS_SEMANA[i]}">${f.join("")}</g>`).join("");
  cont.innerHTML = `<svg viewBox="0 0 ${ancho} ${alto}" width="${ancho}" height="${alto}" role="grid" ` +
    `aria-label="Calendario de focos de calor de ${esc(estado.anio)}">${textos.join("")}${grupos}</svg>`;
  // Orden de c.dias (no el del DOM, que va por filas).
  const porFecha = new Map([...cont.querySelectorAll("rect.dia")].map((r) => [r.dataset.dia, r]));
  celdas = dias.map((d) => porFecha.get(d.fecha_utc));
  celdas.forEach((r) => {
    r.addEventListener("click", () => { alternarDia(r.dataset.dia); });
    r.addEventListener("keydown", teclaCelda);
    r.addEventListener("mouseenter", () => mostrarTooltip(r));
    r.addEventListener("mouseleave", () => { if (document.activeElement !== r) ocultarTooltip(); });
    r.addEventListener("focus", () => mostrarTooltip(r));
    r.addEventListener("blur", ocultarTooltip);
  });
  const total = dias.reduce((s, d) => s + d.n_brutas, 0);
  const arm = dias.reduce((s, d) => s + valorDia(d), 0);
  $("cal-resumen").textContent = `${fmt(arm)} ${ETIQUETA_METRICA} y ${fmt(total)} focos brutos en ${fmt(dias.filter((d) => d.n_brutas).length)} días. ` +
    `Haga clic o use el teclado en un día para verlo en el mapa.`;
}

// ------------------------------------------------------------------ resumen plurianual (H8-04)
let resumenGen = 0;

async function cargarResumen() {
  const gen = ++resumenGen;
  const caja = $("matriz");
  if (caja) caja.innerHTML = `<p class="tenue">Calculando el calendario de quema…</p>`;
  try {
    const r = await pedir(`/resumen?${filtroArea()}`);
    if (gen !== resumenGen) return;
    estado.resumen = r;
    pintarMatriz(r);
    pintarMesReciente(r);
  } catch (err) {
    if (gen !== resumenGen) return;
    if (caja) caja.innerHTML = `<p class="tenue">No se pudo calcular el calendario de quema: ${esc(mensajeDe(err))}</p>`;
  }
}

/** «Calendario de quema»: años (filas) × meses (columnas), color por la métrica armonizada. */
function pintarMatriz(r) {
  const caja = $("matriz");
  if (!caja) return;
  const celdasM = r.matriz ?? [];
  if (!celdasM.length) { caja.innerHTML = `<p class="tenue">Sin datos.</p>`; return; }
  const anios = r.anios.map((a) => a.anio);
  const vals = celdasM.filter((c) => c.completo && c.valor > 0).map((c) => c.valor).sort((a, b) => a - b);
  const q = (p) => vals.length ? vals[Math.min(vals.length - 1, Math.floor(p * vals.length))] : 1;
  const cortes = [q(0.25), q(0.5), q(0.75)];
  const v = (x) => fmt(x, x < 10 ? 1 : 0);
  const maxAnio = Math.max(1, ...r.anios.map((a) => a.valor));
  const T = 22, G = 2, X0 = 44, Y0 = 18, BARRA = 120;
  const ancho = X0 + 12 * (T + G) + 12 + BARRA + 60, alto = Y0 + (anios.length + 1) * (T + G) + 4;
  const partes = [];
  MESES.forEach((m, i) => partes.push(`<text class="cmp-texto" x="${X0 + i * (T + G) + T / 2}" y="12" font-size="10" text-anchor="middle">${m}</text>`));
  const porClave = new Map(celdasM.map((c) => [`${c.anio}-${c.mes}`, c]));
  anios.forEach((a, fila) => {
    const y = Y0 + fila * (T + G);
    const sel = a === Number(estado.anio);
    partes.push(`<text class="cmp-texto${sel ? " anio-sel" : ""}" x="${X0 - 6}" y="${y + T / 2 + 4}" font-size="11" text-anchor="end">${a}</text>`);
    for (let m = 1; m <= 12; m++) {
      const c = porClave.get(`${a}-${m}`);
      const x = X0 + (m - 1) * (T + G);
      if (!c) { partes.push(`<rect x="${x}" y="${y}" width="${T}" height="${T}" rx="2" fill="none" stroke="var(--borde)" stroke-dasharray="2 2"><title>${MESES_LARGOS[m - 1]} ${a}: sin datos</title></rect>`); continue; }
      const lv = nivel(c.valor, cortes);
      const t = `${MESES_LARGOS[m - 1]} ${a}: ${v(c.valor)} celdas activas (armonizado), ${fmt(c.n_brutas)} focos brutos` +
        (c.completo ? "" : ` · mes incompleto (${c.dias} días)`);
      partes.push(`<rect class="celda-mat" data-anio="${a}" x="${x}" y="${y}" width="${T}" height="${T}" rx="2" fill="var(--e${lv})"` +
        `${c.completo ? "" : ' fill-opacity="0.45" stroke="var(--tinta)" stroke-dasharray="2 2"'}><title>${esc(t)}</title></rect>`);
    }
    const a_ = r.anios[fila];
    const bx = X0 + 12 * (T + G) + 12, bw = Math.max(1, (BARRA * a_.valor) / maxAnio);
    partes.push(`<rect x="${bx}" y="${y + 4}" width="${bw}" height="${T - 8}" rx="2" fill="var(--e3)"><title>${a}: ${v(a_.valor)} celdas activas en el año</title></rect>`);
    partes.push(`<text class="cmp-texto" x="${bx + bw + 4}" y="${y + T / 2 + 4}" font-size="10">${v(a_.valor)}${a_.completo ? "" : "*"}</text>`);
  });
  const yM = Y0 + anios.length * (T + G) + 2;
  partes.push(`<text class="cmp-texto" x="${X0 - 6}" y="${yM + T / 2 + 4}" font-size="10" text-anchor="end">mediana</text>`);
  for (let m = 1; m <= 12; m++) {
    const md = r.mediana_mensual[String(m)]?.mediana;
    const x = X0 + (m - 1) * (T + G);
    partes.push(`<rect x="${x}" y="${yM}" width="${T}" height="${T}" rx="2" fill="${md == null ? "none" : `var(--e${nivel(md, cortes)})`}" stroke="var(--tinta)" stroke-width="1.2"><title>Mediana de ${MESES_LARGOS[m - 1]} (${fmt(r.mediana_mensual[String(m)]?.n_anios)} años): ${md == null ? "—" : v(md)} celdas activas</title></rect>`);
  }
  const top = [...r.anios].filter((a) => a.completo).sort((a, b) => b.valor - a.valor).slice(0, 3).map((a) => a.anio);
  caja.innerHTML =
    `<div class="leyenda-cal leyenda-matriz"><span class="tramo"><i class="esc e1"></i>hasta ${v(cortes[0])}</span>` +
    `<span class="tramo"><i class="esc e2"></i>${v(cortes[0])}–${v(cortes[1])}</span><span class="tramo"><i class="esc e3"></i>${v(cortes[1])}–${v(cortes[2])}</span>` +
    `<span class="tramo"><i class="esc e4"></i>más de ${v(cortes[2])}</span><span class="tenue"> celdas activas por mes (armonizado)</span></div>` +
    `<div class="matriz-scroll"><svg id="svg-matriz" width="${ancho}" height="${alto}" role="img" ` +
    `aria-label="Calendario de quema ${anios[0]}–${anios[anios.length - 1]}: actividad armonizada por mes y año">${partes.join("")}</svg></div>` +
    `<p class="tenue">Años con más actividad: ${top.join(", ") || "—"}. Haga clic en una fila para ver ese año en el calendario diario. ` +
    `* año incompleto. Los meses con borde punteado están incompletos. La serie armonizada (ADR 0011) es comparable entre eras de sensores.</p>` +
    `<details><summary>Ver como tabla</summary><table class="tabla-cmp"><thead><tr><th scope="col">Año</th><th scope="col">Celdas activas (armonizado)</th><th scope="col">Focos brutos</th></tr></thead><tbody>` +
    r.anios.map((a) => `<tr><th scope="row">${a.anio}</th><td>${v(a.valor)}${a.completo ? "" : " (incompleto)"}</td><td>${fmt(a.n_brutas)}</td></tr>`).join("") +
    `</tbody></table></details>`;
  caja.querySelectorAll("rect.celda-mat").forEach((rc) => rc.addEventListener("click", () => {
    const anio = Number(rc.dataset.anio);
    if (anio === Number(estado.anio)) return;
    const sel = $("sel-anio");
    if (![...sel.options].some((o) => Number(o.value) === anio)) sel.insertAdjacentHTML("beforeend", `<option>${anio}</option>`);
    sel.value = anio; estado.anio = anio; estado.dia = null; cargar();
  }));
}

function pintarMesReciente(r) {
  const caja = $("mes-reciente");
  if (!caja) return;
  const m = r.mes_reciente;
  if (!m) { caja.innerHTML = `<p class="tenue">Sin datos.</p>`; return; }
  const nombre = `${MESES_LARGOS[m.mes - 1]} de ${m.anio}`;
  const v = (x) => fmt(x, x < 10 ? 1 : 0);
  if (m.mediana == null) {
    caja.innerHTML = `<p><strong>${esc(nombre)}</strong>: ${v(m.valor)} celdas activas. No hay años suficientes para calcular la mediana.</p>`;
    return;
  }
  const signo = m.anomalia_pct == null ? "" : m.anomalia_pct > 0 ? "por encima de" : m.anomalia_pct < 0 ? "por debajo de" : "igual a";
  const pct = m.anomalia_pct == null ? "—" : `${fmt(Math.abs(m.anomalia_pct), 0)} %`;
  caja.innerHTML =
    `<p class="cifra-grande ${m.anomalia_pct > 0 ? "sube" : "baja"}">${m.anomalia_pct > 0 ? "+" : m.anomalia_pct < 0 ? "−" : ""}${esc(pct)}</p>` +
    `<p><strong>${esc(nombre)}</strong>${m.completo ? "" : ` (en curso, ${m.dias} días)`}: ${v(m.valor)} celdas activas, ` +
    `${esc(pct)} ${signo} la mediana histórica (${v(m.mediana)}; ${fmt(m.n_anios_ref)} años).</p>` +
    `<p class="tenue">${esc(m.nota)}. Métrica armonizada (ADR 0011).</p>`;
}

// ------------------------------------------------------------------ rango, coordenadas y descargas (H8-05, H8-06)
function actualizarDescargas() {
  const desde = estado.rango?.desde ?? `${estado.anio}-01-01`;
  const hasta = estado.rango?.hasta ?? `${estado.anio}-12-31`;
  $("btn-csv").href = `/calendario.csv?${consulta(desde, hasta)}`;
  const focos = $("btn-csv-focos");
  if (focos) focos.href = `/detecciones.csv?${consulta(estado.dia ?? desde, estado.dia ?? hasta)}`;
}

function aplicarRango() {
  const d = $("rango-desde").value, h = $("rango-hasta").value;
  if (!d && !h) { estado.rango = null; actualizarDescargas(); cargarFocos(); mostrarEstado(""); return; }
  if (!d || !h) { mostrarEstado("error", "Indique las dos fechas del rango (desde y hasta)."); return; }
  if (d > h) { mostrarEstado("error", "La fecha «desde» debe ser anterior o igual a «hasta»."); return; }
  estado.rango = { desde: d, hasta: h };
  estado.dia = null;
  actualizarDescargas();
  mostrarEstado("cargando", "Cargando focos del rango…");
  cargarFocos().then(() => mostrarEstado("")).catch((err) => mostrarEstado("error", `No se pudieron cargar los focos: ${mensajeDe(err)}`));
}

function aplicarCoordenadas() {
  const ids = ["coord-w", "coord-s", "coord-e", "coord-n"];
  const v = ids.map((id) => Number(String($(id).value).replace(",", ".")));
  const [w, s, e, n] = v;
  if (v.some((x) => !Number.isFinite(x)) || ids.some((id) => $(id).value.trim() === "")) {
    mostrarEstado("error", "Escriba las cuatro coordenadas en grados decimales (oeste, sur, este, norte)."); return;
  }
  if (w < -180 || e > 180 || s < -90 || n > 90) { mostrarEstado("error", "Coordenadas fuera de rango: longitud ±180, latitud ±90."); return; }
  if (w >= e || s >= n) { mostrarEstado("error", "El oeste debe ser menor que el este y el sur menor que el norte."); return; }
  estado.bbox = [w, s, e, n];
  estado.area = null;
  estado.dia = null;
  const opcion = $("sel-area").querySelector('option[value="dibujo"]');
  opcion.disabled = false;
  opcion.textContent = "Coordenadas o rectángulo";
  $("sel-area").value = "dibujo";
  resaltarMunicipio(null);
  cargar();
}

/** Descarga un SVG autónomo: resuelve las variables CSS, añade título, área y cita. */
function descargarSVG(svg, nombre, titulo) {
  if (!svg) return;
  const copia = svg.cloneNode(true);
  const resolver = (txt) => String(txt).replace(/var\((--[\w-]+)\)/g, (_, n) => token(n) || "#888");
  copia.querySelectorAll("*").forEach((el) => {
    for (const at of ["fill", "stroke"]) if (el.getAttribute(at)?.includes("var(")) el.setAttribute(at, resolver(el.getAttribute(at)));
    if (el.classList.contains("cmp-texto")) el.setAttribute("fill", token("--tenue"));
    if (el.tagName === "rect" && el.classList.contains("dia") && !el.getAttribute("fill")) el.setAttribute("fill", token("--e0"));
  });
  const ancho = Number(copia.getAttribute("width")) || 800, alto = Number(copia.getAttribute("height")) || 200;
  const area = estado.calendario?.area?.nombre ?? `recuadro ${estado.bbox.join(", ")}`;
  copia.setAttribute("xmlns", svg.namespaceURI);
  copia.setAttribute("height", alto + 58);
  copia.setAttribute("viewBox", `0 -18 ${ancho} ${alto + 58}`);
  copia.insertAdjacentHTML("afterbegin", `<rect x="0" y="-18" width="${ancho}" height="${alto + 58}" fill="${token("--tarjeta")}"/>` +
    `<text x="0" y="-4" font-size="12" font-weight="700" fill="${token("--tinta")}">${esc(titulo)} · ${esc(area)}</text>`);
  copia.insertAdjacentHTML("beforeend",
    `<text x="0" y="${alto + 14}" font-size="9" fill="${token("--tenue")}">Datos: NASA FIRMS (LANCE / ESDIS). Métrica armonizada (ADR 0011), ${esc(estado.calendario?.rules_version ?? "")}.</text>` +
    `<text x="0" y="${alto + 28}" font-size="9" fill="${token("--tenue")}">Detecciones térmicas, no incendios confirmados. Harmonized Heat Neiva.</text>`);
  const blob = new Blob([new XMLSerializer().serializeToString(copia)], { type: "image/svg+xml" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nombre;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// ------------------------------------------------------------------ estado de carga
let reintento = null;

/** tipo: "cargando" | "vacio" | "error" | "" (reposo). */
function mostrarEstado(tipo, mensaje = "", alReintentar = null) {
  const caja = $("estado-carga");
  caja.className = tipo ? `estado ${tipo}` : "estado";
  $("estado-texto").textContent = mensaje;
  reintento = tipo === "error" ? alReintentar : null;
  $("btn-reintentar").hidden = !reintento;
}

// ------------------------------------------------------------------ carga
function filtroArea() {
  return estado.area ? `area=${encodeURIComponent(estado.area)}` : `bbox=${estado.bbox.join(",")}`;
}

function consulta(desde, hasta) {
  return `${filtroArea()}&desde=${desde}&hasta=${hasta}`;
}

// Un contador y un AbortController por tipo de carga: solo la última petición pinta.
const cargas = {
  anio: { gen: 0, ctrl: null },
  focos: { gen: 0, ctrl: null },
};

function iniciarCarga(tipo) {
  const k = cargas[tipo];
  if (k.ctrl) k.ctrl.abort();
  k.ctrl = new AbortController();
  k.gen += 1;
  return { gen: k.gen, señal: k.ctrl.signal, vigente: () => k.gen === cargas[tipo].gen };
}

/** Devuelve true si pintó; false si quedó obsoleta. Lanza el resto de errores. */
async function cargarFocos() {
  const h = iniciarCarga("focos");
  const desde = estado.dia ?? estado.rango?.desde ?? `${estado.anio}-01-01`;
  const hasta = estado.dia ?? estado.rango?.hasta ?? `${estado.anio}-12-31`;
  try {
    const datos = await pedir(`/detecciones?${consulta(desde, hasta)}&limite=50000`, h.señal);
    if (!h.vigente()) return false;
    pintarFocos(datos);
    return true;
  } catch (err) {
    if (esAborto(err) || !h.vigente()) return false;
    throw err;
  }
}

async function seleccionarDia(dia) {
  estado.dia = dia;
  actualizarEnlaceFirms();
  actualizarDescargas();
  actualizarImagen();
  pintarMeteo();
  celdas.forEach((r, k) => {
    const es = r.dataset.dia === dia;
    r.classList.toggle("sel", es);
    r.setAttribute("aria-selected", String(es));
    if (es) fijarTabindex(k);
  });
  mostrarEstado("cargando", "Cargando focos…");
  try {
    if (await cargarFocos()) mostrarEstado("");
  } catch (err) {
    mostrarEstado("error", `No se pudieron cargar los datos: ${mensajeDe(err)}`, () => seleccionarDia(dia));
  }
}

function pintarVacio(c) {
  capaFocos.clearLayers();
  ultimosFocos = null;
  $("aviso-truncado").hidden = true;
  $("mapa-filtro").textContent = `Sin focos en ${estado.anio}`;
  $("resumen-texto").textContent = resumir(c);
}

/** opciones.encuadrarArea = false conserva la vista (zona explorada desde el globo). */
async function cargar(opciones = {}) {
  const { encuadrarArea = true } = opciones;
  if (vista === "globo") mostrarRegional();
  const h = iniciarCarga("anio");
  if (cargas.focos.ctrl) cargas.focos.ctrl.abort();
  cargas.focos.gen += 1;
  mostrarEstado("cargando", "Cargando datos…");
  try {
    dibujarArea();
    const [w, s, e, n] = estado.bbox;
    if (!estado.anio) {
      const inicial = await pedir(`/calendario?${filtroArea()}`, h.señal);
      if (!h.vigente()) return;
      const anios = inicial.incertidumbre?.anios_con_dato ?? [];
      const sel = $("sel-anio");
      sel.innerHTML = anios.map((a) => `<option>${esc(a)}</option>`).join("");
      estado.anio = anios.length ? anios[anios.length - 1] : new Date().getUTCFullYear();
      if (!anios.length) sel.innerHTML = `<option>${esc(estado.anio)}</option>`;
      sel.value = estado.anio;
    }
    const q = consulta(`${estado.anio}-01-01`, `${estado.anio}-12-31`);
    const c = await pedir(`/calendario?${q}`, h.señal);
    if (!h.vigente()) return;
    estado.calendario = c;
    $("cal-anio").textContent = estado.anio;
    actualizarDescargas();
    pintarCabecera(c); pintarBase(c); pintarClima(c); pintarComparacion(c); pintarPeriodos(c); pintarIncertidumbre(c); pintarCalendario(c);
    cargarResumen();
    if (!hayDatos(c)) {
      pintarVacio(c);
      if (encuadrarArea) encuadrar(() => mapa.fitBounds([[s, w], [n, e]], { padding: [10, 10] }));
      mostrarEstado("vacio", "No hay observaciones para esta área y año.");
      return;
    }
    $("resumen-texto").textContent = resumir(c);
    actualizarImagen();
    actualizarEnlaceFirms();
    pintarMeteo();
    const ok = await cargarFocos();
    if (!h.vigente() || !ok) return;
    if (encuadrarArea) encuadrar(() => mapa.fitBounds([[s, w], [n, e]], { padding: [10, 10] }));
    mostrarEstado("");
  } catch (err) {
    if (esAborto(err) || !h.vigente()) return;
    mostrarEstado("error", `No se pudieron cargar los datos: ${mensajeDe(err)}`, cargar);
    $("resumen-texto").textContent = "No se pudo generar el resumen porque faltan los datos.";
  }
}

$("sel-area").addEventListener("change", (ev) => {
  const v = ev.target.value;
  if (v !== "dibujo") $("sel-area").querySelector('option[value="dibujo"]').textContent = "Rectángulo dibujado";
  if (AREAS[v]) { estado.bbox = AREAS[v]; estado.area = v === "huila" ? "huila" : null; resaltarMunicipio(null); estado.dia = null; cargar(); return; }
  if (v.startsWith("mun:")) {
    const f = municipios.find((m) => `mun:${m.properties.shapeID}` === v);
    if (!f) return;
    estado.bbox = f.properties.bbox;
    estado.area = v;
    resaltarMunicipio(f.properties.shapeID);
    estado.dia = null;
    cargar();
  }
});
$("sel-imagen").addEventListener("change", actualizarImagen);
$("btn-rango").addEventListener("click", aplicarRango);
$("btn-coordenadas").addEventListener("click", aplicarCoordenadas);
$("btn-svg-calendario").addEventListener("click", () =>
  descargarSVG($("calendario").querySelector("svg"), `calendario_${estado.anio}.svg`, `Calendario de actividad ${estado.anio}`));
$("btn-svg-matriz").addEventListener("click", () =>
  descargarSVG($("svg-matriz"), "calendario_de_quema.svg", "Calendario de quema (año × mes)"));
$("sel-anio").addEventListener("change", (ev) => { estado.anio = Number(ev.target.value); estado.dia = null; cargar(); });
$("btn-dibujar").addEventListener("click", activarDibujo);
$("btn-globo").addEventListener("click", () => (vista === "globo" ? mostrarRegional() : mostrarGlobo()));
$("btn-reintentar").addEventListener("click", () => { if (reintento) reintento(); });
iniciarTema();
cargarLimites();
cargar().then(() => {
  // Enlace directo al globo (demo): …/ui/#globo
  if (location.hash === "#globo") { encuadrar(() => mapa.setView([4, -72], 5, { animate: false })); mostrarGlobo(); }
});
