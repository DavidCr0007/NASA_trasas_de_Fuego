// Regresión del país Colombia frente al municipio homónimo de Huila.
export async function probarConfirmacionLugar({enviar,evaluar,esperarA,captura,comprobar,espera,errores,URL_UI}) {
  await enviar("Emulation.setDeviceMetricsOverride",{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await enviar("Page.navigate",{url:URL_UI});
  await esperarA(`typeof mapa!=="undefined" && municipios.length===37 && paisesBusqueda.length>200`,30000,"países y municipios locales");
  await esperarA(`!document.getElementById("mapa-esqueleto").classList.contains("inicial")`,45000,"primer dibujo del planeta");
  await evaluar(`window.canvasConfirmacion=mapa.getCanvas();window.vistaConfirmacion=JSON.stringify({centro:mapa.getCenter(),zoom:mapa.getZoom(),zona:zonaSel?.zona.properties.shapeName});void 0`);
  const consultar = q => evaluar(`document.getElementById("consulta-lugar").value=${JSON.stringify(q)};document.getElementById("consulta-lugar").dispatchEvent(new Event("input"));document.getElementById("buscar-lugar").requestSubmit();void 0`);
  const sinMover = () => evaluar(`vistaConfirmacion===JSON.stringify({centro:mapa.getCenter(),zoom:mapa.getZoom(),zona:zonaSel?.zona.properties.shapeName}) && mapa.getCanvas()===canvasConfirmacion`);
  await consultar("Colombia");
  const resultados=await evaluar(`[...document.querySelectorAll("#lista-lugares button[data-nivel]")].map(b=>({nombre:b.querySelector("strong").textContent,nivel:b.dataset.nivel,contexto:b.querySelector("small").textContent}))`);
  comprobar("Colombia muestra primero el país y conserva el municipio homónimo",resultados[0]?.nivel==="pais" && resultados[1]?.nivel==="municipio" && resultados[1]?.contexto.includes("Huila"),JSON.stringify(resultados));
  comprobar("Buscar no mueve ni selecciona el mapa",await sinMover());
  await captura("01_colombia_opciones");
  await evaluar(`document.querySelector('#lista-lugares button[data-nivel="pais"]').click()`);
  comprobar("Revisar el país exige confirmación y conserva el mapa",await sinMover() && await evaluar(`!document.getElementById("confirmacion-lugar").hidden && document.getElementById("confirmacion-lugar-tipo").textContent==="País" && document.activeElement.id==="confirmar-lugar"`));
  await captura("02_confirmar_pais");
  await evaluar(`document.getElementById("volver-lugares").click()`);
  comprobar("Volver a resultados conserva la ubicación anterior",await sinMover() && await evaluar(`!document.getElementById("lista-lugares").hidden`));
  await evaluar(`document.querySelector('#lista-lugares button[data-nivel="pais"]').click();document.getElementById("confirmar-lugar").click()`);
  await esperarA(`zonaSel?.nivel==="pais" && zonaSel.zona.properties.shapeName==="Colombia" && !mapa.isMoving()`,15000,"país confirmado");
  comprobar("Confirmar Colombia encuadra el país completo",await evaluar(`mapa.getZoom()<6 && document.getElementById("zona-nivel").textContent==="País" && zonaSel.zona.properties.bbox[1]<0 && zonaSel.zona.properties.bbox[3]>10 && mapa.getCanvas()===canvasConfirmacion`));
  await consultar("Colombia, Huila");
  comprobar("El contexto Huila limita la opción al municipio",await evaluar(`document.querySelectorAll("#lista-lugares button[data-nivel]").length===1 && document.querySelector("#lista-lugares button[data-nivel]").dataset.nivel==="municipio"`));
  await evaluar(`document.querySelector('#lista-lugares button[data-nivel="municipio"]').click();document.getElementById("confirmar-lugar").click()`);
  await esperarA(`zonaSel?.nivel==="municipio" && zonaSel.zona.properties.shapeName==="Colombia" && !mapa.isMoving()`,15000,"municipio confirmado");
  comprobar("Confirmar el municipio mantiene el contexto Huila",await evaluar(`zonaSel.contexto.properties.shapeName==="Huila" && document.getElementById("zona-nivel").textContent.includes("Municipio")`));
  await evaluar(`vistaConfirmacion=JSON.stringify({centro:mapa.getCenter(),zoom:mapa.getZoom(),zona:zonaSel?.zona.properties.shapeName});void 0`);
  await consultar("Neiva");
  comprobar("Una coincidencia única tampoco se abre automáticamente",await sinMover() && await evaluar(`document.querySelector('#lista-lugares button[data-nivel="municipio"]').textContent.includes("Neiva")`));
  await evaluar(`document.querySelector('#lista-lugares button[data-nivel="municipio"]').click();document.getElementById("consulta-lugar").value="consulta nueva";document.getElementById("consulta-lugar").dispatchEvent(new Event("input"));document.getElementById("confirmar-lugar").click()`);
  comprobar("Editar la consulta invalida la confirmación pendiente",await sinMover());
  await consultar("Colombia");await evaluar(`document.querySelector('#lista-lugares button[data-nivel="pais"]').click()`);
  await enviar("Input.dispatchKeyEvent",{type:"keyDown",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
  await enviar("Input.dispatchKeyEvent",{type:"keyUp",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
  comprobar("Escape cancela y devuelve el foco al buscador",await sinMover() && await evaluar(`document.getElementById("resultados-lugares").hidden && document.activeElement.id==="consulta-lugar"`));
  // Proveedor controlado para comprobar el mismo flujo de confirmación remota, sin depender de su orden.
  await evaluar(`window.fetchConfirmacion=fetch.bind(window);window.fetch=(url,op)=>String(url).startsWith("/buscar-lugares?")?Promise.resolve(new Response(JSON.stringify({resultados:[{nombre:"Chapinero",tipo:"Barrio",descripcion:"Chapinero, Bogotá, Colombia",lon:-74.06,lat:4.65,bbox:[-74.09,4.6,-74.01,4.7]}]}),{status:200})):fetchConfirmacion(url,op);void 0`);
  await consultar("Chapinero Bogotá");
  await esperarA(`document.querySelector("#lista-lugares strong")?.textContent==="Chapinero"`,5000,"resultado remoto");
  await evaluar(`document.querySelector("#lista-lugares button").click()`);
  comprobar("Los resultados remotos también requieren confirmar",await sinMover() && await evaluar(`document.getElementById("confirmacion-lugar-contexto").textContent.includes("Bogotá")`));
  await evaluar(`document.getElementById("confirmar-lugar").click()`);
  await esperarA(`document.querySelector(".analizar-lugar") && !mapa.isMoving()`,15000,"barrio confirmado");
  comprobar("Confirmar un barrio centra su ubicación",await evaluar(`Math.abs(mapa.getCenter().lng+74.05)<0.1 && mapa.getCanvas()===canvasConfirmacion`));
  for (const [idioma,texto] of [["en","Confirm place"],["fr","Confirmer ce lieu"]]) {
    await evaluar(`Idiomas.cambiar(${JSON.stringify(idioma)})`);await consultar("Colombia");
    await evaluar(`document.querySelector('#lista-lugares button[data-nivel="pais"]').click()`);await espera(100);
    comprobar("Confirmación traducida: "+idioma,await evaluar(`document.getElementById("confirmar-lugar").textContent===${JSON.stringify(texto)}`));
  }
  await enviar("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await espera(200);await captura("03_confirmacion_movil_fr");
  comprobar("Confirmación móvil sin desbordamiento",await evaluar(`document.documentElement.scrollWidth<=innerWidth && document.getElementById("confirmar-lugar").getBoundingClientRect().right<=innerWidth`));
  comprobar("Sin excepciones de aplicación",errores.length===0,errores.slice(0,2).join(" | "));
}
