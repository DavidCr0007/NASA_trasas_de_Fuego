// Prueba de uso de punta a punta en un Chrome real, sin dependencias (Node ≥ 22: WebSocket y fetch nativos).
// Recorre: mapa regional → alejar hasta el globo 3D → país → acercar con la rueda → zona explorada →
// día con focos → tema claro → móvil. Guarda capturas y falla si hay errores en la consola.
//
// Uso (con la API en marcha):
//   node tools/prueba_navegador.mjs [URL=http://127.0.0.1:8000/ui/] [CARPETA_CAPTURAS] [RUTA_CHROME]
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const URL_UI = process.argv[2] ?? "http://127.0.0.1:8000/ui/";
const SALIDA = process.argv[3] ?? join(tmpdir(), "hhn_capturas");
const CHROME = process.argv[4] ?? (process.platform === "win32"
  ? "C:/Program Files/Google/Chrome/Application/chrome.exe" : "google-chrome");
const PUERTO = 9300 + Math.floor(Math.random() * 500);
const espera = (ms) => new Promise((r) => setTimeout(r, ms));
mkdirSync(SALIDA, { recursive: true });

const perfil = mkdtempSync(join(tmpdir(), "hhn-chrome-"));
const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${PUERTO}`, `--user-data-dir=${perfil}`, "--no-first-run",
  "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--window-size=1440,900", "about:blank",
], { stdio: "ignore" });

let ws, id = 0;
const pendientes = new Map();
const errores = [];
const resultados = [];

async function conectar() {
  for (let i = 0; i < 50; i++) {
    try {
      const lista = await (await fetch(`http://127.0.0.1:${PUERTO}/json/list`)).json();
      const pagina = lista.find((x) => x.type === "page");
      if (pagina) return pagina.webSocketDebuggerUrl;
    } catch { /* aún arrancando */ }
    await espera(200);
  }
  throw new Error("Chrome no respondió en el puerto de depuración");
}

function enviar(metodo, params = {}) {
  return new Promise((resolve, reject) => {
    const n = ++id;
    pendientes.set(n, { resolve, reject });
    ws.send(JSON.stringify({ id: n, method: metodo, params }));
  });
}

async function evaluar(expr) {
  const r = await enviar("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(`${expr.slice(0, 60)}…: ${r.exceptionDetails.exception?.description ?? r.exceptionDetails.text}`);
  return r.result.value;
}

async function esperarA(expr, ms = 20000, nombre = expr) {
  const fin = Date.now() + ms;
  while (Date.now() < fin) {
    try { if (await evaluar(expr)) return true; } catch { /* reintenta */ }
    await espera(250);
  }
  throw new Error(`tiempo agotado esperando: ${nombre}`);
}

async function captura(nombre) {
  const r = await enviar("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(SALIDA, `${nombre}.png`), Buffer.from(r.data, "base64"));
}

function comprobar(nombre, ok, detalle = "") {
  resultados.push({ nombre, ok, detalle });
  console.log(`${ok ? "OK  " : "FALLA"} ${nombre}${detalle ? ` — ${detalle}` : ""}`);
}

async function rueda(dy, veces) {
  const [x, y] = await evaluar(`(() => { const r = document.getElementById("globo").getBoundingClientRect(); return [r.left + r.width * 0.62, r.top + r.height / 2]; })()`);
  for (let i = 0; i < veces; i++) {
    await enviar("Input.dispatchMouseEvent", { type: "mouseWheel", x, y, deltaX: 0, deltaY: dy });
    await espera(120);
  }
}

try {
  ws = new WebSocket(await conectar());
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pendientes.has(m.id)) {
      const p = pendientes.get(m.id); pendientes.delete(m.id);
      m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result);
    } else if (m.method === "Runtime.exceptionThrown") {
      errores.push(m.params.exceptionDetails.exception?.description ?? m.params.exceptionDetails.text);
    } else if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
      errores.push(m.params.args.map((a) => a.value ?? a.description).join(" "));
    }
  });
  await enviar("Runtime.enable");
  await enviar("Page.enable");

  // 1. Mapa regional del Huila
  await enviar("Page.navigate", { url: URL_UI });
  await esperarA(`document.getElementById("mapa-filtro")?.textContent.includes("foco")`, 30000, "focos del Huila");
  await espera(1500);
  await captura("01_regional");
  comprobar("mapa regional con focos", true, await evaluar(`document.getElementById("mapa-filtro").textContent`));
  comprobar("leyenda numérica visible", await evaluar(`document.getElementById("leyenda-mapa").textContent.length > 10`));
  const alto = await evaluar(`(() => { const r = document.getElementById("mapa-escena").getBoundingClientRect(); return r.height / innerHeight; })()`);
  comprobar("el mapa ocupa ≥ 60 % del alto de la ventana", alto >= 0.6, `${Math.round(alto * 100)} %`);

  // 2. Alejarse hasta la vista de país → globo 3D
  await evaluar(`void mapa.setView([4, -72], 6, { animate: false })`);
  await espera(300);
  await evaluar(`void mapa.setZoom(5, { animate: false })`);
  await esperarA(`document.getElementById("mapa-escena").dataset.vista === "globo"`, 5000, "paso al globo");
  await esperarA(`document.querySelector(".globo-cifra strong")`, 30000, "cifras globales");
  await espera(6000);
  await captura("02_globo");
  comprobar("alejar en el mapa regional abre el globo", true);
  comprobar("panel mundial con cifras", true, await evaluar(`document.querySelector(".globo-cifras").innerText.split("\\n").slice(0, 2).join(" | ")`));
  comprobar("la página no se desplaza sola", (await evaluar(`scrollY`)) === 0, `scrollY=${await evaluar("scrollY")}`);

  // 3. País de la lista → vuela a él sin salir del globo
  await evaluar(`document.querySelectorAll(".globo-paises button")[2].click()`);
  await espera(3500);
  await captura("03_pais");
  comprobar("clic en un país mantiene el globo", (await evaluar(`document.getElementById("mapa-escena").dataset.vista`)) === "globo",
    await evaluar(`document.querySelector(".globo-pais").innerText`));

  // 4. Acercarse con la rueda → mapa regional en esa zona, con sus focos
  await rueda(-500, 12);
  await esperarA(`document.getElementById("mapa-escena").dataset.vista === "regional"`, 15000, "vuelta al mapa regional");
  await esperarA(`document.getElementById("sel-area").value === "dibujo" && document.getElementById("mapa-filtro").textContent.includes("foco")`, 30000, "zona explorada");
  await espera(2000);
  await captura("04_zona_explorada");
  comprobar("acercarse en el globo abre la zona en el mapa regional", true,
    `${await evaluar(`estado.bbox.join(", ")`)} · ${await evaluar(`document.getElementById("mapa-filtro").textContent`)}`);

  // 5. Un día con focos: puntos individuales con la nueva simbología
  await evaluar(`(() => { const r = [...document.querySelectorAll("rect.dia")].reverse().find((x) => /[1-9]\\d* foco/.test(x.getAttribute("aria-label"))); r.dispatchEvent(new MouseEvent("click", { bubbles: true })); return r.dataset.dia; })()`);
  await esperarA(`document.getElementById("mapa-filtro").textContent.includes(" el ")`, 20000, "vista del día");
  await espera(1500);
  await captura("05_dia");
  comprobar("vista del día con leyenda de FRP", await evaluar(`document.getElementById("leyenda-mapa").textContent.includes("FRP")`),
    await evaluar(`document.getElementById("mapa-filtro").textContent`));

  // 6. Tema claro en el globo (Blue Marble)
  await evaluar(`(() => { const s = document.getElementById("sel-tema"); s.value = "claro"; s.dispatchEvent(new Event("change")); })()`);
  await evaluar(`document.getElementById("btn-globo").click()`);
  await esperarA(`document.getElementById("mapa-escena").dataset.vista === "globo"`, 5000, "globo por botón");
  await espera(6000);
  await captura("06_globo_claro");
  comprobar("botón «Ver el globo 3D» y tema claro", true);

  // 7. Móvil
  await enviar("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await evaluar(`document.getElementById("btn-globo").click()`);
  await espera(2500);
  await captura("07_movil_regional");
  const desborde = await evaluar(`document.documentElement.scrollWidth - innerWidth`);
  comprobar("sin desplazamiento horizontal en móvil", desborde <= 0, `${desborde}px`);

  comprobar("sin errores en la consola", errores.length === 0, errores.slice(0, 5).join(" ‖ "));
} catch (err) {
  comprobar("recorrido completo", false, err.message);
  try { await captura("99_fallo"); } catch { /* sin captura */ }
} finally {
  try { ws?.close(); } catch { /* cerrado */ }
  chrome.kill();
  await espera(500);
  try { rmSync(perfil, { recursive: true, force: true }); } catch { /* bloqueado en Windows */ }
}

const fallas = resultados.filter((r) => !r.ok).length;
console.log(`\n${resultados.length - fallas}/${resultados.length} comprobaciones correctas. Capturas en ${SALIDA}`);
process.exit(fallas ? 1 : 0);
