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
  const c = estado.calendario;
  if (!c || !c.dias || !c.dias.length) return;
  pintarCalendario(c);
  if (typeof pintarComparacion === "function") pintarComparacion(c);
}
window.repintarTema = repintarTema;

// ------------------------------------------------------------------ mapa
const mapa = L.map("mapa", { zoomControl: true, attributionControl: true }).setView([2.6, -75.5], 8);
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

function pintarFocos(datos) {
  capaFocos.clearLayers();
  const lista = datos.detecciones ?? [];
  for (const d of lista) {
    const sensor = String(d.sensor).toLowerCase() === "viirs" ? "viirs" : "modis";
    const pop = `<strong>${esc(d.satelite)}</strong> · ${esc(d.sensor)}<br>` +
      `${esc(fechaHoraLegible(d.fecha_hora_utc))}<br>` +
      `Confianza: ${esc(d.confianza_clase)} (${esc(d.confianza_raw)})<br>` +
      `FRP (potencia radiativa del fuego): ${fmt(d.frp, 1)} MW · Calidad: ${esc(d.calidad)}${d.preliminar ? " <em>(preliminar)</em>" : ""}<br>` +
      `Huella nominal: ±${fmt(d.semilado_nominal_m)} m` +
      (d.n_fusionados ? `<br>Agrupa ${fmt(d.n_fusionados)} detección(es) duplicada(s)` : "");
    L.circle([d.lat, d.lon], { radius: d.semilado_nominal_m, className: `huella huella-${sensor}`, weight: 1 }).addTo(capaFocos);
    L.circleMarker([d.lat, d.lon], { radius: 3, className: `foco foco-${sensor}`, weight: 1 }).bindPopup(pop).addTo(capaFocos);
  }
  const n = lista.length;
  $("mapa-filtro").textContent =
    `${fmt(n)} ${n === 1 ? "foco" : "focos"} ${estado.dia ? `el ${fechaPrecisa(estado.dia)}` : `en ${estado.anio}`}` +
    (datos.truncado ? " (lista truncada)" : "");
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
    `<li><a href="#" data-dia="${esc(p.inicio)}" title="${esc(p.inicio)}${p.fin !== p.inicio ? ` → ${esc(p.fin)}` : ""}">${esc(textoPeriodo(p))}</a>` +
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
    "El área mezcla detecciones reales con datos sintéticos de demostración."],
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

function pintarCalendario(c) {
  const dias = c.dias ?? [];
  const cont = $("calendario");
  if (!dias.length) {
    cont.innerHTML = `<p class="tenue">No hay días con datos para mostrar en el calendario.</p>`;
    $("cal-resumen").textContent = "";
    return;
  }
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
    if (t) partes.push(`<text class="cal-texto" x="0" y="${Y0 + i * (T + G) + 10}" font-size="10">${t}</text>`);
  });
  dias.forEach((d, k) => {
    const pos = k + desfase, col = Math.floor(pos / 7), fila = pos % 7;
    const x = X0 + col * (T + G), y = Y0 + fila * (T + G);
    const fecha = d.fecha_utc;
    if (fecha.endsWith("-01")) {
      partes.push(`<text class="cal-texto" x="${x}" y="11" font-size="10">${MESES[Number(fecha.slice(5, 7)) - 1]}</text>`);
    }
    const lv = nivel(d.n_brutas, cortes);
    const titulo = `${fechaLegible(fecha)}: ${fmt(d.n_brutas)} focos brutos, ${fmt(d.n_detecciones)} tras deduplicar` +
      (d.umbral != null ? ` · umbral ${fmt(d.umbral, 1)} focos` : "") + (d.inusual ? " · INUSUAL" : "") +
      (d.preliminar ? " · NRT preliminar" : "");
    const clases = `dia${d.inusual ? " inusual" : ""}${estado.dia === fecha ? " sel" : ""}`;
    partes.push(`<rect class="${clases}" data-dia="${esc(fecha)}" x="${x}" y="${y}" width="${T}" height="${T}" rx="2" ` +
      `fill="var(--e${lv})"><title>${esc(titulo)}</title></rect>`);
    if (d.preliminar && d.n_brutas > 0) {
      partes.push(`<circle class="nrt-punto" cx="${x + T / 2}" cy="${y + T / 2}" r="1.6" pointer-events="none"/>`);
    }
  });
  cont.innerHTML = `<svg width="${ancho}" height="${alto}" role="img" aria-label="Calendario ${esc(estado.anio)}">${partes.join("")}</svg>`;
  cont.querySelectorAll("rect.dia").forEach((r) =>
    r.addEventListener("click", () => seleccionarDia(r.dataset.dia === estado.dia ? null : r.dataset.dia)));
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
  document.querySelectorAll("rect.dia").forEach((r) => r.classList.toggle("sel", r.dataset.dia === dia));
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
    pintarCabecera(c); pintarBase(c); pintarClima(c); pintarPeriodos(c); pintarIncertidumbre(c); pintarCalendario(c);
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
