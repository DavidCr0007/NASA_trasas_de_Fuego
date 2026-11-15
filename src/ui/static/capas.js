/* Panel de capas (ADR 0013): Base, Focos y Contexto; preajustes Mapa, Fuego y Agua.
 * Cada capa: casilla, icono, nombre, opacidad y modo de mezcla. El estado se guarda en
 * localStorage («hhn-capas») dentro de try/catch; sin almacenamiento se usan los valores
 * por defecto. No envía nada al servidor.
 */
"use strict";

(function (raiz) {
  const CLAVE_CAPAS = "hhn-capas";
  const VERSION = 1;
  const MEZCLAS = { normal: "Normal", multiplicar: "Multiplicar", trama: "Trama" };

  // Un único lienzo WebGL: solo el sombreado (gris) admite mezclas reales; ver globo.js.
  const CATALOGO = [
    { id: "relieve", grupo: "base", nombre: "Relieve", icono: "relieve", fuente: "NASA GIBS · Blue Marble con relieve sombreado" },
    { id: "satelital", grupo: "base", nombre: "Satelital", icono: "satelite", fuente: "NASA GIBS · Blue Marble Next Generation, sin nubes" },
    { id: "hidrografia", grupo: "base", nombre: "Hidrografía", icono: "agua", fuente: "Natural Earth 1:10m · dominio público · sin red" },
    { id: "vias", grupo: "base", nombre: "Vías e infraestructura", icono: "vias", nota: "mínima",
      fuente: "© OpenStreetMap contributors (ODbL) · en grises para que destaquen los focos · requiere internet" },
    { id: "ninguna", grupo: "base", nombre: "Ninguna", icono: "vacio", fuente: "Solo países (Natural Earth) · sin red", sinAjustes: true },
    { id: "sombra", grupo: "fusion", nombre: "Sombreado del relieve", icono: "relieve", mezclas: ["multiplicar", "normal", "trama"], fuente: "NASA GIBS · ASTER GDEM (METI/NASA)" },
    { id: "rios", grupo: "fusion", nombre: "Ríos y lagos", icono: "agua", fuente: "Natural Earth 1:10m · azul, modo normal" },
    { id: "modis", grupo: "focos", nombre: "MODIS (Terra y Aqua)", icono: "foco", fuente: "NASA FIRMS · ~1 km" },
    { id: "noaa20", grupo: "focos", nombre: "VIIRS NOAA-20", icono: "foco", fuente: "NASA FIRMS · 375 m" },
    { id: "noaa21", grupo: "focos", nombre: "VIIRS NOAA-21", icono: "foco", fuente: "NASA FIRMS · 375 m" },
    { id: "snpp", grupo: "focos", nombre: "VIIRS Suomi NPP", icono: "foco", nota: "histórico", fuente: "Solo histórico: sin datos nuevos" },
    { id: "armonizados", grupo: "focos", nombre: "Armonizados", icono: "celdas", nota: "proyecto", fuente: "Celdas activas de ~1 km (ADR 0011): lo que cuenta el calendario" },
    { id: "limites", grupo: "contexto", nombre: "Límites de departamento y municipio", icono: "limite", fuente: "geoBoundaries · DANE, CC BY 4.0 · siempre sobre la base" },
    { id: "clima", grupo: "contexto", nombre: "Clima (reanálisis)", icono: "clima", fuente: "Open-Meteo · ERA5 (C3S/ECMWF) · CC BY 4.0 · requiere internet" },
  ];
  const GRUPOS = [
    { id: "base", titulo: "Base", ayuda: "Una a la vez" },
    { id: "focos", titulo: "Focos", ayuda: "Filtro por satélite desde el zoom 6; el globo muestra todos" },
    { id: "contexto", titulo: "Contexto" },
  ];
  const BASES = CATALOGO.filter((c) => c.grupo === "base").map((c) => c.id);
  const capa = (on, opacidad = 1, mezcla = "normal") => ({ on, opacidad, mezcla });

  /** Capas por defecto (= preajuste «Mapa»). */
  const POR_DEFECTO = Object.freeze({
    base: "relieve",
    capas: {
      relieve: capa(true), satelital: capa(true), hidrografia: capa(true), vias: capa(true), ninguna: capa(true),
      sombra: capa(true, 0.45, "multiplicar"), rios: capa(true, 0.9),
      modis: capa(true), noaa20: capa(true), noaa21: capa(true), snpp: capa(true),
      armonizados: capa(true, 0.6), limites: capa(true, 0.9), clima: capa(false),
    },
  });

  // Preajustes: cambian base, fusión y opacidades; conservan las casillas de satélites y el clima.
  const PREAJUSTES = {
    mapa: { nombre: "Mapa", base: "relieve", capas: { sombra: capa(true, 0.45, "multiplicar"), rios: capa(true, 0.9),
      armonizados: capa(true, 0.6), limites: capa(true, 0.9) }, focos: 1 },
    fuego: { nombre: "Fuego", base: "satelital", capas: { sombra: capa(true, 0.7, "multiplicar"), rios: capa(false, 0.9),
      armonizados: capa(true, 0.8), limites: capa(true, 0.8) }, focos: 1 },
    agua: { nombre: "Agua", base: "hidrografia", capas: { sombra: capa(true, 0.35, "multiplicar"), rios: capa(true, 1),
      armonizados: capa(false, 0.6), limites: capa(true, 0.9) }, focos: 0.6 },
    // Mínimo (ADR 0014): vías en grises, sin sombreado ni ríos; solo destacan focos y zona.
    vias: { nombre: "Vías", base: "vias", capas: { sombra: capa(false, 0.45, "multiplicar"), rios: capa(false, 0.9),
      armonizados: capa(true, 0.6), limites: capa(true, 0.9) }, focos: 1 },
  };

  const copia = (o) => JSON.parse(JSON.stringify(o));
  const mezclasDe = (id) => CATALOGO.find((c) => c.id === id)?.mezclas ?? ["normal"];

  /** Valida un estado leído (de localStorage o de un preajuste) contra el catálogo. */
  function normalizar(guardado) {
    const e = copia(POR_DEFECTO);
    if (!guardado || typeof guardado !== "object" || guardado.version !== VERSION) return e;
    if (BASES.includes(guardado.base)) e.base = guardado.base;
    for (const [id, def] of Object.entries(e.capas)) {
      const g = guardado.capas?.[id];
      if (!g || typeof g !== "object") continue;
      if (typeof g.on === "boolean") def.on = g.on;
      const op = Number(g.opacidad);
      if (Number.isFinite(op)) def.opacidad = Math.min(1, Math.max(0, op));
      if (mezclasDe(id).includes(g.mezcla)) def.mezcla = g.mezcla;
    }
    return e;
  }

  function leer() {
    try { return normalizar(JSON.parse(localStorage.getItem(CLAVE_CAPAS))); }
    catch { return copia(POR_DEFECTO); }
  }
  function guardar(e) {
    try { localStorage.setItem(CLAVE_CAPAS, JSON.stringify({ version: VERSION, ...e })); }
    catch { /* sin almacenamiento: el estado vale solo para esta visita */ }
  }

  function aplicarPreajuste(e, id) {
    const p = PREAJUSTES[id];
    if (!p) return e;
    const n = copia(e);
    n.base = p.base;
    for (const [k, v] of Object.entries(p.capas)) n.capas[k] = copia(v);
    for (const s of ["modis", "noaa20", "noaa21", "snpp"]) n.capas[s].opacidad = p.focos;
    n.capas[p.base].opacidad = 1;
    return n;
  }
  /** Preajuste que coincide con el estado (para marcarlo como activo), o null. */
  function preajusteActivo(e) {
    return Object.keys(PREAJUSTES).find((id) => JSON.stringify(aplicarPreajuste(e, id)) === JSON.stringify(e)) ?? null;
  }

  /** Resumen legible de lo que está activo: «Relieve · Sombreado · 4 satélites · Límites». */
  function resumen(e) {
    const k = e.capas, nombre = (id) => CATALOGO.find((c) => c.id === id).nombre;
    const sensores = ["modis", "noaa20", "noaa21", "snpp"].filter((s) => k[s].on).length;
    return [e.base === "vias" ? "Vías" : nombre(e.base), k.sombra.on && "Sombreado", k.rios.on && e.base !== "hidrografia" && "Ríos",
      sensores ? `${sensores} ${sensores === 1 ? "satélite" : "satélites"}` : "sin focos",
      k.armonizados.on && "Armonizados", k.limites.on && "Límites", k.clima.on && "Clima"].filter(Boolean).join(" · ");
  }

  // Iconos de trazo simple (24×24), decorativos: el nombre siempre acompaña al icono.
  const ICONOS = {
    relieve: '<path d="M3 19 9 9l4 6 3-4 5 8z"/>',
    satelite: '<rect x="9" y="9" width="6" height="6" rx="1"/><path d="M3 5l4 4M17 15l4 4M4 12h3M17 12h3"/>',
    agua: '<path d="M12 3s6 7 6 11a6 6 0 0 1-12 0c0-4 6-11 6-11z"/>',
    vacio: '<rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="3 3"/>',
    vias: '<path d="M8 21 10 3M16 21 14 3M12 6v2M12 11v2M12 16v2"/>',
    foco: '<circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="8" stroke-opacity=".45"/>',
    celdas: '<path d="M4 4h7v7H4zM13 13h7v7h-7zM13 4h7v7h-7z"/>',
    limite: '<path d="M4 6l6-2 5 3 5-2v13l-5 2-5-3-6 2z" stroke-dasharray="3 2"/>',
    clima: '<path d="M7 18h10a4 4 0 0 0 0-8 6 6 0 0 0-11 2 3 3 0 0 0 1 6z"/>',
    ajustes: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
  };
  const icono = (n) => `<svg class="icono" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICONOS[n] ?? ""}</svg>`;
  const escapar = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  function filaHTML(c) {
    const esBase = c.grupo === "base";
    const control = esBase
      ? `<input type="radio" name="capa-base" value="${c.id}">`
      : `<input type="checkbox" value="${c.id}">`;
    const mezclas = mezclasDe(c.id);
    const ajustes = c.sinAjustes ? "" :
      `<button type="button" class="capa-ajustar" aria-expanded="false" aria-controls="ajustes-${c.id}" ` +
      `aria-label="Opacidad y mezcla de ${escapar(c.nombre)}">${icono("ajustes")}</button>` +
      `<div class="capa-ajustes" id="ajustes-${c.id}" hidden>` +
      `<label>Opacidad <input type="range" class="capa-opacidad" min="0" max="100" step="5"><output></output></label>` +
      `<label>Mezcla <select class="capa-mezcla"${mezclas.length < 2 ? ' disabled title="Este motor dibuja esta capa solo en modo normal"' : ""}>` +
      mezclas.map((m) => `<option value="${m}">${MEZCLAS[m]}</option>`).join("") + `</select></label>` +
      (c.id === "satelital" ? `<div class="capa-ranura" data-ranura="imagen"></div>` : "") +
      `<p class="capa-fuente">${escapar(c.fuente)}</p></div>`;
    return `<div class="capa" data-capa="${c.id}">` +
      `<label class="capa-principal">${control}${icono(c.icono)}<span class="capa-nombre">${escapar(c.nombre)}</span>` +
      `${c.nota ? `<span class="capa-nota">${escapar(c.nota)}</span>` : ""}</label>${ajustes}</div>`;
  }

  /**
   * Monta el panel en `contenedor` y llama a `alCambiar(estado)` en cada cambio y al inicio.
   * `resumenEl` (opcional) recibe el texto de capas activas.
   */
  function iniciar({ contenedor, alCambiar, resumenEl }) {
    let estado = leer();
    const grupoHTML = (g) => {
      const filas = CATALOGO.filter((c) => c.grupo === g.id).map(filaHTML).join("");
      const fusion = g.id === "base" ? `<p class="capa-subtitulo">Sobre la base</p>` +
        CATALOGO.filter((c) => c.grupo === "fusion").map(filaHTML).join("") : "";
      return `<section class="grupo-capas" data-grupo="${g.id}">` +
        `<h3><button type="button" class="grupo-alternar" aria-expanded="true" aria-controls="grupo-${g.id}">${g.titulo}</button></h3>` +
        `<div id="grupo-${g.id}" class="grupo-cuerpo" role="group" aria-label="${g.titulo}">` +
        (g.ayuda ? `<p class="capa-ayuda">${g.ayuda}</p>` : "") + filas + fusion + `</div></section>`;
    };
    contenedor.innerHTML =
      `<div class="capas-preajustes" role="group" aria-label="Preajustes">` +
      Object.entries(PREAJUSTES).map(([id, p]) => `<button type="button" data-preajuste="${id}" aria-pressed="false">${p.nombre}</button>`).join("") +
      `</div>` + GRUPOS.map(grupoHTML).join("");

    function pintar() {
      for (const fila of contenedor.querySelectorAll(".capa")) {
        const id = fila.dataset.capa, c = estado.capas[id];
        const esBase = BASES.includes(id);
        const activa = esBase ? estado.base === id : c.on;
        fila.dataset.activa = String(activa);
        fila.querySelector("input[type=radio], input[type=checkbox]").checked = activa;
        const rango = fila.querySelector(".capa-opacidad");
        if (rango) {
          rango.value = Math.round(c.opacidad * 100);
          rango.setAttribute("aria-valuetext", `${rango.value} %`);
          fila.querySelector("output").textContent = `${rango.value} %`;
          fila.querySelector(".capa-mezcla").value = c.mezcla;
        }
      }
      const activo = preajusteActivo(estado);
      contenedor.querySelectorAll("[data-preajuste]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.preajuste === activo)));
      if (resumenEl) resumenEl.textContent = resumen(estado);
    }
    function cambiar(nuevo) {
      estado = nuevo;
      guardar(estado);
      pintar();
      alCambiar(copia(estado));
    }

    contenedor.addEventListener("change", (ev) => {
      const fila = ev.target.closest(".capa");
      if (!fila) return;
      const id = fila.dataset.capa, n = copia(estado);
      if (ev.target.matches("input[type=radio]")) n.base = id;
      else if (ev.target.matches("input[type=checkbox]")) n.capas[id].on = ev.target.checked;
      else if (ev.target.matches(".capa-mezcla")) n.capas[id].mezcla = ev.target.value;
      else return;
      cambiar(n);
    });
    contenedor.addEventListener("input", (ev) => {
      if (!ev.target.matches(".capa-opacidad")) return;
      const id = ev.target.closest(".capa").dataset.capa, n = copia(estado);
      n.capas[id].opacidad = Number(ev.target.value) / 100;
      cambiar(n);
    });
    contenedor.addEventListener("click", (ev) => {
      const b = ev.target.closest("button");
      if (!b) return;
      if (b.dataset.preajuste) { cambiar(aplicarPreajuste(estado, b.dataset.preajuste)); return; }
      if (b.matches(".capa-ajustar, .grupo-alternar")) {
        const abierto = b.getAttribute("aria-expanded") === "true";
        b.setAttribute("aria-expanded", String(!abierto));
        document.getElementById(b.getAttribute("aria-controls")).hidden = abierto;
      }
    });
    pintar();
    alCambiar(copia(estado));
    return {
      estado: () => copia(estado),
      ranura: (nombre) => contenedor.querySelector(`[data-ranura="${nombre}"]`),
      preajuste: (id) => cambiar(aplicarPreajuste(estado, id)),
      restablecer: () => cambiar(copia(POR_DEFECTO)),
    };
  }

  const api = { CLAVE_CAPAS, VERSION, CATALOGO, POR_DEFECTO, PREAJUSTES, BASES, normalizar, aplicarPreajuste,
    preajusteActivo, resumen, iniciar };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.Capas = api;
})(typeof window !== "undefined" ? window : globalThis);
