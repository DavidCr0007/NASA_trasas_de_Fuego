/* Demo estática para GitHub Pages (ADR 0015). Solo se carga en el sitio que genera
 * tools/exportar_estatico.py, antes que cualquier otro script.
 *
 * Pages no ejecuta la API de Python: este archivo intercepta fetch y responde con las
 * respuestas que la MISMA API dejó precalculadas en api/. Los periodos parciales del
 * calendario y las consultas de focos por área, recuadro o fecha se derivan aquí de esos
 * archivos. Lo que necesita servidor responde con un aviso claro, nunca con datos inventados.
 */
"use strict";

(function () {
  const original = window.fetch.bind(window);
  const raiz = new URL(".", document.baseURI);
  const enRaiz = (ruta) => new URL(ruta, raiz).href;
  window.HHN_ESTATICO = { raiz: raiz.href };

  const AVISO_API = "No disponible en la demo publicada: ejecute la API local (make api) para ";
  const memo = new Map();
  function leer(ruta) {
    if (!memo.has(ruta)) {
      const p = original(enRaiz(ruta)).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      });
      p.catch(() => memo.delete(ruta));
      memo.set(ruta, p);
    }
    return memo.get(ruta);
  }
  const responder = (cuerpo, estado = 200) =>
    new Response(JSON.stringify(cuerpo), { status: estado, headers: { "Content-Type": "application/json" } });
  const noDisponible = (para, estado = 404) => responder({ detail: AVISO_API + para + "." }, estado);
  const slug = (area) => area.replace(/[^A-Za-z0-9_-]/g, "-");

  let limites = null;
  async function geometriaDe(area) {
    limites ??= Promise.all([leer("datos/huila_departamento.geojson"), leer("datos/huila_municipios.geojson")]);
    const [depto, munis] = await limites;
    if (area === "huila") return depto.features[0]?.geometry ?? null;
    if (!area.startsWith("mun:")) return null;
    return munis.features.find((f) => f.properties.shapeID === area.slice(4))?.geometry ?? null;
  }

  async function detecciones() {
    const d = await leer("api/detecciones.json");
    d.objetos ??= d.filas.map((f) => Object.fromEntries(d.campos.map((c, i) => [c, f[i]])));
    return d;
  }

  /** Focos del archivo completo filtrados por fechas (UTC) y por área (forma real) o recuadro. */
  async function filtrar(params) {
    const d = await detecciones();
    const desde = params.get("desde") || d.desde, hasta = params.get("hasta") || d.hasta;
    const area = params.get("area");
    const geom = area ? await geometriaDe(area) : null;
    if (area && !geom) return null;
    const caja = !area && params.get("bbox") ? params.get("bbox").split(",").map(Number) : null;
    const lista = d.objetos.filter((x) => {
      const dia = x.fecha_hora_utc.slice(0, 10);
      if (dia < desde || dia > hasta) return false;
      if (caja && (x.lon < caja[0] || x.lon > caja[2] || x.lat < caja[1] || x.lat > caja[3])) return false;
      return !geom || window.Zonas.contiene(geom, x.lon, x.lat);
    });
    return { d, desde, hasta, lista, caja: caja ?? (geom ? window.Zonas.cajaDe(geom) : null) };
  }

  async function rutaDetecciones(params) {
    const f = await filtrar(params);
    if (!f) return noDisponible("consultar esa área");
    const limite = Number(params.get("limite") || 5000);
    return responder({ ...f.d.base, bbox: f.caja, area: null, desde: f.desde, hasta: f.hasta,
      origen_datos: f.d.origen_datos, truncado: f.lista.length > limite, detecciones: f.lista.slice(0, limite),
      incertidumbre: { grilla_deg: f.d.grilla_deg } });
  }

  async function rutaCalendario(params) {
    const area = params.get("area");
    if (!area) return noDisponible("consultar áreas dibujadas, por coordenadas o buscadas en internet");
    const s = slug(area), indice = await leer("api/indice.json");
    const desde = params.get("desde"), hasta = params.get("hasta");
    if (!desde && !hasta) {
      return responder(await leer(`api/calendario/${s}/inicial.json`)
        .catch(() => leer(`api/calendario/${s}/${indice.anios[indice.anios.length - 1]}.json`)));
    }
    const y0 = desde.slice(0, 4), y1 = hasta.slice(0, 4);
    if (y0 === y1 && desde === `${y0}-01-01` && hasta === `${y0}-12-31` && indice.anios.includes(Number(y0))) {
      return responder(await leer(`api/calendario/${s}/${y0}.json`));
    }
    // Periodo parcial (un día, el rango del globo): días de los años precalculados + confianza del periodo.
    const anios = indice.anios.filter((a) => String(a) >= y0 && String(a) <= y1);
    const archivos = await Promise.all((anios.length ? anios : [indice.anios[indice.anios.length - 1]])
      .map((a) => leer(`api/calendario/${s}/${a}.json`)));
    const plantilla = archivos[archivos.length - 1];
    const f = await filtrar(params);
    const clases = { alta: 0, nominal: 0, baja: 0 };
    for (const x of f?.lista ?? []) clases[x.confianza_clase] = (clases[x.confianza_clase] ?? 0) + 1;
    return responder({ ...plantilla, desde, hasta,
      dias: anios.length ? archivos.flatMap((c) => c.dias ?? []).filter((x) => x.fecha_utc >= desde && x.fecha_utc <= hasta) : [],
      periodos_inusuales: (plantilla.periodos_inusuales ?? []).filter((p) => p.fin >= desde && p.inicio <= hasta),
      incertidumbre: { ...plantilla.incertidumbre, clases_confianza: clases } });
  }

  // Misma agregación que /global para fechas del calendario; no reutilizar la última semana.
  async function globalPorFechas(p) {
    const res=Number(p.get("res")||0.5), desde=p.get("desde"), hasta=p.get("hasta");
    if (![0.25,0.5,1].includes(res) || !desde || !hasta || desde>hasta) return responder({detail:"Periodo o resolución inválidos"},422);
    const [d, plantilla, mundo] = await Promise.all([detecciones(),leer(`api/global/7_${res}.json`),leer("datos/mundo_paises.geojson")]);
    const filas=d.objetos.filter(x=>x.fecha_hora_utc.slice(0,10)>=desde && x.fecha_hora_utc.slice(0,10)<=hasta);
    const grupos=new Map(), serie=new Map(), paises=new Map();
    for (const x of filas) {
      const fi=Math.floor(x.lat/res),co=Math.floor(x.lon/res),k=fi+":"+co;
      if (!grupos.has(k)) grupos.set(k,{fi,co,n:0,lat:0,lon:0,frp:null,suma:0,alta:0,viirs:0,ultimo:""});
      const g=grupos.get(k);g.n++;g.lat+=x.lat;g.lon+=x.lon;g.suma+=x.frp??0;
      if(x.frp!=null)g.frp=Math.max(g.frp??0,x.frp);
      g.alta+=Number(x.confianza_clase==="alta");g.viirs+=Number(x.sensor==="VIIRS");
      g.ultimo=g.ultimo>x.fecha_hora_utc?g.ultimo:x.fecha_hora_utc;
      const dia=x.fecha_hora_utc.slice(0,10);
      if(!serie.has(dia))serie.set(dia,{fecha_utc:dia,n:0,n_alta:0});
      serie.get(dia).n++;serie.get(dia).n_alta+=Number(x.confianza_clase==="alta");
    }
    const redondear=(n,c=3)=>Number(n.toFixed(c));
    const celdas=[...grupos.values()].sort((a,b)=>a.fi-b.fi||a.co-b.co).map(g=>{
      const lat=g.lat/g.n,lon=g.lon/g.n;
      const f=mundo.features.find(f=>window.Zonas.contiene(f.geometry,redondear(lon,2),redondear(lat,2)));
      const iso=f?.properties.iso_a3??"";
      if(!paises.has(iso))paises.set(iso,{iso_a3:iso||null,nombre:f?.properties.nombre??"Fuera de país (mar o costa)",n:0,n_alta:0,frp_max:0,celdas:0});
      const pais=paises.get(iso);pais.n+=g.n;pais.n_alta+=g.alta;pais.frp_max=redondear(Math.max(pais.frp_max,g.frp??0),1);pais.celdas++;
      return [redondear(lat),redondear(lon),g.n,g.frp==null?null:redondear(g.frp,1),redondear(g.suma,1),g.alta,g.viirs,new Date(g.ultimo).toISOString().slice(0,16)+"Z",iso];
    });
    return responder({...plantilla,desde,hasta,dias_solicitados:Math.round((Date.parse(hasta)-Date.parse(desde))/86400000)+1,
      dias_en_periodo:serie.size,total_detecciones:filas.length,total_alta:filas.filter(x=>x.confianza_clase==="alta").length,
      n_paises:[...paises.keys()].filter(Boolean).length,celdas,paises:[...paises.values()].sort((a,b)=>b.n-a.n||a.nombre.localeCompare(b.nombre)).slice(0,25),
      serie_diaria:[...serie.values()].sort((a,b)=>a.fecha_utc.localeCompare(b.fecha_utc)),
      actualizado_hasta_utc:celdas.length?celdas.map(c=>c[7]).sort().at(-1):null,
      calidad:filas.length?([...new Set(filas.map(x=>x.calidad))].length>1?"mixta":filas[0].calidad):null,
      preliminar:filas.some(x=>x.calidad==="NRT")});
  }

  async function responderApi(url) {
    const p = url.searchParams, ruta = url.pathname;
    try {
      if(ruta==="/estado-servicios")return responder({firms:{configurada:false,cifrada:false,estado:"sin_servidor",modo:"estatico",origen_datos:"sintetico",ultima_ingesta:null},idiomas:["es","en","fr"]});
      if(ruta==="/procedencia")return responder(await leer("api/procedencia.json"));
      if (ruta === "/detecciones") return await rutaDetecciones(p);
      if (ruta === "/calendario") return await rutaCalendario(p);
      if (ruta === "/resumen") {
        return p.get("area") ? responder(await leer(`api/resumen/${slug(p.get("area"))}.json`))
          : noDisponible("resumir áreas dibujadas o por coordenadas");
      }
      if (ruta === "/global") return p.has("desde") ? await globalPorFechas(p) : responder(await leer(`api/global/${p.get("dias")||2}_${p.get("res")||0.5}.json`));
      if (ruta.startsWith("/limites/")) return noDisponible("ver límites administrativos fuera del Huila");
      if (ruta === "/buscar-lugares") return noDisponible("buscar lugares en internet; los municipios del Huila sí se buscan", 503);
    } catch {
      return noDisponible("esta consulta");
    }
    return noDisponible("esta consulta");
  }

  const RUTAS_API = /^\/(detecciones|calendario|resumen|global|buscar-lugares|estado-servicios|procedencia|salud|cita)$|^\/limites\//;
  window.fetch = function (entrada, opciones) {
    const url = new URL(typeof entrada === "string" || entrada instanceof URL ? entrada : entrada.url, location.href);
    if (url.origin !== location.origin) return original(entrada, opciones);
    // Rutas absolutas de la interfaz (/ui/...) → archivos del sitio; rutas de la API → precalculadas.
    if (url.pathname.startsWith("/ui/")) return original(enRaiz(url.pathname.slice(4) + url.search), opciones);
    if (RUTAS_API.test(url.pathname)) return responderApi(url);
    return original(entrada, opciones);
  };

  // Descargas CSV: solo las precalculadas (Huila, año completo).
  document.addEventListener("click", async (ev) => {
    const a = ev.target.closest?.("a[download]");
    if (!a) return;
    const u = new URL(a.href, location.href);
    const tipo = { "/calendario.csv": "calendario", "/detecciones.csv": "detecciones" }[u.pathname];
    if (!tipo || u.origin !== location.origin) return;
    ev.preventDefault();
    const q = u.searchParams, y = (q.get("desde") ?? "").slice(0, 4), nombre = `${tipo}_huila_${y}`;
    const indice = await leer("api/indice.json");
    if (q.get("area") === "huila" && q.get("desde") === `${y}-01-01` && q.get("hasta") === `${y}-12-31` && indice.csv.includes(nombre)) {
      const enlace = document.createElement("a");
      enlace.href = enRaiz(`api/csv/${nombre}.csv`);
      enlace.download = `${nombre}.csv`;
      document.body.appendChild(enlace); enlace.click(); enlace.remove();
    } else {
      window.alert("En la demo publicada solo se descargan los CSV del Huila por año completo. Para otras áreas o fechas, ejecute la API local (make api).");
    }
  }, true);

  document.addEventListener("DOMContentLoaded", () => {
    const aviso = document.createElement("p");
    aviso.className = "alerta-breve";
    aviso.textContent = "Demo publicada sin servidor: datos SINTÉTICOS precalculados del Huila. La búsqueda en internet, " +
      "las áreas dibujadas y los límites fuera del Huila requieren la API local (make api).";
    document.querySelector(".marca")?.appendChild(aviso);
  });
})();
