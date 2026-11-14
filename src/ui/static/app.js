/* Harmonized Heat Neiva: mapa y calendario de actividad (H4, H6).
 * Sin paso de compilación y sin dependencias remotas: Leaflet va incluido en vendor/.
 * Las teselas base de OpenStreetMap son opcionales; sin internet el mapa queda en gris.
 * Los colores viven en styles.css (variables por tema); aquí solo se asignan clases.
 */
"use strict";

const AREAS = {
  huila: [-76.7, 1.4, -74.3, 3.9], // bbox aproximado (firms_schema.HUILA_BBOX, por confirmar)
  neiva: [-75.53, 2.68, -75.03, 3.18], // Neiva (2,93; -75,28) ± 0,25°
};
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const CLAVE_TEMA = "hhn-tema";

const estado = { bbox: AREAS.huila, anio: null, dia: null, calendario: null };

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

/** Vuelve a pintar lo que se dibuja en JS; los colores salen de CSS, así que basta con repintar. */
function repintarTema() {
  if (ultimosFocos) pintarFocos(ultimosFocos);
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
const mapa = L.map("mapa", { zoomControl: true, attributionControl: true, preferCanvas: true, renderer: lienzo }).setView([2.6, -75.5], 8);
const token = (nombre) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
let ultimosFocos = null;
// En la vista anual la rejilla depende del zoom: se rehace al acercar o alejar.
mapa.on("zoomend", () => { if (ultimosFocos && !estado.dia) pintarFocos(ultimosFocos); });
mapa.attributionControl.setPrefix(false);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 17,
  className: "teselas-base",
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(mapa);
// D-10: cita de FIRMS en el mapa (forma corta según la FAQ; la completa va en el pie).
mapa.attributionControl.addAttribution(
  'Focos: <a href="https://www.earthdata.nasa.gov/data/tools/firms">NASA FIRMS</a> (LANCE / ESDIS)'
);
const capaArea = L.layerGroup().addTo(mapa);
const capaFocos = L.layerGroup().addTo(mapa);

function dibujarArea() {
  capaArea.clearLayers();
  const [w, s, e, n] = estado.bbox;
  L.rectangle([[s, w], [n, e]], { className: "area-rect", weight: 1.5, fill: false, dashArray: "4 4" }).addTo(capaArea);
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
    const opcion = $("sel-area").querySelector('option[value="dibujo"]');
    opcion.disabled = false;
    $("sel-area").value = "dibujo";
    estado.dia = null;
    cargar();
  };
  mapa.on("mousedown", abajo).on("mousemove", mover).on("mouseup", arriba);
}

function popupFoco(d) {
  return `<strong>${esc(d.satelite)}</strong> · ${esc(d.sensor)}<br>` +
    `${esc(fechaHoraLegible(d.fecha_hora_utc))} <span class="tenue">(${esc(d.fecha_hora_utc)})</span><br>` +
    `Confianza: ${esc(d.confianza_clase)} (${esc(d.confianza_raw)})<br>` +
    `FRP (potencia radiativa del fuego): ${fmt(d.frp, 1)} MW · Calidad: ${esc(d.calidad)}${d.preliminar ? " <em>(preliminar)</em>" : ""}<br>` +
    `Huella nominal: ±${fmt(d.semilado_nominal_m)} m` +
    (d.n_fusionados ? `<br>Agrupa ${fmt(d.n_fusionados)} detección(es) duplicada(s)` : "");
}

/** Día seleccionado: cada foco con su huella nominal (círculo del tamaño del píxel). */
function pintarFocosIndividuales(lista) {
  const color = { modis: token("--modis"), viirs: token("--viirs") };
  const borde = token("--tinta");
  for (const d of lista) {
    const sensor = String(d.sensor).toLowerCase() === "viirs" ? "viirs" : "modis";
    L.circle([d.lat, d.lon], { renderer: lienzo, radius: d.semilado_nominal_m, color: color[sensor], weight: 1, fillColor: color[sensor], fillOpacity: 0.18 }).addTo(capaFocos);
    L.circleMarker([d.lat, d.lon], { renderer: lienzo, radius: 4, color: borde, weight: 1, fillColor: color[sensor], fillOpacity: 0.9 })
      .bindPopup(popupFoco(d)).addTo(capaFocos);
  }
}

/** Lado de la rejilla de densidad (grados) según el zoom: ~11 km lejos, la celda de 1 km de cerca. */
function ladoRejilla() {
  const z = mapa.getZoom();
  return z <= 8 ? 0.1 : z <= 9 ? 0.05 : z <= 10 ? 0.025 : 0.009;
}

/** Vista anual: rejilla de densidad (cuadros coloreados por número de focos). */
function pintarCeldas(lista) {
  const lado = ladoRejilla();
  const celdas = new Map();
  for (const d of lista) {
    const fila = Math.floor(d.lat / lado), col = Math.floor(d.lon / lado);
    const k = `${fila}:${col}`;
    const c = celdas.get(k) ?? { fila, col, n: 0, modis: 0, viirs: 0, dias: new Set() };
    c.n += 1;
    if (String(d.sensor).toLowerCase() === "viirs") c.viirs += 1; else c.modis += 1;
    c.dias.add(String(d.fecha_hora_utc).slice(0, 10));
    celdas.set(k, c);
  }
  const valores = [...celdas.values()].map((c) => c.n).sort((a, b) => a - b);
  const q = (p) => valores[Math.min(valores.length - 1, Math.floor(p * valores.length))] ?? 1;
  const cortes = [q(0.5), q(0.75), q(0.9)];
  const escala = [token("--e1"), token("--e2"), token("--e3"), token("--e4")];
  const borde = token("--tinta");
  const km = Math.round(lado * 111);
  for (const c of celdas.values()) {
    const nv = c.n <= cortes[0] ? 0 : c.n <= cortes[1] ? 1 : c.n <= cortes[2] ? 2 : 3;
    L.rectangle([[c.fila * lado, c.col * lado], [(c.fila + 1) * lado, (c.col + 1) * lado]], {
      renderer: lienzo, color: borde, weight: 0.4, opacity: 0.35, fillColor: escala[nv], fillOpacity: 0.78,
    }).bindPopup(
      `<strong>${fmt(c.n)} ${c.n === 1 ? "foco" : "focos"}</strong> en ${esc(estado.anio)} en este cuadro de ~${fmt(km)} km<br>` +
      `${fmt(c.dias.size)} ${c.dias.size === 1 ? "día" : "días"} con focos · MODIS ${fmt(c.modis)} · VIIRS ${fmt(c.viirs)}<br>` +
      `<span class="tenue">Acerque el mapa para más detalle o elija un día en el calendario para ver cada foco.</span>`,
    ).addTo(capaFocos);
  }
  return { n: celdas.size, km, cortes };
}

function pintarFocos(datos) {
  ultimosFocos = datos;
  capaFocos.clearLayers();
  const lista = datos.detecciones ?? [];
  const n = lista.length;
  let detalle = "";
  if (estado.dia) {
    pintarFocosIndividuales(lista);
  } else {
    const r = pintarCeldas(lista);
    detalle = ` · densidad en cuadros de ~${fmt(r.km)} km`;
  }
  $("mapa-filtro").textContent =
    `${fmt(n)} ${n === 1 ? "foco" : "focos"} ${estado.dia ? `el ${fechaPrecisa(estado.dia)}` : `en ${estado.anio}`}${detalle}` +
    (datos.truncado ? " (lista truncada)" : "");
  const modo = $("mapa-modo");
  if (modo) {
    modo.textContent = estado.dia
      ? "Vista del día: cada foco con su huella nominal; el círculo es el píxel, no la posición exacta del fuego."
      : "Vista del año: cuadros de densidad; más oscuro = más focos en el año. El tamaño del cuadro se ajusta al zoom. Elija un día en el calendario para ver cada foco con su huella.";
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
    return `<div class="barra-mes${pico ? " pico" : ""}" title="${MESES[i]}: media ${esc(fmt(m.media, 1))} focos (${esc(fmt(m.anios))} años)">` +
      `<i style="height:${(100 * m.media) / max}%"></i>${MESES[i]}</div>`;
  }).join("")}</div>` +
    `<p class="tenue">Media mensual de focos (n_brutas). Meses pico: ${esc(picos.map((m) => MESES[m - 1]).join(", ") || "—")}.</p>`;
}

/** Este año (suma mensual de n_brutas) frente al promedio histórico mensual, en SVG propio. */
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
    if (m >= 0 && m < 12) { suma[m] = (suma[m] ?? 0) + (d.n_brutas || 0); diasMes[m] += 1; }
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
  const etiqueta = `Focos de calor por mes en ${anio}: ${fmt(total)} en total` +
    (clim ? `, frente al promedio histórico mensual (línea). Meses pico: ${picos.map((m) => MESES_LARGOS[m - 1]).join(", ") || "ninguno"}.`
      : ". Sin promedio histórico: base insuficiente.");
  const filas = MESES.map((m, i) =>
    `<tr><th scope="row">${picos.includes(i + 1) ? `<strong>${m}</strong>` : m}</th>` +
    `<td>${suma[i] == null ? "sin datos" : `${esc(fmt(suma[i]))} focos${incompleto[i] ? ` (mes incompleto: ${diasMes[i]} días)` : ""}`}</td>` +
    (clim ? `<td>${media[i] == null ? "—" : `${esc(fmt(media[i], 1))} focos`}</td>` : "") + `</tr>`).join("");
  caja.innerHTML =
    `<h3 class="cmp-titulo">Este año frente al promedio histórico</h3>` +
    `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(etiqueta)}" preserveAspectRatio="xMidYMid meet">${p.join("")}</svg>` +
    `<p class="tenue">Barras: focos de calor de ${esc(anio)} por mes${clim ? ". Línea: promedio histórico mensual" : ""}.` +
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
    ` · ${fmt(p.dias)} día(s), máx. ${fmt(p.maximo)} focos en un día</li>`).join("");
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
  if (total === 0) return `${cabeza} no se detectaron focos de calor en esta área.` + (c.preliminar ? " Incluye datos preliminares (NRT) que pueden cambiar." : "");
  const partes = [`${cabeza} el área tuvo ${fmt(total)} ${total === 1 ? "foco" : "focos"} de calor en ${fmt(conFocos)} ${conFocos === 1 ? "día" : "días"}.`];
  const b = c.linea_base;
  if (b && b.estado !== "suficiente") {
    partes.push(`Todavía no se puede decir qué días fueron inusuales: hay ${fmt(b.anios_disponibles)} años de datos y se necesitan ${fmt(b.anios_minimos)}.`);
  } else {
    const inusuales = dias.filter((d) => d.inusual === true).length;
    if (inusuales === 0) {
      partes.push("Ningún día superó lo habitual.");
    } else {
      let frase = `${fmt(inusuales)} ${inusuales === 1 ? "día estuvo" : "días estuvieron"} fuera de lo normal`;
      const p = periodosOrdenados(c)[0];
      if (p) {
        frase += `; el periodo más crítico fue del ${fechaLegible(p.inicio)} al ${fechaLegible(p.fin)} ` +
          `(${fmt(p.dias)} ${p.dias === 1 ? "día" : "días seguidos"}, hasta ${fmt(p.maximo)} focos en un día)`;
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
  let t = `${fechaLegible(d.fecha_utc)}: ${fmt(n)} ${n === 1 ? "foco" : "focos"} de calor`;
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
    `${esc(fmt(n))} ${n === 1 ? "foco" : "focos"} de calor (${esc(fmt(d.n_detecciones))} tras quitar duplicados)<br>` +
    `MODIS ${esc(fmt(d.n_modis))} · VIIRS ${esc(fmt(d.n_viirs))}`;
  if (d.umbral != null) h += `<br>Lo habitual para esta fecha: hasta ${esc(fmt(d.umbral, 1))} focos`;
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
  const rango = (lo, hi) => (hi < lo ? "—" : lo === hi ? fmt(lo) : `${fmt(lo)}–${fmt(hi)}`);
  const tramos = hayValores
    ? [["e0", "0"], ["e1", rango(1, a)], ["e2", rango(a + 1, b)], ["e3", rango(b + 1, c)], ["e4", `${fmt(c + 1)}+`]]
    : [["e0", "0"]];
  caja.innerHTML = tramos.map(([cls, txt]) => `<span class="tramo"><i class="esc ${cls}"></i>${esc(txt)}</span>`).join("") +
    `<span class="tenue"> focos por día</span>`;
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
  const valores = dias.map((d) => d.n_brutas).filter((v) => v > 0).sort((a, b) => a - b);
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
    const lv = nivel(d.n_brutas, cortes);
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
  $("cal-resumen").textContent = `${fmt(total)} focos brutos en ${fmt(dias.filter((d) => d.n_brutas).length)} días. ` +
    `Haga clic o use el teclado en un día para verlo en el mapa.`;
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
function consulta(desde, hasta) {
  return `bbox=${estado.bbox.join(",")}&desde=${desde}&hasta=${hasta}`;
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
  const desde = estado.dia ?? `${estado.anio}-01-01`;
  const hasta = estado.dia ?? `${estado.anio}-12-31`;
  try {
    const datos = await pedir(`/detecciones?${consulta(desde, hasta)}&limite=20000`, h.señal);
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
  $("mapa-filtro").textContent = `Sin focos en ${estado.anio}`;
  $("resumen-texto").textContent = resumir(c);
}

async function cargar() {
  const h = iniciarCarga("anio");
  if (cargas.focos.ctrl) cargas.focos.ctrl.abort();
  cargas.focos.gen += 1;
  mostrarEstado("cargando", "Cargando datos…");
  try {
    dibujarArea();
    const [w, s, e, n] = estado.bbox;
    if (!estado.anio) {
      const inicial = await pedir(`/calendario?bbox=${estado.bbox.join(",")}`, h.señal);
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
    $("btn-csv").href = `/calendario.csv?${q}`;
    pintarCabecera(c); pintarBase(c); pintarClima(c); pintarComparacion(c); pintarPeriodos(c); pintarIncertidumbre(c); pintarCalendario(c);
    if (!hayDatos(c)) {
      pintarVacio(c);
      mapa.fitBounds([[s, w], [n, e]], { padding: [10, 10] });
      mostrarEstado("vacio", "No hay observaciones para esta área y año.");
      return;
    }
    $("resumen-texto").textContent = resumir(c);
    const ok = await cargarFocos();
    if (!h.vigente() || !ok) return;
    mapa.fitBounds([[s, w], [n, e]], { padding: [10, 10] });
    mostrarEstado("");
  } catch (err) {
    if (esAborto(err) || !h.vigente()) return;
    mostrarEstado("error", `No se pudieron cargar los datos: ${mensajeDe(err)}`, cargar);
    $("resumen-texto").textContent = "No se pudo generar el resumen porque faltan los datos.";
  }
}

$("sel-area").addEventListener("change", (ev) => {
  if (AREAS[ev.target.value]) { estado.bbox = AREAS[ev.target.value]; estado.dia = null; cargar(); }
});
$("sel-anio").addEventListener("change", (ev) => { estado.anio = Number(ev.target.value); estado.dia = null; cargar(); });
$("btn-dibujar").addEventListener("click", activarDibujo);
$("btn-reintentar").addEventListener("click", () => { if (reintento) reintento(); });
iniciarTema();
cargar();
