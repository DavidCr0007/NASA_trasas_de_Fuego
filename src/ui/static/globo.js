/* Harmonized Heat: globo 3D con los focos activos de todo el mundo (ADR 0012).
 * MapLibre GL JS 5 va incluido en vendor/ (sin CDN). Fondo: NASA GIBS (Blue Marble de día,
 * Black Marble en el tema oscuro), opcional; sin red quedan los países de Natural Earth (local).
 * Los focos llegan agregados en celdas desde /global; el detalle de cada foco se ve en el
 * mapa regional (Leaflet) al acercarse.
 */
"use strict";

(function () {
  const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/";
  const FONDOS = {
    claro: `${GIBS}BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg`,
    oscuro: `${GIBS}VIIRS_Black_Marble/default/2016-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png`,
  };
  // Clases de FRP máximo (MW) de la celda: mismas que la leyenda y el mapa regional.
  const CORTES_FRP = [5, 20, 100, 500];
  const PERIODOS = [[1, "Últimas 24 h"], [2, "Últimas 48 h"], [7, "Últimos 7 días"]];

  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const fmt = (n, d = 0) => (n == null ? "—" : Number(n).toLocaleString("es-CO", { maximumFractionDigits: d }));
  const token = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const fecha = (iso) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}))?/.exec(String(iso ?? ""));
    return m ? `${Number(m[3])} ${MESES[Number(m[2]) - 1]}${m[4] ? `, ${m[4]} UTC` : ` ${m[1]}`}` : "—";
  };
  const movimientoReducido = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /**
   * opciones: { contenedor, panel, oscuro(): bool, alExplorar(lon, lat, zoomLeaflet),
   *             umbralRegional (zoom MapLibre a partir del cual se pasa al mapa regional) }
   */
  function crear(opciones) {
    const { contenedor, panel } = opciones;
    const umbral = opciones.umbralRegional ?? 5.2;
    let mapa = null, listo = false, datos = null, dias = 2, res = 0.5, gen = 0;
    let programatico = false, zoomInicio = 0, rotar = null, paises = null;
    const cache = new Map();

    function colores() {
      return {
        f: [token("--f1"), token("--f2"), token("--f3"), token("--f4"), token("--f5")],
        borde: token("--globo-borde"), tierra: token("--globo-tierra"), mar: token("--globo-mar"),
        trazo: token("--globo-trazo"), sel: token("--sel"),
      };
    }

    function estilo() {
      const c = colores();
      return {
        version: 8,
        projection: { type: "globe" },
        sky: { "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 1, 7, 0] },
        sources: {
          fondo: { type: "raster", tiles: [opciones.oscuro() ? FONDOS.oscuro : FONDOS.claro], tileSize: 256, maxzoom: 8,
            attribution: 'Fondo: <a href="https://www.earthdata.nasa.gov/data/tools/gibs">NASA GIBS</a> (Blue Marble / Black Marble)' },
          paises: { type: "geojson", data: "/ui/datos/mundo_paises.geojson",
            attribution: 'Países: <a href="https://www.naturalearthdata.com">Natural Earth</a> (dominio público)' },
          focos: { type: "geojson", data: { type: "FeatureCollection", features: [] },
            attribution: 'Focos: <a href="https://www.earthdata.nasa.gov/data/tools/firms">NASA FIRMS</a> (LANCE / ESDIS)' },
        },
        layers: [
          { id: "mar", type: "background", paint: { "background-color": c.mar } },
          { id: "tierra", type: "fill", source: "paises", paint: { "fill-color": c.tierra } },
          { id: "fondo", type: "raster", source: "fondo", paint: { "raster-opacity": 1, "raster-fade-duration": 200 } },
          { id: "fronteras", type: "line", source: "paises", paint: { "line-color": c.borde, "line-width": 0.6, "line-opacity": 0.55 } },
          { id: "pais-sel", type: "line", source: "paises", filter: ["==", ["get", "iso_a3"], ""],
            paint: { "line-color": c.sel, "line-width": 2.2 } },
          { id: "focos-halo", type: "circle", source: "focos", paint: {
            "circle-color": colorFrp(c), "circle-opacity": 0.28, "circle-blur": 1,
            "circle-radius": radio(2.4), "circle-pitch-alignment": "map" } },
          { id: "focos", type: "circle", source: "focos", paint: {
            "circle-color": colorFrp(c), "circle-opacity": ["interpolate", ["linear"], ["get", "frac_alta"], 0, 0.72, 0.3, 0.95],
            "circle-radius": radio(1), "circle-stroke-color": c.trazo, "circle-stroke-width": 0.5,
            "circle-pitch-alignment": "map" } },
        ],
      };
    }

    function colorFrp(c) {
      return ["step", ["coalesce", ["get", "frp_max"], 0], c.f[0], CORTES_FRP[0], c.f[1], CORTES_FRP[1], c.f[2], CORTES_FRP[2], c.f[3], CORTES_FRP[3], c.f[4]];
    }

    /** Radio por número de focos (raíz cuadrada: el área del círculo crece con el conteo). */
    function radio(k) {
      const r = (base, f, max) => ["*", k, ["min", max, ["+", base, ["*", f, ["sqrt", ["get", "n"]]]]]];
      return ["interpolate", ["linear"], ["zoom"], 0, r(1.1, 0.16, 7), 3, r(1.8, 0.32, 13), 6, r(3, 0.6, 24)];
    }

    function aGeojson(d) {
      const i = Object.fromEntries(d.campos_celda.map((k, j) => [k, j]));
      return {
        type: "FeatureCollection",
        features: d.celdas.map((c) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [c[i.lon], c[i.lat]] },
          properties: { n: c[i.n], frp_max: c[i.frp_max], frp_sum: c[i.frp_sum], n_alta: c[i.n_alta],
            n_viirs: c[i.n_viirs], ultimo: c[i.ultimo_utc], iso: c[i.iso_a3], frac_alta: c[i.n_alta] / Math.max(1, c[i.n]) },
        })).sort((a, b) => (a.properties.frp_max ?? 0) - (b.properties.frp_max ?? 0)),
      };
    }

    async function cargarDatos() {
      const clave = `${dias}:${res}`;
      const g = ++gen;
      pintarPanelCargando();
      try {
        let d = cache.get(clave);
        if (!d) {
          const r = await fetch(`/global?dias=${dias}&res=${res}`);
          const texto = await r.text();
          let cuerpo = null;
          try { cuerpo = JSON.parse(texto); } catch { /* no JSON */ }
          if (!r.ok || !cuerpo) throw new Error(cuerpo?.detail ?? `HTTP ${r.status}`);
          d = cuerpo;
          cache.set(clave, d);
        }
        if (g !== gen) return;
        datos = d;
        aplicarDatos();
        pintarPanel();
      } catch (err) {
        if (g !== gen) return;
        panel.querySelector(".globo-cifras").innerHTML =
          `<p class="globo-error">No se pudieron cargar los focos globales: ${esc(err.message)}</p>`;
      }
    }

    /** La fuente existe en cuanto carga el estilo, sin esperar a las teselas de fondo (GIBS). */
    function aplicarDatos() {
      const fuente = mapa && mapa.getSource("focos");
      if (fuente && datos) fuente.setData(aGeojson(datos));
    }

    function pintarPanelCargando() {
      const caja = panel.querySelector(".globo-cifras");
      if (caja && !datos) caja.innerHTML = `<p class="tenue">Cargando focos de todo el mundo…</p>`;
    }

    function sparkline(serie) {
      if (!serie.length) return "";
      const W = 220, H = 36, max = Math.max(1, ...serie.map((s) => s.n)), bw = W / serie.length;
      const barras = serie.map((s, k) => {
        const h = Math.max(1, (H - 12) * s.n / max);
        return `<rect x="${k * bw + 1}" y="${H - 12 - h}" width="${Math.max(1, bw - 2)}" height="${h}" rx="1.5"><title>${esc(fecha(s.fecha_utc))}: ${esc(fmt(s.n))} focos</title></rect>`;
      }).join("");
      const etiquetas = `<text x="0" y="${H - 1}" font-size="9">${esc(fecha(serie[0].fecha_utc).replace(/ \d{4}$/, ""))}</text>` +
        `<text x="${W}" y="${H - 1}" font-size="9" text-anchor="end">${esc(fecha(serie[serie.length - 1].fecha_utc).replace(/ \d{4}$/, ""))}</text>`;
      return `<svg class="globo-serie" viewBox="0 0 ${W} ${H}" width="100%" role="img" ` +
        `aria-label="Focos por día: ${esc(serie.map((s) => `${fecha(s.fecha_utc)} ${fmt(s.n)}`).join("; "))}">${barras}${etiquetas}</svg>`;
    }

    function pintarPanel() {
      const d = datos;
      if (!d) return;
      const ultimoDia = d.serie_diaria.length ? d.serie_diaria[d.serie_diaria.length - 1] : null;
      const parcial = ultimoDia && d.hasta === d.cobertura.hasta;
      panel.querySelector(".globo-cifras").innerHTML =
        `<p class="globo-cifra"><strong>${esc(fmt(d.total_detecciones))}</strong> focos de calor</p>` +
        `<p class="tenue">${esc(fmt(d.total_alta))} de confianza alta · ${esc(fmt(d.n_paises))} países · ` +
        `${esc(fecha(d.desde))} → ${esc(fecha(d.hasta))}${parcial ? " (último día aún en curso)" : ""}</p>` +
        sparkline(d.serie_diaria) +
        `<h3>Países con más focos</h3><ol class="globo-paises">${d.paises.filter((p) => p.iso_a3).slice(0, 8).map((p) =>
          `<li><button type="button" data-iso="${esc(p.iso_a3)}"><span>${esc(p.nombre)}</span>` +
          `<span class="tenue">${esc(fmt(p.n))}</span></button></li>`).join("")}</ol>`;
      panel.querySelectorAll(".globo-paises button").forEach((b) => b.addEventListener("click", () => irAPais(b.dataset.iso)));
      const ins = panel.querySelector(".globo-insignia");
      ins.className = `globo-insignia insignia ${d.preliminar ? "preliminar" : "estandar"}`;
      ins.textContent = d.preliminar ? "PRELIMINAR · NRT" : "Calidad estándar";
      ins.title = d.preliminar ? "Datos casi en tiempo real (NRT): pueden corregirse." : "Datos de la versión estándar.";
    }

    async function cargarPaises() {
      if (paises) return paises;
      try {
        const r = await fetch("/ui/datos/mundo_paises.geojson");
        paises = new Map((await r.json()).features.map((f) => [f.properties.iso_a3, f.properties]));
      } catch { paises = new Map(); }
      return paises;
    }

    async function irAPais(iso) {
      const p = (await cargarPaises()).get(iso);
      if (!p || !listo) return;
      detenerRotacion();
      mapa.setFilter("pais-sel", ["==", ["get", "iso_a3"], iso]);
      const [w, s, e, n] = p.bbox;
      programatico = true;
      // Se queda por debajo del umbral regional: la vista de país es el globo.
      mapa.fitBounds([[w, s], [e, n]], { padding: 48, maxZoom: umbral - 0.4, duration: movimientoReducido() ? 0 : 1600 });
      const fila = datos?.paises.find((x) => x.iso_a3 === iso);
      const nota = panel.querySelector(".globo-pais");
      nota.hidden = false;
      nota.innerHTML = `<strong>${esc(p.nombre)}</strong>: ${fila ? `${esc(fmt(fila.n))} focos, ${esc(fmt(fila.n_alta))} de confianza alta, ` +
        `FRP máx. ${esc(fmt(fila.frp_max, 0))} MW.` : "sin focos en el periodo."} <span class="tenue">Acérquese para ver cada foco en el mapa regional.</span>`;
    }

    function popup(f, lngLat) {
      const p = f.properties;
      const pais = paises?.get(p.iso)?.nombre ?? (p.iso ? p.iso : "fuera de país (mar o costa)");
      const html = `<strong>${esc(fmt(p.n))} ${p.n === 1 ? "foco" : "focos"}</strong> en esta celda de ~${esc(fmt(res * 111))} km<br>` +
        `${esc(pais)} · confianza alta: ${esc(fmt(p.n_alta))}<br>` +
        `FRP máx.: ${esc(fmt(p.frp_max, 1))} MW · VIIRS ${esc(fmt(p.n_viirs))} · MODIS ${esc(fmt(p.n - p.n_viirs))}<br>` +
        `Último: ${esc(fecha(p.ultimo))}<br>` +
        `<button type="button" class="globo-explorar">Ver cada foco en el mapa regional</button>`;
      const pop = new maplibregl.Popup({ closeButton: true, maxWidth: "280px", className: "globo-popup" }).setLngLat(lngLat).setHTML(html).addTo(mapa);
      pop.getElement().querySelector(".globo-explorar").addEventListener("click", () => {
        pop.remove();
        opciones.alExplorar(lngLat.lng, lngLat.lat, 9);
      });
    }

    function iniciarRotacion() {
      if (movimientoReducido() || rotar) return;
      const paso = () => {
        if (!rotar) return;
        const c = mapa.getCenter();
        if (mapa.getZoom() < 3) mapa.jumpTo({ center: [c.lng + 0.08, c.lat] });
        rotar = requestAnimationFrame(paso);
      };
      rotar = requestAnimationFrame(paso);
      panel.querySelector(".globo-rotar").setAttribute("aria-pressed", "true");
    }
    function detenerRotacion() {
      if (rotar) cancelAnimationFrame(rotar);
      rotar = null;
      panel.querySelector(".globo-rotar")?.setAttribute("aria-pressed", "false");
    }

    function construir(centro, zoom) {
      mapa = new maplibregl.Map({
        container: contenedor, style: estilo(), center: centro, zoom, minZoom: 0.6, maxZoom: umbral + 1,
        attributionControl: { compact: true }, renderWorldCopies: false, dragRotate: false, pitchWithRotate: false,
      });
      mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      mapa.on("styledata", () => { if (!listo && mapa.getSource("focos")) { listo = true; aplicarDatos(); } });
      mapa.on("load", () => {
        listo = true;
        aplicarDatos();
        mapa.getCanvas().setAttribute("aria-label", "Globo terráqueo con los focos de calor activos de todo el mundo");
      });
      ["mousedown", "touchstart", "wheel"].forEach((ev) => mapa.on(ev, detenerRotacion));
      mapa.on("mouseenter", "focos", () => { mapa.getCanvas().style.cursor = "pointer"; });
      mapa.on("mouseleave", "focos", () => { mapa.getCanvas().style.cursor = ""; });
      mapa.on("click", "focos", (ev) => { detenerRotacion(); cargarPaises().then(() => popup(ev.features[0], ev.lngLat)); });
      mapa.on("zoomstart", () => { zoomInicio = mapa.getZoom(); });
      mapa.on("moveend", () => { programatico = false; });
      mapa.on("zoomend", () => {
        const z = mapa.getZoom();
        const nuevaRes = z < 2.5 ? 0.5 : 0.25;
        if (nuevaRes !== res) { res = nuevaRes; cargarDatos(); }
        // Acercarse más allá de la vista de país lleva al mapa regional (Leaflet), en el mismo punto.
        if (!programatico && z > zoomInicio && z >= umbral) {
          const c = mapa.getCenter();
          opciones.alExplorar(c.lng, c.lat, Math.round(z + 1));
        }
      });
    }

    function montarPanel() {
      panel.innerHTML =
        `<div class="globo-cabeza"><h2>Focos activos en el mundo</h2><span class="globo-insignia insignia">…</span></div>` +
        `<label class="globo-periodo">Periodo <select>${PERIODOS.map(([v, t]) => `<option value="${v}"${v === dias ? " selected" : ""}>${t}</option>`).join("")}</select></label>` +
        `<div class="globo-cifras" aria-live="polite"></div>` +
        `<p class="globo-pais" hidden></p>` +
        `<div class="globo-leyenda" aria-label="Leyenda del globo"><span class="tenue">FRP máx. (MW):</span>` +
        ["&lt; 5", "5–20", "20–100", "100–500", "≥ 500"].map((t, k) => `<span><i class="esc-frp f${k + 1}"></i>${t}</span>`).join("") +
        `<span class="tenue">Tamaño = n.º de focos en la celda.</span></div>` +
        `<p class="tenue globo-nota">Detecciones térmicas, no incendios confirmados. Acérquese para ver cada foco.</p>` +
        `<div class="globo-acciones"><button type="button" class="globo-rotar" aria-pressed="false">Girar el globo</button>` +
        `<button type="button" class="globo-volver">Volver al mapa regional</button></div>`;
      panel.querySelector(".globo-periodo select").addEventListener("change", (ev) => { dias = Number(ev.target.value); cargarDatos(); });
      panel.querySelector(".globo-rotar").addEventListener("click", () => (rotar ? detenerRotacion() : iniciarRotacion()));
      panel.querySelector(".globo-volver").addEventListener("click", () => opciones.alVolver());
    }

    return {
      /** Muestra el globo centrado en [lon, lat] con el zoom MapLibre dado. */
      mostrar(lon, lat, zoom) {
        if (!mapa) {
          montarPanel();
          construir([lon, lat], zoom);
          cargarDatos();
          cargarPaises();
          setTimeout(iniciarRotacion, 2500);
        } else {
          programatico = true;
          mapa.resize();
          mapa.jumpTo({ center: [lon, lat], zoom });
          programatico = false;
        }
      },
      ocultar() { detenerRotacion(); },
      /** Vuelve a pintar con los colores y el fondo del tema activo. */
      repintar() {
        if (!mapa || !listo) return;
        const c = colores();
        mapa.setPaintProperty("mar", "background-color", c.mar);
        mapa.setPaintProperty("tierra", "fill-color", c.tierra);
        mapa.setPaintProperty("fronteras", "line-color", c.borde);
        mapa.setPaintProperty("pais-sel", "line-color", c.sel);
        mapa.setPaintProperty("focos", "circle-color", colorFrp(c));
        mapa.setPaintProperty("focos", "circle-stroke-color", c.trazo);
        mapa.setPaintProperty("focos-halo", "circle-color", colorFrp(c));
        mapa.getSource("fondo").setTiles([opciones.oscuro() ? FONDOS.oscuro : FONDOS.claro]);
      },
    };
  }

  window.Globo = { crear, CORTES_FRP };
})();
