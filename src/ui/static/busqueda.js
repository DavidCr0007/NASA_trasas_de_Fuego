/* Búsqueda explícita: no hace solicitudes mientras se escribe. */
"use strict";
window.iniciarBusquedaLugares = function ({ explorar }) {
  const form = document.getElementById("buscar-lugar");
  const campo = document.getElementById("consulta-lugar");
  const boton = document.getElementById("btn-buscar-lugar");
  const panel = document.getElementById("resultados-lugares");
  const lista = document.getElementById("lista-lugares");
  const estado = document.getElementById("estado-busqueda");
  let ctrl = null, generacion = 0;
  function cerrar(foco = false) {
    generacion++; ctrl?.abort(); boton.disabled = false;
    panel.hidden = true; boton.setAttribute("aria-expanded", "false");
    if (foco) campo.focus({ preventScroll: true });
  }
  form.addEventListener("submit", async ev => {
    ev.preventDefault();
    const q = campo.value.trim();
    if (q.length < 3) { campo.focus(); return; }
    ctrl?.abort(); ctrl = new AbortController();
    const gen = ++generacion;
    campo.focus({ preventScroll: true });
    lista.replaceChildren(); panel.hidden = false;
    boton.setAttribute("aria-expanded", "true"); boton.disabled = true;
    estado.textContent = "Buscando lugares…";
    try {
      const r = await fetch(`/buscar-lugares?q=${encodeURIComponent(q)}`, { signal: ctrl.signal });
      const d = await r.json();
      if (gen !== generacion) return;
      if (!r.ok) throw new Error(typeof d.detail === "string" && d.detail !== "Not Found" ? d.detail : "El buscador de lugares no está disponible");
      const resultados = d.resultados ?? [];
      estado.textContent = resultados.length ? `${resultados.length} ${resultados.length===1 ? "coincidencia" : "coincidencias"}. Compruebe la ciudad y el país.`
        : "Sin resultados. Pruebe añadir la ciudad, el departamento o el país.";
      for (const lugar of resultados) {
        const li = document.createElement("li"), b = document.createElement("button");
        b.type = "button"; b.title = lugar.descripcion;
        const nombre = document.createElement("strong"), tipo = document.createElement("span"), contexto = document.createElement("small");
        nombre.textContent = lugar.nombre; tipo.textContent = lugar.tipo; contexto.textContent = lugar.descripcion;
        b.append(nombre, tipo, contexto); li.appendChild(b); lista.appendChild(li);
        b.addEventListener("click", () => { cerrar(); campo.value = lugar.nombre; explorar(lugar); });
      }
    } catch (e) {
      if (e.name === "AbortError" || gen !== generacion) return;
      estado.textContent = ["TypeError", "SyntaxError"].includes(e.name) ? "No hay conexión con el buscador. Intente nuevamente." : e.message;
    } finally { if (gen === generacion) boton.disabled = false; }
  });
  campo.addEventListener("input", () => cerrar());
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
