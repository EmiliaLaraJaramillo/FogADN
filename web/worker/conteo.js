/* Web Worker: cuenta las bases de un bloque en segundo plano para no bloquear la interfaz de la página.
 * Recibe { id, parte, buffer } (ArrayBuffer transferido, sin copia) y responde con progreso y resultado.
 * La página lanza varios de estos Web Workers (uno por hilo del celular), cada uno con una parte del bloque.
 * Un Web Worker corre en otro hilo del navegador; no equivale a un hilo nativo de Android o iOS y el sistema
 * puede suspenderlo si la pestaña pasa a segundo plano.
 */
importScripts('conteo-nucleo.js');

var TROZO = 1024 * 1024;

self.onmessage = function (e) {
  var id = e.data.id;
  var bytes = new Uint8Array(e.data.buffer);
  var estado = ConteoADN.nuevoEstado();
  var t0 = Date.now();
  for (var desde = 0; desde < bytes.length; desde += TROZO) {
    ConteoADN.contarBloque(bytes, desde, Math.min(desde + TROZO, bytes.length), estado);
    self.postMessage({ tipo: 'progreso', id: id, parte: e.data.parte, pct: Math.min(100, 100 * (desde + TROZO) / bytes.length) });
  }
  self.postMessage({ tipo: 'listo', id: id, parte: e.data.parte, conteo: ConteoADN.resumir(estado.hist), bytes: bytes.length,
                     ms: Date.now() - t0 });
};
