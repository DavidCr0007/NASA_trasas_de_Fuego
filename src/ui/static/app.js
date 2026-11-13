/* Harmonized Heat Neiva: mapa y calendario de actividad (H4).
 * Sin paso de compilación y sin dependencias remotas: Leaflet va incluido en vendor/.
 * Las teselas base de OpenStreetMap son opcionales; sin internet el mapa queda en gris.
 */
"use strict";

const AREAS = {
  huila: [-76.7, 1.4, -74.3, 3.9], // bbox aproximado (firms_schema.HUILA_BBOX, por confirmar)
  neiva: [-75.53, 2.68, -75.03, 3.18], // Neiva (2,93; -75,28) ± 0,25°
};
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const COLOR = { MODIS: "#b45309", VIIRS: "#be123c" };

const estado = { bbox: AREAS.huila, anio: null, dia: null, calendario: null };

const $ = (id) => document.getElementById(id);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (n, d = 0) => (n == null ? "—" : Number(n).toLocaleString("es-CO", { maximumFractionDigits: d }));

async function pedir(ruta) {
  const r = await fetch(ruta);
  if (!r.ok) {
    let detalle = r.statusText;
    try { detalle = (await r.json()).detail ?? (await r.json()).detalle; } catch { /* sin cuerpo */ }
    throw new Error(`${r.status}: ${detalle}`);
  }
  return r.json();
}

// ------------------------------------------------------------------ mapa
const mapa = L.map("mapa", { zoomControl: true, attributionControl: true }).setView([2.6, -75.5], 8);
mapa.attributionControl.setPrefix(false);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 17,
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
  L.rectangle([[s, w], [n, e]], { color: "#1f1d1a", weight: 1.5, fill: false, dashArray: "4 4" }).addTo(capaArea);
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
    if (rect) rect.setBounds(b); else rect = L.rectangle(b, { color: "#4338ca", weight: 1.5 }).addTo(mapa);
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

function pintarFocos(datos) {
  capaFocos.clearLayers();
  for (const d of datos.detecciones) {
    const color = COLOR[d.sensor];
    const pop = `<strong>${esc(d.satelite)}</strong> · ${esc(d.sensor)}<br>` +
      `${esc(d.fecha_hora_utc.replace("T", " ").replace("Z", " UTC"))}<br>` +
      `Confianza: ${esc(d.confianza_clase)} (${esc(d.confianza_raw)})<br>` +
      `FRP: ${fmt(d.frp, 1)} MW · Calidad: ${esc(d.calidad)}${d.preliminar ? " <em>(preliminar)</em>" : ""}<br>` +
      `Huella nominal: ±${fmt(d.semilado_nominal_m)} m` +
      (d.n_fusionados ? `<br>Agrupa ${d.n_fusionados} detección(es) duplicada(s)` : "");
    L.circle([d.lat, d.lon], { radius: d.semilado_nominal_m, color, weight: 1, fillOpacity: 0.25 }).addTo(capaFocos);
    L.circleMarker([d.lat, d.lon], { radius: 3, color, weight: 1, fillOpacity: 0.9 }).bindPopup(pop).addTo(capaFocos);
  }
  const n = datos.detecciones.length;
  $("mapa-filtro").textContent =
    `${fmt(n)} foco(s) ${estado.dia ? `el ${estado.dia}` : `en ${estado.anio}`}` + (datos.truncado ? " (truncado)" : "");
}

// ------------------------------------------------------------------ panel
function pintarBase(c) {
  const b = c.linea_base;
  const caja = $("base-estado");
  if (b.estado !== "suficiente") {
    caja.innerHTML = `<div class="aviso-caja"><strong>Base insuficiente</strong>` +
      `${fmt(b.anios_disponibles)} año(s) con dato en el área; se requieren ${fmt(b.anios_minimos)}. ` +
      `No se marcan días inusuales.</div>`;
    return;
  }
  const inusuales = c.dias.filter((d) => d.inusual).length;
  caja.innerHTML = `<div class="ok-caja"><strong>${fmt(inusuales)} día(s) inusual(es) en ${esc(c.desde.slice(0, 4))}</strong>` +
    `Umbral: P${fmt(b.percentil)} de ${esc(b.metrica)} en los otros años, mismo día del año ± ${fmt(b.ventana_dias)} días ` +
    `(se excluye el año evaluado). Años con dato: ${esc(b.anios_usados.join(", "))}.</div>` +
    `<p class="tenue">${esc(b.nota_ventana)}</p>`;
}

function pintarClima(c) {
  const caja = $("clima");
  if (!c.climatologia_mensual) {
    caja.innerHTML = `<p class="tenue">Requiere base suficiente.</p>`;
    return;
  }
  const meses = Array.from({ length: 12 }, (_, i) => c.climatologia_mensual[String(i + 1)] ?? { media: 0, anios: 0 });
  const max = Math.max(1, ...meses.map((m) => m.media));
  caja.innerHTML = `<div class="barras">${meses.map((m, i) => {
    const pico = c.meses_pico.includes(i + 1);
    return `<div class="barra-mes${pico ? " pico" : ""}" title="${MESES[i]}: media ${fmt(m.media, 1)} focos (${m.anios} años)">` +
      `<i style="height:${(100 * m.media) / max}%"></i>${MESES[i]}</div>`;
  }).join("")}</div>` +
    `<p class="tenue">Media mensual de focos (n_brutas). Meses pico: ${c.meses_pico.map((m) => MESES[m - 1]).join(", ")}.</p>`;
}

function pintarPeriodos(c) {
  const lista = $("periodos");
  if (!c.periodos_inusuales) { lista.innerHTML = `<li class="tenue">Requiere base suficiente.</li>`; return; }
  if (!c.periodos_inusuales.length) { lista.innerHTML = `<li class="tenue">Sin días inusuales en el año.</li>`; return; }
  const orden = [...c.periodos_inusuales].sort((a, b) => b.dias - a.dias || b.maximo - a.maximo).slice(0, 6);
  lista.innerHTML = orden.map((p) =>
    `<li><a href="#" data-dia="${esc(p.inicio)}">${esc(p.inicio)}${p.fin !== p.inicio ? ` → ${esc(p.fin)}` : ""}</a>` +
    ` · ${p.dias} día(s), máx. ${fmt(p.maximo)} focos</li>`).join("");
  lista.querySelectorAll("a").forEach((a) => a.addEventListener("click", (ev) => {
    ev.preventDefault(); seleccionarDia(a.dataset.dia);
  }));
}

function pintarIncertidumbre(c) {
  const i = c.incertidumbre;
  const pasadas = Object.entries(i.horario_pasada_utc)
    .map(([sat, p]) => `${esc(sat)}: ${esc(p.min)}–${esc(p.max)} (${fmt(p.n)})`).join("<br>") || "—";
  const clases = Object.entries(i.clases_confianza).map(([k, v]) => `${esc(k)} ${fmt(v)}`).join(" · ");
  $("incertidumbre").innerHTML =
    `<dt>Resolución</dt><dd>MODIS ${fmt(i.resolucion_m.MODIS)} m · VIIRS ${fmt(i.resolucion_m.VIIRS)} m</dd>` +
    `<dt>Grilla</dt><dd>${fmt(i.grilla_deg, 3)}° (~1 km)</dd>` +
    `<dt>Pasadas UTC</dt><dd>${pasadas}</dd>` +
    `<dt>Confianza</dt><dd>${clases}</dd>` +
    `<dt>Días con dato</dt><dd>${fmt(i.porcentaje_dias_con_dato, 1)} % de ${fmt(i.dias_en_rango)}</dd>` +
    `<dt>Años con dato</dt><dd>${esc(i.anios_con_dato.join(", ")) || "—"}</dd>` +
    `<dt>Reglas</dt><dd>${esc(c.rules_version)}</dd>`;
}

function pintarCabecera(c) {
  const insignia = $("insignia-calidad");
  insignia.className = "insignia " + (c.preliminar ? "preliminar" : "estandar");
  insignia.textContent = c.preliminar ? "PRELIMINAR · incluye datos NRT" : `Calidad ${c.calidad ?? "—"}`;
  $("insignia-version").textContent = c.rules_version;
  $("cita").textContent = c.cita;
  $("aviso").textContent = c.aviso;
}

// ------------------------------------------------------------------ calendario
function nivel(v, cortes) {
  if (!v) return 0;
  return v <= cortes[0] ? 1 : v <= cortes[1] ? 2 : v <= cortes[2] ? 3 : 4;
}

function pintarCalendario(c) {
  const dias = c.dias;
  const valores = dias.map((d) => d.n_brutas).filter((v) => v > 0).sort((a, b) => a - b);
  const q = (p) => valores.length ? valores[Math.min(valores.length - 1, Math.floor(p * valores.length))] : 1;
  const cortes = [q(0.25), q(0.5), q(0.75)];
  const T = 13, G = 2, X0 = 26, Y0 = 18;
  const primero = new Date(dias[0].fecha_utc + "T00:00:00Z");
  const desfase = (primero.getUTCDay() + 6) % 7; // lunes = 0
  const semanas = Math.ceil((dias.length + desfase) / 7);
  const ancho = X0 + semanas * (T + G), alto = Y0 + 7 * (T + G);
  const partes = [];
  ["L", "", "X", "", "V", "", "D"].forEach((t, i) => {
    if (t) partes.push(`<text x="0" y="${Y0 + i * (T + G) + 10}" font-size="10" fill="#6b655c">${t}</text>`);
  });
  dias.forEach((d, k) => {
    const pos = k + desfase, col = Math.floor(pos / 7), fila = pos % 7;
    const x = X0 + col * (T + G), y = Y0 + fila * (T + G);
    const fecha = d.fecha_utc;
    if (fecha.endsWith("-01")) {
      partes.push(`<text x="${x}" y="11" font-size="10" fill="#6b655c">${MESES[Number(fecha.slice(5, 7)) - 1]}</text>`);
    }
    const lv = nivel(d.n_brutas, cortes);
    const titulo = `${fecha}: ${d.n_brutas} foco(s) brutos, ${d.n_detecciones} tras deduplicar` +
      (d.umbral != null ? ` · umbral ${fmt(d.umbral, 1)}` : "") + (d.inusual ? " · INUSUAL" : "") +
      (d.preliminar ? " · NRT preliminar" : "");
    partes.push(`<rect class="dia${estado.dia === fecha ? " sel" : ""}" data-dia="${fecha}" x="${x}" y="${y}" width="${T}" height="${T}" rx="2" ` +
      `fill="var(--e${lv})"${d.inusual ? ' stroke="#4338ca" stroke-width="2"' : ""}><title>${esc(titulo)}</title></rect>`);
    if (d.preliminar && d.n_brutas > 0) {
      partes.push(`<circle cx="${x + T / 2}" cy="${y + T / 2}" r="1.6" fill="#fff" pointer-events="none"/>`);
    }
  });
  $("calendario").innerHTML = `<svg width="${ancho}" height="${alto}" role="img" aria-label="Calendario ${esc(estado.anio)}">${partes.join("")}</svg>`;
  $("calendario").querySelectorAll("rect.dia").forEach((r) =>
    r.addEventListener("click", () => seleccionarDia(r.dataset.dia === estado.dia ? null : r.dataset.dia)));
  const total = dias.reduce((s, d) => s + d.n_brutas, 0);
  $("cal-resumen").textContent = `${fmt(total)} focos brutos en ${fmt(dias.filter((d) => d.n_brutas).length)} días. ` +
    `Haga clic en un día para verlo en el mapa; otro clic vuelve al año completo.`;
}

// ------------------------------------------------------------------ carga
function consulta(desde, hasta) {
  return `bbox=${estado.bbox.join(",")}&desde=${desde}&hasta=${hasta}`;
}

async function cargarFocos() {
  const desde = estado.dia ?? `${estado.anio}-01-01`;
  const hasta = estado.dia ?? `${estado.anio}-12-31`;
  pintarFocos(await pedir(`/detecciones?${consulta(desde, hasta)}&limite=20000`));
}

async function seleccionarDia(dia) {
  estado.dia = dia;
  document.querySelectorAll("rect.dia").forEach((r) => r.classList.toggle("sel", r.dataset.dia === dia));
  await cargarFocos();
}

async function cargar() {
  $("estado-carga").textContent = "Cargando…";
  try {
    dibujarArea();
    const [w, s, e, n] = estado.bbox;
    if (!estado.anio) {
      const inicial = await pedir(`/calendario?bbox=${estado.bbox.join(",")}`);
      const anios = inicial.incertidumbre.anios_con_dato;
      const sel = $("sel-anio");
      sel.innerHTML = anios.map((a) => `<option>${a}</option>`).join("");
      estado.anio = anios.length ? anios[anios.length - 1] : new Date().getUTCFullYear();
      sel.value = estado.anio;
    }
    const q = consulta(`${estado.anio}-01-01`, `${estado.anio}-12-31`);
    const c = await pedir(`/calendario?${q}`);
    estado.calendario = c;
    $("cal-anio").textContent = estado.anio;
    $("btn-csv").href = `/calendario.csv?${q}`;
    pintarCabecera(c); pintarBase(c); pintarClima(c); pintarPeriodos(c); pintarIncertidumbre(c); pintarCalendario(c);
    await cargarFocos();
    mapa.fitBounds([[s, w], [n, e]], { padding: [10, 10] });
    $("estado-carga").textContent = "";
  } catch (err) {
    $("estado-carga").textContent = `Error: ${err.message}`;
  }
}

$("sel-area").addEventListener("change", (ev) => {
  if (AREAS[ev.target.value]) { estado.bbox = AREAS[ev.target.value]; estado.dia = null; cargar(); }
});
$("sel-anio").addEventListener("change", (ev) => { estado.anio = Number(ev.target.value); estado.dia = null; cargar(); });
$("btn-dibujar").addEventListener("click", activarDibujo);
cargar();
