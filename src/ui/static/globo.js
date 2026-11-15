/* Harmonized Heat: globo 3D con los focos activos de todo el mundo (ADR 0012).
 * Un solo lienzo MapLibre GL JS 5 (incluido en vendor/), de la esfera al detalle.
 * Blue Marble natural se mantiene fijo. Límites geoBoundaries bajo demanda.
 */
"use strict";

(function () {
  const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/";
  const FONDOS = {
    claro: `${GIBS}BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg`,
  };
  const fondo = () => FONDOS.claro;
  // Clases de FRP máximo (MW) de la celda: mismas que la leyenda y el mapa regional.
  const CORTES_FRP = [5, 20, 100, 500];
  const PERIODOS = [[1, "1 día del archivo"], [2, "2 días del archivo"], [7, "7 días del archivo"]];

  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const fmt = (n, d = 0) => (n == null ? "—" : Number(n).toLocaleString("es-CO", { maximumFractionDigits: d }));
  const token = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const fecha = (iso) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}))?/.exec(String(iso ?? ""));
    return m ? `${Number(m[3])} ${MESES[Number(m[2]) - 1]} ${m[1]}${m[4] ? `, ${m[4]} UTC` : ""}` : "—";
  };
  const movimientoReducido = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /**
   * opciones: contenedor y panel; callbacks de ficha, encuadre y carga.
   * Toda navegación conserva el mapa y la proyección; no hay otro motor de detalle.
   */
  function crear(opciones) {
    const { contenedor, panel } = opciones;
    const zoomPais = 4.8;
    let mapa = null, listo = false, datos = null, dias = 2, res = 0.5, gen = 0;
    let rotar = null, paises = null;
    let paginaCeldas = 0, paisCeldas = "";
    let paisSeleccionado = null, marcadorLugar = null;
    const cache = new Map();
    let consulta = null;
    let activo = true;
    let detalle = null, vistaGen = 0, limitesCtrl = null, dibujando = false;
    const limitesCache = new Map();
    let indiceLimites = null;
    const vacio = () => ({ type: "FeatureCollection", features: [] });
    const detalleDisponible = () => Boolean(datos?.detalle_mismo_conjunto);
    const notaSinDetalle = "El globo y el mapa regional usan conjuntos distintos. No se puede abrir aquí el detalle de estas detecciones.";

    function colores() {
      return {
        f: [token("--f1"), token("--f2"), token("--f3"), token("--f4"), token("--f5")],
        tierra: "#718c57", mar: "#071521", trazo: "#35251e",
      };
    }

    function estilo() {
      const c = colores();
      return {
        version: 8,
        projection: { type: "globe" },
        sky: { "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 1, 7, 0] },
        sources: {
          fondo: { type: "raster", tiles: [fondo()], tileSize: 256, maxzoom: 8 },
          paises: { type: "geojson", data: "/ui/datos/mundo_paises.geojson",
          },
          adm0: { type: "geojson", data: vacio() },
          adm1: { type: "geojson", data: vacio() },
          adm2: { type: "geojson", data: vacio() },
          detalle: { type: "geojson", data: vacio(), cluster: true, clusterRadius: 35, clusterMaxZoom: 10,
            clusterProperties: { frp_max: ["max", ["coalesce", ["get", "frp"], 0]] } },
          seleccion: { type: "geojson", data: vacio() },
          focos: { type: "geojson", data: { type: "FeatureCollection", features: [] } },
        },
        layers: [
          { id: "mar", type: "background", paint: { "background-color": c.mar } },
          { id: "tierra", type: "fill", source: "paises", paint: { "fill-color": c.tierra } },
          { id: "fondo", type: "raster", source: "fondo", paint: { "raster-opacity": 1, "raster-saturation": 0, "raster-fade-duration": 200 } },
          ...[0, 1, 2].map((nivel) => ({ id: `limites-adm${nivel}`, type: "line", source: `adm${nivel}`,
            minzoom: [3, 5, 8][nivel], paint: { "line-color": ["#fff8dc", "#f7e6ad", "#edf5f8"][nivel],
              "line-width": [1.1, 0.9, 0.65][nivel],
              "line-opacity": ["interpolate", ["linear"], ["zoom"], [3,5,8][nivel], 0, [4,6,9][nivel], [0.8,0.65,0.55][nivel]] } })),
          { id: "focos-halo", type: "circle", source: "focos", paint: {
            "circle-color": colorFrp(c), "circle-opacity": 0.28, "circle-blur": 1,
            "circle-radius": radio(2.4), "circle-pitch-alignment": "map" } },
          { id: "focos", type: "circle", source: "focos", paint: {
            "circle-color": colorFrp(c), "circle-opacity": ["interpolate", ["linear"], ["get", "frac_alta"], 0, 0.72, 0.3, 0.95],
            "circle-radius": radio(1), "circle-stroke-color": c.trazo, "circle-stroke-width": 0.5,
            "circle-pitch-alignment": "map" } },
          { id: "detalle-grupos", type: "circle", source: "detalle", filter: ["has", "point_count"], paint: {
            "circle-color": colorFrp(c), "circle-radius": ["min", 22, ["+", 4, ["sqrt", ["get", "point_count"]]]],
            "circle-stroke-color": c.trazo, "circle-stroke-width": 1, "circle-opacity": 0.92 } },
          { id: "detalle-focos", type: "circle", source: "detalle", filter: ["!", ["has", "point_count"]], paint: {
            "circle-color": ["step", ["coalesce", ["get", "frp"], 0], c.f[0], 5,c.f[1],20,c.f[2],100,c.f[3],500,c.f[4]],
            "circle-radius": ["step", ["coalesce", ["get", "frp"], 0], 3.5,5,5,20,7,100,9.5,500,12.5],
            "circle-opacity": ["match", ["get", "confianza_clase"], "alta",0.95,"baja",0.55,0.8],
            "circle-stroke-color": c.trazo, "circle-stroke-width": 1 } },
          { id: "area-seleccion", type: "line", source: "seleccion", minzoom: 5, paint: { "line-color": "#ffffff", "line-width": 1.2, "line-dasharray": [3, 3] } },
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
      consulta?.abort();
      consulta = new AbortController();
      panel.setAttribute("aria-busy", "true");
      opciones.alCarga?.(true);
      pintarPanelCargando();
      try {
        let d = cache.get(clave);
        if (!d) {
          const r = await fetch(`/global?dias=${dias}&res=${res}`, { signal: consulta.signal });
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
        if (err.name === "AbortError" || g !== gen) return;
        panel.querySelector(".globo-cifras").innerHTML =
          `<p class="globo-error">No se pudieron cargar los focos globales: ${esc(err.message)}</p>`;
      } finally {
        if (g === gen) { panel.removeAttribute("aria-busy"); opciones.alCarga?.(false); }
      }
    }

    /** La fuente existe en cuanto carga el estilo, sin esperar a las teselas de fondo (GIBS). */
    function aplicarDatos() {
      const fuente = mapa && mapa.getSource("focos");
      if (fuente && datos) fuente.setData(aGeojson(datos));
      if (mapa?.getSource("detalle") && detalle) mapa.getSource("detalle").setData(detalle);
      actualizarCapas();
    }

    function actualizarCapas() {
      if (!mapa?.getLayer("focos")) return;
      const cercano = mapa.getZoom() >= 6 && detalle !== null && (opciones.usarDetalle?.() ?? true);
      for (const id of ["focos", "focos-halo"]) mapa.setLayoutProperty(id, "visibility", cercano ? "none" : "visible");
      for (const id of ["detalle-focos", "detalle-grupos"]) mapa.setLayoutProperty(id, "visibility", cercano ? "visible" : "none");
    }

    function pintarPanelCargando() {
      const caja = panel.querySelector(".globo-cifras");
      if (caja && !datos) caja.innerHTML = `<div class="datos-esqueleto" aria-label="Resumen pendiente"><i></i><i></i><i></i></div>`;
    }

    function sparkline(serie) {
      if (serie.length < 2) return "";
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
      const parcial = ultimoDia && d.hasta === new Date().toISOString().slice(0, 10);
      const antiguedad = d.actualizado_hasta_utc ? Date.now() - Date.parse(d.actualizado_hasta_utc) : Infinity;
      const desactualizado = antiguedad > 48 * 60 * 60 * 1000;
      panel.querySelector(".globo-origen").textContent =
        `${d.origen_datos === "sintetico" ? "Datos sintéticos (demostración)" :
          d.origen_datos === "mixto" ? "Datos reales y sintéticos mezclados" :
            d.origen_datos === "real" ? "Datos reales NASA FIRMS" : "Origen no indicado"} · ${d.rules_version || "reglas sin versión"}`;
      const naturaleza = panel.querySelector(".globo-naturaleza");
      naturaleza.textContent = d.origen_datos === "real" ? "Datos reales · NASA FIRMS"
        : d.origen_datos === "sintetico" ? "Demostración · datos sintéticos"
        : d.origen_datos === "mixto" ? "Datos reales y sintéticos mezclados" : "Origen sin confirmar";
      naturaleza.className = `globo-naturaleza${d.origen_datos === "real" ? "" : " alerta-origen"}`;
      panel.querySelector(".globo-cobertura").textContent = d.desde===d.hasta
        ? `${fecha(d.desde)} · UTC` : `${fecha(d.desde)} → ${fecha(d.hasta)} · UTC`;
      panel.querySelector(".globo-actualizacion").textContent = `Último dato: ${fecha(d.actualizado_hasta_utc)}`;
      panel.querySelector(".globo-vigencia").hidden = !desactualizado;
      panel.querySelector(".globo-vigencia").textContent = desactualizado
        ? "Archivo sin actualizar en las últimas 48 horas. Verifique la fecha antes de usar estos datos."
        : "";
      panel.querySelector(".globo-detalle-estado").hidden = detalleDisponible();
      opciones.alDatos?.(d);
      actualizarContexto(activo);
      const rankingAbierto = panel.querySelector(".globo-ranking")?.open ?? false;
      panel.querySelector(".globo-cifras").innerHTML =
        `<p class="globo-cifra"><strong>${esc(fmt(d.total_detecciones))}</strong> focos de calor</p>` +
        `<p class="tenue">${esc(fmt(d.total_alta))} de confianza alta · ${esc(fmt(d.n_paises))} países` +
        `${parcial ? " · último día en curso" : ""}</p>` +
        sparkline(d.serie_diaria) +
        `<details class="globo-ranking"><summary>Países con más focos</summary><ol class="globo-paises">${d.paises.filter((p) => p.iso_a3).slice(0, 8).map((p) =>
          `<li><button type="button" data-iso="${esc(p.iso_a3)}"><span>${esc(p.nombre)}</span>` +
          `<span class="tenue">${esc(fmt(p.n))}</span></button></li>`).join("")}</ol></details>`;
      panel.querySelector(".globo-ranking").open = rankingAbierto;
      panel.querySelectorAll(".globo-paises button").forEach((b) => b.addEventListener("click", () => irAPais(b.dataset.iso)));
      const ins = panel.querySelector(".globo-insignia");
      ins.className = `globo-insignia insignia ${d.preliminar ? "preliminar" : "estandar"}`;
      ins.textContent = d.preliminar ? "PRELIMINAR · NRT" : "Calidad estándar";
      ins.title = d.preliminar ? "Datos casi en tiempo real (NRT): pueden corregirse." : "Datos de la versión estándar.";
      const selector = panel.querySelector(".globo-pais-buscar");
      selector.innerHTML = `<option value="">Todos los países</option>` + d.paises.filter((p) => p.iso_a3).map((p) =>
        `<option value="${esc(p.iso_a3)}">${esc(p.nombre)} (${esc(fmt(p.n))})</option>`).join("");
      if (![...selector.options].some((o) => o.value === paisCeldas)) paisCeldas = "";
      selector.value = paisCeldas;
      pintarListaCeldas();
      pintarPaisSeleccionado();
    }

    function pintarListaCeldas() {
      const d = datos;
      if (!d) return;
      const i = Object.fromEntries(d.campos_celda.map((k, j) => [k, j]));
      const filtradas = d.celdas.filter((c) => !paisCeldas || c[i.iso_a3] === paisCeldas)
        .sort((a, b) => b[i.n] - a[i.n] || a[i.lat] - b[i.lat] || a[i.lon] - b[i.lon]);
      const tam = 20, paginas = Math.max(1, Math.ceil(filtradas.length / tam));
      paginaCeldas = Math.min(paginaCeldas, paginas - 1);
      const desde = paginaCeldas * tam;
      const pagina = filtradas.slice(desde, desde + tam);
      panel.querySelector(".globo-celdas-estado").textContent = filtradas.length
        ? `${fmt(filtradas.length)} celdas · página ${paginaCeldas + 1} de ${paginas}`
        : "Sin celdas en este país y periodo.";
      const lista = panel.querySelector(".globo-celdas");
      lista.innerHTML = pagina.map((c, k) => `<li><button type="button" data-indice="${k}">` +
        `${esc(fmt(c[i.n]))} focos · FRP máx. ${esc(fmt(c[i.frp_max], 1))} MW · ` +
        `${esc(fmt(c[i.lat], 3))}, ${esc(fmt(c[i.lon], 3))}</button></li>`).join("");
      lista.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
        const c = pagina[Number(b.dataset.indice)];
        const lon = c[i.lon], lat = c[i.lat];
        const f = { properties: { n: c[i.n], frp_max: c[i.frp_max], n_alta: c[i.n_alta],
          n_viirs: c[i.n_viirs], ultimo: c[i.ultimo_utc], iso: c[i.iso_a3] } };
        detenerRotacion();
        mapa.flyTo({ center: [lon, lat], zoom: Math.max(zoomPais,Math.min(8,mapa.getZoom())), duration:movimientoReducido()?0:900 });
        popup(f, { lng: lon, lat });
      }));
      panel.querySelector(".globo-celdas-anterior").disabled = paginaCeldas === 0;
      panel.querySelector(".globo-celdas-siguiente").disabled = paginaCeldas >= paginas - 1;
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
      opciones.alExploracion?.();
      const [w, s, e, n] = p.bbox;
      mapa.fitBounds([[w, s], [e, n]], { padding: 48, maxZoom: zoomPais, duration: movimientoReducido() ? 0 : 1600 });
      paisSeleccionado = iso;
      pintarPaisSeleccionado();
    }

    function pintarPaisSeleccionado() {
      const nota = panel.querySelector(".globo-pais");
      nota.hidden = !paisSeleccionado;
      if (!paisSeleccionado) return;
      const fila = datos?.paises.find(x=>x.iso_a3===paisSeleccionado);
      const nombre = paises?.get(paisSeleccionado)?.nombre ?? paisSeleccionado;
      nota.innerHTML = `<div class="pais-seleccionado-cabeza"><strong>${esc(nombre)}</strong><button type="button" class="quitar-pais" aria-label="Quitar selección de país">×</button></div>` +
        `<p>${fila ? `${esc(fmt(fila.n))} focos · ${esc(fmt(fila.n_alta))} de confianza alta` : "Sin focos en este periodo"}</p>`;
      nota.querySelector("button").addEventListener("click",()=>{paisSeleccionado=null;pintarPaisSeleccionado();});
    }

    function popup(f, lngLat) {
      const p = f.properties;
      const pais = paises?.get(p.iso)?.nombre ?? (p.iso ? p.iso : "fuera de país (mar o costa)");
      const html = `<strong>${esc(fmt(p.n))} ${p.n === 1 ? "foco" : "focos"}</strong> en esta celda de ~${esc(fmt(res * 111))} km<br>` +
        `${esc(pais)} · confianza alta: ${esc(fmt(p.n_alta))}<br>` +
        `FRP máx.: ${esc(fmt(p.frp_max, 1))} MW · VIIRS ${esc(fmt(p.n_viirs))} · MODIS ${esc(fmt(p.n - p.n_viirs))}<br>` +
        `Último: ${esc(fecha(p.ultimo))}<br>` +
        (detalleDisponible()
          ? `<button type="button" class="globo-explorar">Ver cada foco en el mapa regional</button>`
          : `<span class="globo-sin-detalle">${esc(notaSinDetalle)}</span> ` +
            `<a href="https://firms.modaps.eosdis.nasa.gov/map/" target="_blank" rel="noopener">Abrir visor NASA FIRMS</a>`);
      const pop = new maplibregl.Popup({ closeButton: true, maxWidth: "280px", className: "globo-popup" }).setLngLat(lngLat).setHTML(html).addTo(mapa);
      pop.getElement().querySelector(".globo-explorar")?.addEventListener("click", () => {
        pop.remove();
        opciones.alExplorar(lngLat.lng, lngLat.lat, 9, { desde: datos.desde, hasta: datos.hasta });
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

    async function cargarLimitesVista() {
      const generacion = ++vistaGen;
      limitesCtrl?.abort();
      limitesCtrl = new AbortController();
      const signal = limitesCtrl.signal;
      const zoom = mapa.getZoom();
      const cajas = cajasVisibles();
      const nivel = zoom >= 8 ? 2 : zoom >= 5 ? 1 : zoom >= 3 ? 0 : -1;
      const aviso = panel.querySelector(".limites-estado");
      if (nivel < 0) { aviso.textContent = "Escala continental · acerque para ver países y divisiones administrativas."; return; }
      if (!indiceLimites) {
        try {
          const r = await fetch("/ui/datos/indice_limites.json");
          if (!r.ok) throw new Error("índice no disponible");
          indiceLimites = new Map((await r.json()).paises.map(p=>[p.iso,p]));
        } catch { indiceLimites = await cargarPaises(); }
      }
      const indice = indiceLimites;
      if (generacion !== vistaGen) return;
      const candidatos = [...indice.entries()].filter(([,p]) => {
        const [w,s,e,n] = p.bbox;
        return cajas.some(c=>e>=c[0] && w<=c[2] && n>=c[1] && s<=c[3]);
      });
      const tareas = candidatos.flatMap(([iso]) => Array.from({length:nivel + 1}, (_, n) => [iso,n]));
      const capas = [[],[],[]], fuentes = new Map();
      let faltantes = 0, hechos = 0;
      aviso.textContent = `Cargando límites de ${candidatos.length} países…`;
      async function trabajador() {
        while (tareas.length && !signal.aborted) {
          const [iso,n] = tareas.shift(), clave = `${iso}:${n}`;
          try {
            let geo = limitesCache.get(clave);
            if (!geo) {
              const r = await fetch(`/limites/${iso}/${n}`, {signal});
              if (!r.ok) throw new Error(`HTTP ${r.status}`);
              geo = await r.json();
              if (limitesCache.size >= 12) limitesCache.delete(limitesCache.keys().next().value);
              limitesCache.set(clave,geo);
            }
            if (generacion !== vistaGen) return;
            capas[n].push(...geo.features);
            fuentes.set(clave, geo.metadatos);
            mapa.getSource(`adm${n}`).setData({type:"FeatureCollection",features:capas[n]});
          } catch (e) { if (e.name === "AbortError") return; faltantes++; }
          hechos++;
          if (generacion === vistaGen) aviso.textContent = `Límites: ${hechos} capas consultadas${faltantes ? ` · ${faltantes} no disponibles` : ""}.`;
        }
      }
      await Promise.all([trabajador(),trabajador(),trabajador()]);
      if (generacion !== vistaGen) return;
      panel.querySelector(".limites-fuentes").textContent = [...fuentes.entries()].map(([clave,m]) =>
        `${clave.replace(":"," ADM")} · ${m?.boundaryYearRepresented || "año no indicado"} · ${m?.boundarySource || "fuente no indicada"} · ${m?.boundaryLicense || "licencia no indicada"}`).join("; ") || "Sin límites publicados o sin conexión. El relieve y los focos siguen disponibles.";
    }

    function cajasVisibles() {
      const b=mapa.getBounds(), ancho=b.getEast()-b.getWest();
      const s=Math.max(-85,b.getSouth()),n=Math.min(85,b.getNorth());
      if(ancho>=360)return [[-180,s,180,n]];
      const w=((b.getWest()+180)%360+360)%360-180,e=w+ancho;
      return e>180 ? [[w,s,180,n],[-180,s,e-360,n]] : [[w,s,e,n]];
    }

    function notificarVista() {
      actualizarCapas();
      const c = mapa.getCenter(), cajas = cajasVisibles();
      opciones.alVista?.({zoom:mapa.getZoom(), centro:[c.lng,c.lat],
        bbox:cajas[0], cajas,
        rango:datos ? {desde:datos.desde,hasta:datos.hasta} : null});
      if (listo) cargarLimitesVista();
    }

    function construir(centro, zoom) {
      mapa = new maplibregl.Map({
        container: contenedor, style: estilo(), center: centro, zoom, minZoom: 0, maxZoom: 17,
        attributionControl: { compact: true, customAttribution: [
          'Relieve: <a href="https://www.earthdata.nasa.gov/data/tools/gibs">NASA GIBS</a>',
          'Focos: <a href="https://www.earthdata.nasa.gov/data/tools/firms">NASA FIRMS</a> (LANCE / ESDIS)',
          'Límites: <a href="https://www.geoboundaries.org/">geoBoundaries</a> (DANE, CC BY 4.0 para COL ADM2; fuentes por país)',
        ] }, renderWorldCopies: true, dragRotate: false, pitchWithRotate: false,
      });
      mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      mapa.on("dataloading", e => { if(e.sourceId==="fondo")opciones.alCargaBase?.(true); });
      mapa.on("sourcedata", e => { if(e.sourceId==="fondo" && e.isSourceLoaded)opciones.alCargaBase?.(false); });
      mapa.on("idle", () => opciones.alCargaBase?.(false));
      mapa.on("styledata", () => { if (!listo && mapa.getSource("focos")) { listo = true; aplicarDatos(); } });
      mapa.on("load", () => {
        listo = true;
        aplicarDatos();
        mapa.getCanvas().setAttribute("aria-label", "Globo terráqueo con los focos de calor activos de todo el mundo");
        notificarVista();
        opciones.alListo?.();
      });
      ["mousedown", "touchstart", "wheel"].forEach((ev) => mapa.on(ev, detenerRotacion));
      mapa.on("mouseenter", "focos", () => { mapa.getCanvas().style.cursor = "pointer"; });
      mapa.on("mouseleave", "focos", () => { mapa.getCanvas().style.cursor = ""; });
      mapa.on("click", "focos", (ev) => { if (!dibujando) { detenerRotacion(); cargarPaises().then(() => popup(ev.features[0], ev.lngLat)); } });
      mapa.on("click", "detalle-focos", (ev) => {
        if (dibujando) return;
        const d = ev.features[0].properties;
        new maplibregl.Popup({maxWidth:"340px"}).setLngLat(ev.lngLat).setHTML(opciones.ficha?.(d) || `FRP: ${esc(d.frp)} MW`).addTo(mapa);
      });
      mapa.on("click", "detalle-grupos", async (ev) => {
        if (dibujando) return;
        const f=ev.features[0], z=await mapa.getSource("detalle").getClusterExpansionZoom(f.properties.cluster_id);
        mapa.easeTo({center:f.geometry.coordinates,zoom:z,duration:movimientoReducido()?0:600});
      });
      for(const nivel of [0,1,2]) mapa.on("click",`limites-adm${nivel}`,ev=>{
        if(dibujando || mapa.queryRenderedFeatures(ev.point,{layers:["detalle-focos","detalle-grupos"]}).length)return;
        const nombre=ev.features[0]?.properties?.shapeName || "División administrativa";
        new maplibregl.Popup({maxWidth:"260px"}).setLngLat(ev.lngLat)
          .setHTML(`<strong>${esc(nombre)}</strong><p>${["País","Departamento o equivalente","Municipio o equivalente"][nivel]} · geoBoundaries ADM${nivel}</p>`).addTo(mapa);
      });
      mapa.on("moveend", notificarVista);
      mapa.on("zoomend", () => {
        const z = mapa.getZoom();
        const nuevaRes = z < 2.5 ? 0.5 : 0.25;
        if (nuevaRes !== res) { res = nuevaRes; cargarDatos(); }
        actualizarCapas();
      });
    }

    function montarPanel() {
      panel.innerHTML =
        `<div class="globo-cabeza"><h2>Resumen mundial</h2><span class="globo-insignia insignia">…</span></div>` +
        `<p class="globo-naturaleza"></p>` +
        `<p class="globo-cobertura tenue"></p><p class="globo-vigencia aviso-caja" role="status" hidden></p>` +
        `<label class="globo-periodo">Periodo mundial <select>${PERIODOS.map(([v, t]) => `<option value="${v}"${v === dias ? " selected" : ""}>${t}</option>`).join("")}</select></label>` +
        `<p class="globo-detalle-estado aviso-caja" role="status" hidden>${esc(notaSinDetalle)} ` +
        `<a href="https://firms.modaps.eosdis.nasa.gov/map/" target="_blank" rel="noopener">Abrir visor NASA FIRMS</a>.</p>` +
        `<div class="globo-cifras" aria-live="polite"></div>` +
        `<section class="globo-pais" aria-label="País seleccionado" hidden></section>` +
        `<div class="globo-leyenda" aria-label="Leyenda del globo"><span class="tenue">Potencia · FRP (MW):</span>` +
        `<div class="escala-frp">`+["&lt; 5", "5–&lt;20", "20–&lt;100", "100–&lt;500", "≥ 500"].map((t, k) => `<span><i class="esc-frp f${k + 1}"></i>${t}</span>`).join("")+`</div>` +
        `<details class="lectura-focos"><summary>Cómo leer los círculos</summary><p>En grupos: color = potencia máxima; tamaño = cantidad. En un foco: color y tamaño = potencia. La transparencia indica confianza.</p></details><a href="#guia-termica">Guía de colores y sensores</a></div>` +
        `<p class="tenue globo-nota">Detecciones térmicas, no incendios confirmados.</p>` +
        `<details class="globo-metadatos"><summary>Origen y actualización</summary><p class="globo-origen tenue"></p><p class="globo-actualizacion tenue"></p></details>` +
        `<details class="limites-guia"><summary>Límites geográficos</summary><p class="limites-estado" role="status">Escala continental</p><p class="limites-fuentes tenue"></p><p class="tenue">Países desde zoom 3; departamentos o equivalentes desde 5; municipios o equivalentes desde 8. La cobertura y el nivel administrativo varían por país.</p></details>` +
        `<details class="globo-lista"><summary>Explorar celdas por lista</summary>` +
        `<label>País <select class="globo-pais-buscar"></select></label>` +
        `<p class="globo-celdas-estado tenue" role="status"></p><ol class="globo-celdas"></ol>` +
        `<div class="globo-paginacion"><button type="button" class="globo-celdas-anterior">Anterior</button>` +
        `<button type="button" class="globo-celdas-siguiente">Siguiente</button></div></details>` +
        `<div class="globo-acciones"><button type="button" class="globo-rotar" aria-pressed="false">Girar el globo</button>` +
        `<button type="button" class="globo-volver">Ir al análisis regional</button></div>`;
      panel.querySelector(".globo-periodo select").addEventListener("change", (ev) => { dias = Number(ev.target.value); cargarDatos(); });
      panel.querySelector(".globo-pais-buscar").addEventListener("change", (ev) => {
        paisCeldas = ev.target.value; paginaCeldas = 0; pintarListaCeldas();
      });
      panel.querySelector(".globo-celdas-anterior").addEventListener("click", () => { paginaCeldas -= 1; pintarListaCeldas(); });
      panel.querySelector(".globo-celdas-siguiente").addEventListener("click", () => { paginaCeldas += 1; pintarListaCeldas(); });
      panel.querySelector(".globo-rotar").addEventListener("click", () => (rotar ? detenerRotacion() : iniciarRotacion()));
      panel.querySelector(".globo-volver").addEventListener("click", () => opciones.alVolver());
    }

    function actualizarContexto(enGlobo) {
      activo = enGlobo;
      panel.querySelector(".globo-rotar").disabled = false;
      panel.querySelector(".globo-nota").textContent = !detalleDisponible()
        ? notaSinDetalle
        : enGlobo ? "Totales mundiales del periodo; el mapa detalla la zona visible."
          : "Detalle regional en el mapa. Este resumen mantiene los totales mundiales del periodo seleccionado.";
    }

    return {
      actualizarContexto,
      obtenerMapa: () => mapa,
      cobertura: () => datos,
      localizar(lugar, analizar) {
        opciones.alExploracion?.();
        paisSeleccionado=null;pintarPaisSeleccionado();
        marcadorLugar?.remove();
        const popupLugar = new maplibregl.Popup({maxWidth:"300px",focusAfterOpen:false}).setHTML(
          `<strong>${esc(lugar.nombre)}</strong><p>${esc(lugar.tipo)} · ${esc(lugar.descripcion)}</p>`+
          `<button type="button" class="analizar-lugar">Analizar esta zona</button>`+
          `<p class="tenue">Se usará el recuadro aproximado del lugar.</p>`);
        marcadorLugar = new maplibregl.Marker({color:"#2186a2"}).setLngLat([lugar.lon,lugar.lat]).setPopup(popupLugar).addTo(mapa);
        marcadorLugar.getElement().setAttribute("aria-label",`Lugar buscado: ${lugar.nombre}`);
        marcadorLugar.getElement().setAttribute("role","button");
        marcadorLugar.togglePopup();
        popupLugar.getElement().querySelector(".analizar-lugar").addEventListener("click",()=>{popupLugar.remove();analizar(lugar);});
        this.enfocar(lugar.bbox);
        mapa.getCanvas().focus({preventScroll:true});
      },
      enfocar(bbox) { mapa.fitBounds([[bbox[0],bbox[1]],[bbox[2],bbox[3]]], {padding:35,maxZoom:13,duration:movimientoReducido()?0:900}); },
      detalle(d) {
        detalle = {type:"FeatureCollection",features:(d.detecciones ?? []).map(p => ({type:"Feature",
          geometry:{type:"Point",coordinates:[p.lon,p.lat]},properties:p}))};
        if (mapa?.getSource("detalle")) mapa.getSource("detalle").setData(detalle);
        actualizarCapas();
      },
      seleccion(bbox) {
        if (!mapa?.getSource("seleccion")) return;
        const [w,s,e,n]=bbox;
        mapa.getSource("seleccion").setData({type:"FeatureCollection",features:[{type:"Feature",properties:{},
          geometry:{type:"Polygon",coordinates:[[[w,s],[e,s],[e,n],[w,n],[w,s]]]}}]});
      },
      imagen(url) {
        if (!mapa?.getSource("imagen")) {
          if (!url) return;
          mapa.addSource("imagen",{type:"raster",tiles:[url],tileSize:256,maxzoom:9});
          mapa.addLayer({id:"imagen",type:"raster",source:"imagen",paint:{"raster-opacity":0.85}},"limites-adm0");
        }
        mapa.setLayoutProperty("imagen","visibility",url?"visible":"none");
        if (url) mapa.getSource("imagen").setTiles([url]);
      },
      dibujar(alTerminar) {
        let inicio=null;
        dibujando=true;
        mapa.getCanvas().style.cursor="crosshair";
        const finalizar = (bbox) => { dibujando=false;mapa.off("click",clic);mapa.off("mousemove",mover);
          document.removeEventListener("keydown",tecla);mapa.getCanvas().style.cursor="";alTerminar(bbox); };
        const caja = p => [Math.min(inicio.lng,p.lng),Math.min(inicio.lat,p.lat),Math.max(inicio.lng,p.lng),Math.max(inicio.lat,p.lat)];
        const mover=ev=>{if(inicio)this.seleccion(caja(ev.lngLat));};
        const clic=ev=>{if(!inicio)inicio=ev.lngLat;else finalizar(caja(ev.lngLat));};
        const tecla=ev=>{if(ev.key==="Escape")finalizar(null);};
        mapa.on("click",clic);mapa.on("mousemove",mover);document.addEventListener("keydown",tecla);
      },
      /** Muestra el globo centrado en [lon, lat] con el zoom MapLibre dado. */
      mostrar(lon, lat, zoom) {
        if (!mapa) {
          montarPanel();
          construir([lon, lat], zoom);
          cargarDatos();
          cargarPaises();
          // El movimiento se inicia a petición del usuario para facilitar la selección.
        } else {
          mapa.resize();
          mapa.flyTo({ center: [lon, lat], zoom, duration:movimientoReducido()?0:900 });
        }
        if (datos) opciones.alDatos?.(datos);
      },
      ocultar() { detenerRotacion(); },
      /** Vuelve a pintar con los colores y el fondo del tema activo. */
      repintar() { /* El tema cambia los controles mediante CSS; la Tierra conserva su imagen y colores. */ },
    };
  }

  window.Globo = { crear, CORTES_FRP, fondo };
})();
