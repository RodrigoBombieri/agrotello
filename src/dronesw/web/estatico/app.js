// La pantalla de AgroTello: dibujar un lote, planificar su recorrido y ver su NDVI.
//
// Todo el cálculo lo hace el servidor; acá solo se dibuja. La única cuenta que vive en el
// navegador es la paleta de colores, y está acá a propósito: el servidor manda los valores
// crudos del NDVI, así la escala se puede mover sin volver a pedirle nada.

const MAPA_SATELITAL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const CENTRO = [-32.6959, -58.8953];

// Los once anclajes de RdYlGn, la misma paleta que usa la versión de línea de comandos.
const PALETA = [
  [165, 0, 38], [214, 47, 38], [244, 109, 67], [252, 172, 96], [254, 224, 139],
  [254, 254, 189], [217, 239, 139], [164, 216, 105], [102, 189, 99], [25, 151, 79],
  [0, 104, 55],
];
const OPACIDAD = 217; // sobre 255: deja ver la foto satelital por debajo

const $ = (id) => document.getElementById(id);
const CAMPOS_VUELO = ["altura_m", "separacion_m", "velocidad_ms", "angulo_grados", "margen_m"];

let lote = null;        // el polígono dibujado
let recorrido = null;   // la línea del zigzag
let capaNdvi = null;    // la imagen de NDVI apoyada sobre el mapa
let analisis = null;    // la última respuesta de /api/ndvi

// --- Mapa -------------------------------------------------------------------

const mapa = L.map("mapa").setView(CENTRO, 16);
L.tileLayer(MAPA_SATELITAL, { maxZoom: 19, attribution: "Esri" }).addTo(mapa);
mapa.pm.setGlobalOptions({ pathOptions: { color: "#4aa564", weight: 2, fillOpacity: 0.08 } });

// --- Color ------------------------------------------------------------------

function color(t) {
  const x = Math.max(0, Math.min(1, t)) * (PALETA.length - 1);
  const i = Math.floor(x);
  const f = x - i;
  const a = PALETA[i];
  const b = PALETA[Math.min(i + 1, PALETA.length - 1)];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

// --- Hablar con el servidor -------------------------------------------------

function mensajeDeError(datos) {
  const detalle = datos && datos.detail;
  if (typeof detalle === "string") return detalle;
  // Cuando la validación falla, FastAPI devuelve una lista con el campo y el motivo.
  if (Array.isArray(detalle)) {
    return detalle.map((e) => `${e.loc.slice(1).join(".")}: ${e.msg}`).join(" · ");
  }
  return "No se pudo completar la operación";
}

async function pedir(ruta, cuerpo) {
  const opciones = cuerpo
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) }
    : {};
  const respuesta = await fetch(ruta, opciones);
  const datos = await respuesta.json();
  if (!respuesta.ok) throw new Error(mensajeDeError(datos));
  return datos;
}

function avisar(texto) {
  $("aviso").textContent = texto;
  $("aviso").classList.toggle("oculto", !texto);
}

async function intentar(boton, accion) {
  const etiqueta = boton.textContent;
  boton.disabled = true;
  boton.textContent = "…";
  avisar("");
  try {
    await accion();
  } catch (error) {
    avisar(error.message);
  } finally {
    boton.disabled = false;
    boton.textContent = etiqueta;
  }
}

// --- El lote ----------------------------------------------------------------

function vertices() {
  if (!lote) return null;
  return lote.getLatLngs()[0].map((p) => [p.lat, p.lng]);
}

function cuerpoLote() {
  const vuelo = {};
  CAMPOS_VUELO.forEach((c) => (vuelo[c] = Number($(c).value)));
  return { nombre: $("nombre").value || "lote", poligono: vertices(), vuelo };
}

function ponerLote(capa) {
  if (lote) mapa.removeLayer(lote);
  lote = capa;
  // Queda editable: se pueden arrastrar los vértices para corregir el contorno, y los
  // puntos intermedios para agregar uno nuevo. Dibujar a ojo sobre una foto nunca sale
  // bien a la primera.
  lote.pm.enable({ allowSelfIntersection: false });
  lote.on("pm:edit", limpiarDerivados);
  limpiarDerivados();
}

function limpiarDerivados() {
  // El recorrido y el NDVI dependen del contorno: si el contorno cambia, dejan de valer.
  if (recorrido) { mapa.removeLayer(recorrido); recorrido = null; }
  if (capaNdvi) { mapa.removeLayer(capaNdvi); capaNdvi = null; }
  analisis = null;
  $("plan").classList.add("oculto");
  $("analisis").classList.add("oculto");
  $("escenas").disabled = true;
  $("analizar").disabled = true;
}

mapa.on("pm:create", (e) => ponerLote(e.layer));

$("dibujar").onclick = () => mapa.pm.enableDraw("Polygon", { finishOn: "dblclick" });

$("borrar").onclick = () => {
  if (lote) mapa.removeLayer(lote);
  lote = null;
  limpiarDerivados();
  $("lotes").value = "";
};

// --- Lotes guardados --------------------------------------------------------

async function cargarLista() {
  const lotes = await pedir("/api/lotes");
  const select = $("lotes");
  select.innerHTML = '<option value="">— nuevo —</option>';
  lotes.forEach((l) => {
    const opcion = document.createElement("option");
    opcion.value = l.archivo;
    opcion.textContent = `${l.nombre} (${l.archivo})`;
    select.appendChild(opcion);
  });
}

$("lotes").onchange = async (e) => {
  if (!e.target.value) return;
  const datos = await pedir(`/api/lotes/${e.target.value}`);
  ponerLote(L.polygon(datos.poligono, { color: "#4aa564", weight: 2, fillOpacity: 0.08 }).addTo(mapa));
  CAMPOS_VUELO.forEach((c) => ($(c).value = datos.vuelo[c]));
  $("nombre").value = e.target.value;
  mapa.fitBounds(lote.getBounds(), { padding: [40, 40] });
};

$("guardar").onclick = () =>
  intentar($("guardar"), async () => {
    if (!lote) throw new Error("Dibujá o elegí un lote primero");
    const guardado = await pedir("/api/lotes", cuerpoLote());
    await cargarLista();
    $("lotes").value = guardado.archivo;
    avisar(`Guardado como ${guardado.archivo}.yaml`);
  });

// --- Planificar -------------------------------------------------------------

$("planificar").onclick = () =>
  intentar($("planificar"), async () => {
    if (!lote) throw new Error("Dibujá o elegí un lote primero");
    const plan = await pedir("/api/plan", cuerpoLote());

    if (recorrido) mapa.removeLayer(recorrido);
    recorrido = L.polyline(
      plan.waypoints.map((w) => [w.lat, w.lon]),
      { color: "#ffd166", weight: 2, opacity: 0.9 }
    ).addTo(mapa);

    const minutos = Math.floor(plan.duracion_s / 60);
    const segundos = plan.duracion_s % 60;
    $("plan").innerHTML =
      dato("Waypoints", plan.cantidad) +
      dato("Recorrido", `${(plan.distancia_m / 1000).toFixed(2)} km`) +
      dato("Duración", `${minutos} min ${String(segundos).padStart(2, "0")} s`);
    $("plan").classList.remove("oculto");
  });

// --- Satélite ---------------------------------------------------------------

$("buscar").onclick = () =>
  intentar($("buscar"), async () => {
    if (!lote) throw new Error("Dibujá o elegí un lote primero");
    const escenas = await pedir("/api/escenas", {
      lote: cuerpoLote(),
      desde: $("desde").value,
      hasta: $("hasta").value,
    });
    const select = $("escenas");
    select.innerHTML = "";
    if (!escenas.length) {
      select.innerHTML = '<option value="">— no hay pasadas —</option>';
      return;
    }
    escenas.reverse().forEach((e) => {
      const opcion = document.createElement("option");
      opcion.value = e.fecha;
      opcion.textContent = `${e.fecha} — ${e.nube_pct}% de nube`;
      select.appendChild(opcion);
    });
    select.disabled = false;
    $("analizar").disabled = false;
  });

$("analizar").onclick = () =>
  intentar($("analizar"), async () => {
    analisis = await pedir("/api/ndvi", { lote: cuerpoLote(), fecha: $("escenas").value });
    mostrarAnalisis();
    repintar();
  });

// --- Dibujar el NDVI --------------------------------------------------------

function lienzoDeNdvi(valores, desde, hasta) {
  const alto = valores.length;
  const ancho = valores[0].length;
  const lienzo = document.createElement("canvas");
  lienzo.width = ancho;
  lienzo.height = alto;

  const contexto = lienzo.getContext("2d");
  const imagen = contexto.createImageData(ancho, alto);
  for (let fila = 0; fila < alto; fila++) {
    for (let columna = 0; columna < ancho; columna++) {
      const valor = valores[fila][columna];
      const i = (fila * ancho + columna) * 4;
      if (valor === null) continue; // fuera del lote o tapado: queda transparente
      const [r, g, b] = color((valor - desde) / (hasta - desde));
      imagen.data[i] = r;
      imagen.data[i + 1] = g;
      imagen.data[i + 2] = b;
      imagen.data[i + 3] = OPACIDAD;
    }
  }
  contexto.putImageData(imagen, 0, 0);
  return lienzo.toDataURL();
}

function repintar() {
  if (!analisis) return;

  // Los dos controles son independientes y se pueden cruzar. Si eso pasara, el rango
  // quedaría invertido o vacío y los colores saldrían al revés o todos iguales.
  const a = Number($("desde_escala").value);
  const b = Number($("hasta_escala").value);
  const desde = Math.min(a, b);
  const hasta = Math.max(a, b) > desde ? Math.max(a, b) : desde + 0.001;

  $("escala_desde").textContent = desde.toFixed(2);
  $("escala_hasta").textContent = hasta.toFixed(2);

  const bordes = analisis.bordes;
  const limites = [[bordes.sur, bordes.oeste], [bordes.norte, bordes.este]];
  if (capaNdvi) mapa.removeLayer(capaNdvi);
  capaNdvi = L.imageOverlay(lienzoDeNdvi(analisis.valores, desde, hasta), limites, {
    className: "ndvi-capa",
  }).addTo(mapa);
}

// --- Los resultados en el panel ---------------------------------------------

const dato = (etiqueta, valor) => `<div class="dato"><span>${etiqueta}</span><b>${valor}</b></div>`;

function mostrarAnalisis() {
  const r = analisis.resumen;
  const colorDeZona = { flojo: "#d73027", normal: "#fee08b", vigoroso: "#1a9850" };

  const zonas = analisis.zonas
    .map(
      (z) =>
        `<div class="zona"><i style="background:${colorDeZona[z.nombre]}"></i>` +
        `<span>${z.nombre}</span><b>${z.hectareas.toFixed(2)} ha · ${z.porcentaje}%</b></div>`
    )
    .join("");

  $("analisis").innerHTML =
    dato("Fecha", analisis.fecha) +
    dato("NDVI medio", r.medio.toFixed(3)) +
    dato("Superficie", `${analisis.hectareas.toFixed(2)} ha`) +
    dato("Cobertura útil", `${r.cobertura_pct}%`) +
    zonas +
    `<div class="escala">
       <div class="barra"></div>
       <div class="extremos"><span id="escala_desde"></span><span id="escala_hasta"></span></div>
       <input type="range" id="desde_escala" min="${r.minimo}" max="${r.maximo}" step="0.005" value="${r.p2}">
       <input type="range" id="hasta_escala" min="${r.minimo}" max="${r.maximo}" step="0.005" value="${r.p98}">
     </div>` +
    (analisis.uniforme
      ? '<p class="dato" style="color:#d9822b">El lote varía muy poco: las zonas separan ruido.</p>'
      : "") +
    (r.cobertura_pct < 80
      ? `<p class="dato" style="color:#d9822b">Solo se vio el ${r.cobertura_pct}% del lote.</p>`
      : "");

  $("analisis").classList.remove("oculto");
  $("desde_escala").oninput = repintar;
  $("hasta_escala").oninput = repintar;
}

// --- Leer un píxel apuntándolo ----------------------------------------------

mapa.on("mousemove", (e) => {
  const lectura = $("lectura");
  if (!analisis) return lectura.classList.add("oculto");

  const b = analisis.bordes;
  const alto = analisis.valores.length;
  const ancho = analisis.valores[0].length;
  const fila = Math.floor(((b.norte - e.latlng.lat) / (b.norte - b.sur)) * alto);
  const columna = Math.floor(((e.latlng.lng - b.oeste) / (b.este - b.oeste)) * ancho);

  const dentro = fila >= 0 && fila < alto && columna >= 0 && columna < ancho;
  const valor = dentro ? analisis.valores[fila][columna] : null;
  if (valor === null) return lectura.classList.add("oculto");

  lectura.textContent = `NDVI ${valor.toFixed(3)}`;
  lectura.style.left = `${e.originalEvent.clientX + 14}px`;
  lectura.style.top = `${e.originalEvent.clientY + 14}px`;
  lectura.classList.remove("oculto");
});

mapa.on("mouseout", () => $("lectura").classList.add("oculto"));

// --- Arranque ---------------------------------------------------------------

const hoy = new Date();
const haceTresMeses = new Date(hoy.getTime() - 90 * 86400000);
$("hasta").value = hoy.toISOString().slice(0, 10);
$("desde").value = haceTresMeses.toISOString().slice(0, 10);

cargarLista().catch((error) => avisar(error.message));

// --- Volar ------------------------------------------------------------------
//
// El vuelo corre en el servidor; acá solo se ordena, se mira y se corta. El estado llega
// por WebSocket dos veces por segundo, que es suficiente para ver moverse un dron a 8 m/s.

let seguimiento = null;  // el WebSocket, abierto solo mientras hay vuelo
let marcador = null;     // dónde está el dron ahora
let rastro = null;       // por dónde pasó de verdad, que no es lo mismo que el plan

$("volar").onclick = () =>
  intentar($("volar"), async () => {
    if (!lote) throw new Error("Dibujá o elegí un lote primero");

    // Se replanifica para que la confirmación muestre lo que se va a volar de verdad, y no
    // lo que quedó en pantalla de un plan anterior con otros parámetros.
    const plan = await pedir("/api/plan", cuerpoLote());
    const minutos = Math.floor(plan.duracion_s / 60);

    $("confirmacion").innerHTML =
      "<p>Vas a armar los motores y despegar:</p>" +
      dato("Waypoints", plan.cantidad) +
      dato("Altura", `${$("altura_m").value} m`) +
      dato("Recorrido", `${(plan.distancia_m / 1000).toFixed(2)} km`) +
      dato("Duración", `~${minutos} min`) +
      dato("Conexión", $("direccion").value) +
      '<div class="confirmar">' +
      '<button id="confirmar" class="peligro">Confirmar despegue</button>' +
      '<button id="cancelar" class="secundario">Cancelar</button></div>';
    $("confirmacion").classList.remove("oculto");

    $("cancelar").onclick = () => $("confirmacion").classList.add("oculto");
    $("confirmar").onclick = () =>
      intentar($("confirmar"), async () => {
        await pedir("/api/vuelo", {
          lote: cuerpoLote(),
          direccion: $("direccion").value,
        });
        $("confirmacion").classList.add("oculto");
        abrirSeguimiento();
      });
  });

$("abortar").onclick = () => intentar($("abortar"), () => pedir("/api/vuelo/abortar", {}));

function abrirSeguimiento() {
  if (seguimiento) seguimiento.close();
  if (rastro) { mapa.removeLayer(rastro); rastro = null; }

  seguimiento = new WebSocket(`ws://${location.host}/api/vuelo/estado`);
  seguimiento.onmessage = (mensaje) => mostrarVuelo(JSON.parse(mensaje.data));
  seguimiento.onerror = () => avisar("Se cortó la conexión con el servidor");
}

function mostrarVuelo(estado) {
  const volando = ["preparando", "volando", "volviendo"].includes(estado.fase);

  $("telemetria").innerHTML =
    dato("Estado", estado.mensaje || estado.fase) +
    (estado.waypoints ? dato("Waypoint", `${estado.waypoint} / ${estado.waypoints}`) : "") +
    (estado.bateria_pct !== null ? dato("Batería", `${estado.bateria_pct} %`) : "") +
    (estado.posicion ? dato("Altura", `${estado.posicion.altura_m} m`) : "");
  $("telemetria").classList.remove("oculto");
  $("abortar").classList.toggle("oculto", !volando);
  $("volar").disabled = volando;

  if (estado.posicion) {
    const donde = [estado.posicion.lat, estado.posicion.lon];
    if (!marcador) {
      marcador = L.circleMarker(donde, {
        radius: 7, color: "#fff", weight: 2, fillColor: "#4ea3ff", fillOpacity: 1,
      }).addTo(mapa);
    } else {
      marcador.setLatLng(donde);
    }
  }

  // El rastro va en otro color que el plan: lo interesante es ver dónde se separan.
  if (estado.recorrido.length > 1) {
    if (rastro) mapa.removeLayer(rastro);
    rastro = L.polyline(estado.recorrido, { color: "#4ea3ff", weight: 3, opacity: 0.8 }).addTo(mapa);
  }

  if (estado.fase === "terminado" || estado.fase === "error") {
    if (seguimiento) { seguimiento.close(); seguimiento = null; }
    if (estado.fase === "error") avisar(estado.mensaje);
  }
}