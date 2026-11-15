// Cantidades reales por periodo, coherencia calendario/globo/detalle y respuestas atrasadas.
export async function probarPeriodos({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI,registrar}) {
  await enviar("Emulation.setDeviceMetricsOverride",{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await enviar("Page.navigate",{url:URL_UI});
  await esperarA(`typeof mapa!=="undefined" && globo.cobertura() && estado.calendario && !document.getElementById("globo-panel").hasAttribute("aria-busy")`,45000,"datos y calendario");
  await esperarA(`!document.getElementById("mapa-esqueleto").classList.contains("inicial")`,45000,"primer dibujo del planeta");
  await evaluar(`window.lienzoPeriodos=mapa.getCanvas();void 0`);
  const quieto = () => esperarA(`!globo.actualizandoPeriodo() && !document.getElementById("globo-panel").hasAttribute("aria-busy")`,45000,"periodo actualizado");
  const elegir = async n => {
    await evaluar(`document.querySelector(".globo-periodo select").value=${JSON.stringify(String(n))};document.querySelector(".globo-periodo select").dispatchEvent(new Event("change"));void 0`);
    await quieto();
  };
  const resultados=[];
  for (const dias of [1,2,7]) {
    await elegir(dias);
    await esperarA(`mapa.isSourceLoaded("focos") && mapa.queryRenderedFeatures({layers:["focos"]}).length>0`,30000,"focos dibujados");
    const r=await evaluar(`(()=>{const d=globo.cobertura(),f=mapa.getSource("focos").serialize().data.features;return {dias:${dias},desde:d.desde,hasta:d.hasta,total:d.total_detecciones,celdas:f.length,suma:f.reduce((s,x)=>s+x.properties.n,0),panel:Number(document.querySelector(".globo-cifra strong").textContent.replace(/\\D/g,""))}})()`);
    resultados.push(r);
    comprobar(`Periodo ${dias}: puntos y contador mundial coinciden`,r.total===r.suma && r.total===r.panel,JSON.stringify(r));
  }
  comprobar("1, 2 y 7 días cambian las cantidades con archivo suficiente",resultados[0].total<resultados[1].total && resultados[1].total<resultados[2].total);
  await captura("01_semana");
  const dias=await evaluar(`(()=>{const d=estado.calendario.dias.filter(d=>d.n_detecciones>0 && d.fecha_utc>=globo.cobertura().desde && d.fecha_utc<=globo.cobertura().hasta).sort((a,b)=>b.n_detecciones-a.n_detecciones);return [d[0]?.fecha_utc,d.find(x=>x.n_detecciones!==d[0]?.n_detecciones)?.fecha_utc]})()`);
  if (!dias[0] || !dias[1]) throw new Error("Se necesitan dos días con cantidades locales distintas");
  const locales=[];
  for (const dia of dias) {
    await evaluar(`seleccionarDia(${JSON.stringify(dia)})`);await quieto();
    await esperarA(`ultimosFocos && periodoMapa?.desde===${JSON.stringify(dia)}`,20000,"detalle del día");
    const r=await evaluar(`({dia:${JSON.stringify(dia)},cantidad:ultimosFocos.detecciones.length,correctos:ultimosFocos.detecciones.every(x=>x.fecha_hora_utc.startsWith(${JSON.stringify(dia)})),global:globo.cobertura().desde===${JSON.stringify(dia)} && globo.cobertura().hasta===${JSON.stringify(dia)}})`);
    locales.push(r);comprobar("Calendario y mapa usan el mismo día: "+dia,r.correctos && r.global,JSON.stringify(r));
  }
  comprobar("Cambiar de día cambia los puntos de la zona",locales[0].cantidad!==locales[1].cantidad);
  const rango=[...dias].sort();
  await evaluar(`document.getElementById("rango-desde").value=${JSON.stringify(rango[0])};document.getElementById("rango-hasta").value=${JSON.stringify(rango[1])};aplicarRango();void 0`);await quieto();
  comprobar("El rango filtra los puntos y el contador mundial con las mismas fechas",await evaluar(`globo.cobertura().desde===${JSON.stringify(rango[0])} && globo.cobertura().hasta===${JSON.stringify(rango[1])} && ultimosFocos.detecciones.every(x=>x.fecha_hora_utc.slice(0,10)>=${JSON.stringify(rango[0])} && x.fecha_hora_utc.slice(0,10)<=${JSON.stringify(rango[1])}) && document.querySelector(".globo-periodo select").value==="fechas"`));
  await elegir(7);
  comprobar("El periodo reciente sustituye al día y rango anteriores",await evaluar(`estado.dia===null && estado.rango===null && ultimosFocos.desde===globo.cobertura().desde && ultimosFocos.hasta===globo.cobertura().hasta`));
  // Una respuesta que ignora el aborto tampoco puede volver a pintar el día anterior.
  await evaluar(`window.fetchPeriodos=fetch.bind(window);window.fechaLenta=${JSON.stringify(dias[0])};window.fetch=(url,op)=>String(url).startsWith("/detecciones?") && new URL(url,location.href).searchParams.get("desde")===fechaLenta?new Promise(resolve=>setTimeout(()=>fetchPeriodos(url,{...op,signal:undefined}).then(resolve),650)):fetchPeriodos(url,op);void 0`);
  await evaluar(`seleccionarDia(${JSON.stringify(dias[0])});void 0`);await espera(120);
  await evaluar(`seleccionarDia(${JSON.stringify(dias[1])})`);await espera(900);await quieto();
  const carrera=await evaluar(`({dia:estado.dia,periodo:periodoMapa,global:globo.periodoActual(),fechas:[...new Set(ultimosFocos.detecciones.map(x=>x.fecha_hora_utc.slice(0,10)))],cantidad:ultimosFocos.detecciones.length})`);
  registrar("carrera",carrera);console.log("CARRERA",JSON.stringify(carrera));
  comprobar("Una respuesta tardía no repone puntos del día anterior",await evaluar(`estado.dia===${JSON.stringify(dias[1])} && ultimosFocos.detecciones.every(x=>x.fecha_hora_utc.startsWith(${JSON.stringify(dias[1])})) && periodoMapa.desde===${JSON.stringify(dias[1])}`));
  await evaluar(`window.fetch=fetchPeriodos;void 0`);
  const fuera=await evaluar(`sumarDias(globo.cobertura().cobertura.desde,-1)`);
  await evaluar(`seleccionarDia(${JSON.stringify(fuera)})`);await quieto();
  comprobar("Una fecha sin observaciones vacía los puntos y muestra cero",await evaluar(`globo.cobertura().total_detecciones===0 && mapa.getSource("focos").serialize().data.features.length===0 && mapa.getSource("detalle").serialize().data.features.length===0 && ultimosFocos.detecciones.length===0`));
  await captura("02_fecha_sin_datos");
  comprobar("El cambio de fechas conserva el mismo mapa",await evaluar(`mapa.getCanvas()===lienzoPeriodos`));
  registrar("resultados",{mundiales:resultados,locales});
  // Simular exactamente el archivo de un día que causaba el problema en producción.
  await enviar("Page.addScriptToEvaluateOnNewDocument",{source:`const fetchArchivo=fetch.bind(window);window.fetch=async(url,op)=>{if(!String(url).startsWith("/global?"))return fetchArchivo(url,op);const u=new URL(url,location.href);u.searchParams.set("dias","1");u.searchParams.delete("desde");u.searchParams.delete("hasta");const r=await fetchArchivo(u.pathname+u.search,op),d=await r.json();d.cobertura={desde:d.hasta,hasta:d.hasta,dias_con_datos:1};return new Response(JSON.stringify(d),{status:200});};`});
  await enviar("Page.reload",{});await quieto();
  await esperarA(`document.querySelector(".globo-periodo select")?.value==="1"`,20000,"archivo de un día");
  comprobar("Archivo de un día: 2 y 7 días no se ofrecen como disponibles",await evaluar(`[...document.querySelector(".globo-periodo select").options].filter(x=>["2","7"].includes(x.value)).every(x=>x.disabled) && !document.querySelector(".globo-cobertura-estado").hidden`));
  await esperarA(`!document.getElementById("mapa-esqueleto").classList.contains("inicial") && mapa.isSourceLoaded("focos")`,45000,"archivo de un día dibujado");
  await captura("03_cobertura_insuficiente");
  comprobar("Sin excepciones de aplicación",errores.length===0,errores.slice(0,2).join(" | "));
}
