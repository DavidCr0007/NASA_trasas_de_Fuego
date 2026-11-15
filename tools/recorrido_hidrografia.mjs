// Comprueba geometrías realmente dibujadas en varios continentes y respaldo sin teselas.
export async function probarHidrografia({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI,registrar}) {
  await enviar("Emulation.setDeviceMetricsOverride",{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await enviar("Network.enable");
  await enviar("Page.navigate",{url:URL_UI});
  await esperarA(`typeof mapa!=="undefined" && mapa.isStyleLoaded() && typeof capasCtrl!=="undefined"`,30000,"mapa y capas");
  await evaluar(`window.canvasHidro=mapa.getCanvas();document.querySelector('[data-preajuste="agua"]').click();void 0`);
  const regiones = [
    ["amazonas",-60.02,-3.12,8], ["nilo",31.23,30.04,9],
    ["sena",2.35,48.85,11], ["mississippi",-90.07,29.95,10],
    ["asia",90.39,23.80,9], ["australia",151.2,-33.86,10],
    ["afluentes-suiza",7.79,46.94,13],
  ];
  const evidencia=[];
  for (const [nombre,lon,lat,zoom] of regiones) {
    await evaluar(`mapa.jumpTo({center:[${lon},${lat}],zoom:${zoom}});void 0`);
    await esperarA(`mapa.isSourceLoaded("hidrografia-detalle") && mapa.queryRenderedFeatures({layers:["rios-detalle","agua-detalle"]}).length>0`,30000,"agua visible en "+nombre);
    await esperarA(`mapa.getPaintProperty("rios","line-opacity").at(-1)===0`,10000,"transición al detalle");
    const valores=await evaluar(`(()=>{const f=mapa.queryRenderedFeatures({layers:["rios-detalle","agua-detalle"]});return {region:${JSON.stringify(nombre)},elementos:f.length,clases:[...new Set(f.map(x=>x.properties.class))],mismoMapa:mapa.getCanvas()===canvasHidro}})()`);
    evidencia.push(valores);
    comprobar("Hidrografía visible en "+nombre,valores.elementos>0 && valores.mismoMapa,JSON.stringify(valores));
    if (nombre === "afluentes-suiza") comprobar("Los afluentes pequeños aparecen al acercarse",valores.clases.includes("stream"),valores.clases.join(", "));
    if (["nilo","sena"].includes(nombre)) {await esperarA(`mapa.loaded()`,30000,"teselas listas para captura");await espera(350);await captura(nombre);}
  }
  await evaluar(`document.querySelector('[data-preajuste="fuego"]').click();void 0`);
  comprobar("Apagar ríos oculta también el detalle mundial",await evaluar(`mapa.getLayoutProperty("rios-detalle","visibility")==="none" && mapa.getLayoutProperty("agua-detalle","visibility")==="none"`));
  // Fallo del proveedor: el agua generalizada debe seguir disponible fuera de Colombia.
  await evaluar(`window.erroresHidroPrueba=[];mapa.on("error",e=>erroresHidroPrueba.push({claves:Object.keys(e),sourceId:e.sourceId,fuente:typeof e.source==="string"?e.source:e.source?.id,mensaje:e.error?.message}));void 0`);
  await enviar("Network.setBlockedURLs",{urls:["*tiles.openfreemap.org*"]});
  // Renovar TileJSON fuerza una consulta de red en el hilo principal; los workers pueden
  // conservar teselas aun con Network.setBlockedURLs aplicado solo a la página.
  await evaluar(`document.querySelector('[data-preajuste="agua"]').click();mapa.getSource("hidrografia-detalle").setUrl("https://tiles.openfreemap.org/planet?verificacion=sinred");mapa.jumpTo({center:[7.1,50.7],zoom:8});void 0`);
  await espera(2500);
  const recuperacion=await evaluar(`({opacidad:mapa.getPaintProperty("rios","line-opacity"),dibujados:mapa.queryRenderedFeatures({layers:["rios","lagos"]}).length,errores:erroresHidroPrueba})`);
  registrar("recuperacion",recuperacion);console.log("RECUPERACION",JSON.stringify(recuperacion));
  await esperarA(`mapa.getPaintProperty("rios","line-opacity").at(-1)>0 && mapa.queryRenderedFeatures({layers:["rios","lagos"]}).length>0`,30000,"recuperación al mover el mapa sin proveedor");
  comprobar("El respaldo se recupera si las teselas fallan al cambiar de zona",true);
  await enviar("Page.reload",{});
  await esperarA(`typeof mapa!=="undefined" && mapa.getLayer("rios") && typeof capasCtrl!=="undefined"`,30000,"mapa con proveedor bloqueado");
  await evaluar(`document.querySelector('[data-preajuste="agua"]').click();mapa.jumpTo({center:[31.23,30.04],zoom:7});void 0`);
  await esperarA(`mapa.isSourceLoaded("hidrografia") && mapa.queryRenderedFeatures({layers:["rios","lagos"]}).length>0`,30000,"respaldo mundial sin proveedor");
  comprobar("Sin teselas remotas sigue visible el Nilo",true);
  await captura("respaldo_sin_teselas");
  await enviar("Network.setBlockedURLs",{urls:[]});
  await enviar("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await espera(250);await captura("movil_agua");
  comprobar("Vista móvil sin desbordamiento",await evaluar(`document.documentElement.scrollWidth<=innerWidth`));
  comprobar("Sin excepciones de aplicación",errores.length===0,errores.slice(0,2).join(" | "));
  registrar("cobertura",evidencia);
}
