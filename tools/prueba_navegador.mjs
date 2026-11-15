// Prueba de uso de punta a punta en un Chrome real, sin dependencias (Node ≥ 22: WebSocket y fetch nativos).
// Recorre el planeta continuo, límites globales, tema, carga localizada, calendario, ficha y dibujo.
// Guarda capturas y falla si hay errores de consola o se reconstruye el mapa al explorar.
//
// Uso (con la API en marcha):
//   node tools/prueba_navegador.mjs [URL=http://127.0.0.1:8000/ui/] [CARPETA_CAPTURAS] [RUTA_CHROME] [normal|planeta|busqueda|panel|separado|capas]
import { probarMapa } from './recorrido_mapa.mjs';
import { probarBusqueda } from './recorrido_busqueda.mjs';
import { probarCapas } from './recorrido_capas.mjs';
import { probarAuditoria } from './recorrido_auditoria.mjs';
import { probarIdiomas } from './recorrido_idiomas.mjs';
import { probarHidrografia } from './recorrido_hidrografia.mjs';
import { probarConfirmacionLugar } from './recorrido_confirmacion_lugar.mjs';
import { probarPeriodos } from './recorrido_periodos.mjs';
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname, basename } from "node:path";

const URL_UI = process.argv[2] ?? "http://127.0.0.1:8000/ui/";
const SALIDA = process.argv[3] ?? join(tmpdir(), "hhn_capturas");
const CHROME = process.argv[4] ?? (process.platform === "win32"
  ? "C:/Program Files/Google/Chrome/Application/chrome.exe" : "google-chrome");
const MODO = process.argv[5] ?? "normal";
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

  if(MODO==="periodos") await probarPeriodos({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI,registrar:(nombre,datos)=>writeFileSync(join(SALIDA,nombre+".json"),JSON.stringify(datos,null,2))});
  else if(MODO==="confirmacion") await probarConfirmacionLugar({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI});
  else if(MODO==="hidrografia") await probarHidrografia({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI,registrar:(nombre,datos)=>writeFileSync(join(SALIDA,nombre+".json"),JSON.stringify(datos,null,2))});
  else if(MODO==="idiomas") await probarIdiomas({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI,registrar:(nombre,datos)=>writeFileSync(join(SALIDA,nombre+".json"),JSON.stringify(datos,null,2))});
  else if(MODO==="auditoria" || MODO==="auditoria-local") await probarAuditoria({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI,verificarCarga:MODO==="auditoria-local"});
  else if(MODO==="busqueda") await probarBusqueda({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI});
  else if(MODO==="capas") await probarCapas({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI,
    guardar:(nombre,datos)=>writeFileSync(join(SALIDA,`${nombre}.png`),Buffer.from(datos,"base64"))});
  else await probarMapa({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI,MODO});
} catch (err) {
  comprobar("recorrido completo", false, err.message);
  try { await captura("99_fallo"); } catch { /* sin captura */ }
} finally {
  try { ws?.close(); } catch { /* cerrado */ }
  chrome.kill();
  await espera(500);
  const perfilAbsoluto = resolve(perfil);
  const perfilPropio = dirname(perfilAbsoluto) === resolve(tmpdir()) && basename(perfilAbsoluto).startsWith("hhn-chrome-");
  try { if (perfilPropio) rmSync(perfilAbsoluto, { recursive: true, force: true }); } catch { /* bloqueado en Windows */ }
}

const fallas = resultados.filter((r) => !r.ok).length;
console.log(`\n${resultados.length - fallas}/${resultados.length} comprobaciones correctas. Capturas en ${SALIDA}`);
process.exit(fallas ? 1 : 0);
