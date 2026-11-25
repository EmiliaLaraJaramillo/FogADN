/* Dashboard del Master. Todo el estado llega por WebSocket (/ws/dashboard); las acciones usan la API HTTP.
 * Los textos que vienen de los celulares se insertan con textContent (nunca como HTML). */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var estadoActual = null, archivoElegido = null, archivosLista = [], mapaPrevio = '';
  var tarjetas = {};

  // ---------- formato (coma decimal, espacio como separador de miles) ----------
  function num(n, d) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return Number(n).toLocaleString('fr-FR', { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 }).replace(/[  ]/g, ' ');
  }
  function tam(bytes) {
    if (bytes >= 1073741824) return num(bytes / 1073741824, 2) + ' GB';
    if (bytes >= 1048576) return num(bytes / 1048576, 1) + ' MB';
    return num(bytes / 1024, 0) + ' KB';
  }
  function dur(s) {
    s = Math.max(0, Math.round(s));
    var m = Math.floor(s / 60), r = s % 60;
    return m ? m + ' min ' + (r < 10 ? '0' : '') + r + ' s' : r + ' s';
  }
  function hora(t) { return new Date(t * 1000).toLocaleTimeString('es', { hour12: false }); }
  function fechaHora(t) { return t ? new Date(t * 1000).toLocaleString('es', { hour12: false }) : '—'; }
  function fijar(id, texto) { var e = $(id); if (e.textContent !== texto) e.textContent = texto; }
  function cambiar(e, texto) {          // actualiza y destella el número cuando cambia (conteo en vivo)
    if (e.textContent === texto) return;
    e.textContent = texto; e.classList.remove('tick'); void e.offsetWidth; e.classList.add('tick');
  }
  function mensaje(id, texto, clase) { var e = $(id); e.textContent = texto || ''; e.className = 'msg' + (clase ? ' ' + clase : ''); }

  // ---------- reloj ----------
  function reloj() {
    var d = new Date();
    fijar('reloj', d.toLocaleDateString('es', { weekday: 'short', day: 'numeric', month: 'short' }) + ' · ' +
                   d.toLocaleTimeString('es', { hour12: false }));
  }
  reloj(); setInterval(reloj, 1000);

  // ---------- WebSocket ----------
  function conectar() {
    var ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/dashboard');
    ws.onmessage = function (e) { var m = JSON.parse(e.data); if (m.type === 'state') pintar(m); };
    ws.onclose = function () {
      fijar('p-estado-d', 'Sin conexión con el Master. Reintentando…');
      setTimeout(conectar, 2000);
    };
  }

  // ---------- pintar ----------
  function pintar(s) {
    var antes = estadoActual && estadoActual.sesion.estado;
    estadoActual = s;
    var se = s.sesion, m = s.master;
    fijar('p-host', m.nombre);
    fijar('p-red', m.ip + ':' + m.puerto);
    fijar('p-workers', String(s.conectados));
    fijar('p-workers-d', s.conectados === 0 ? 'Ningún celular' : (s.conectados === 1 ? '1 celular' : s.conectados + ' celulares'));
    fijar('c-n', String(s.conectados)); fijar('c-n2', String(s.conectados));

    var punto = '<i class="punto' + (se.estado === 'en_curso' ? ' proc' : '') + '"></i>';
    var txt = { sin_sesion: ['Listo', 'Sin procesamiento'], en_curso: ['Procesando', s.conectados ? 'Repartiendo bloques' : 'Esperando celulares'],
                completada: ['Completado', 'Procesamiento terminado'], cancelada: ['Cancelado', 'Procesamiento cancelado'] }[se.estado];
    var pe = $('p-estado');
    if (pe.dataset.v !== se.estado) { pe.innerHTML = punto + txt[0]; pe.dataset.v = se.estado; }
    fijar('p-estado-d', txt[1]);

    pintarWorkers(s);
    pintarProceso(se);
    pintarResultados(se);
    pintarEventos(s.eventos);

    var enCurso = se.estado === 'en_curso';
    $('btn-cancelar').hidden = !enCurso;
    $('btn-iniciar').disabled = enCurso || !archivoElegido;
    $('btn-iniciar').textContent = enCurso ? 'Procesando…' : 'Iniciar procesamiento';
    if (antes === 'en_curso' && !enCurso) { cargarArchivos(); setTimeout(cargarHistorial, 400); }
  }

  // ---------- workers ----------
  var CAMPOS = [['dispositivo', 'Dispositivo'], ['navegador', 'Navegador'], ['recursos', 'Núcleos · memoria'],
                ['bloques', 'Bloques procesados'], ['tiempos', 'Proceso · descarga'], ['actual', 'Tarea actual'],
                ['ultima', 'Última comunicación']];

  function crearTarjeta(w) {
    var art = document.createElement('article');
    art.className = 'w';
    var cab = document.createElement('div'); cab.className = 'w-cab';
    var id = document.createElement('span'); id.className = 'w-id'; id.textContent = w.id;
    var pas = document.createElement('span'); pas.className = 'pastilla'; pas.dataset.k = 'estado';
    cab.appendChild(id); cab.appendChild(pas); art.appendChild(cab);
    var pr = document.createElement('div'); pr.className = 'progreso'; var ba = document.createElement('div'); ba.dataset.k = 'barra';
    pr.appendChild(ba); art.appendChild(pr);
    var dl = document.createElement('dl');
    CAMPOS.forEach(function (c) {
      var dt = document.createElement('dt'); dt.textContent = c[1];
      var dd = document.createElement('dd'); dd.dataset.k = c[0];
      dl.appendChild(dt); dl.appendChild(dd);
    });
    art.appendChild(dl);
    return art;
  }

  function dato(art, k, valor) {
    var e = art.querySelector('[data-k="' + k + '"]');
    var t = String(valor);
    if (e.textContent !== t) e.textContent = t;
    e.classList.toggle('nd', t === 'No disponible');
  }

  var ROT = { disponible: 'Disponible', procesando: 'Procesando', completado: 'Completado', desconectado: 'Desconectado', error: 'Error' };

  function pintarWorkers(s) {
    var cont = $('workers'), vistos = {};
    s.workers.forEach(function (w) {
      vistos[w.id] = true;
      var art = tarjetas[w.id];
      if (!art) { art = tarjetas[w.id] = crearTarjeta(w); cont.appendChild(art); }
      art.classList.toggle('fuera', w.estado === 'desconectado');
      var p = art.querySelector('[data-k="estado"]');
      p.textContent = ROT[w.estado] || w.estado;
      p.className = 'pastilla ' + w.estado;
      art.querySelector('[data-k="barra"]').style.width = (w.estado === 'procesando' ? w.progreso : 0) + '%';
      var nd = 'No disponible';
      dato(art, 'dispositivo', (w.modelo === nd ? 'Modelo ' + nd.toLowerCase() : w.modelo) + ' · ' + w.plataforma);
      dato(art, 'navegador', w.navegador);
      dato(art, 'recursos', (typeof w.nucleos === 'number' ? w.nucleos + ' núcleos' : 'Núcleos ' + nd.toLowerCase()) + ' · ' +
                            (typeof w.memoria_gb === 'number' ? '≈ ' + num(w.memoria_gb, 0) + ' GB' : 'memoria ' + nd.toLowerCase()));
      dato(art, 'bloques', num(w.bloques_procesados) + ' · ' + tam(w.bytes_procesados));
      dato(art, 'tiempos', num(w.t_proceso_ms / 1000, 1) + ' s · ' + num(w.t_transfer_ms / 1000, 1) + ' s');
      var idx = w.tarea_actual ? parseInt(w.tarea_actual.split('-').pop(), 10) + 1 : null;
      dato(art, 'actual', idx ? 'Bloque ' + num(idx) : '—');
      var hace = Math.max(0, s.ahora - w.ultima_comunicacion);
      dato(art, 'ultima', w.estado === 'desconectado' ? 'Hace ' + dur(hace) : (hace < 2 ? 'Ahora' : 'Hace ' + Math.round(hace) + ' s'));
    });
    Object.keys(tarjetas).forEach(function (id) {
      if (!vistos[id]) { tarjetas[id].remove(); delete tarjetas[id]; }
    });
    $('sin-workers').hidden = s.workers.length > 0;
  }

  // ---------- procesamiento ----------
  function pintarProceso(se) {
    var hay = !!se.archivo;
    fijar('e-archivo', hay ? se.archivo : 'Sin archivo');
    fijar('e-pct', hay ? num(se.progreso, 1) + ' %' : '0 %');
    $('e-barra').style.width = (hay ? se.progreso : 0) + '%';
    fijar('e-tam', hay ? tam(se.bytes) : '—');
    fijar('e-bloques', hay ? num(se.bloques) + ' de ' + tam(se.tamano_bloque) : '—');
    fijar('e-part', hay ? String(se.workers_participantes) : '—');
    fijar('e-tiempo', hay ? dur(se.transcurrido_s) : '—');
    fijar('e-vel', hay ? num(se.mb_s, 1) + ' MB/s' : '—');
    fijar('e-tt', hay ? num(se.t_transfer_s, 1) + ' s / ' + num(se.t_proceso_s, 1) + ' s' : '—');
    fijar('e-p', hay ? num(se.pendientes) : '0'); fijar('e-a', hay ? num(se.asignados) : '0'); fijar('e-c', hay ? num(se.completados) : '0');
    var mapa = hay ? se.mapa : '';
    var cont = $('mapa');
    if (mapa.length !== mapaPrevio.length) {
      cont.textContent = '';
      for (var i = 0; i < mapa.length; i++) { var c = document.createElement('i'); c.className = mapa[i]; cont.appendChild(c); }
    } else {
      for (var j = 0; j < mapa.length; j++) if (mapa[j] !== mapaPrevio[j]) cont.children[j].className = mapa[j];
    }
    mapaPrevio = mapa;
  }

  function pintarEventos(ev) {
    var ul = $('eventos'), html = ev.slice().reverse().slice(0, 8);
    var firma = html.map(function (e) { return e.t + e.texto; }).join('|');
    if (ul.dataset.f === firma) return;
    ul.dataset.f = firma; ul.textContent = '';
    if (!html.length) { var v = document.createElement('li'); v.textContent = 'Sin eventos todavía.'; ul.appendChild(v); return; }
    html.forEach(function (e) {
      var li = document.createElement('li'), t = document.createElement('time'), x = document.createElement('span');
      t.textContent = hora(e.t); x.textContent = e.texto; li.appendChild(t); li.appendChild(x); ul.appendChild(li);
    });
  }

  // ---------- resultados ----------
  var NOMBRE_ESTADO = { en_curso: 'En curso (parcial)', completada: 'Completada', cancelada: 'Cancelada', sin_sesion: '—' };
  function pintarResultados(se) {
    var hay = !!se.archivo, c = se.conteo || {A: 0, T: 0, C: 0, G: 0, otros: 0};
    var total = c.A + c.T + c.C + c.G;
    ['A', 'T', 'C', 'G'].forEach(function (b) {
      var el = document.querySelector('.base[data-b="' + b + '"]');
      cambiar(el.querySelector('b'), hay ? num(c[b]) : '—');
      el.querySelector('.progreso > div').style.width = (hay && total ? 100 * c[b] / total : 0) + '%';
    });
    cambiar($('r-total'), hay ? num(total) : '—');
    fijar('r-otros', hay ? 'Además, ' + num(c.otros) + ' caracteres no ATCG (N y otros), que no entran en el total.' : '');
    fijar('r-archivo', hay ? se.archivo : '—');
    fijar('r-estado', NOMBRE_ESTADO[se.estado] || '—');
    fijar('r-inicio', hay ? fechaHora(se.t_inicio) : '—');
    fijar('r-fin', hay && se.t_fin ? fechaHora(se.t_fin) : '—');
    fijar('r-dur', hay ? dur(se.transcurrido_s) : '—');
    fijar('r-w', hay ? String(se.workers_participantes) : '—');
    fijar('r-tam', hay ? tam(se.bytes) : '—');
    fijar('r-bl', hay ? num(se.bloques) : '—');
    fijar('r-vel', hay ? num(se.mb_s, 1) + ' MB/s' : '—');
    ['exp-csv', 'exp-json'].forEach(function (id) { $(id).setAttribute('aria-disabled', hay ? 'false' : 'true'); });
  }

  // ---------- archivos ----------
  function cargarArchivos() {
    fetch('/api/archivos').then(function (r) { return r.json(); }).then(function (lista) {
      archivosLista = lista;
      var ul = $('lista-archivos'); ul.textContent = '';
      if (!lista.length) { var v = document.createElement('li'); v.className = 'vacio'; v.textContent = 'Aún no hay archivos .fna.'; ul.appendChild(v); }
      lista.forEach(function (a) {
        var li = document.createElement('li'), b = document.createElement('button');
        b.type = 'button'; b.className = 'opcion'; b.setAttribute('aria-pressed', String(a.nombre === archivoElegido));
        var n = document.createElement('span'); n.className = 'nom'; n.textContent = a.nombre;
        var t = document.createElement('span'); t.textContent = tam(a.bytes);
        b.appendChild(n); b.appendChild(t);
        b.onclick = function () { elegir(a.nombre); };
        li.appendChild(b); ul.appendChild(li);
      });
      if (archivoElegido && !lista.some(function (a) { return a.nombre === archivoElegido; })) archivoElegido = null;
      refrescarBoton();
    });
  }
  function elegir(nombre) { archivoElegido = nombre; mensaje('archivo-msg', ''); cargarArchivos(); }
  function refrescarBoton() {
    var enCurso = estadoActual && estadoActual.sesion.estado === 'en_curso';
    $('btn-iniciar').disabled = enCurso || !archivoElegido;
  }

  $('btn-iniciar').onclick = function () {
    $('btn-iniciar').disabled = true;
    fetch('/api/sesion/iniciar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ archivo: archivoElegido, tamano_bloque: parseInt($('tam-bloque').value, 10) * 1048576 }) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.detail || 'No se pudo iniciar'); return j; }); })
      .then(function (j) {
        mensaje('archivo-msg', 'Procesamiento iniciado: ' + num(j.bloques) + ' bloques.' +
                (estadoActual && estadoActual.conectados ? '' : ' Esperando celulares.'), 'ok');
        setTimeout(function () { mensaje('archivo-msg', ''); }, 5000);
      })
      .catch(function (e) { mensaje('archivo-msg', e.message, 'error'); refrescarBoton(); });
  };
  $('btn-cancelar').onclick = function () {
    if (confirm('¿Cancelar el procesamiento en curso?')) fetch('/api/sesion/cancelar', { method: 'POST' });
  };

  // ---------- subida por arrastrar y soltar ----------
  var zona = $('zona'), entrada = $('entrada');
  zona.onclick = function () { entrada.click(); };
  zona.onkeydown = function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); entrada.click(); } };
  ['dragenter', 'dragover'].forEach(function (n) { zona.addEventListener(n, function (e) { e.preventDefault(); zona.classList.add('sobre'); }); });
  ['dragleave', 'drop'].forEach(function (n) { zona.addEventListener(n, function (e) { e.preventDefault(); zona.classList.remove('sobre'); }); });
  zona.addEventListener('drop', function (e) { if (e.dataTransfer.files.length) subir(e.dataTransfer.files[0]); });
  entrada.onchange = function () { if (entrada.files.length) subir(entrada.files[0]); entrada.value = ''; };

  function subir(f) {
    if (!/\.fna$/i.test(f.name)) { mensaje('subida-msg', 'Formato no válido: el archivo debe terminar en .fna.', 'error'); return; }
    if (archivosLista.some(function (a) { return a.nombre === f.name; })) { mensaje('subida-msg', 'Ya existe un archivo con ese nombre.', 'error'); return; }
    mensaje('subida-msg', '');
    $('subida').hidden = false; fijar('subida-nombre', f.name + ' · ' + tam(f.size));
    var x = new XMLHttpRequest();
    x.open('POST', '/api/archivos/subir?nombre=' + encodeURIComponent(f.name));
    x.upload.onprogress = function (e) {
      if (!e.lengthComputable) return;
      var p = 100 * e.loaded / e.total;
      $('subida-barra').style.width = p + '%'; fijar('subida-pct', num(p, 0) + ' %');
    };
    x.onload = function () {
      if (x.status === 200) { mensaje('subida-msg', 'Archivo cargado: ' + f.name, 'ok'); elegir(f.name); setTimeout(function () { mensaje('subida-msg', ''); }, 5000); }
      else { var d = ''; try { d = JSON.parse(x.responseText).detail; } catch (e) {} mensaje('subida-msg', d || 'No se pudo cargar el archivo.', 'error'); }
      setTimeout(function () { $('subida').hidden = true; $('subida-barra').style.width = '0'; }, 1200);
    };
    x.onerror = function () { mensaje('subida-msg', 'Se perdió la conexión durante la carga.', 'error'); };
    x.send(f);                       // el navegador envía el archivo en streaming, sin cargarlo entero en memoria
  }

  // ---------- QR ----------
  function ajustarQR() {                                   // tamaño = múltiplo entero de módulos: bordes nítidos, sin difuminar
    var svg = $('qr').querySelector('svg');
    if (!svg) return;
    var n = parseInt(svg.getAttribute('viewBox').split(' ')[2], 10);
    var px = Math.max(1, Math.floor(200 / n)) * n;
    svg.setAttribute('width', px); svg.setAttribute('height', px);
  }
  function mostrarQR(ip) {
    fetch('/api/token' + (ip ? '?ip=' + encodeURIComponent(ip) : '')).then(function (r) { return r.json(); }).then(function (t) {
      $('qr').innerHTML = t.qr_svg;                         // SVG generado por el Master (con viewBox y margen de 4 módulos)
      ajustarQR();
      fijar('qr-url', t.url);
      fijar('qr-vig', String(Math.round(t.vigencia_s / 60)));
      var sel = $('sel-ip'); sel.textContent = '';
      (t.ips.length ? t.ips : [t.ip]).forEach(function (i) {
        var o = document.createElement('option'); o.value = i; o.textContent = i; o.selected = i === t.ip; sel.appendChild(o);
      });
    });
  }
  $('btn-agregar').onclick = function () { $('modal').hidden = false; mostrarQR(); $('modal-cerrar').focus(); };
  $('modal-cerrar').onclick = function () { $('modal').hidden = true; };
  $('modal').onclick = function (e) { if (e.target === $('modal')) $('modal').hidden = true; };
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') $('modal').hidden = true; });
  $('sel-ip').onchange = function () { mostrarQR($('sel-ip').value); };
  $('qr-renovar').onclick = function () { mostrarQR($('sel-ip').value); };

  // ---------- historial ----------
  function cargarHistorial() {
    fetch('/api/historial').then(function (r) { return r.json(); }).then(function (filas) {
      var cuerpo = $('his-cuerpo'); cuerpo.textContent = '';
      $('his-vacio').hidden = filas.length > 0;
      filas.forEach(function (f) {
        var tr = document.createElement('tr');
        function celda(texto, clase) { var td = document.createElement('td'); td.textContent = texto; if (clase) td.className = clase; tr.appendChild(td); return td; }
        celda(f.archivo, 'arch').title = f.archivo;
        celda(f.inicio);
        celda(dur(f.duracion_s));
        celda(num(f.workers_participantes));
        var e = celda(''); var sp = document.createElement('span');
        sp.className = 'estado-h ' + f.estado; sp.textContent = f.estado === 'completada' ? 'Completada' : 'Cancelada'; e.appendChild(sp);
        ['A', 'T', 'C', 'G', 'total_bases'].forEach(function (k) { celda(num(f[k]), 'n'); });
        cuerpo.appendChild(tr);
      });
    });
  }

  cargarArchivos();
  cargarHistorial();
  conectar();
})();
