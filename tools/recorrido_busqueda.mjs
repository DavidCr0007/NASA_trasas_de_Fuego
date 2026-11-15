// Búsqueda real cacheada y estados de interfaz simulados, sin consultas externas por tecla.
export async function probarBusqueda({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI}) {
  await enviar("Emulation.setDeviceMetricsOverride",{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await enviar("Page.navigate",{url:URL_UI});
  await esperarA(`typeof mapa!=="undefined" && document.querySelector(".globo-cifra strong")`,30000,"mapa y resumen");
  await evaluar(`window.lienzoBusqueda=mapa.getCanvas();window.peticionesLugar=[];window.fetchLugaresOriginal=fetch.bind(window);window.fetch=async(url,opts)=>{
    const u=new URL(String(url),location.href);if(u.pathname!=="/buscar-lugares")return window.fetchLugaresOriginal(url,opts);
    const q=u.searchParams.get("q");window.peticionesLugar.push(q);
    if(q==="ZZ-SIN-RESULTADOS")return new Response(JSON.stringify({resultados:[]}),{status:200});
    if(q==="ZZ-SIN-CONEXION")return new Response(JSON.stringify({detail:"Buscador no disponible temporalmente"}),{status:503});
    if(q==="ZZ-LENTA"){await new Promise(r=>setTimeout(r,600));return new Response(JSON.stringify({resultados:[{nombre:"Obsoleto",descripcion:"No debe aparecer",tipo:"Lugar",lat:0,lon:0,bbox:[-1,-1,1,1]}]}),{status:200});}
    return window.fetchLugaresOriginal(url,opts);
  };void 0`);
  await evaluar(`(()=>{const s=document.querySelector(".globo-periodo select");s.value="1";s.dispatchEvent(new Event("change"));})()`);
  await esperarA(`globo.cobertura()?.desde===globo.cobertura()?.hasta && !document.getElementById("globo-panel").hasAttribute("aria-busy")`,30000,"periodo de un día");
  comprobar("un solo día no genera una gráfica de barra redundante",await evaluar(`!document.querySelector(".globo-serie")`));
  comprobar("la naturaleza de los datos permanece visible fuera de los detalles técnicos",await evaluar(`(()=>{const e=document.querySelector(".globo-naturaleza");return e.clientHeight>0 && e.textContent.includes("Datos reales") && !e.closest("details")})()`));
  await captura("05_panel_un_dia");
  comprobar("los cinco rangos de la leyenda caben en una fila",await evaluar(`(()=>{const e=[...document.querySelectorAll(".escala-frp > span")];return e.length===5 && e.every(x=>Math.abs(x.getBoundingClientRect().top-e[0].getBoundingClientRect().top)<1)})()`));
  await evaluar(`document.querySelector(".globo-ranking").open=true;document.querySelector('.globo-paises button[data-iso="BRA"]').click()`);
  await espera(1800);
  await evaluar(`(()=>{const s=document.querySelector(".globo-periodo select");s.value="2";s.dispatchEvent(new Event("change"));})()`);
  await esperarA(`globo.cobertura()?.desde!==globo.cobertura()?.hasta && !document.getElementById("globo-panel").hasAttribute("aria-busy")`,30000,"nuevo periodo");
  comprobar("la tarjeta del país actualiza sus cifras al cambiar de periodo",await evaluar(`document.querySelector(".globo-pais").textContent.includes(globo.cobertura().paises.find(x=>x.iso_a3==="BRA").n.toLocaleString("es-CO"))`));
  await evaluar(`document.querySelector(".globo-ranking").open=false`);await captura("06_panel_auditado");
  const rect=`(()=>{const r=document.getElementById("globo").getBoundingClientRect();return [r.x,r.y,r.width,r.height].map(Math.round)})()`;
  const antes=await evaluar(rect);
  await evaluar(`(()=>{const c=document.getElementById("consulta-lugar");c.value="Chapinero, Bogota, Colombia";c.dispatchEvent(new Event("input"));c.focus()})()`);
  await espera(350);
  comprobar("escribir no envía búsquedas automáticas",await evaluar(`window.peticionesLugar.length===0`));
  await enviar("Input.dispatchKeyEvent",{type:"keyDown",key:"Enter",code:"Enter",windowsVirtualKeyCode:13});
  await enviar("Input.dispatchKeyEvent",{type:"keyUp",key:"Enter",code:"Enter",windowsVirtualKeyCode:13});
  await esperarA(`document.querySelectorAll("#lista-lugares button").length>0`,20000,"resultados reales de Chapinero");
  comprobar("los resultados distinguen barrio, ciudad y país",await evaluar(`document.querySelector("#lista-lugares").textContent.includes("Colombia") && document.querySelector("#lista-lugares small")?.textContent.includes("Bogot")`));
  const consultasAntes = await evaluar(`window.peticionesLugar.length`);
  const buscar = await evaluar(`(()=>{const r=document.getElementById("btn-buscar-lugar").getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()`);
  await enviar("Input.dispatchMouseEvent",{type:"mousePressed",x:buscar[0],y:buscar[1],button:"left",clickCount:1});
  await enviar("Input.dispatchMouseEvent",{type:"mouseReleased",x:buscar[0],y:buscar[1],button:"left",clickCount:1});
  await esperarA(`window.peticionesLugar.length===${consultasAntes} && !document.getElementById("btn-buscar-lugar").disabled && document.querySelectorAll("#lista-lugares button").length>0`,5000,"buscar con ratón");
  comprobar("Buscar con ratón reutiliza la consulta cacheada sin duplicarla",await evaluar(`window.peticionesLugar.length===${consultasAntes}`));
  comprobar("abrir resultados conserva el tamaño del mapa",JSON.stringify(antes)===JSON.stringify(await evaluar(rect)));
  await captura("07_busqueda_lugares");
  await enviar("Input.dispatchKeyEvent",{type:"keyDown",key:"ArrowDown",code:"ArrowDown",windowsVirtualKeyCode:40});
  await enviar("Input.dispatchKeyEvent",{type:"keyUp",key:"ArrowDown",code:"ArrowDown",windowsVirtualKeyCode:40});
  comprobar("los resultados pueden recorrerse con el teclado",await evaluar(`document.activeElement.matches("#lista-lugares button")`));
  await enviar("Input.dispatchKeyEvent",{type:"keyDown",key:"Enter",code:"Enter",windowsVirtualKeyCode:13});
  await enviar("Input.dispatchKeyEvent",{type:"keyUp",key:"Enter",code:"Enter",windowsVirtualKeyCode:13});
  await esperarA(`document.querySelector(".analizar-lugar")`,5000,"lugar seleccionado");
  await espera(1100);
  comprobar("seleccionar un barrio conserva el lienzo y centra el mapa",await evaluar(`mapa.getCanvas()===window.lienzoBusqueda && Math.abs(mapa.getCenter().lng+74.06)<0.1 && document.querySelector(".globo-pais").hidden`));
  await captura("08_lugar_seleccionado");
  await evaluar(`document.querySelector(".analizar-lugar").click()`);
  await esperarA(`!document.getElementById("panel-analisis").hasAttribute("aria-busy")`,30000,"análisis del lugar");
  comprobar("analizar el lugar actualiza el área como recuadro aproximado",await evaluar(`estado.area===null && document.getElementById("sel-area").selectedOptions[0].textContent.includes("recuadro") && document.getElementById("area-actual").textContent.includes("Bogot")`));
  async function consultar(q) {
    await evaluar(`(()=>{const c=document.getElementById("consulta-lugar");c.value=${JSON.stringify(q)};c.dispatchEvent(new Event("input"));document.getElementById("buscar-lugar").requestSubmit()})()`);
  }
  await consultar("ZZ-SIN-RESULTADOS");
  await esperarA(`document.getElementById("estado-busqueda").textContent.includes("Sin resultados")`,3000,"búsqueda vacía");
  comprobar("sin resultados ofrece una indicación para mejorar la consulta",await evaluar(`document.getElementById("lista-lugares").children.length===0 && document.getElementById("estado-busqueda").textContent.includes("país")`));
  await consultar("ZZ-SIN-CONEXION");
  await esperarA(`document.getElementById("estado-busqueda").textContent.includes("no disponible")`,3000,"error de búsqueda");
  comprobar("un error de búsqueda conserva el mapa",await evaluar(`mapa.getCanvas()===window.lienzoBusqueda`));
  await consultar("ZZ-LENTA");
  await evaluar(`(()=>{const c=document.getElementById("consulta-lugar");c.value="consulta nueva";c.dispatchEvent(new Event("input"));})()`);
  await espera(700);
  comprobar("una respuesta obsoleta no vuelve a abrir los resultados",await evaluar(`document.getElementById("resultados-lugares").hidden && !document.getElementById("lista-lugares").textContent.includes("Obsoleto")`));
  await consultar("ZZ-SIN-RESULTADOS");await espera(100);
  await evaluar(`document.getElementById("consulta-lugar").focus()`);
  await enviar("Input.dispatchKeyEvent",{type:"keyDown",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
  await enviar("Input.dispatchKeyEvent",{type:"keyUp",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
  comprobar("Escape cierra los resultados",await evaluar(`document.getElementById("resultados-lugares").hidden`));
  await enviar("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:2,mobile:true});
  await evaluar(`scrollTo(0,0)`);await consultar("Chapinero, Bogota, Colombia");
  await esperarA(`document.querySelectorAll("#lista-lugares button").length>0`,10000,"búsqueda móvil");
  await captura("09_busqueda_movil");
  comprobar("la búsqueda móvil no genera desborde horizontal",await evaluar(`document.documentElement.scrollWidth<=innerWidth && document.getElementById("resultados-lugares").getBoundingClientRect().right<=innerWidth`));
  comprobar("sin errores de consola",errores.length===0,errores.slice(0,6).join(" | "));
}
