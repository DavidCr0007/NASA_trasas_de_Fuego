/* Búsqueda explícita: no hace solicitudes mientras se escribe (ADR 0013).
 * 1. Primero, países, municipios y departamento locales (sin red).
 * 2. Si no hay coincidencias, Nominatim a través de /buscar-lugares, solo con conexión.
 *    Caché en la memoria de esta pestaña y como máximo una consulta por segundo; el
 *    servidor no guarda las búsquedas (solo aplica el mismo límite a toda la aplicación).
 */
"use strict";
window.iniciarBusquedaLugares = function ({ explorar, buscarLocal = () => [], elegirLocal = () => {} }) {
  const form = document.getElementById("buscar-lugar");
  const campo = document.getElementById("consulta-lugar");
  const boton = document.getElementById("btn-buscar-lugar");
  const panel = document.getElementById("resultados-lugares");
  const lista = document.getElementById("lista-lugares");
  const estado = document.getElementById("estado-busqueda");
  const confirmacion = document.getElementById("confirmacion-lugar");
  const confirmar = document.getElementById("confirmar-lugar");
  const INTERVALO_MS = 1000; // política de Nominatim: una consulta por segundo como máximo
  const cache = new Map(); // solo en memoria: se pierde al cerrar la pestaña
  let ctrl = null, generacion = 0, ultimaRemota = -Infinity;
  let pendiente = null, botonElegido = null, estadoResultados = "";
  const clave = (q) => q.normalize("NFC").toLocaleLowerCase("es").replace(/\s+/g, " ").trim();

  function cerrar(foco = false) {
    generacion++; ctrl?.abort(); boton.disabled = false;
    pendiente = null; confirmacion.hidden = true; lista.hidden = false;
    panel.hidden = true; boton.setAttribute("aria-expanded", "false");
    if (foco) campo.focus({ preventScroll: true });
  }
  function abrir() {
    pendiente = null; confirmacion.hidden = true; lista.hidden = false;
    lista.replaceChildren(); panel.hidden = false;
    boton.setAttribute("aria-expanded", "true");
  }
  function boton_(nombreTxt, tipoTxt, contextoTxt, alElegir) {
    const li = document.createElement("li"), b = document.createElement("button");
    b.type = "button"; b.title = contextoTxt;
    const nombre = document.createElement("strong"), tipo = document.createElement("span"), contexto = document.createElement("small");
    nombre.textContent = nombreTxt; tipo.textContent = tipoTxt; contexto.textContent = contextoTxt;
    b.append(nombre, tipo, contexto); li.appendChild(b); lista.appendChild(li);
    b.addEventListener("click", () => {
      pendiente = { nombre: nombreTxt, alElegir }; botonElegido = b;
      estadoResultados = estado.textContent;
      document.getElementById("confirmacion-lugar-nombre").textContent = nombreTxt;
      document.getElementById("confirmacion-lugar-tipo").textContent = tipoTxt;
      document.getElementById("confirmacion-lugar-contexto").textContent = contextoTxt;
      estado.textContent = "Compruebe el lugar y su categoría. El mapa se moverá solo al confirmar.";
      lista.hidden = true; confirmacion.hidden = false;
      confirmar.focus({ preventScroll: true });
    });
    return b;
  }

  function mostrarLocales(q, locales) {
    abrir();
    estado.textContent = `${locales.length} ${locales.length === 1 ? "coincidencia" : "coincidencias"} en los límites locales (sin internet).`;
    for (const r of locales) {
      boton_(r.nombre, r.tipo, r.descripcion, () => elegirLocal(r)).dataset.nivel = r.nivel;
    }
    const li = document.createElement("li"), mas = document.createElement("button");
    mas.type = "button"; mas.className = "buscar-internet"; mas.textContent = "Buscar también en internet";
    mas.addEventListener("click", () => buscarRemoto(q));
    li.appendChild(mas); lista.appendChild(li);
  }

  async function buscarRemoto(q) {
    ctrl?.abort(); ctrl = new AbortController();
    const gen = ++generacion;
    abrir(); boton.disabled = true;
    try {
      const idioma=window.Idiomas?.actual??"es", claveCache=idioma+":"+clave(q);
      let d = cache.get(claveCache);
      if (!d) {
        if (navigator.onLine === false) throw new Error("Sin conexión: solo está disponible la búsqueda local de municipios y departamentos.");
        const espera = ultimaRemota + INTERVALO_MS - performance.now();
        if (espera > 0) { estado.textContent = "Esperando un segundo entre búsquedas…"; await new Promise((r) => setTimeout(r, espera)); }
        if (gen !== generacion) return;
        estado.textContent = "Buscando lugares en internet…";
        ultimaRemota = performance.now();
        const r = await fetch(`/buscar-lugares?q=${encodeURIComponent(q)}&idioma=${idioma}`, { signal: ctrl.signal });
        const cuerpo = await r.json();
        if (!r.ok) throw new Error(typeof cuerpo.detail === "string" && cuerpo.detail !== "Not Found" ? cuerpo.detail : "El buscador de lugares no está disponible");
        d = cuerpo;
        if (cache.size >= 32) cache.delete(cache.keys().next().value);
        cache.set(claveCache, d);
      }
      if (gen !== generacion) return;
      const resultados = d.resultados ?? [];
      estado.textContent = resultados.length ? `${resultados.length} ${resultados.length===1 ? "coincidencia" : "coincidencias"} (Nominatim). Compruebe la ciudad y el país.`
        : "Sin resultados. Pruebe añadir la ciudad, el departamento o el país.";
      for (const lugar of resultados) boton_(lugar.nombre, lugar.tipo, lugar.descripcion, () => explorar(lugar));
    } catch (e) {
      if (e.name === "AbortError" || gen !== generacion) return;
      estado.textContent = ["TypeError", "SyntaxError"].includes(e.name) ? "No hay conexión con el buscador. Intente nuevamente." : e.message;
    } finally { if (gen === generacion) boton.disabled = false; }
  }

  form.addEventListener("submit", ev => {
    ev.preventDefault();
    const q = campo.value.trim();
    if (q.length < 3) { campo.focus(); return; }
    campo.focus({ preventScroll: true });
    const locales = buscarLocal(q);
    // Incluso una coincidencia única se revisa y confirma antes de modificar el mapa.
    if (locales.length) { generacion++; ctrl?.abort(); mostrarLocales(q, locales); return; }
    buscarRemoto(q);
  });
  campo.addEventListener("input", () => cerrar());
  confirmar.addEventListener("click", () => {
    if (!pendiente) return;
    const elegido = pendiente;
    cerrar(); campo.value = elegido.nombre; elegido.alElegir();
  });
  document.getElementById("volver-lugares").addEventListener("click", () => {
    pendiente = null; confirmacion.hidden = true; lista.hidden = false;
    estado.textContent = estadoResultados; botonElegido?.focus({ preventScroll: true });
  });
  document.addEventListener("idioma-cambiado",()=>cerrar());
  document.getElementById("cerrar-lugares").addEventListener("click", () => cerrar(true));
  document.addEventListener("pointerdown", ev => { if (!form.contains(ev.target)) cerrar(); });
  document.addEventListener("focusin", ev => { if (!form.contains(ev.target)) cerrar(); });
  form.addEventListener("keydown", ev => {
    if (ev.key === "Enter" && !ev.isComposing) {
      if (ev.target === campo) {
        ev.preventDefault();
        if (!boton.disabled && form.reportValidity()) form.requestSubmit();
        return;
      }
      if (ev.target.matches("#lista-lugares button")) { ev.preventDefault(); ev.target.click(); return; }
    }
    if (ev.key === "Escape") { ev.preventDefault(); cerrar(true); return; }
    const botones = [...lista.querySelectorAll("button")];
    if (!panel.hidden && !lista.hidden && botones.length && ["ArrowDown", "ArrowUp"].includes(ev.key)) {
      ev.preventDefault();
      const i = botones.indexOf(document.activeElement);
      if (ev.key === "ArrowDown") botones[Math.min(i + 1, botones.length - 1)].focus();
      else if (i <= 0) campo.focus(); else botones[i - 1].focus();
    }
  });
};
