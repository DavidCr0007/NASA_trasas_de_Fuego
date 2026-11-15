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
      if (ruta === "/global") return responder(await leer(`api/global/${p.get("dias")}_${p.get("res")}.json`));
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
