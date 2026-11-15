/* Harmonized Heat Neiva: mapa y calendario de actividad (H4, H6).
 * Sin paso de compilación: MapLibre va incluido en vendor/.
 * Un solo relieve NASA GIBS entre escalas; los países locales sirven de fondo sin red.
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
let capasEstado = null; // estado del panel de capas (capas.js); se aplica en globo.capas()

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

// Un único lienzo desde la esfera hasta el detalle.
const token = nombre => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
let ultimosFocos = null, vista = "globo", seguirViewport = true, vistaActual = null, gestoMapa = 0;
const cargasMapa = new Set(["inicio"]);
let demoraCarga = null;
function cargaMapa(clave, activa) {
  if (activa) cargasMapa.add(clave); else cargasMapa.delete(clave);
  const ocupado = cargasMapa.size > 0;
  const esqueleto = $("mapa-esqueleto");
  if (!ocupado) { clearTimeout(demoraCarga); demoraCarga=null; esqueleto.hidden=true; }
  else if(esqueleto.classList.contains("inicial")) esqueleto.hidden=false;
  else if(esqueleto.hidden && demoraCarga===null) demoraCarga=setTimeout(()=>{
    demoraCarga=null; if(cargasMapa.size)esqueleto.hidden=false;
  },180);
  $("globo").setAttribute("aria-busy", String(ocupado));
}
const globo = window.Globo.crear({
  contenedor: $("globo"), panel: $("globo-panel"), oscuro: temaOscuro,
  ficha: d => popupFoco(d),
  usarDetalle: () => !seguirViewport || Boolean(globo.cobertura()?.detalle_mismo_conjunto),
  alListo: () => { $("mapa-esqueleto").classList.remove("inicial"); cargaMapa("inicio", false); dibujarArea(); },
  alCarga: activa => cargaMapa("global", activa),
  alCargaBase: activa => cargaMapa("base", activa),
  alExplorar: (lon,lat,z) => mostrarRegional(lon,lat,z),
  alExploracion: () => { seguirViewport=true; },
  alSeleccionarPunto: (lon, lat, zoom) => seleccionarZonaEn(lon, lat, zoom),
  alVolver: () => mostrarRegional(),
  alPeriodo: elegido => {
    vistaCtrl?.abort(); vistaSolicitud++; cargaMapa("vista",false);
    cargas.focos.ctrl?.abort(); cargas.focos.gen++;
    ultimosFocos=null; periodoMapa=null;
    if (!elegido) {
      estado.dia=null; estado.rango=null;
      $("rango-desde").value=$("rango-hasta").value="";
    }
    celdas.forEach(r=>{const seleccionada=r.dataset.dia===estado.dia;r.classList.toggle("sel",seleccionada);r.setAttribute("aria-selected",String(seleccionada));});
    actualizarDescargas(); actualizarImagen(); pintarMeteo(); pintarLineaTiempo();
    mostrarEstado("");
  },
  alDatos: async d => {
    pintarLineaTiempo(); actualizarDescargas(); actualizarEnlaceFirms();
    if (vistaActual?.zoom >= 6 || !seguirViewport) await cargarFocos();
    else fijarPeriodoMapa(d.desde,d.hasta);
  },
  alVista: v => {
    vistaActual = v;
    vista = v.zoom >= 6 ? "regional" : "globo";
    document.body.dataset.escala = vista;
    $("contexto-vista").textContent = v.zoom < 3 ? "Planeta" : v.zoom < 6 ? "País" : "Detalle";
    $("btn-globo").textContent = vista === "globo" ? "Ver región" : "Ver planeta";
    $("btn-globo").setAttribute("aria-pressed", String(vista === "globo"));
    if (v.zoom >= 6 && seguirViewport) cargarVista();
    else if(v.zoom < 6) $("mapa-filtro").textContent = "Relieve natural · acerque para explorar focos y límites";
  },
});
globo.mostrar(-72,4,innerWidth<700 ? 0.9 : 1.8);
const mapa = globo.obtenerMapa();
mapa.on("dragstart", () => { seguirViewport = true; gestoMapa++; });
mapa.on("zoomstart", e => { if(e.originalEvent) { seguirViewport=true; gestoMapa++; } });
let vistaCtrl = null, vistaSolicitud = 0;
async function cargarVista() {
  if (!vistaActual || vistaActual.zoom < 6 || !seguirViewport || globo.actualizandoPeriodo()) return;
  const cobertura = globo.cobertura(), periodo = globo.periodoActual();
  const desde = periodo?.desde;
  const hasta = periodo?.hasta;
  if (!desde || !hasta || !cobertura?.detalle_mismo_conjunto) return;
  const bbox = vistaActual.bbox;
  if (bbox[0] >= bbox[2] || bbox[1] >= bbox[3]) return;
  vistaCtrl?.abort();vistaCtrl = new AbortController();
  const solicitud = ++vistaSolicitud;
  cargaMapa("vista",true);
  try {
    const partes = await Promise.all((vistaActual.cajas ?? [bbox]).map(c=>
      pedir('/detecciones?bbox='+c.join(',')+'&desde='+desde+'&hasta='+hasta+'&limite=50000', vistaCtrl.signal)));
    const registros=[...new Map(partes.flatMap(p=>p.detecciones).map(d=>[d.record_id,d])).values()];
    const datos={...partes[0],detecciones:registros.slice(0,50000),truncado:partes.some(p=>p.truncado)||registros.length>50000};
    if(solicitud !== vistaSolicitud) return;
    ultimosFocos=datos;globo.detalle(datos);fijarPeriodoMapa(desde,hasta);
    $("mapa-filtro").textContent = fmt(datos.detecciones.length)+' focos · '+fechaLegible(desde)+' → '+fechaLegible(hasta);
    $("aviso-truncado").hidden = !datos.truncado;
    $("aviso-truncado").textContent = datos.truncado ? "Consulta limitada a 50.000 focos. Acerque el mapa para consultar una zona menor." : "";
  } catch(e) {
    if (!esAborto(e) && solicitud===vistaSolicitud) $("mapa-filtro").textContent="No se pudo actualizar esta zona. Los datos anteriores siguen visibles.";
  } finally { if(solicitud===vistaSolicitud)cargaMapa("vista",false); }
}
function mostrarGlobo(zoomInicial = innerWidth<700 ? 0.9 : 1.8) {
  seguirViewport=true;
  mapa.flyTo({zoom:zoomInicial??1, center:mapa.getCenter(), duration:window.matchMedia("(prefers-reduced-motion: reduce)").matches?0:1000});
}
function mostrarRegional(lon,lat,zoom=8) {
  if(lon==null){
    seguirViewport=false;globo.enfocar(estado.bbox);
    if(estado.anio){mostrarEstado("cargando","Actualizando el mapa…");
      cargarFocos().then(()=>mostrarEstado("")).catch(e=>mostrarEstado("error",mensajeDe(e)));}
  }
  else{seguirViewport=true;mapa.flyTo({center:[lon,lat],zoom:Math.max(6,zoom),duration:800});}
}
function dibujarArea(){globo.seleccion(estado.bbox);}
function actualizarAreaActual() {
  const sel=$("sel-area"),opcion=sel.selectedOptions[0];
  $("area-actual").hidden=sel.value!=="dibujo";
  $("area-actual").textContent=opcion?.dataset.nombreCompleto??"";
}
let municipios=[], departamentos=[], ciudades=[], paisesMundo=[], paisesBusqueda=[];
function resaltarMunicipio(){dibujarArea();}
async function cargarLimites(){
  try{
    const vacio=()=>({features:[]});
    const [geo,depto,urbes,paises,indice]=await Promise.all([pedir("/ui/datos/huila_municipios.geojson"),
      pedir("/ui/datos/huila_departamento.geojson").catch(vacio),
      pedir("/ui/datos/ciudades_colombia.geojson").catch(vacio),
      pedir("/ui/datos/mundo_paises.geojson").catch(vacio), pedir("/ui/datos/indice_limites.json").catch(()=>({paises:[]}))]);
    municipios=geo.features??[]; departamentos=depto.features??[];
    ciudades=urbes.features??[]; paisesMundo=paises.features??[];
    paisesBusqueda=(indice.paises??[]).map(p=>({type:"Feature",properties:{nombre:p.nombre,iso_a3:p.iso,bbox:p.bbox},
      geometry:paisesMundo.find(f=>f.properties.iso_a3===p.iso)?.geometry??null}));
    if (!paisesBusqueda.length) paisesBusqueda=paisesMundo;
    globo.limitesLocales({municipios,departamentos});
    const grupo=document.createElement("optgroup");grupo.label="Municipios del Huila";
    for(const f of municipios){const o=document.createElement("option");o.value='mun:'+f.properties.shapeID;o.textContent=f.properties.shapeName;grupo.appendChild(o);}
    $("sel-area").appendChild(grupo);
  }catch{/* Las consultas por coordenadas siguen disponibles. */}
}

// ------------------------------------------------------------------ zona seleccionada (ADR 0013)
// La pertenencia de un punto a una zona se calcula en el navegador (zonas.js) con los límites
// locales del Huila y, fuera de él, con los ADM1/ADM2 ya descargados para la vista.
const NIVELES_ZONA = { pais: "País", localidad: "Ciudad o localidad", barrio: "Barrio o sector", lugar: "Lugar",
  ciudad: "Ciudad (área urbana)", municipio: "Municipio", departamento: "Departamento" };
let zonaSel = null, zonaGen = 0;
let puntoSel = null; // punto del foco elegido: al cruzar un umbral de zoom se vuelve a calcular su zona
const fuentesZonas = () => ({
  departamentos: [...departamentos, ...globo.limites(1)],
  municipios: [...municipios, ...globo.limites(2)],
  ciudades,
});

/**
 * Fuera del Huila y sin límites cargados para la vista (p. ej. desde el globo), busca el país
 * del punto en los países locales y pide sus ADM1/ADM2 a /limites (geoBoundaries, con caché).
 */
async function fuentesRemotas(lon, lat) {
  const pais = window.Zonas.zonaDe(lon, lat, paisesMundo);
  if (!pais) return null;
  const iso = pais.properties.iso_a3;
  const [adm1, adm2] = await Promise.all([1, 2].map((n) => globo.limitesDe(iso, n).catch(() => null)));
  return { departamentos: adm1?.features ?? [], municipios: adm2?.features ?? [], ciudades, pais: pais.properties.nombre };
}

/** Área de la API para una zona local (filtra por la forma real); null fuera del Huila. */
function areaDeZona(sel) {
  if (departamentos.includes(sel.zona)) return "huila";
  if (municipios.includes(sel.zona)) return `mun:${sel.zona.properties.shapeID}`;
  return null;
}

/** Periodo de los focos que el mapa muestra ahora; la tarjeta de la zona cuenta ese mismo periodo. */
let periodoMapa = null;
function periodoActual() {
  if (periodoMapa) return periodoMapa;
  const desde = estado.dia ?? estado.rango?.desde ?? (estado.anio ? `${estado.anio}-01-01` : null);
  const hasta = estado.dia ?? estado.rango?.hasta ?? (estado.anio ? `${estado.anio}-12-31` : null);
  return { desde, hasta };
}
function fijarPeriodoMapa(desde, hasta) {
  const cambio = periodoMapa?.desde !== desde || periodoMapa?.hasta !== hasta;
  periodoMapa = { desde, hasta };
  if (zonaSel && (cambio || !areaDeZona(zonaSel))) mostrarZona(zonaSel);
}

async function seleccionarZonaEn(lon, lat, zoom) {
  puntoSel = { lon, lat, nivel: window.Zonas.nivelResaltado(zoom) };
  const gen = ++zonaGen;
  let sel = window.Zonas.zonaSeleccionada(lon, lat, zoom, fuentesZonas());
  // Completa: el nivel pedido existe y, si es municipio o ciudad, también su contexto. Si no
  // (p. ej. fuera del Huila sin ADM2 cargado para la vista), se piden los límites del país.
  const completa = (s) => s && (puntoSel.nivel === "departamento" || (s.nivel !== "departamento" && s.contexto));
  if (!completa(sel)) {
    if (!sel) mostrarSinZona("Buscando los límites de esta zona…");
    const remotas = await fuentesRemotas(lon, lat).catch(() => null);
    if (gen !== zonaGen) return;
    sel = (remotas && window.Zonas.zonaSeleccionada(lon, lat, zoom, remotas)) ?? sel;
  }
  if (sel) { mostrarZona(sel); return; }
  mostrarSinZona(window.HHN_ESTATICO ? "En la demo publicada solo están los límites del Huila; fuera de él, ejecute la API local (make api)."
    : navigator.onLine === false ? "Sin conexión: fuera del Huila los límites se descargan de geoBoundaries."
    : "No hay límites administrativos publicados para este punto (mar o territorio sin datos).");
}

function mostrarSinZona(nota) {
  globo.resaltar(null); zonaSel = null;
  $("tarjeta-zona").hidden = false;
  $("zona-nivel").textContent = "Sin zona";
  $("zona-titulo").textContent = "Fuera de los límites cargados";
  for (const id of ["zona-focos", "zona-alta", "zona-origen", "zona-fecha"]) $(id).textContent = "—";
  $("zona-nota").textContent = nota;
  $("zona-analizar").hidden = $("zona-encuadrar").hidden = true;
}

/** Al acercarse o alejarse con un foco elegido, la zona pasa de departamento a municipio y a ciudad. */
function reevaluarZonaPorZoom() {
  if (!puntoSel || !zonaSel) return;
  const nivel = window.Zonas.nivelResaltado(mapa.getZoom());
  if (nivel !== puntoSel.nivel) seleccionarZonaEn(puntoSel.lon, puntoSel.lat, mapa.getZoom());
}

/** Resalta la zona, atenúa el resto y llena la tarjeta con sus cifras del periodo. */
async function mostrarZona(sel, { encuadrar = false } = {}) {
  const gen = ++zonaGen;
  zonaSel = sel;
  globo.resaltar(sel);
  if (encuadrar) globo.enfocar(sel.zona.properties?.bbox ?? window.Zonas.cajaDe(sel.zona.geometry));
  const nombre = sel.zona.properties?.shapeName ?? "Zona";
  const contexto = sel.contexto?.properties?.shapeName;
  $("tarjeta-zona").hidden = false;
  $("zona-nivel").textContent = NIVELES_ZONA[sel.nivel] + (contexto && contexto !== nombre ? ` · ${contexto}` : "");
  $("zona-titulo").textContent = nombre;
  $("zona-analizar").hidden = $("zona-encuadrar").hidden = false;
  const { desde, hasta } = periodoActual();
  $("zona-fecha").textContent = !desde ? "—" : desde === hasta ? `${fechaLegible(desde)} (UTC)` : `${fechaLegible(desde)} → ${fechaLegible(hasta)} (UTC)`;
  $("zona-focos").textContent = $("zona-alta").textContent = "…";
  const area = areaDeZona(sel);
  let n, alta, origen, nota;
  try {
    if (area && desde) {
      const c = await pedir(`/calendario?area=${encodeURIComponent(area)}&desde=${desde}&hasta=${hasta}`);
      n = (c.dias ?? []).reduce((s, d) => s + (d.n_detecciones ?? 0), 0);
      alta = c.incertidumbre?.clases_confianza?.alta ?? null;
      origen = c.origen_datos;
      nota = "Zona completa, todos los satélites, sin duplicados (servidor).";
    } else {
      ({ n, alta } = window.Zonas.contarEn(sel.zona.geometry, globo.deteccionesVisibles()));
      origen = ultimosFocos?.origen_datos;
      nota = "Contado en el navegador con los focos cargados y visibles en el mapa; puede estar incompleto.";
    }
  } catch (err) {
    if (gen !== zonaGen) return;
    $("zona-focos").textContent = $("zona-alta").textContent = "—";
    $("zona-nota").textContent = `No se pudieron contar los focos: ${mensajeDe(err)}`;
    return;
  }
  if (gen !== zonaGen) return;
  $("zona-focos").textContent = fmt(n);
  $("zona-alta").textContent = fmt(alta);
  $("zona-origen").textContent = origen === "sintetico" ? "Sintético (demostración)" : origen === "real" ? "Real · NASA FIRMS"
    : origen === "mixto" ? "Mixto: real y sintético" : "Sin indicar";
  $("zona-origen").className = origen === "real" ? "" : "zona-alerta";
  $("zona-nota").textContent = nota;
}

/** «Ver zona completa»: encuadra el polígono entero para ver sus vías, límites y nombre. */
function encuadrarZona() {
  if (!zonaSel) return;
  seguirViewport = true;
  globo.enfocar(zonaSel.zona.properties?.bbox ?? window.Zonas.cajaDe(zonaSel.zona.geometry));
}

function quitarZona() {
  zonaGen++; zonaSel = null; puntoSel = null;
  globo.resaltar(null);
  $("tarjeta-zona").hidden = true;
}

function analizarZona() {
  if (!zonaSel) return;
  const area = areaDeZona(zonaSel);
  seguirViewport = false;
  estado.bbox = zonaSel.zona.properties?.bbox ?? window.Zonas.cajaDe(zonaSel.zona.geometry);
  estado.area = area; estado.dia = null;
  const sel = $("sel-area");
  if (area === "huila" || (area && [...sel.options].some((o) => o.value === area))) sel.value = area;
  else {
    const opcion = sel.querySelector('option[value="dibujo"]');
    opcion.disabled = false; opcion.textContent = `${zonaSel.zona.properties?.shapeName ?? "Zona"} (recuadro)`;
    sel.value = "dibujo";
  }
  actualizarAreaActual();
  cargar();
}

// ------------------------------------------------------------------ línea de tiempo (día del mapa)
function pintarLineaTiempo() {
  const c = estado.calendario, entrada = $("dia-mapa");
  const desde = c?.desde ?? (estado.anio ? `${estado.anio}-01-01` : ""), hasta = c?.hasta ?? (estado.anio ? `${estado.anio}-12-31` : "");
  entrada.min = desde; entrada.max = hasta; entrada.value = estado.dia ?? "";
  $("dia-todos").setAttribute("aria-pressed", String(!estado.dia));
  $("dia-anterior").disabled = Boolean(estado.dia && estado.dia <= desde);
  $("dia-siguiente").disabled = Boolean(estado.dia && estado.dia >= hasta);
  const periodo = globo.periodoActual();
  $("linea-estado").textContent = estado.dia ? `${fechaLegible(estado.dia)} · UTC`
    : periodo?.desde ? `${fechaLegible(periodo.desde)} → ${fechaLegible(periodo.hasta)} · UTC`
      : estado.anio ? `${estado.anio} completo · UTC` : "Fechas en UTC";
}
function moverDia(paso) {
  const c = estado.calendario;
  const desde = c?.desde ?? `${estado.anio}-01-01`, hasta = c?.hasta ?? `${estado.anio}-12-31`;
  const dia = estado.dia ? sumarDias(estado.dia, paso) : paso < 0 ? hasta : desde;
  if (dia < desde || dia > hasta) return;
  seleccionarDia(dia);
}

// ------------------------------------------------------------------ imagen del día (H7-02)
// NASA GIBS: color real del día seleccionado. Panel propio fuera de .leaflet-tile-pane para
// que el filtro del tema oscuro no invierta la imagen. Requiere red; es opcional.
const CAPAS_GIBS = {modis:"MODIS_Terra_CorrectedReflectance_TrueColor",viirs:"VIIRS_NOAA20_CorrectedReflectance_TrueColor"};

// La imagen del día es una variante de la base Satelital: solo se dibuja con esa base activa.
function actualizarImagen() {
  const sel=$("sel-imagen"),nota=$("imagen-nota");sel.disabled=!estado.dia;
  const capa=CAPAS_GIBS[sel.value], satelital=!capasEstado || capasEstado.base==="satelital";
  globo.imagen(estado.dia && capa && satelital ? 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/'+capa+'/default/'+estado.dia+'/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg' : null);
  nota.textContent=!estado.dia ? "Elija un día en la línea de tiempo para ver la imagen de ese día."
    : satelital ? "Imagen opcional del día seleccionado (NASA GIBS)." : "Active la base Satelital para ver la imagen del día.";
}

// ------------------------------------------------------------------ conexión NASA FIRMS
// Abre el mismo día y área en el visor oficial (útil para la comparación manual H5-02).
function actualizarEnlaceFirms() {
  const a = $("enlace-firms");
  if (!a) return;
  const [w, s, e, n] = estado.bbox;
  const lat = ((s + n) / 2).toFixed(3), lon = ((w + e) / 2).toFixed(3);
  const p = estado.calendario && estado.calendario.periodos_inusuales ? periodosOrdenados(estado.calendario)[0] : null;
  const dia = estado.dia ?? globo.periodoActual()?.hasta ?? p?.inicio ?? null;
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
    $("capa-clima-texto").textContent = `Clima ${titulo}: máx. ${fmt(Math.max(...vals("temperature_2m_max")), 1)} °C, ` +
      `humedad mín. ${fmt(Math.min(...vals("relative_humidity_2m_min")))} %, lluvia ${fmt(lluvia, 1)} mm.`;
    caja.innerHTML =
      `<p><strong>Clima ${esc(titulo)}</strong>: máx. ${fmt(Math.max(...vals("temperature_2m_max")), 1)} °C, ` +
      `humedad mín. ${fmt(Math.min(...vals("relative_humidity_2m_min")))} %, lluvia total ${fmt(lluvia, 1)} mm.</p>` +
      `<details><summary>Ver día por día</summary><table class="tabla-cmp"><thead><tr><th scope="col">Día</th>` +
      `<th scope="col">T. máx.</th><th scope="col">Hum. mín.</th><th scope="col">Lluvia</th><th scope="col">Viento máx.</th>` +
      `</tr></thead><tbody>${filas}</tbody></table></details>` +
      `<p class="tenue">Punto central del área (${esc(fmt(Number(lat), 2))}; ${esc(fmt(Number(lon), 2))}). Calor, humedad baja y ausencia de lluvia favorecen las quemas, pero no las causan.</p>`;
  } catch {
    if (gen !== meteoGen) return;
    $("capa-clima-texto").textContent = "No se pudo consultar el clima (requiere internet).";
    caja.innerHTML = `<p class="tenue">No se pudo consultar el clima (requiere internet o la fecha aún no está en el archivo, que tiene unos días de retraso). El resto de la herramienta funciona sin él.</p>`;
  }
}

function activarDibujo(){
  quitarZona();
  const b=$("btn-dibujar");b.textContent="Seleccione dos esquinas…";b.classList.add("activo");
  globo.dibujar(bbox=>{b.textContent="Dibujar área en el mapa";b.classList.remove("activo");
    if(!bbox || bbox[0]===bbox[2] || bbox[1]===bbox[3])return;
    estado.bbox=bbox;estado.area=null;estado.dia=null;seguirViewport=false;
    const opcion=$("sel-area").querySelector('option[value="dibujo"]');opcion.disabled=false;opcion.textContent="Área dibujada";
    $("sel-area").value="dibujo";cargar();
  });
}

// ------------------------------------------------------------------ simbología de los focos
// Tamaño y color = FRP (clases fijas, comparables entre días y regiones; las mismas del globo).
// Todos los sensores usan círculos; la ficha identifica la calidad NRT.
const CORTES_FRP = [5, 20, 100, 500];
const claseFrp = (frp) => (frp == null ? 0 : CORTES_FRP.filter((c) => frp >= c).length);

function popupFoco(d) {
  const clase = claseFrp(d.frp);
  const intensidad = ["muy baja", "baja", "moderada", "alta", "muy alta"][clase];
  return `<div class="ficha-foco"><strong>${esc(d.satelite)}</strong> · ${esc(d.sensor)}` +
    `${d.preliminar ? ' <span class="insignia preliminar mini">NRT</span>' : ""}<dl>` +
    `<dt>Fecha</dt><dd>${esc(fechaHoraLegible(d.fecha_hora_utc))}</dd>` +
    `<dt>Intensidad</dt><dd>FRP ${fmt(d.frp, 1)} MW (${intensidad})</dd>` +
    `<dt>Temperatura de brillo</dt><dd>${d.brillo == null ? "No disponible" : `${fmt(d.brillo - 273.15, 1)} °C (${fmt(d.brillo, 1)} K)`} · píxel, no llama</dd>` +
    `<dt>Confianza</dt><dd>${esc(d.confianza_clase)} (${esc(d.confianza_raw)})${d.sensor === "MODIS" ? " · cortes MODIS provisionales" : ""}</dd>` +
    `<dt>Calidad</dt><dd>${esc(d.calidad)}${d.preliminar ? " · preliminar, puede corregirse" : ""}</dd>` +
    `<dt>Píxel</dt><dd>±${fmt(d.semilado_nominal_m)} m nominal: el fuego está dentro de ese cuadro</dd>` +
    `<dt>Posición</dt><dd>${fmt(d.lat, 4)}; ${fmt(d.lon, 4)}</dd>` +
    (d.n_fusionados ? `<dt>Fusionados</dt><dd>agrupa ${fmt(d.n_fusionados)} detección(es) casi simultánea(s)</dd>` : "") +
    `</dl><details class="foco-procedencia"><summary>Procedencia del registro</summary><dl>` +
    `<dt>Identificador</dt><dd>${esc(d.record_id ?? "No disponible")}</dd>` +
    `<dt>Origen</dt><dd>${d.sintetico === true || d.sintetico === "true" ? "Sintético · demostración" : d.sintetico === false || d.sintetico === "false" ? "Real declarado · NASA FIRMS" : "Origen no verificado"}</dd>` +
    `<dt>Producto</dt><dd>${esc(d.fuente ?? "No disponible")} · colección ${esc(d.coleccion ?? "sin indicar")} · versión ${esc(d.version ?? "sin indicar")}</dd>` +
    `<dt>Archivo y registro</dt><dd>${esc(d.archivo_origen ?? "No disponible")} · ${esc(d.fila ?? "—")} (desde 1, sin cabecera)</dd>` +
    `<dt>SHA-256 crudo</dt><dd>${esc(d.sha256_origen ?? "No disponible")}</dd>` +
    `<dt>Descarga UTC</dt><dd>${esc(fechaHoraLegible(d.fecha_descarga))}</dd>` +
    `<dt>Reglas</dt><dd>${esc(d.rules_version ?? "No disponible")}</dd>` +
    `<dt>Conjunto</dt><dd>${esc(d.dataset_id ?? "Sin manifiesto de ejecución")}</dd>` +
    `</dl><a href="/procedencia" target="_blank" rel="noopener">Consultar linaje del conjunto</a></details></div>`;
}



/** Leyenda mínima (abajo a la izquierda): escala FRP y clases de confianza, fijas en todas las vistas. */
function pintarLeyendaMapa() {
  const caja = $("leyenda-mapa");
  if (!caja) return;
  const tramos = ["&lt; 5", "5–20", "20–100", "100–500", "≥ 500"];
  // Confianza: opacidad y grosor de borde (los mismos valores que pinta globo.js); no depende del color.
  const conf = [["alta", 0.95, 2], ["nominal", 0.8, 1], ["baja", 0.5, 0.5]];
  caja.innerHTML = `<strong>Potencia · FRP (MW)</strong><div class="escala-frp">${tramos.map((t, k) =>
    `<span><i class="esc-frp f${k + 1}"></i>${t}</span>`).join("")}</div>` +
    `<strong>Confianza</strong><div class="fila-leyenda">${conf.map(([t, o, b]) =>
      `<span><i class="muestra-confianza" style="opacity:${o};border-width:${b + 0.5}px"></i>${t}</span>`).join("")}</div>` +
    `<a href="#guia-termica">Guía de colores y sensores</a>`;
}

function pintarFocos(datos){
  ultimosFocos=datos;globo.detalle(datos);
  if(mapa.getZoom()>=6) $("mapa-filtro").textContent=
    (datos.origen_datos==="sintetico" ? "Muestra sintética · " : datos.origen_datos==="mixto" ? "Datos reales y sintéticos · " : "")+
    fmt(datos.detecciones?.length??0)+' focos · '+fechaLegible(globo.periodoActual()?.desde??datos.desde)+' → '+fechaLegible(globo.periodoActual()?.hasta??datos.hasta);
  $("aviso-truncado").hidden=!datos.truncado;
  $("aviso-truncado").textContent=datos.truncado?"Consulta limitada: acerque el área o seleccione un día.":"";
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
  const mesesCubiertos = new Set((c.dias ?? []).map((d) => String(d.fecha_utc).slice(0, 7))).size;
  const mostrar = Boolean(c.climatologia_mensual) || mesesCubiertos >= 3;
  $("tarjeta-temporada").hidden = !mostrar;
  $("temporada-titulo").textContent = c.climatologia_mensual
    ? "Temporada (climatología mensual)" : `Actividad mensual de ${estado.anio}`;
  if (!c.climatologia_mensual) {
    caja.innerHTML = "";
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
  if ($("tarjeta-temporada").hidden) { caja.innerHTML = ""; return; }
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
    } else if (clim) {
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
    `<details class="cmp-detalle"><summary class="cmp-titulo">${clim ? "Comparar este año con el promedio histórico" : `Ver actividad por mes en ${esc(anio)} (${esc(fmt(total))} celdas)`}</summary>` +
    `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(etiqueta)}" preserveAspectRatio="xMidYMid meet">${p.join("")}</svg>` +
    `<p class="tenue">Barras: ${ETIQUETA_METRICA} de ${esc(anio)} por mes${clim ? ". Línea: promedio histórico mensual" : ""}.` +
    `${incompleto.some(Boolean) ? " Las barras con borde punteado son meses incompletos y no se comparan de igual a igual con el promedio." : ""}</p>` +
    (clim ? `<p class="tenue">El promedio histórico usa los meses completos de todos los años disponibles, incluido este año si el mes está completo.</p>`
      : `<p class="tenue">Los meses sin barra están fuera de la cobertura del archivo.</p>`) +
    `<details><summary>Ver como tabla</summary><table class="tabla-cmp"><thead><tr><th scope="col">Mes</th>` +
    `<th scope="col">${esc(anio)}</th>${clim ? `<th scope="col">Promedio</th>` : ""}</tr></thead><tbody>${filas}</tbody></table></details></details>`;
}

function periodosOrdenados(c) {
  return [...(c.periodos_inusuales ?? [])].sort((a, b) => b.dias - a.dias || b.maximo - a.maximo);
}

function textoPeriodo(p) {
  return p.fin !== p.inicio ? `${fechaLegible(p.inicio)} → ${fechaLegible(p.fin)}` : fechaLegible(p.inicio);
}

function pintarPeriodos(c) {
  const lista = $("periodos");
  $("tarjeta-periodos").hidden = !c.periodos_inusuales;
  if (!c.periodos_inusuales) { lista.innerHTML = ""; return; }
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
  // Advertencia visible en el pie cuando hay datos sintéticos (también en datos mixtos).
  const pie = $("pie-sintetico");
  pie.hidden = c.origen_datos !== "sintetico" && c.origen_datos !== "mixto";
  pie.textContent = c.origen_datos === "sintetico"
    ? "Advertencia: DATOS SINTÉTICOS de demostración. No describen incendios reales."
    : c.origen_datos === "mixto" ? "Advertencia: los datos mezclan detecciones reales con datos sintéticos de demostración." : "";
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
let resumenCtrl = null;
const resumenCache = new Map();

async function cargarResumen() {
  const gen = ++resumenGen;
  resumenCtrl?.abort();
  const clave = filtroArea();
  const caja = $("matriz");
  const guardado = resumenCache.get(clave);
  if (guardado) {
    estado.resumen = guardado;
    pintarMatriz(guardado);
    pintarMesReciente(guardado);
    return;
  }
  resumenCtrl = new AbortController();
  if (!estado.resumen) {
    $("tarjeta-mes-reciente").hidden = true;
    if (caja) caja.innerHTML = `<p class="tenue">Calculando el calendario de quema…</p>`;
  }
  try {
    const r = await pedir(`/resumen?${clave}`, resumenCtrl.signal);
    if (gen !== resumenGen) return;
    if (resumenCache.size >= 8) resumenCache.delete(resumenCache.keys().next().value);
    resumenCache.set(clave, r);
    estado.resumen = r;
    pintarMatriz(r);
    pintarMesReciente(r);
  } catch (err) {
    if (esAborto(err) || gen !== resumenGen) return;
    if (caja) caja.innerHTML = `<p class="tenue">No se pudo calcular el calendario de quema: ${esc(mensajeDe(err))}</p>`;
    $("tarjeta-mes-reciente").hidden = true;
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
    seguirViewport=false; sel.value = anio; estado.anio = anio; estado.dia = null; cargar();
  }));
}

function pintarMesReciente(r) {
  const caja = $("mes-reciente");
  if (!caja) return;
  const m = r.mes_reciente;
  $("tarjeta-mes-reciente").hidden = !m;
  if (!m) { caja.innerHTML = ""; return; }
  const nombre = `${MESES_LARGOS[m.mes - 1]} de ${m.anio}`;
  const v = (x) => fmt(x, x < 10 ? 1 : 0);
  if (m.mediana == null) {
    $("tarjeta-mes-reciente").querySelector("h2").textContent = "Actividad reciente";
    caja.innerHTML = `<p><strong>${esc(nombre)}</strong>: ${v(m.valor)} celdas activas${m.completo ? "" : ` en ${fmt(m.dias)} días cubiertos`}.</p>`;
    return;
  }
  $("tarjeta-mes-reciente").querySelector("h2").textContent = "Mes más reciente frente a la mediana";
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
  const periodo = globo.periodoActual();
  if (focos) focos.href = `/detecciones.csv?${consulta(periodo?.desde ?? estado.dia ?? desde, periodo?.hasta ?? estado.dia ?? hasta)}`;
}

function aplicarRango() {
  const d = $("rango-desde").value, h = $("rango-hasta").value;
  if (!d && !h) { estado.rango = null; estado.dia=null; actualizarDescargas(); globo.periodo(`${estado.anio}-01-01`,`${estado.anio}-12-31`); return; }
  if (!d || !h) { mostrarEstado("error", "Indique las dos fechas del rango (desde y hasta)."); return; }
  if (d > h) { mostrarEstado("error", "La fecha «desde» debe ser anterior o igual a «hasta»."); return; }
  estado.rango = { desde: d, hasta: h };
  estado.dia = null;
  actualizarDescargas();
  mostrarEstado("cargando", "Cargando focos del rango…");
  globo.periodo(d,h);
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
  seguirViewport=false;
  estado.bbox = [w, s, e, n];
  quitarZona();
  estado.area = null;
  estado.dia = null;
  const opcion = $("sel-area").querySelector('option[value="dibujo"]');
  opcion.disabled = false;
  opcion.textContent = "Coordenadas";
  opcion.dataset.nombreCompleto = "Área definida por coordenadas";
  $("sel-area").value = "dibujo";
  actualizarAreaActual();
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
  const traducirExportacion=s=>window.Idiomas?.traducir(s)??s;
  copia.setAttribute("xmlns", svg.namespaceURI);
  copia.setAttribute("height", alto + 58);
  copia.setAttribute("viewBox", `0 -18 ${ancho} ${alto + 58}`);
  copia.insertAdjacentHTML("afterbegin", `<rect x="0" y="-18" width="${ancho}" height="${alto + 58}" fill="${token("--tarjeta")}"/>` +
    `<text x="0" y="-4" font-size="12" font-weight="700" fill="${token("--tinta")}">${esc(traducirExportacion(titulo))} · ${esc(traducirExportacion(area))}</text>`);
  copia.insertAdjacentHTML("beforeend",
    `<text x="0" y="${alto + 14}" font-size="9" fill="${token("--tenue")}">${esc(traducirExportacion("Datos: NASA FIRMS (LANCE / ESDIS). Métrica armonizada (ADR 0011), "))}${esc(estado.calendario?.rules_version ?? "")}.</text>` +
    `<text x="0" y="${alto + 28}" font-size="9" fill="${token("--tenue")}">${esc(traducirExportacion("Detecciones térmicas, no incendios confirmados."))} Harmonized Heat Neiva.</text>`);
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
  cargaMapa("consulta", tipo === "cargando");
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
  const gen = k.gen;
  return { gen, señal: k.ctrl.signal, vigente: () => gen === cargas[tipo].gen };
}

/** Devuelve true si pintó; false si quedó obsoleta. Lanza el resto de errores. */
async function cargarFocos() {
  if (globo.actualizandoPeriodo()) return false;
  if (seguirViewport && vistaActual?.zoom>=6) { await cargarVista(); return true; }
  const gestoAlPedir = gestoMapa;
  const h = iniciarCarga("focos");
  const periodo = globo.periodoActual();
  const desde = periodo?.desde ?? estado.dia ?? estado.rango?.desde ?? `${estado.anio}-01-01`;
  const hasta = periodo?.hasta ?? estado.dia ?? estado.rango?.hasta ?? `${estado.anio}-12-31`;
  try {
    const datos = await pedir(`/detecciones?${consulta(desde, hasta)}&limite=50000`, h.señal);
    if (!h.vigente()) return false;
    if (seguirViewport && gestoAlPedir!==gestoMapa) return true;
    pintarFocos(datos);
    fijarPeriodoMapa(desde, hasta);
    return true;
  } catch (err) {
    if (esAborto(err) || !h.vigente()) return false;
    throw err;
  }
}

async function seleccionarDia(dia) {
  estado.dia = dia;
  seguirViewport=false;
  if(mapa.getZoom()<6)globo.enfocar(estado.bbox);
  actualizarEnlaceFirms();
  actualizarDescargas();
  actualizarImagen();
  pintarMeteo();
  pintarLineaTiempo();
  celdas.forEach((r, k) => {
    const es = r.dataset.dia === dia;
    r.classList.toggle("sel", es);
    r.setAttribute("aria-selected", String(es));
    if (es) fijarTabindex(k);
  });
  mostrarEstado("cargando", "Cargando focos…");
  try {
    const desde = dia ?? estado.rango?.desde ?? `${estado.anio}-01-01`;
    const hasta = dia ?? estado.rango?.hasta ?? `${estado.anio}-12-31`;
    await globo.periodo(desde,hasta);
  } catch (err) {
    mostrarEstado("error", `No se pudieron cargar los datos: ${mensajeDe(err)}`, () => seleccionarDia(dia));
  }
}

function pintarVacio(c) {
  globo.detalle({detecciones:[]});
  ultimosFocos = null;
  $("aviso-truncado").hidden = true;
  $("mapa-filtro").textContent = `Sin focos en ${estado.anio}`;
  $("resumen-texto").textContent = resumir(c);
}

/** opciones.encuadrarArea = false conserva la vista (zona explorada desde el globo). */
async function cargar(opciones = {}) {
  const { encuadrarArea = true } = opciones;
  const gestoInicial = gestoMapa;
  vistaCtrl?.abort();vistaSolicitud++;cargaMapa("vista",false);
  const h = iniciarCarga("anio");
  resumenGen += 1;
  resumenCtrl?.abort();
  meteoGen += 1;
  if (cargas.focos.ctrl) cargas.focos.ctrl.abort();
  cargas.focos.gen += 1;
  mostrarEstado("cargando", "Cargando datos…");
  $("panel-analisis").setAttribute("aria-busy", "true");
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
    $("resumen-anio").textContent = estado.anio;
    actualizarDescargas();
    pintarCabecera(c); pintarBase(c); pintarClima(c); pintarComparacion(c); pintarPeriodos(c); pintarIncertidumbre(c); pintarCalendario(c);
    pintarLineaTiempo();
    cargarResumen();
    if (!hayDatos(c)) {
      pintarVacio(c);
      $("panel-analisis").removeAttribute("aria-busy");
      if (encuadrarArea && gestoInicial===gestoMapa) globo.enfocar(estado.bbox);
      mostrarEstado("vacio", "No hay observaciones para esta área y año.");
      return;
    }
    $("resumen-texto").textContent = resumir(c);
    actualizarImagen();
    actualizarEnlaceFirms();
    pintarMeteo();
    const ok = await cargarFocos();
    if (!h.vigente()) return;
    $("panel-analisis").removeAttribute("aria-busy");
    if (!ok) return;
    if (encuadrarArea && gestoInicial===gestoMapa) globo.enfocar(estado.bbox);
    mostrarEstado("");
  } catch (err) {
    if (esAborto(err) || !h.vigente()) return;
    $("panel-analisis").removeAttribute("aria-busy");
    mostrarEstado("error", `No se pudieron cargar los datos: ${mensajeDe(err)}`, cargar);
    $("resumen-texto").textContent = "No se pudo generar el resumen porque faltan los datos.";
  }
}

$("sel-area").addEventListener("change", (ev) => {
  quitarZona();
  const v = ev.target.value;
  seguirViewport=false;
  actualizarAreaActual();
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
$("sel-anio").addEventListener("change", (ev) => {
  seguirViewport=false; estado.anio=Number(ev.target.value); estado.dia=null; estado.rango=null;
  $("rango-desde").value=$("rango-hasta").value="";
  globo.periodo(`${estado.anio}-01-01`,`${estado.anio}-12-31`); cargar();
});
$("btn-dibujar").addEventListener("click", activarDibujo);
$("btn-globo").addEventListener("click", () => (vista === "globo" ? mostrarRegional() : mostrarGlobo()));
$("btn-reintentar").addEventListener("click", () => { if (reintento) reintento(); });
iniciarTema();
pintarLeyendaMapa();

// ------------------------------------------------------------------ panel de capas (ADR 0013)
const capasCtrl = window.Capas.iniciar({
  contenedor: $("panel-capas-cuerpo"), resumenEl: $("capas-resumen"),
  alCambiar: (e) => {
    const baseAntes = capasEstado?.base;
    capasEstado = e;
    globo.capas(e);
    $("capa-clima").hidden = !e.capas.clima.on;
    if (baseAntes !== e.base) actualizarImagen();
  },
});
capasCtrl.ranura("imagen")?.appendChild($("control-imagen"));
(function iniciarPanelCapas() {
  const boton = $("btn-capas"), panel = $("panel-capas");
  const fijar = (abierto) => { boton.setAttribute("aria-expanded", String(abierto)); panel.hidden = !abierto; };
  // Abierto en escritorio; en pantallas estrechas el mapa tiene prioridad.
  fijar(!window.matchMedia("(max-width: 700px)").matches);
  boton.addEventListener("click", () => fijar(panel.hidden));
  panel.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") { ev.stopPropagation(); fijar(false); boton.focus(); }
  });
})();

// ------------------------------------------------------------------ búsqueda: local primero
window.iniciarBusquedaLugares({
  buscarLocal: (q) => window.Zonas.buscarLocal(q, { municipios, departamentos, paises: paisesBusqueda }),
  elegirLocal: (r) => {
    if (r.nivel === "pais") {
      const bbox=r.feature.properties.bbox;
      explorarLugar({nombre:r.nombre,tipo:r.tipo,nivel:"pais",descripcion:r.descripcion,bbox,
        lon:(bbox[0]+bbox[2])/2,lat:(bbox[1]+bbox[3])/2,geometria:r.feature.geometry});
      return;
    }
    globo.quitarLugar();
    seguirViewport = true; puntoSel = null; // zona buscada: no cambia de nivel con el zoom
    const sel = r.nivel === "municipio"
      ? { nivel: "municipio", zona: r.feature, contexto: departamentos[0] ?? null }
      : { nivel: "departamento", zona: r.feature, contexto: null };
    mostrarZona(sel, { encuadrar: true });
  },
  explorar: explorarLugar,
});
function explorarLugar(lugar) {
    quitarZona();
    seguirViewport=true;
    globo.localizar(lugar, seleccionado => {
      seguirViewport=false;
      estado.bbox=seleccionado.bbox; estado.area=null; estado.dia=null;
      const opcion=$("sel-area").querySelector('option[value="dibujo"]');
      opcion.disabled=false; opcion.textContent=seleccionado.nombre+" (recuadro)";
      opcion.dataset.nombreCompleto=seleccionado.descripcion+" · recuadro aproximado";
      $("sel-area").value="dibujo";actualizarAreaActual();cargar();
    });
    // Nominatim devuelve el polígono de municipios y departamentos: se resalta igual que uno local.
    if (lugar.geometria) {
      puntoSel = null;
      const nivel = lugar.nivel ?? ({ "País":"pais", "Municipio":"municipio", "Ciudad":"localidad", "Localidad":"localidad",
        "Barrio":"barrio", "Barrio o sector":"barrio", "Departamento o estado":"departamento", "División administrativa":"departamento" }[lugar.tipo] ?? "lugar");
      mostrarZona({ nivel, zona: { type: "Feature", properties: { shapeName: lugar.nombre, bbox: lugar.bbox }, geometry: lugar.geometria }, contexto: null });
    }
}
$("zona-cerrar").addEventListener("click", quitarZona);
$("zona-encuadrar").addEventListener("click", encuadrarZona);
mapa.on("zoomend", reevaluarZonaPorZoom);
$("zona-analizar").addEventListener("click", analizarZona);
$("dia-anterior").addEventListener("click", () => moverDia(-1));
$("dia-siguiente").addEventListener("click", () => moverDia(1));
$("dia-todos").addEventListener("click", () => { if (estado.dia) seleccionarDia(null); });
$("dia-mapa").addEventListener("change", (ev) => {
  const v = ev.target.value;
  if (!v) { if (estado.dia) seleccionarDia(null); return; }
  if ((ev.target.min && v < ev.target.min) || (ev.target.max && v > ev.target.max)) { pintarLineaTiempo(); return; }
  seleccionarDia(v);
});
document.addEventListener("click", (ev) => {
  if (ev.target.closest('a[href="#guia-termica"]')) $("guia-termica").open = true;
  if (!ev.target.closest(".controles-secundarios")) document.querySelector(".controles-secundarios").open = false;
});
document.addEventListener("keydown", (ev) => {
  const opciones = document.querySelector(".controles-secundarios");
  if (ev.key === "Escape" && opciones.open) {
    opciones.open = false;
    opciones.querySelector("summary").focus();
  }
});
cargarLimites();
cargar({encuadrarArea:location.hash==="#regional"});
// Diagnóstico sin valores de credenciales. La ausencia de clave nunca se representa como dato real.
(async()=>{
  const caja=$("estado-firms");
  try {
    const r=await pedir("/estado-servicios"), f=r.firms;
    const mensaje=f.estado==="sin_servidor" ? "Esta demo estática no ejecuta un servidor FIRMS."
      : f.estado==="cifrado_invalido" ? "FIRMS: no se pudo descifrar la clave. Revise los secretos del despliegue."
      : !f.configurada ? "FIRMS: falta configurar la clave en el servidor."
      : f.cifrada ? "FIRMS: clave cifrada configurada en el servidor." : "FIRMS: clave configurada en el servidor.";
    const estado=document.createElement("span");estado.textContent=mensaje;caja.replaceChildren(estado);
    if(f.origen_datos==="sintetico" && f.modo!=="estatico"){
      const modo=document.createElement("span");modo.textContent="Se muestran datos sintéticos de demostración. El administrador debe activar las observaciones reales.";
      caja.append(document.createElement("br"),modo);
    }
  }catch{caja.textContent="No se pudo consultar el estado de conexión FIRMS.";}
})();
