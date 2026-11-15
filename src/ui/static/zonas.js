/* Zonas administrativas en el cliente (ADR 0013): pertenencia de un punto, nivel de
 * resaltado según el zoom, búsqueda local y celdas de la grilla armonizada.
 * Funciones puras, sin DOM ni red: se prueban con node (tests/test_interfaz.py).
 */
"use strict";

(function (raiz) {
  // Umbral PROVISIONAL de resaltado, en zoom MapLibre (teselas de 512 px; ≈ zoom 9 de Leaflet).
  // El pedido inicial proponía 9. La prueba visual (tools/recorrido_capas.mjs, 2026-11-15) midió
  // que el Huila (2,29° de alto) solo cabe completo en el mapa de escritorio 1440×900 hasta el
  // zoom 7,55; a zoom 8 ocupa ~834 px de alto y ya no cabe, mientras el municipio mediano mide
  // ~100 px y el menor (Elías) ~60 px: legibles y fáciles de pulsar. Por eso, desde 8 se resalta
  // el MUNICIPIO (con el departamento como contexto) y por debajo el DEPARTAMENTO.
  // Capturas: docs/capturas/visor_capas_20261115/umbral_zoom_7_9.png y umbral_zoom_8.png.
  const UMBRAL_ZOOM_MUNICIPIO = 8;
  // Umbral PROVISIONAL de CIUDAD (ADR 0014). La prueba visual midió que el municipio de Neiva
  // (0,68°) deja de caber en el mapa de escritorio desde el zoom 9,58; a zoom 11 el área urbana
  // de Neiva (~0,045°, Natural Earth) mide ~130 px. Desde 11, si el punto cae en un área urbana,
  // se resalta la ciudad con su municipio como contexto; si no, sigue el municipio.
  // Captura: docs/capturas/visor_capas_20261115/umbral_zoom_11.png.
  const UMBRAL_ZOOM_CIUDAD = 11;
  // Etiquetas: el nombre del departamento desde este zoom y hasta el umbral municipal;
  // los municipios desde el umbral. Las líneas de los límites no dependen del zoom.
  const ZOOM_ETIQUETA_DEPARTAMENTO = 5.5;
  // Grilla armonizada (ADR 0001, PROVISIONAL): origen (lat, lon) = (-90, -180), lado 0,009°.
  const GRILLA_ORIGEN = [-90, -180];
  const GRILLA_LADO = 0.009;

  const nivelResaltado = (zoom) => (zoom >= UMBRAL_ZOOM_CIUDAD ? "ciudad" : zoom >= UMBRAL_ZOOM_MUNICIPIO ? "municipio" : "departamento");

  function etiquetasVisibles(zoom) {
    return { departamento: zoom >= ZOOM_ETIQUETA_DEPARTAMENTO && zoom < UMBRAL_ZOOM_MUNICIPIO,
      municipio: zoom >= UMBRAL_ZOOM_MUNICIPIO };
  }

  function poligonos(geom) {
    if (!geom) return [];
    if (geom.type === "Polygon") return [geom.coordinates];
    if (geom.type === "MultiPolygon") return geom.coordinates;
    return [];
  }

  function enAnillo(anillo, x, y) {
    let dentro = false;
    for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
      const [xi, yi] = anillo[i], [xj, yj] = anillo[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) dentro = !dentro;
    }
    return dentro;
  }

  function cajaDe(geom) {
    let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
    for (const pol of poligonos(geom)) for (const [x, y] of pol[0]) {
      if (x < w) w = x; if (x > e) e = x; if (y < s) s = y; if (y > n) n = y;
    }
    return [w, s, e, n];
  }

  /** ¿El punto (lon, lat) está dentro de la geometría? Respeta los huecos. */
  function contiene(geom, lon, lat) {
    for (const pol of poligonos(geom)) {
      if (enAnillo(pol[0], lon, lat) && !pol.slice(1).some((h) => enAnillo(h, lon, lat))) return true;
    }
    return false;
  }

  /** Primera zona que contiene el punto; descarta antes por recuadro. */
  function zonaDe(lon, lat, features) {
    for (const f of features ?? []) {
      const b = f.properties?.bbox ?? (f._caja ??= cajaDe(f.geometry));
      if (lon < b[0] || lon > b[2] || lat < b[1] || lat > b[3]) continue;
      if (contiene(f.geometry, lon, lat)) return f;
    }
    return null;
  }

  /**
   * Zona que se resalta al seleccionar un punto, según el zoom: ciudad (contexto: municipio),
   * municipio (contexto: departamento) o departamento. Si falta el nivel pedido, baja al
   * siguiente que exista. Devuelve null si el punto no cae en ninguna zona conocida.
   */
  function zonaSeleccionada(lon, lat, zoom, { departamentos = [], municipios = [], ciudades = [] }) {
    const nivel = nivelResaltado(zoom);
    const depto = zonaDe(lon, lat, departamentos);
    const muni = nivel !== "departamento" ? zonaDe(lon, lat, municipios) : null;
    if (nivel === "ciudad") {
      const ciudad = zonaDe(lon, lat, ciudades);
      if (ciudad) return { nivel: "ciudad", zona: ciudad, contexto: muni ?? depto };
    }
    if (muni) return { nivel: "municipio", zona: muni, contexto: depto };
    return depto ? { nivel: "departamento", zona: depto, contexto: null } : null;
  }

  /** Polígono del mundo con la zona como hueco: sirve para atenuar todo lo demás. */
  function mascara(geom) {
    const mundo = [[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]];
    const huecos = poligonos(geom).map((pol) => [...pol[0]].reverse());
    return { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [mundo, ...huecos] } };
  }

  /** Punto interior para la etiqueta (barrido horizontal; el centroide puede caer fuera). */
  function puntoInterior(geom) {
    const mayor = poligonos(geom).sort((a, b) => b[0].length - a[0].length)[0];
    if (!mayor) return null;
    const ys = mayor[0].map((p) => p[1]);
    const y0 = Math.min(...ys), y1 = Math.max(...ys);
    for (const f of [0.5, 0.4, 0.6, 0.3, 0.7]) {
      const y = y0 + (y1 - y0) * f, cortes = [];
      for (const anillo of mayor) for (let i = 1; i < anillo.length; i++) {
        const [xa, ya] = anillo[i - 1], [xb, yb] = anillo[i];
        if ((ya > y) !== (yb > y)) cortes.push(xa + ((y - ya) * (xb - xa)) / (yb - ya));
      }
      cortes.sort((a, b) => a - b);
      let mejor = null;
      for (let i = 0; i + 1 < cortes.length; i += 2) if (!mejor || cortes[i + 1] - cortes[i] > mejor[1] - mejor[0]) mejor = [cortes[i], cortes[i + 1]];
      if (mejor && contiene(geom, (mejor[0] + mejor[1]) / 2, y)) return [(mejor[0] + mejor[1]) / 2, y];
    }
    const b = cajaDe(geom);
    return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
  }

  /** Minúsculas, sin tildes ni espacios repetidos: «Garzón» ≡ «garzon». */
  const normalizar = (t) => String(t ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9ñ ]+/g, " ").replace(/\s+/g, " ").trim();

  /**
   * Búsqueda en la lista local (sin red). Exacto > empieza por > contiene. También acepta
   * «Neiva, Huila» o «municipio de Neiva». Devuelve [{nombre, tipo, nivel, feature}].
   */
  function buscarLocal(texto, { municipios = [], departamentos = [] } = {}) {
    const q = normalizar(texto).replace(/^(municipio|departamento) (de |del )?/, "").split(" huila")[0].trim()
      || normalizar(texto);
    if (q.length < 3) return [];
    const candidatos = [
      ...departamentos.map((f) => ({ f, nivel: "departamento", tipo: "Departamento" })),
      ...municipios.map((f) => ({ f, nivel: "municipio", tipo: "Municipio" })),
    ];
    const puntaje = (nombre) => {
      const n = normalizar(nombre);
      return n === q ? 3 : n.startsWith(q) ? 2 : n.includes(q) ? 1 : 0;
    };
    // Ante un empate exacto gana el departamento; en coincidencias parciales, el municipio.
    const orden = (c) => c.p * 10 + ((c.p === 3) === (c.nivel === "departamento") ? 1 : 0);
    return candidatos.map((c) => ({ ...c, p: puntaje(c.f.properties.shapeName) }))
      .filter((c) => c.p > 0)
      .sort((a, b) => orden(b) - orden(a)
        || a.f.properties.shapeName.localeCompare(b.f.properties.shapeName, "es"))
      .slice(0, 6)
      .map((c) => ({ nombre: c.f.properties.shapeName, tipo: c.tipo, nivel: c.nivel, feature: c.f }));
  }

  /** Cuenta focos y focos de confianza alta dentro de la geometría (respaldo en el cliente). */
  function contarEn(geom, detecciones) {
    const b = cajaDe(geom);
    let n = 0, alta = 0;
    for (const d of detecciones ?? []) {
      if (d.lon < b[0] || d.lon > b[2] || d.lat < b[1] || d.lat > b[3] || !contiene(geom, d.lon, d.lat)) continue;
      n++; if (d.confianza_clase === "alta") alta++;
    }
    return { n, alta };
  }

  /** Celdas activas de la grilla armonizada (una por cell_id) como polígonos GeoJSON. */
  function celdasActivas(detecciones, lado = GRILLA_LADO) {
    const celdas = new Map();
    for (const d of detecciones ?? []) {
      const m = /^f(-?\d+)_c(-?\d+)$/.exec(d.cell_id ?? "");
      if (!m) continue;
      const previa = celdas.get(d.cell_id);
      const frp = Math.max(previa?.frp_max ?? 0, d.frp ?? 0);
      celdas.set(d.cell_id, { fila: Number(m[1]), col: Number(m[2]), frp_max: frp, n: (previa?.n ?? 0) + 1 });
    }
    const [lat0, lon0] = GRILLA_ORIGEN;
    return { type: "FeatureCollection", features: [...celdas.entries()].map(([id, c]) => {
      const s = lat0 + c.fila * lado, w = lon0 + c.col * lado;
      return { type: "Feature", properties: { cell_id: id, frp_max: c.frp_max, n: c.n },
        geometry: { type: "Polygon", coordinates: [[[w, s], [w + lado, s], [w + lado, s + lado], [w, s + lado], [w, s]]] } };
    }) };
  }

  const api = { UMBRAL_ZOOM_MUNICIPIO, UMBRAL_ZOOM_CIUDAD, ZOOM_ETIQUETA_DEPARTAMENTO, GRILLA_ORIGEN, GRILLA_LADO,
    nivelResaltado, etiquetasVisibles, contiene, zonaDe, zonaSeleccionada, mascara, puntoInterior,
    cajaDe, normalizar, buscarLocal, contarEn, celdasActivas };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.Zonas = api;
})(typeof window !== "undefined" ? window : globalThis);
