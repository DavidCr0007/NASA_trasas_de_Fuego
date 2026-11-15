/* Búsqueda explícita: no hace solicitudes mientras se escribe (ADR 0013).
 * 1. Primero, la lista local de municipios y departamento (sin red).
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
  const INTERVALO_MS = 1000; // política de Nominatim: una consulta por segundo como máximo
  const cache = new Map(); // solo en memoria: se pierde al cerrar la pestaña
  let ctrl = null, generacion = 0, ultimaRemota = -Infinity;
  const clave = (q) => q.normalize("NFC").toLocaleLowerCase("es").replace(/\s+/g, " ").trim();

  function cerrar(foco = false) {
    generacion++; ctrl?.abort(); boton.disabled = false;
    panel.hidden = true; boton.setAttribute("aria-expanded", "false");
    if (foco) campo.focus({ preventScroll: true });
  }
  function abrir() {
    lista.replaceChildren(); panel.hidden = false;
    boton.setAttribute("aria-expanded", "true");
  }
  function boton_(nombreTxt, tipoTxt, contextoTxt, alElegir) {
    const li = document.createElement("li"), b = document.createElement("button");
    b.type = "button"; b.title = contextoTxt;
    const nombre = document.createElement("strong"), tipo = document.createElement("span"), contexto = document.createElement("small");
    nombre.textContent = nombreTxt; tipo.textContent = tipoTxt; contexto.textContent = contextoTxt;
    b.append(nombre, tipo, contexto); li.appendChild(b); lista.appendChild(li);
    b.addEventListener("click", () => { cerrar(); alElegir(); });
    return b;
  }

  function mostrarLocales(q, locales) {
    abrir();
    estado.textContent = `${locales.length} ${locales.length === 1 ? "coincidencia" : "coincidencias"} en los límites locales (sin internet).`;
    for (const r of locales) {
      boton_(r.nombre, r.tipo, r.nivel === "municipio" ? `${r.nombre}, Huila, Colombia · límite DANE` : "Huila, Colombia · unión de los municipios DANE",
        () => { campo.value = r.nombre; elegirLocal(r); });
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
      for (const lugar of resultados) boton_(lugar.nombre, lugar.tipo, lugar.descripcion, () => { campo.value = lugar.nombre; explorar(lugar); });
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
    // Un único resultado exacto se abre directamente; si hay varios, se elige de la lista.
    if (locales.length === 1) { generacion++; ctrl?.abort(); cerrar(); campo.value = locales[0].nombre; elegirLocal(locales[0]); return; }
    if (locales.length) { generacion++; ctrl?.abort(); mostrarLocales(q, locales); return; }
    buscarRemoto(q);
  });
  campo.addEventListener("input", () => cerrar());
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
    if (!panel.hidden && botones.length && ["ArrowDown", "ArrowUp"].includes(ev.key)) {
      ev.preventDefault();
      const i = botones.indexOf(document.activeElement);
      if (ev.key === "ArrowDown") botones[Math.min(i + 1, botones.length - 1)].focus();
      else if (i <= 0) campo.focus(); else botones[i - 1].focus();
    }
  });
};
