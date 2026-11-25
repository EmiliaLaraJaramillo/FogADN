/* Página del celular (Edge): se une al Master con el token del QR, pide bloques, los descarga por HTTP, los cuenta en
 * un Web Worker y devuelve el resultado parcial por WebSocket. Si la conexión se cae, se reconecta sola.
 * Sintaxis conservadora (sin ?. ni ??) para navegadores móviles antiguos.
 */
(function () {
  'use strict';
  var params = new URLSearchParams(location.search);
  var token = params.get('token') || '';
  var CLAVE_ID = 'fog_worker_id';

  var ws = null, workerId = null, salidaVoluntaria = false;
  var latidoS = 3, reintentoS = 1, temporizadorLatido = null;
  var enProceso = false, progresoActual = 0, tareaActual = null, resultadoPendiente = null, ultimoResultado = null;
  var totales = { bloques: 0, bytes: 0, descargaMs: 0, conteoMs: 0 };
  var contador = null;

  function $(id) { return document.getElementById(id); }
  function fmt(n, d) { return Number(n).toLocaleString('es', { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 }); }

  function estado(texto, clase, detalle) {
    var e = $('estado');
    e.textContent = texto;
    e.className = 'pastilla' + (clase ? ' ' + clase : '');
    if (detalle !== undefined) $('detalle').textContent = detalle;
  }
  function barra(pct) {
    $('relleno').style.width = pct + '%';
    $('barra').setAttribute('aria-valuenow', Math.round(pct));
  }
  function pintarTotales() {
    $('n-bloques').textContent = fmt(totales.bloques);
    $('n-mb').textContent = fmt(totales.bytes / 1048576, 1) + ' MB';
    $('t-desc').textContent = fmt(totales.descargaMs / 1000, 1) + ' s';
    $('t-cont').textContent = fmt(totales.conteoMs / 1000, 1) + ' s';
  }

  function gpuRender() {
    try {
      var c = document.createElement('canvas');
      var g = c.getContext('webgl') || c.getContext('experimental-webgl');
      if (!g) return null;
      var e = g.getExtension('WEBGL_debug_renderer_info');
      return String(e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : g.getParameter(g.RENDERER));
    } catch (x) { return null; }
  }

  // --- lo que el navegador permite saber del dispositivo (lo ausente se envía como null) ---
  function infoDispositivo() {
    var ua = navigator.userAgent || '';
    var m, nav = null, plat = null;
    if ((m = ua.match(/(Edg|EdgA|EdgiOS)\/([\d.]+)/))) nav = 'Edge ' + m[2];
    else if ((m = ua.match(/(CriOS|Chrome)\/([\d.]+)/))) nav = 'Chrome ' + m[2].split('.')[0];
    else if ((m = ua.match(/(FxiOS|Firefox)\/([\d.]+)/))) nav = 'Firefox ' + m[2].split('.')[0];
    else if ((m = ua.match(/Version\/([\d.]+).*Safari/))) nav = 'Safari ' + m[1];
    if ((m = ua.match(/Android ([\d.]+)/))) plat = 'Android ' + m[1];
    else if ((m = ua.match(/OS ([\d_]+) like Mac OS X/))) plat = (/iPad/.test(ua) ? 'iPadOS ' : 'iOS ') + m[1].replace(/_/g, '.');
    else if (/Windows/.test(ua)) plat = 'Windows';
    else if (/Mac OS X/.test(ua)) plat = 'macOS';
    // En Android moderno Chrome oculta el modelo en la cadena del navegador ("K"); en iOS nunca lo informa.
    var modelo = null;
    if ((m = ua.match(/Android [\d.]+; ([^;)]+)/)) && m[1] !== 'K' && !/^(Mobile|Linux)$/.test(m[1])) modelo = m[1].trim();
    var tipo = null;
    if (/iPhone/.test(ua)) tipo = 'iPhone';
    else if (/iPad/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) tipo = 'iPad';   // iPadOS se hace pasar por Mac
    else if (/Android/.test(ua)) tipo = /Mobile/.test(ua) ? 'Android (celular)' : 'Android (tablet)';
    var pantalla = null;
    try { pantalla = screen.width + '×' + screen.height + ' @' + (window.devicePixelRatio || 1) + 'x'; } catch (e) {}
    var zona = null;
    try { zona = Intl.DateTimeFormat().resolvedOptions().timeZone || null; } catch (e) {}
    var cn = navigator.connection || null;
    return {
      modelo: modelo, plataforma: plat, navegador: nav, tipo: tipo, pantalla: pantalla, gpu: gpuRender(),
      idioma: navigator.language || null, zona_horaria: zona,
      red: cn ? ((cn.effectiveType || '') + (cn.downlink ? ' · ' + cn.downlink + ' Mb/s' : '')) || null : null,   // no existe en Safari
      nucleos: navigator.hardwareConcurrency || null,     // hilos lógicos del procesador
      memoria_gb: navigator.deviceMemory || null      // solo en Chrome y en contexto seguro (https); en http no existe
    };
  }
  var info = infoDispositivo();
  $('nav').textContent = info.navegador || 'No disponible';
  $('plat').textContent = info.plataforma || 'No disponible';
  $('nuc').textContent = info.nucleos || 'No disponible';
  $('pan').textContent = info.pantalla || 'No disponible';
  $('tipo').textContent = info.tipo || 'No disponible';

  // --- Web Worker de conteo ---
  function crearContador() {
    contador = new Worker('/static/worker/conteo.js');
    contador.onmessage = function (e) {
      var m = e.data;
      if (!tareaActual || m.id !== tareaActual.task_id) return;
      if (m.tipo === 'progreso') {
        progresoActual = m.pct;
        barra(m.pct);
      } else if (m.tipo === 'listo') {
        var tc = tareaActual.tDescargaMs;
        ultimoResultado = { type: 'result', task_id: m.id, conteo: m.conteo, bytes: m.bytes,
                            t_transfer_ms: tc, t_proceso_ms: m.ms };
        enviarResultado(ultimoResultado);
      }
    };
    contador.onerror = function () {
      estado('Error', 'error', 'El procesamiento en segundo plano falló. Recarga la página.');
    };
  }

  // --- WebSocket ---
  function conectar() {
    var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
    var url = proto + location.host + '/ws/worker?token=' + encodeURIComponent(token) +
              (workerId ? '&worker_id=' + encodeURIComponent(workerId) : '');
    ws = new WebSocket(url);
    ws.onopen = function () {
      ws.send(JSON.stringify({ type: 'hello', worker_id: workerId || localStorage.getItem(CLAVE_ID), info: info }));
    };
    ws.onmessage = function (e) { recibir(JSON.parse(e.data)); };
    ws.onclose = function (e) {
      clearInterval(temporizadorLatido);
      if (salidaVoluntaria) return;
      if (e.code === 4401) {
        estado('Enlace vencido', 'error', 'El código QR ya no es válido. Vuelve a escanear el QR del dashboard.');
        return;
      }
      estado('Reconectando…', 'alerta', 'Se perdió la conexión con el Master. Reintentando.');
      setTimeout(conectar, 2000);
    };
  }

  function enviar(obj) {
    if (ws && ws.readyState === 1) { ws.send(JSON.stringify(obj)); return true; }
    return false;
  }

  function recibir(m) {
    if (m.type === 'welcome') {
      workerId = m.worker_id;
      localStorage.setItem(CLAVE_ID, workerId);
      latidoS = m.latido_s; reintentoS = m.reintento_s;
      $('wid').textContent = workerId;
      clearInterval(temporizadorLatido);
      temporizadorLatido = setInterval(function () { enviar({ type: 'heartbeat', progreso: progresoActual }); }, latidoS * 1000);
      if (resultadoPendiente) { enviar(resultadoPendiente); resultadoPendiente = null; }
      else if (!enProceso) { estado('Disponible', '', 'Conectado. Esperando trabajo del Master.'); solicitar(); }
    } else if (m.type === 'task') {
      procesar(m);
    } else if (m.type === 'no_task') {
      var txt = { sin_sesion: 'Conectado. El Master aún no inicia un procesamiento.',
                  esperando: 'No quedan bloques por asignar. Esperando por si otro celular se desconecta.',
                  terminada: 'Procesamiento completado. Esperando una nueva sesión.' }[m.motivo] || 'Esperando trabajo.';
      estado(m.motivo === 'terminada' ? 'Completado' : 'Disponible', m.motivo === 'terminada' ? 'ok' : '', txt);
      barra(m.motivo === 'terminada' ? 100 : 0);
      $('bloque').innerHTML = '&nbsp;';
      setTimeout(solicitar, reintentoS * 1000);
    } else if (m.type === 'ack') {
      totales.bloques += 1;
      totales.bytes += ultimoResultado ? ultimoResultado.bytes : 0;
      totales.descargaMs += ultimoResultado ? ultimoResultado.t_transfer_ms : 0;
      totales.conteoMs += ultimoResultado ? ultimoResultado.t_proceso_ms : 0;
      pintarTotales();
      terminarBloque();
    } else if (m.type === 'reject') {
      terminarBloque();          // duplicado o inválido: el Master ya tiene ese bloque o lo reasignó
    } else if (m.type === 'error' && m.motivo === 'worker_no_registrado') {
      enviar({ type: 'hello', worker_id: null, info: info });
    }
  }

  function solicitar() {
    if (!enProceso) enviar({ type: 'request_task' });
  }

  function terminarBloque() {
    enProceso = false; tareaActual = null; progresoActual = 0;
    solicitar();
  }

  function enviarResultado(r) {
    if (!enviar(r)) resultadoPendiente = r;       // sin conexión: se entrega al reconectar (el Master evita duplicados)
  }

  function procesar(t) {
    enProceso = true; progresoActual = 0;
    tareaActual = { task_id: t.task_id, tDescargaMs: 0 };
    estado('Procesando', '', 'Descargando el bloque ' + (t.indice + 1) + ' de ' + t.total + '.');
    $('bloque').textContent = 'Bloque ' + (t.indice + 1) + ' de ' + t.total + ' · ' + fmt(t.longitud / 1048576, 1) + ' MB';
    barra(0);
    var t0 = performance.now();
    fetch('/api/bloques/' + encodeURIComponent(t.task_id) + '?worker_id=' + encodeURIComponent(workerId), { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.arrayBuffer();
      })
      .then(function (buf) {
        tareaActual.tDescargaMs = performance.now() - t0;
        estado('Procesando', '', 'Contando bases del bloque ' + (t.indice + 1) + ' de ' + t.total + '.');
        contador.postMessage({ id: t.task_id, buffer: buf }, [buf]);     // se transfiere sin copiar
      })
      .catch(function () {
        // El bloque se reasignó o la red falló: el Master ya lo devolvió a la cola; se pide otro.
        enProceso = false; tareaActual = null;
        setTimeout(solicitar, reintentoS * 1000);
      });
  }

  $('salir').onclick = function () {
    salidaVoluntaria = true;
    clearInterval(temporizadorLatido);
    if (ws) ws.close();
    if (contador) contador.terminate();
    estado('Desconectado', 'alerta', 'Este celular salió de la sesión. Escanea el QR para volver a unirte.');
    barra(0);
  };

  if (!token) {
    estado('Sin token', 'error', 'Abre esta página escaneando el código QR del dashboard.');
  } else if (typeof Worker === 'undefined' || typeof fetch === 'undefined' || typeof WebSocket === 'undefined') {
    estado('No compatible', 'error', 'Este navegador no admite Web Workers, fetch o WebSocket.');
  } else {
    crearContador();
    conectar();
  }
})();
