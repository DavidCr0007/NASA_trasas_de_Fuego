// Recorrido del visor de capas (ADR 0013) en Chrome sin interfaz. Lo invoca prueba_navegador.mjs
// con el modo «capas». Comprueba capas por defecto, límites fijos al cambiar de base, resaltado de
// municipio estable a ambos lados del umbral, búsqueda local y preajustes; mide el zoom
// al que el Huila deja de caber (prueba visual del umbral) y guarda capturas de escritorio y móvil
// en claro y oscuro.
const HUILA = [-76.6247, 1.5521, -74.4133, 3.8432];
const NEIVA = [-75.2819, 2.9273];

export async function probarCapas({ enviar, evaluar, esperarA, captura, comprobar, espera, errores, URL_UI, guardar }) {
  async function abrir(ancho, alto, movil, tema) {
    await enviar("Emulation.setDeviceMetricsOverride", { width: ancho, height: alto, deviceScaleFactor: 1, mobile: movil });
    await enviar("Page.navigate", { url: URL_UI });
    await esperarA(`document.readyState === "complete" && typeof mapa !== "undefined" && mapa.loaded && mapa.isStyleLoaded()`, 30000, "mapa listo");
    await esperarA(`document.querySelectorAll("#panel-capas-cuerpo .capa").length === window.Capas.CATALOGO.length`, 10000, "panel de capas");
    await evaluar(`(() => { const s = document.getElementById("sel-tema"); s.value = ${JSON.stringify(tema)}; s.dispatchEvent(new Event("change")); return true; })()`);
    await esperarA(`estado.calendario !== null && municipios.length === 37`, 30000, "datos y límites");
  }
  const enfocar = (lon, lat, zoom) => evaluar(`(() => { mapa.jumpTo({ center: [${lon}, ${lat}], zoom: ${zoom} }); return true; })()`);
  const quieto = () => esperarA(`mapa.loaded() && !mapa.isMoving()`, 30000, "mapa quieto").then(() => espera(1200));
  const visibilidad = (id) => evaluar(`mapa.getLayoutProperty(${JSON.stringify(id)}, "visibility") ?? "visible"`);

  // 1. Capas por defecto (sin localStorage previo).
  await enviar("Page.navigate", { url: "about:blank" });
  await abrir(1440, 900, false, "claro");
  await evaluar(`(() => { try { localStorage.removeItem("hhn-capas"); } catch {} return true; })()`);
  await abrir(1440, 900, false, "claro");
  const porDefecto = await evaluar(`({ base: document.querySelector('input[name="capa-base"]:checked')?.value,
    preajuste: document.querySelector('[data-preajuste][aria-pressed="true"]')?.dataset.preajuste,
    activas: [...document.querySelectorAll('.capa[data-activa="true"]')].map(f => f.dataset.capa),
    panel: document.getElementById("btn-capas").getAttribute("aria-expanded") })`);
  comprobar("capas por defecto: base Relieve y preajuste Mapa", porDefecto.base === "relieve" && porDefecto.preajuste === "mapa",
    JSON.stringify(porDefecto));
  comprobar("clima apagado por defecto", !porDefecto.activas.includes("clima"));

  // 2. Límites fijos: siguen visibles con cada base.
  await enfocar(...NEIVA, 8);
  await quieto();
  const bases = {};
  for (const base of ["satelital", "hidrografia", "ninguna", "relieve"]) {
    await evaluar(`(() => { document.querySelector('input[name="capa-base"][value="${base}"]').click(); return true; })()`);
    await espera(400);
    bases[base] = [await visibilidad("limites-departamento"), await visibilidad("limites-municipio")];
  }
  comprobar("límites visibles con todas las bases", Object.values(bases).every(([d, m]) => d === "visible" && m === "visible"), JSON.stringify(bases));
  const orden = await evaluar(`mapa.getStyle().layers.map(l => l.id)`);
  const pos = (id) => orden.indexOf(id);
  comprobar("límites encima de toda base y debajo de los focos",
    ["fondo", "satelital", "sombra", "rios", "zona-mascara"].every((id) => pos(id) < pos("limites-municipio")) && pos("limites-departamento") < pos("detalle-focos"),
    orden.join(" > "));

  // 3. Prueba visual del umbral: zoom máximo al que el Huila cabe completo en la vista.
  const cabe = await evaluar(`mapa.cameraForBounds([[${HUILA[0]}, ${HUILA[1]}], [${HUILA[2]}, ${HUILA[3]}]], { padding: 20 }).zoom`);
  comprobar("umbral municipal ≥ zoom en que el departamento deja de caber", cabe < (await evaluar("Zonas.UMBRAL_ZOOM_MUNICIPIO")) ,
    `el Huila cabe hasta el zoom ${cabe.toFixed(2)} en 1440×900`);
  const umbral = await evaluar("Zonas.UMBRAL_ZOOM_MUNICIPIO");
  for (const [zoom, esperado] of [[umbral - 0.1, "Municipio"], [umbral, "Municipio"]]) {
    await enfocar(...NEIVA, zoom);
    await quieto();
    await evaluar(`(() => { seleccionarZonaEn(${NEIVA[0]}, ${NEIVA[1]}, mapa.getZoom()); return true; })()`);
    await esperarA(`document.getElementById("zona-focos").textContent !== "…"`, 15000, "cifras de la zona");
    const t = await evaluar(`({ nivel: document.getElementById("zona-nivel").textContent, nombre: document.getElementById("zona-titulo").textContent,
      contexto: zonaSel?.contexto?.properties?.shapeName ?? null })`);
    comprobar(`zoom ${zoom}: resalta ${esperado.toLowerCase()}`, t.nivel.startsWith(esperado), JSON.stringify(t));
    await captura(`umbral_zoom_${String(Math.round(zoom * 10) / 10).replace(".", "_")}`);
  }

  // 4. Búsqueda local (sin red): «garzon» encuentra Garzón y ajusta la vista a su polígono.
  await evaluar(`(() => { const c = document.getElementById("consulta-lugar"); c.value = "garzon"; document.getElementById("buscar-lugar").requestSubmit(); return true; })()`);
  await esperarA(`document.querySelector("#lista-lugares button strong")`,5000,"resultado local");
  await evaluar(`document.querySelector("#lista-lugares button").click()`);
  await esperarA(`document.getElementById("zona-titulo").textContent === "Garzón"`, 10000, "Garzón resaltado");
  await quieto();
  comprobar("búsqueda local de municipio", true, await evaluar(`document.getElementById("zona-nivel").textContent`));

  // 5. Preajuste Fuego: base satelital con sombreado multiplicado.
  await evaluar(`(() => { document.querySelector('[data-preajuste="fuego"]').click(); return true; })()`);
  await quieto();
  const fuego = await evaluar(`({ base: capasEstado.base, sombra: capasEstado.capas.sombra, sat: mapa.getLayoutProperty("satelital", "visibility") })`);
  comprobar("preajuste Fuego", fuego.base === "satelital" && fuego.sombra.mezcla === "multiplicar" && fuego.sat === "visible", JSON.stringify(fuego));
  await evaluar(`(() => { document.querySelector('[data-preajuste="mapa"]').click(); return true; })()`);

  // 5b. La selección del foco conserva su municipio al acercarse y alejarse.
  const zonaActual = () => evaluar(`({ nivel: document.getElementById("zona-nivel").textContent,
    nombre: document.getElementById("zona-titulo").textContent,
    etiqueta: document.querySelector(".etiqueta-zona")?.textContent ?? null })`);
  await enfocar(...NEIVA, 7.5);
  await quieto();
  await evaluar(`(() => { seleccionarZonaEn(${NEIVA[0]}, ${NEIVA[1]}, mapa.getZoom()); return true; })()`);
  await esperarA(`document.getElementById("zona-titulo").textContent === "Neiva"`, 15000, "municipio");
  const cabeMunicipio = await evaluar(`(() => { const b = municipios.find(m => m.properties.shapeName === "Neiva").properties.bbox;
    return mapa.cameraForBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 20 }).zoom; })()`);
  const ciudad = await evaluar("Zonas.UMBRAL_ZOOM_CIUDAD");
  comprobar("umbral de ciudad ≥ zoom en que el municipio deja de caber", cabeMunicipio < ciudad,
    `el municipio de Neiva cabe hasta el zoom ${cabeMunicipio.toFixed(2)}`);
  for (const [zoom, esperado, archivo] of [[umbral + 0.3, "Municipio", null], [ciudad, "Municipio", "umbral_zoom_11"]]) {
    await enfocar(...NEIVA, zoom);
    await esperarA(`document.getElementById("zona-nivel").textContent.startsWith(${JSON.stringify(esperado)})`, 15000, esperado);
    await quieto();
    const z = await zonaActual();
    comprobar(`al acercarse a ${zoom}: ${esperado.toLowerCase()} con su nombre en el mapa`, z.etiqueta === z.nombre, JSON.stringify(z));
    if (archivo) await captura(archivo);
  }

  // 5c. Fuera del Huila y desde lejos: los límites del país se piden a /limites (requiere internet).
  await enfocar(-75.23, 4.44, 6.5);
  await quieto();
  await evaluar(`(() => { seleccionarZonaEn(-75.23, 4.44, mapa.getZoom()); return true; })()`);
  if (await evaluar("Boolean(window.HHN_ESTATICO)")) {
    // Demo estática de GitHub Pages (ADR 0015): sin /limites; la tarjeta debe decirlo.
    await esperarA(`document.getElementById("zona-nota").textContent.includes("No se encontró")`, 20000, "aviso de la demo estática");
    comprobar("demo estática: informa si no hay un límite municipal", true, await evaluar(`document.getElementById("zona-nota").textContent`));
  } else {
    await esperarA(`!["Fuera de los límites cargados", "Neiva"].includes(document.getElementById("zona-titulo").textContent)`, 60000, "zona fuera del Huila");
    const fuera = await zonaActual();
    comprobar("fuera del Huila: resalta el municipio del foco", fuera.nivel.startsWith("Municipio") && /ibagu/i.test(fuera.nombre), JSON.stringify(fuera));
  }

  // 5d. Base mínima «Vías e infraestructura» (preajuste Vías) en el municipio y en la ciudad.
  await evaluar(`(() => { document.querySelector('[data-preajuste="vias"]').click(); return true; })()`);
  const v = await evaluar(`({ base: capasEstado.base, vias: mapa.getLayoutProperty("vias", "visibility"),
    lim: mapa.getLayoutProperty("limites-municipio", "visibility") })`);
  comprobar("preajuste Vías: base mínima con límites", v.base === "vias" && v.vias === "visible" && v.lim === "visible", JSON.stringify(v));
  await evaluar(`(() => { quitarZona(); const c = document.getElementById("consulta-lugar"); c.value = "Neiva";
    document.getElementById("buscar-lugar").requestSubmit(); return true; })()`);
  await esperarA(`document.querySelector("#lista-lugares button strong")`,5000,"resultado local");
  await evaluar(`document.querySelector("#lista-lugares button").click()`);
  await esperarA(`document.getElementById("zona-titulo").textContent === "Neiva"`, 15000, "Neiva");
  await quieto();
  await captura("vias_municipio");
  await evaluar(`(() => { seleccionarZonaEn(${NEIVA[0]}, ${NEIVA[1]}, 12); return true; })()`);
  await esperarA(`document.getElementById("zona-nivel").textContent.startsWith("Municipio")`, 15000, "municipio");
  await evaluar(`(() => { encuadrarZona(); return true; })()`);
  await quieto();
  await captura("vias_ciudad");
  await evaluar(`(() => { quitarZona(); document.querySelector('[data-preajuste="mapa"]').click(); return true; })()`);

  // 6. Capturas: escritorio y móvil, claro y oscuro, con un municipio resaltado.
  for (const [nombre, ancho, alto, movil] of [["escritorio", 1440, 900, false], ["movil", 390, 844, true]]) {
    for (const tema of ["claro", "oscuro"]) {
      await abrir(ancho, alto, movil, tema);
      await evaluar(`(() => { const c = document.getElementById("consulta-lugar"); c.value = "Neiva"; document.getElementById("buscar-lugar").requestSubmit(); return true; })()`);
      await esperarA(`document.querySelector("#lista-lugares button strong")`,5000,"resultado local");
      await evaluar(`document.querySelector("#lista-lugares button").click()`);
      await esperarA(`document.getElementById("zona-titulo").textContent === "Neiva" && document.getElementById("zona-focos").textContent !== "…"`, 15000, "Neiva");
      // Día con más focos del año (línea de tiempo): la captura muestra focos, celdas y cifras.
      const dia = await evaluar(`(() => { const d = [...estado.calendario.dias].sort((a, b) => b.n_brutas - a.n_brutas)[0].fecha_utc; seleccionarDia(d); return d; })()`);
      await esperarA(`periodoMapa?.desde === ${JSON.stringify(dia)} && document.getElementById("zona-focos").textContent !== "…"`, 20000, "día pico");
      await evaluar(`(() => { globo.enfocar(municipios.find(m => m.properties.shapeName === "Neiva").properties.bbox); return true; })()`);
      await quieto();
      if (!movil) { await captura(`${nombre}_${tema}`); continue; }
      // Móvil: página completa (mapa, tarjeta de la zona, leyenda y línea de tiempo) y el panel abierto.
      const alto_ = await evaluar(`Math.min(2600, document.querySelector(".mapa-tarjeta").getBoundingClientRect().bottom + scrollY + 20)`);
      const r = await enviar("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: ancho, height: alto_, scale: 1 } });
      await guardar(`${nombre}_${tema}`, r.data);
      await evaluar(`(() => { document.getElementById("btn-capas").click(); return true; })()`);
      await espera(400);
      await captura(`${nombre}_${tema}_capas`);
    }
  }
  comprobar("sin errores de consola", errores.length === 0, errores.slice(0, 3).join(" | "));
}
