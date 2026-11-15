// Flujo de búsqueda y municipio del foco. Respuestas geocodificadas controladas;
// mapa, consultas FIRMS y geometrías geoBoundaries reales, sin peticiones masivas al buscador.
export async function probarLugaresFocos({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI}) {
  await enviar("Emulation.setDeviceMetricsOverride",{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await enviar("Page.navigate",{url:URL_UI});
  await esperarA(`typeof mapa!=="undefined" && estado.calendario && municipios.length===37 && mapa.isStyleLoaded()`,30000,"planeta y límites locales");
  const quieto = () => esperarA(`!mapa.isMoving() && mapa.areTilesLoaded()`,30000,"mapa y teselas listas").then(()=>espera(250));
  await quieto();
  await evaluar(`window.lienzoPrueba=mapa.getCanvas();window.tituloPrueba=document.querySelector("h1");void 0`);
  comprobar("inicio mundial sin área predeterminada en Huila",await evaluar(`estado.area===null && document.getElementById("sel-area").value==="mundo" && mapa.getStyle().sources.seleccion.data.features.length===0 && Math.abs(mapa.getCenter().lng)<1`));
  comprobar("límites locales con la misma escala que los globales",await evaluar(`mapa.getLayer("limites-municipio").minzoom===8 && mapa.getLayer("limites-departamento").minzoom===5 && JSON.stringify(mapa.getPaintProperty("limites-municipio","line-opacity"))===JSON.stringify(mapa.getPaintProperty("limites-adm2","line-opacity"))`));
  await captura("01_inicio_global");
  await evaluar(`window.fetchOriginalPrueba=fetch.bind(window); window.consultasPrueba=[];
    window.fetch=async(url,opts)=>{
      const u=new URL(String(url),location.href);
      if(u.pathname!=="/buscar-lugares")return fetchOriginalPrueba(url,opts);
      const q=u.searchParams.get("q");consultasPrueba.push(q);
      const datos={
        "España":{nombre:"España",tipo:"País",descripcion:"España, Europa",lat:40.4,lon:-3.7,bbox:[-9.5,35.9,4.3,43.8]},
        "Medellín, Colombia":{nombre:"Medellín",tipo:"Ciudad",descripcion:"Medellín, Antioquia, Colombia",lat:6.24,lon:-75.58,bbox:[-75.72,6.16,-75.48,6.38]},
        "Chapinero, Bogotá":{nombre:"Chapinero",tipo:"Barrio",descripcion:"Chapinero, Bogotá, Colombia",lat:4.64,lon:-74.06,bbox:[-74.07,4.63,-74.05,4.66]},
        "Palermo, Argentina":{nombre:"Palermo",tipo:"Barrio",descripcion:"Palermo, Buenos Aires, Argentina",lat:-34.58,lon:-58.43,bbox:[-58.46,-34.6,-58.4,-34.56]},
      };
      const lugar=datos[q];
      if(q!=="Palermo, Argentina") {const [w,s,e,n]=lugar.bbox;lugar.geometria={type:"Polygon",coordinates:[[[w,s],[e,s],[e,n],[w,n],[w,s]]]};}
      return new Response(JSON.stringify({resultados:[lugar]}),{status:200});
    };void 0`);
  async function buscar(q) {
    await evaluar(`(()=>{const c=document.getElementById("consulta-lugar");c.value=${JSON.stringify(q)};c.dispatchEvent(new Event("input"));document.getElementById("buscar-lugar").requestSubmit()})()`);
    await esperarA(`!document.getElementById("resultados-lugares").hidden && document.querySelector("#lista-lugares button") && !document.getElementById("btn-buscar-lugar").disabled`,8000,"resultado de "+q);
    await evaluar(`document.querySelector("#lista-lugares button").click()`);
    await quieto();
  }
  for (const [q,nivel,zmin,zmax] of [["España","pais",2,6],["Medellín, Colombia","ciudad",7,12],["Chapinero, Bogotá","barrio",10,14]]) {
    await buscar(q);
    comprobar(`búsqueda de ${nivel}: encuadre y clasificación correctos`,await evaluar(`zonaSel?.nivel===${JSON.stringify(nivel)} && mapa.getZoom()>${zmin} && mapa.getZoom()<${zmax} && mapa.getCanvas()===lienzoPrueba`));
    comprobar(`búsqueda de ${nivel}: centro contenido y análisis preservado`,await evaluar(`(()=>{const b=zonaSel.zona.properties.bbox,c=mapa.getCenter();return c.lng>=b[0] && c.lng<=b[2] && c.lat>=b[1] && c.lat<=b[3] && estado.area===null && document.getElementById("sel-area").value==="mundo"})()`));
    await captura("02_busqueda_"+nivel);
  }
  await buscar("Palermo, Argentina");
  comprobar("un barrio sin polígono retira el resaltado de la búsqueda anterior",await evaluar(`zonaSel===null && document.getElementById("tarjeta-zona").hidden && mapa.getStyle().sources.zona.data.features.length===0 && Math.abs(mapa.getCenter().lng+58.43)<0.1`));
  comprobar("un lugar homónimo fuera de Colombia no se sustituye por el municipio local",await evaluar(`consultasPrueba.includes("Palermo, Argentina") && mapa.getCenter().lat<0`));
  await evaluar(`(()=>{const c=document.getElementById("consulta-lugar");c.value="Garzón";document.getElementById("buscar-lugar").requestSubmit()})()`);
  await esperarA(`document.querySelector("#lista-lugares .buscar-internet")`,5000,"confirmación local");
  comprobar("una coincidencia local requiere elegir y permite buscar homónimos",await evaluar(`document.querySelector("#lista-lugares button strong").textContent==="Garzón" && document.querySelector("#lista-lugares .buscar-internet") && mapa.getCenter().lat<0`));
  await evaluar(`document.querySelector("#lista-lugares button").click()`);
  await esperarA(`!mapa.isMoving() && zonaSel?.zona.properties.shapeName==="Garzón"`,5000,"municipio local");
  comprobar("búsqueda local encuadra el límite real sin internet",await evaluar(`zonaSel.nivel==="municipio" && mapa.getCanvas()===lienzoPrueba`));
  // Seleccionar un punto dentro del área urbana desde lejos conserva el municipio entero.
  await evaluar(`quitarZona();mapa.jumpTo({center:[-75.28,2.93],zoom:7});void seleccionarZonaEn(-75.28,2.93,7)`);
  await esperarA(`zonaSel?.nivel==="municipio" && !mapa.isMoving()`,6000,"municipio del foco");
  comprobar("el foco centra y encuadra su municipio completo desde lejos",await evaluar(`zonaSel.zona.properties.shapeName==="Neiva" && mapa.getZoom()>7 && Zonas.contiene(zonaSel.zona.geometry,-75.28,2.93) && mapa.getStyle().sources.zona.data.features.length===1`));
  const muni=await evaluar(`zonaSel.zona.properties.shapeID`);
  await evaluar(`mapa.jumpTo({zoom:12});void 0`);await espera(250);
  comprobar("hacer zoom conserva el municipio y no lo cambia al área urbana",await evaluar(`zonaSel.nivel==="municipio" && zonaSel.zona.properties.shapeID===${JSON.stringify(muni)}`));
  await quieto();
  await captura("03_foco_municipio");
  // Clic real sobre una detección FIRMS renderizada: verifica el callback completo.
  await evaluar(`(async()=>{const c=globo.cobertura();const r=await fetchOriginalPrueba('/detecciones?bbox=-76.7,1.4,-74.3,3.9&desde='+c.desde+'&hasta='+c.hasta+'&limite=50000');
    const d=await r.json();window.focoPrueba=d.detecciones.find(p=>Zonas.municipioDelFoco(p.lon,p.lat,{municipios,departamentos}));
    if(!focoPrueba)throw new Error("Faltan focos FIRMS en la muestra para el clic real");
    quitarZona();document.querySelectorAll('.maplibregl-popup-close-button').forEach(b=>b.click());
    if(document.getElementById('btn-capas').getAttribute('aria-expanded')==='true')document.getElementById('btn-capas').click();
    seguirViewport=true;mapa.jumpTo({center:[focoPrueba.lon,focoPrueba.lat],zoom:12});return true})()`);
  await esperarA(`!cargasMapa.has("vista") && mapa.queryRenderedFeatures(mapa.project([focoPrueba.lon,focoPrueba.lat]),{layers:["detalle-focos"]}).length>0`,20000,"detección individual renderizada");
  await quieto();
  await evaluar(`seguirViewport=false;void 0`); // Un foco del análisis no cambia al conjunto mundial.
  const punto=await evaluar(`(()=>{const p=mapa.project([focoPrueba.lon,focoPrueba.lat]),r=mapa.getCanvas().getBoundingClientRect();return [r.x+p.x,r.y+p.y]})()`);
  await enviar("Input.dispatchMouseEvent",{type:"mousePressed",x:punto[0],y:punto[1],button:"left",clickCount:1});
  await enviar("Input.dispatchMouseEvent",{type:"mouseReleased",x:punto[0],y:punto[1],button:"left",clickCount:1});
  await esperarA(`zonaSel?.nivel==="municipio" && document.querySelector(".ficha-foco") && !mapa.isMoving()`,8000,"clic y encuadre automático");
  comprobar("clic real en un foco FIRMS conserva su conjunto, abre su ficha y selecciona el municipio",await evaluar(`!seguirViewport && Zonas.contiene(zonaSel.zona.geometry,focoPrueba.lon,focoPrueba.lat) && puntoSel.lon===focoPrueba.lon && puntoSel.lat===focoPrueba.lat && mapa.getCanvas()===lienzoPrueba`));
  comprobar("el encuadre automático incluye el límite municipal completo",await evaluar(`(()=>{const b=zonaSel.zona.properties.bbox ?? Zonas.cajaDe(zonaSel.zona.geometry),v=mapa.getBounds();return v.getWest()<=b[0] && v.getSouth()<=b[1] && v.getEast()>=b[2] && v.getNorth()>=b[3]})()`));
  await quieto();await captura("03_clic_foco_real");
  // Geometrías remotas reales: Tolima y Venezuela, con el mismo resolver que los locales.
  await evaluar(`seguirViewport=true;void 0`);
  for (const [lon,lat,pais] of [[-75.23,4.44,"Tolima"],[-67.6,10.25,"Venezuela"]]) {
    await evaluar(`void seleccionarZonaEn(${lon},${lat},4)`);
    await esperarA(`zonaSel?.nivel==="municipio" && Zonas.contiene(zonaSel.zona.geometry,${lon},${lat}) && !mapa.isMoving()`,60000,"municipio de "+pais);
    comprobar(`foco en ${pais}: límite real, centro y zoom automático`,await evaluar(`mapa.getZoom()>6 && mapa.getCanvas()===lienzoPrueba && mapa.getStyle().sources.zona.data.features.length===1`));
    await quieto();
    await captura("04_foco_"+pais.toLowerCase());
  }
  // La respuesta municipal lenta no puede sobreescribir una búsqueda posterior.
  await evaluar(`window.remotasPrueba=fuentesRemotas;fuentesRemotas=async()=>{await new Promise(r=>setTimeout(r,1100));return null};void seleccionarZonaEn(0,0,4)`);
  await buscar("Medellín, Colombia");await espera(1300);
  comprobar("una búsqueda nueva descarta la respuesta pendiente del municipio anterior",await evaluar(`zonaSel?.zona.properties.shapeName==="Medellín" && !cargasMapa.has("municipio") && Math.abs(mapa.getCenter().lng+75.58)<0.1`));
  await evaluar(`void seleccionarZonaEn(0,0,4)`);
  await esperarA(`document.getElementById("zona-nota").textContent.includes("No se encontró") && !mapa.isMoving()`,6000,"municipio no disponible");
  comprobar("sin límite municipal centra el foco y avisa sin inventar un área",await evaluar(`zonaSel===null && mapa.getStyle().sources.zona.data.features.length===0 && Math.abs(mapa.getCenter().lng)<0.1 && !cargasMapa.has("municipio")`));
  await evaluar(`fuentesRemotas=remotasPrueba;void 0`);
  await enviar("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await buscar("Chapinero, Bogotá");
  comprobar("búsqueda móvil mantiene el mapa y evita desbordes",await evaluar(`document.documentElement.scrollWidth<=innerWidth && mapa.getCanvas()===lienzoPrueba && zonaSel.nivel==="barrio"`));
  await captura("05_barrio_movil");
  comprobar("la estructura de página se conserva durante todas las selecciones",await evaluar(`document.querySelector("h1")===tituloPrueba && !document.body.hasAttribute("aria-busy")`));
  comprobar("sin errores de consola",errores.length===0,errores.slice(0,6).join(" | "));
}
