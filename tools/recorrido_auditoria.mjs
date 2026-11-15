// Segunda fase: interacciones sobre la demo publicada o una instancia local.
// No certifica lector de pantalla ni calibración científica.
export async function probarAuditoria({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI,verificarCarga=false}) {
  await enviar("Emulation.setDeviceMetricsOverride",{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await enviar("Page.navigate",{url:URL_UI});
  await esperarA(`typeof mapa!=="undefined" && estado.calendario && municipios.length===37 && !document.getElementById("panel-analisis").hasAttribute("aria-busy")`,45000,"aplicación ejecutada");
  const quieto=()=>esperarA(`!mapa.isMoving() && mapa.areTilesLoaded() && document.getElementById("mapa-esqueleto").hidden`,45000,"mapa dibujado y teselas listas");
  await quieto();
  await evaluar(`window.lienzoAuditoria=mapa.getCanvas();void 0`);
  comprobar("Inicialización completa: origen resuelto y resumen calculado",await evaluar(`!document.getElementById("insignia-origen").textContent.includes("desconocido") && !document.getElementById("resumen-texto").textContent.includes("Cargando")`));
  await captura("01_origen_resuelto");
  async function buscarLocal(q) {
    await evaluar(`(()=>{const c=document.getElementById("consulta-lugar");c.value=${JSON.stringify(q)};c.dispatchEvent(new Event("input"));document.getElementById("buscar-lugar").requestSubmit();})()`);
    await espera(150);
    await evaluar(`(()=>{if(!document.getElementById("resultados-lugares").hidden)document.querySelector("#lista-lugares button")?.click()})()`);
    await esperarA(`zonaSel?.zona.properties.shapeName===${JSON.stringify(q)} && !mapa.isMoving()`,10000,"zona "+q);
  }
  await buscarLocal("Neiva");
  comprobar("F01: búsqueda de Neiva encuadra el municipio",await evaluar(`zonaSel.nivel==="municipio" && Math.abs(mapa.getCenter().lng+75.3)<0.5 && Math.abs(mapa.getCenter().lat-2.95)<0.5 && mapa.getCanvas()===lienzoAuditoria`));
  await evaluar(`document.getElementById("zona-analizar").click()`);
  await esperarA(`!document.getElementById("panel-analisis").hasAttribute("aria-busy") && estado.area?.startsWith("mun:")`,30000,"análisis municipal");
  const anioAntes=await evaluar(`estado.anio`);
  await evaluar(`(()=>{const s=document.getElementById("sel-anio");const a=[...s.options].find(o=>Number(o.value)!==estado.anio);if(!a)throw new Error("La muestra no tiene otro año");s.value=a.value;s.dispatchEvent(new Event("change"));})()`);
  await esperarA(`!document.getElementById("panel-analisis").hasAttribute("aria-busy") && estado.anio!==${anioAntes}`,30000,"año alternativo");
  comprobar("F02: año e indicadores se actualizan",await evaluar(`Number(document.getElementById("cal-anio").textContent)===Number(estado.anio) && estado.calendario.dias.every(d=>d.fecha_utc.startsWith(String(estado.anio)))`));
  await evaluar(`(()=>{const d=estado.calendario.dias.filter(d=>d.n_detecciones>0)[0];if(!d)throw new Error("Faltan focos para el rango");window.fechaAuditoria=d.fecha_utc;document.getElementById("rango-desde").value=d.fecha_utc;document.getElementById("rango-hasta").value=d.fecha_utc;document.getElementById("btn-rango").click();})()`);
  await esperarA(`ultimosFocos?.desde===fechaAuditoria && ultimosFocos?.hasta===fechaAuditoria`,15000,"rango del mapa");
  comprobar("F03: el mapa respeta el rango de un día UTC",await evaluar(`ultimosFocos.detecciones.length>0 && ultimosFocos.detecciones.every(d=>d.fecha_hora_utc.startsWith(fechaAuditoria))`));
  // Dibujo de un recuadro: se verifica lo que realmente ofrece la aplicación.
  await evaluar(`(()=>{const b=zonaSel.zona.properties.bbox;window.cajaAuditoria=[b[0]-.01,b[1]-.01,b[2]+.01,b[3]+.01];const [w,s,e,n]=cajaAuditoria;document.getElementById("btn-dibujar").click();mapa.fire("click",{lngLat:{lng:w,lat:s},point:mapa.project([w,s]),originalEvent:{target:mapa.getCanvas()}});mapa.fire("click",{lngLat:{lng:e,lat:n},point:mapa.project([e,n]),originalEvent:{target:mapa.getCanvas()}});})()`);
  await esperarA(`estado.area===null && !document.getElementById("panel-analisis").hasAttribute("aria-busy") && JSON.stringify(ultimosFocos?.bbox)===JSON.stringify(cajaAuditoria) && !mapa.isMoving()`,30000,"recuadro y focos actualizados");
  comprobar("F04 parcial: el recuadro usa exactamente sus cuatro coordenadas",await evaluar(`JSON.stringify(estado.bbox)===JSON.stringify(cajaAuditoria) && estado.calendario.area.filtro==="recuadro"`));
  await evaluar(`(()=>{window.focoAuditoria=ultimosFocos.detecciones[0];if(!focoAuditoria)throw new Error("El recuadro no contiene focos");if(document.getElementById("btn-capas").getAttribute("aria-expanded")==="true")document.getElementById("btn-capas").click();mapa.jumpTo({center:[focoAuditoria.lon,focoAuditoria.lat],zoom:13});})()`);
  await esperarA(`mapa.queryRenderedFeatures(mapa.project([focoAuditoria.lon,focoAuditoria.lat]),{layers:["detalle-focos"]}).length>0`,15000,"círculo individual");
  const punto=await evaluar(`(()=>{const p=mapa.project([focoAuditoria.lon,focoAuditoria.lat]),r=mapa.getCanvas().getBoundingClientRect();return [r.x+p.x,r.y+p.y]})()`);
  await enviar("Input.dispatchMouseEvent",{type:"mousePressed",x:punto[0],y:punto[1],button:"left",clickCount:1});
  await enviar("Input.dispatchMouseEvent",{type:"mouseReleased",x:punto[0],y:punto[1],button:"left",clickCount:1});
  await esperarA(`document.querySelector(".ficha-foco")`,6000,"ficha del foco");
  comprobar("F05: ficha con sensor, fecha, FRP y confianza",await evaluar(`(()=>{const t=document.querySelector(".ficha-foco").textContent;return ["Fecha","FRP","Confianza","VIIRS"].every(c=>t.includes(c)) || ["Fecha","FRP","Confianza","MODIS"].every(c=>t.includes(c))})()`));
  if(await evaluar(`Boolean(document.querySelector(".foco-procedencia"))`)) {
    await evaluar(`document.querySelector(".foco-procedencia").open=true`);
    comprobar("Ficha de linaje enlaza archivo, checksum y ejecución",await evaluar(`(()=>{const t=document.querySelector(".foco-procedencia").textContent;return t.includes(focoAuditoria.record_id) && t.includes(focoAuditoria.sha256_origen) && t.includes(focoAuditoria.dataset_id)})()`));
  }
  await quieto();
  if(verificarCarga) comprobar("La ficha expandida permanece dentro del mapa",await evaluar(`(()=>{const r=document.querySelector(".maplibregl-popup").getBoundingClientRect(),m=mapa.getCanvas().getBoundingClientRect();return r.top>=m.top && r.bottom<=m.bottom})()`));
  await captura("02_ficha_foco");
  await evaluar(`document.querySelectorAll(".maplibregl-popup-close-button").forEach(b=>b.click())`);
  await buscarLocal("Garzón");await buscarLocal("Neiva");
  comprobar("F09: cambiar de región elimina la selección anterior",await evaluar(`zonaSel.zona.properties.shapeName==="Neiva" && document.getElementById("zona-titulo").textContent==="Neiva" && document.querySelectorAll(".etiqueta-zona").length===1`));
  await enviar("Network.enable");
  await enviar("Network.emulateNetworkConditions",{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
  await evaluar(`(()=>{const c=document.getElementById("consulta-lugar");c.value="ZZ auditoría conexión";document.getElementById("buscar-lugar").requestSubmit();})()`);
  await esperarA(`/conexión|conectar|no disponible/i.test(document.getElementById("estado-busqueda").textContent)`,6000,"error de conexión");
  comprobar("F08: sin red informa el error y conserva el mapa",await evaluar(`mapa.getCanvas()===lienzoAuditoria && document.getElementById("estado-busqueda").textContent.length>15`));
  await enviar("Network.emulateNetworkConditions",{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  await evaluar(`document.getElementById("consulta-lugar").focus()`);
  await enviar("Input.dispatchKeyEvent",{type:"keyDown",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
  await enviar("Input.dispatchKeyEvent",{type:"keyUp",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
  comprobar("F10 parcial: Escape cierra y devuelve el foco al buscador",await evaluar(`document.getElementById("resultados-lugares").hidden && document.activeElement===document.getElementById("consulta-lugar")`));
  const arbol=await enviar("Accessibility.getFullAXTree");
  comprobar("F10 parcial: buscador etiquetado en el árbol accesible",arbol.nodes.some(n=>["searchbox","textbox"].includes(n.role?.value) && /lugar|dirección|ubicación/i.test(n.name?.value??"")));
  await enviar("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await evaluar(`scrollTo(0,0)`);await espera(500);
  comprobar("F10 parcial: móvil sin desborde horizontal",await evaluar(`document.documentElement.scrollWidth<=innerWidth`));
  await captura("03_movil");
  if(verificarCarga) {
    await evaluar(`window.fetchCargaAuditoria=fetch.bind(window);window.demoraFocosAuditoria=false;window.fetch=async(u,o)=>{if(String(u).startsWith("/detecciones?")){window.demoraFocosAuditoria=true;await new Promise(r=>setTimeout(r,1500));}return fetchCargaAuditoria(u,o)};estado.rango=null;estado.dia=null;(()=>{const s=document.getElementById("sel-anio");s.selectedIndex=(s.selectedIndex+1)%s.options.length;s.dispatchEvent(new Event("change"))})()`);
    await esperarA(`window.demoraFocosAuditoria`,15000,"petición de focos demorada");
    comprobar("El análisis conserva aria-busy hasta recibir los focos",await evaluar(`document.getElementById("panel-analisis").getAttribute("aria-busy")==="true"`));
    await esperarA(`!document.getElementById("panel-analisis").hasAttribute("aria-busy")`,15000,"fin de la carga completa");
    await evaluar(`window.fetch=fetchCargaAuditoria;void 0`);
  }
  comprobar("Sin excepciones de aplicación",errores.filter(e=>!e.includes("Failed to fetch")).length===0,errores.slice(0,2).join(" | "));
}
