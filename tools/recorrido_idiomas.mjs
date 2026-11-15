// Conservación del mapa, traducción dinámica, persistencia y revisión de textos científicos.
export async function probarIdiomas({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI,registrar}){
  await enviar("Emulation.setDeviceMetricsOverride",{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await enviar("Page.navigate",{url:URL_UI});
  await esperarA(`typeof Idiomas!=="undefined" && typeof mapa!=="undefined" && estado.calendario && document.querySelector(".globo-cifra strong")`,30000,"idiomas y datos");
  await esperarA(`!document.getElementById("mapa-esqueleto").classList.contains("inicial")`,45000,"primer dibujo del mapa");
  await esperarA(`!document.getElementById("panel-analisis").hasAttribute("aria-busy")`,15000,"análisis listo");
  await evaluar(`window.lienzoIdiomas=mapa.getCanvas();window.ubicacionIdiomas=location.href;window.filtroIdiomas=JSON.stringify({area:estado.area,bbox:estado.bbox,anio:estado.anio,dia:estado.dia,rango:estado.rango});void 0`);
  const textos={es:["Explorador de focos","Resumen mundial"],en:["Heat detection explorer","World summary"],fr:["Explorateur de détections thermiques","Résumé mondial"]};
  const origen=await evaluar(`estado.calendario.origen_datos`);
  const revision={};
  for(const idioma of ["es","en","fr"]){
    await evaluar(`Idiomas.cambiar(${JSON.stringify(idioma)})`);
    await esperarA(`document.getElementById("mapa-titulo").textContent===${JSON.stringify(textos[idioma][0])}`,5000,"título "+idioma);
    comprobar(`${idioma}: títulos y atributo lang traducidos`,await evaluar(`document.documentElement.lang===${JSON.stringify(idioma)} && document.querySelector(".globo-cabeza h2").textContent===${JSON.stringify(textos[idioma][1])}`));
    comprobar(`${idioma}: idioma conserva el mapa y la selección temporal`,await evaluar(`mapa.getCanvas()===lienzoIdiomas && location.href===ubicacionIdiomas && filtroIdiomas===JSON.stringify({area:estado.area,bbox:estado.bbox,anio:estado.anio,dia:estado.dia,rango:estado.rango})`));
    const aviso=await evaluar(`document.getElementById("insignia-origen").textContent`);
    const palabra=origen==="real"?(idioma==="es"?"reales":idioma==="en"?"Real":"réelles"):(idioma==="es"?"SINTÉTICOS":idioma==="en"?"SYNTHETIC":"SYNTHÉTIQUES");
    comprobar(`${idioma}: naturaleza de los datos visible`,aviso.includes(palabra),aviso);
    await captura("01_"+idioma+"_escritorio");
    if(idioma!=="es"){
      await evaluar(`window.detallesIdiomas=[...document.querySelectorAll("details")].map(d=>[d,d.open]);for(const [d] of detallesIdiomas)if(!d.matches(".controles-secundarios"))d.open=true`);
      await espera(250);
      revision[idioma]=await evaluar(`(()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),a=[];let n;const re=/\\b(focos|cargando|datos|celdas|requiere|insuficiente|inusuales|umbrales|promedio|recuento|seleccionado|píxel|pueden|marcan|requieren|observaciones|necesitan|histórico|calidad|fuente|calculando|se usan|días|años)\\b/iu;while(n=w.nextNode()){const e=n.parentElement,t=n.data.trim();if(!t||!e||e.closest("script,style,code,q,[hidden],#cita,#aviso")||!e.getClientRects().length)continue;let oculto=false;for(let p=e;p;p=p.parentElement)if(p.tagName==="DETAILS"&&!p.open&&!p.firstElementChild?.contains(e))oculto=true;if(!oculto&&re.test(t))a.push(t);}return [...new Set(a)]})()`);
      await evaluar(`for(const [d,abierto] of detallesIdiomas)d.open=abierto`);
    }
  }
  await evaluar(`(()=>{const s=document.querySelector(".globo-periodo select");s.value="1";s.dispatchEvent(new Event("change"))})()`);
  await esperarA(`!document.getElementById("globo-panel").hasAttribute("aria-busy")`,15000,"periodo actualizado");await espera(250);
  comprobar("fr: datos nuevos conservan el idioma",await evaluar(`document.querySelector(".globo-cabeza h2").textContent==="Résumé mondial" && /données|synthétiques/i.test(document.querySelector(".globo-naturaleza").textContent)`));
  await evaluar(`document.getElementById("consulta-lugar").value="Neiva";document.getElementById("buscar-lugar").requestSubmit()`);
  await espera(150);await evaluar(`if(!document.getElementById("resultados-lugares").hidden)document.querySelector("#lista-lugares button")?.click()`);
  await evaluar(`document.getElementById("confirmar-lugar").click()`);
  await esperarA(`zonaSel?.zona.properties.shapeName==="Neiva"`,5000,"Neiva");await espera(250);
  comprobar("fr: la búsqueda conserva el nombre del lugar y traduce su categoría",await evaluar(`document.getElementById("zona-titulo").textContent==="Neiva" && document.getElementById("zona-nivel").textContent.includes("Commune")`));
  await enviar("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await evaluar(`scrollTo(0,0)`);await espera(250);await captura("02_fr_movil");
  comprobar("fr: selector y controles móviles sin desborde",await evaluar(`document.documentElement.scrollWidth<=innerWidth && document.getElementById("sel-idioma").getBoundingClientRect().right<=innerWidth`));
  await enviar("Page.reload",{});
  await esperarA(`typeof Idiomas!=="undefined" && document.documentElement.lang==="fr" && document.getElementById("mapa-titulo").textContent==="Explorateur de détections thermiques"`,15000,"preferencia persistente");
  comprobar("La preferencia de idioma persiste al recargar",true);
  await evaluar(`Idiomas.cambiar("es")`);await espera(150);
  comprobar("Volver a español restaura los textos originales",await evaluar(`document.getElementById("mapa-titulo").textContent==="Explorador de focos" && document.getElementById("consulta-lugar").placeholder==="Municipio, departamento o lugar…"`));
  await enviar("Page.navigate",{url:URL_UI+(URL_UI.includes("?")?"&":"?")+"lang=en"});
  await esperarA(`document.documentElement.lang==="en" && document.getElementById("mapa-titulo")?.textContent==="Heat detection explorer"`,15000,"enlace directo en inglés");
  comprobar("El enlace lang=en abre la versión en inglés",true);
  await evaluar(`Idiomas.cambiar("fr")`);await enviar("Page.reload",{});
  await esperarA(`document.documentElement.lang==="fr" && document.getElementById("mapa-titulo")?.textContent==="Explorateur de détections thermiques"`,15000,"preferencia tras enlace directo");
  comprobar("Cambiar de idioma actualiza también el enlace directo",true);
  registrar("revision_textos",revision);
  console.log("TEXTOS_PARA_REVISAR",JSON.stringify(revision));
  comprobar("Sin excepciones de aplicación",errores.filter(e=>!e.includes("Failed to fetch")).length===0,errores.slice(0,2).join(" | "));
}
