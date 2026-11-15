/* Localización del texto de presentación. No altera IDs, valores, geometría ni respuestas API.
 * Se conservan los mensajes originales por nodo para volver a español sin traducción inversa.
 * Los nodos dinámicos y etiquetas accesibles usan el mismo catálogo local. */
(function(raiz){
  "use strict";
  const catalogo=typeof module==="object" && module.exports?require("./traducciones.js"):raiz.HHN_TRADUCCIONES;
  const idiomas={es:"es-CO",en:"en-US",fr:"fr-FR"};
  const normalizar=s=>String(s).replace(/\s+/g," ").trim();
  const exactos=new Map(catalogo.textos.map(f=>[normalizar(f[0]),f]));
  for(const f of catalogo.fragmentos)if(!exactos.has(f[0]))exactos.set(f[0],f);
  const alias={"Zoom in":"Acercar","Zoom out":"Alejar","Close popup":"Cerrar ficha","Toggle attribution":"Mostrar créditos","Map":"Mapa"};
  for(const f of [["Acercar","Zoom in","Zoom avant"],["Alejar","Zoom out","Zoom arrière"],["Cerrar ficha","Close popup","Fermer la fiche"],["Mostrar créditos","Show credits","Afficher les crédits"]])exactos.set(f[0],f);
  const escapar=s=>s.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
  const fragmentos=[...catalogo.textos,...catalogo.fragmentos].sort((a,b)=>b[0].length-a[0].length);
  const porFragmento=new Map(fragmentos.map(f=>[f[0],f]));
  const patron=new RegExp("(^|[^\\p{L}\\p{N}_])("+fragmentos.map(f=>escapar(f[0])).join("|")+")(?=$|[^\\p{L}\\p{N}_])","gu");
  const meses=["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  const largos=["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
  function fecha(d,m,a,idioma,conAnio=true){return new Intl.DateTimeFormat(idiomas[idioma],{timeZone:"UTC",day:"numeric",month:"short",...(conAnio?{year:"numeric"}:{})}).format(new Date(Date.UTC(a,m,d)));}
  function traducir(texto,idioma="es"){
    if(!idiomas[idioma])idioma="es";
    const original=String(texto),n=normalizar(original),indice={es:0,en:1,fr:2}[idioma];
    const fila=exactos.get(alias[n]??n);
    if(fila)return (original.match(/^\s*/)?.[0]??"")+fila[indice]+(original.match(/\s*$/)?.[0]??"");
    if(idioma==="es" || !n)return original;
    let salida=original;
    salida=salida.replace(/\(del (.+?) al (.+?)\)/g,(_,a,b)=>idioma==="en"?`(from ${a} to ${b})`:`(du ${a} au ${b})`);
    // Los números de origen de la aplicación usan es-CO. No se tocan años sin separadores,
    // coordenadas de geometría, IDs, rutas, atributos numéricos ni columnas de los CSV.
    salida=salida.replace(/(?<![\p{L}\p{N}_])(-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+,\d+)(?![\p{L}\p{N}_])/gu,v=>{
      const decimal=v.includes(",")?v.split(",")[1].length:0;
      return new Intl.NumberFormat(idiomas[idioma],{maximumFractionDigits:decimal}).format(Number(v.replace(/\./g,"").replace(",",".")));
    });
    salida=salida.replace(/\b(\d{1,2}) (ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic) (\d{4})\b/g,(_,d,m,a)=>fecha(Number(d),meses.indexOf(m),Number(a),idioma));
    salida=salida.replace(/\b(\d{1,2}) (ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)(?![\p{L}.])/gu,(_,d,m)=>fecha(Number(d),meses.indexOf(m),2000,idioma,false));
    salida=salida.replace(/\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre) de (\d{4})/g,(_,m,a)=>new Intl.DateTimeFormat(idiomas[idioma],{timeZone:"UTC",month:"long",year:"numeric"}).format(new Date(Date.UTC(Number(a),largos.indexOf(m),1))));
    const mes=meses.indexOf(n);
    if(mes>=0)return new Intl.DateTimeFormat(idiomas[idioma],{month:"short",timeZone:"UTC"}).format(new Date(Date.UTC(2000,mes,1)));
    salida=salida.replace(patron,(_,inicio,frase)=>inicio+porFragmento.get(frase)[indice]);
    return salida;
  }
  if(typeof module==="object" && module.exports){module.exports={traducir,idiomas};return;}
  let actual="es";
  try{const q=new URLSearchParams(location.search).get("lang"),v=q||localStorage.getItem("hhn-idioma");if(idiomas[v])actual=v;}catch{/* almacenamiento opcional */}
  const textos=new WeakMap(),atributos=new WeakMap();
  const atributosVisibles=["aria-label","title","placeholder","alt","aria-description"];
  const omitido=n=>n.parentElement?.closest("script,style,noscript,code,pre,[data-no-traducir],q[lang='en']");
  function traducirNodo(n){
    if(omitido(n))return;
    let r=textos.get(n);
    if(!r || n.data!==r.mostrado)r={origen:n.data,mostrado:n.data};
    const t=traducir(r.origen,actual);r.mostrado=t;textos.set(n,r);
    if(n.data!==t)n.data=t;
  }
  function traducirAtributos(e){
    if(e.closest?.("[data-no-traducir]"))return;
    let regs=atributos.get(e);if(!regs){regs={};atributos.set(e,regs);}
    for(const nombre of atributosVisibles){
      if(!e.hasAttribute(nombre))continue;
      const valor=e.getAttribute(nombre);let r=regs[nombre];
      if(!r || valor!==r.mostrado)r={origen:valor,mostrado:valor};
      r.mostrado=traducir(r.origen,actual);regs[nombre]=r;
      if(valor!==r.mostrado)e.setAttribute(nombre,r.mostrado);
    }
  }
  function aplicar(root=document.body){
    if(root.nodeType===3){traducirNodo(root);return;}
    if(root.nodeType!==1)return;
    traducirAtributos(root);
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_ELEMENT|NodeFilter.SHOW_TEXT);
    let n;while((n=walker.nextNode())){if(n.nodeType===3)traducirNodo(n);else traducirAtributos(n);}
  }
  function cambiar(id){
    if(!idiomas[id])return;
    actual=id;document.documentElement.lang=id;
    try{localStorage.setItem("hhn-idioma",id);}catch{/* opcional */}
    const url=new URL(location.href);if(url.searchParams.has("lang")){url.searchParams.set("lang",id);history.replaceState(null,"",url);}
    const selector=document.getElementById("sel-idioma");if(selector)selector.value=id;
    aplicar();document.title=traducir("Harmonized Heat Neiva",id);enlazarDocumentos();
    document.dispatchEvent(new CustomEvent("idioma-cambiado",{detail:{idioma:id}}));
  }
  raiz.Idiomas={get actual(){return actual;},get locale(){return idiomas[actual];},traducir:(s,id=actual)=>traducir(s,id),cambiar,aplicar};
  document.documentElement.lang=actual;
  const pendientes=new Set();let marco=null;
  const observer=new MutationObserver(registros=>{
    for(const r of registros){
      if(r.type==="characterData")pendientes.add(r.target);
      else if(r.type==="attributes")pendientes.add(r.target);
      else for(const n of r.addedNodes)pendientes.add(n);
    }
    if(marco===null)marco=requestAnimationFrame(()=>{marco=null;for(const n of pendientes)if(n.isConnected)aplicar(n);pendientes.clear();});
  });
  observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:atributosVisibles});
  function enlazarDocumentos(){
    for(const ruta of ["metodologia","limitaciones"])for(const a of document.querySelectorAll(`a[data-documento='${ruta}'],a[href^='/${ruta}']`)){
      a.dataset.documento=ruta;a.href=raiz.HHN_ESTATICO?raiz.HHN_ESTATICO.raiz+`textos/${ruta}.${actual}.md`:`/${ruta}?idioma=${actual}`;
    }
    if(raiz.HHN_ESTATICO)for(const a of document.querySelectorAll("a[href='/procedencia']"))a.href=raiz.HHN_ESTATICO.raiz+"api/procedencia.json";
  }
  function iniciar(){const s=document.getElementById("sel-idioma");s.value=actual;s.addEventListener("change",()=>cambiar(s.value));aplicar();enlazarDocumentos();}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",iniciar,{once:true});else iniciar();
})(typeof window!=="undefined"?window:globalThis);
