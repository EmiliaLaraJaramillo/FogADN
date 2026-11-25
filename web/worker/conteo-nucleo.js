/* Conteo de bases A, T, C y G en un bloque FASTA (mismas reglas que master/app/fasta/conteo.py):
 *  - las líneas que empiezan con '>' son encabezados y se ignoran completas (el salto de línea que las cierra cuenta como blanco);
 *  - A, T, C y G cuentan sin distinguir mayúsculas de minúsculas;
 *  - cualquier otro carácter que no sea espacio en blanco se informa como «otros».
 * El bloque empieza siempre al inicio de una línea (lo garantiza el Master).
 * Sintaxis conservadora (ES5 + typed arrays) para que funcione también en iOS antiguos.
 */
(function (raiz) {
  // El estado ({ enEncabezado, inicioDeLinea, hist }) se conserva entre trozos del mismo bloque.
  function contarBloque(bytes, desde, hasta, estado) {
    var hist = estado.hist;
    var enEnc = estado.enEncabezado, inicio = estado.inicioDeLinea;
    for (var i = desde; i < hasta; i++) {
      var b = bytes[i];
      if (enEnc) {
        if (b === 10) { enEnc = false; inicio = true; hist[10]++; }
        continue;
      }
      if (inicio && b === 62) { enEnc = true; inicio = false; continue; }
      inicio = (b === 10);
      hist[b]++;
    }
    estado.enEncabezado = enEnc;
    estado.inicioDeLinea = inicio;
  }

  function nuevoEstado() {
    return { enEncabezado: false, inicioDeLinea: true, hist: new Uint32Array(256) };
  }

  function resumir(hist) {
    var A = hist[65] + hist[97], T = hist[84] + hist[116], C = hist[67] + hist[99], G = hist[71] + hist[103];
    var total = 0;
    for (var k = 0; k < 256; k++) total += hist[k];
    var blancos = hist[9] + hist[10] + hist[13] + hist[32];
    return { A: A, T: T, C: C, G: G, otros: total - A - T - C - G - blancos };
  }

  // Parte un bloque en `n` rangos [desde, hasta) contiguos; cada corte cae justo despues de un salto de linea, de modo
  // que cada parte empieza al inicio de una linea y puede contarse por separado (en otro hilo) con el mismo resultado.
  function partirEnLineas(bytes, n) {
    var len = bytes.length, partes = [], ini = 0;
    for (var k = 1; k <= n; k++) {
      var fin = len;
      if (k < n) {
        fin = Math.max(ini, Math.floor(len * k / n));
        while (fin > 0 && fin < len && bytes[fin - 1] !== 10) fin++;
      }
      if (fin > ini) partes.push([ini, fin]);
      ini = fin;
    }
    return partes;
  }

  function sumar(a, b) {
    return { A: a.A + b.A, T: a.T + b.T, C: a.C + b.C, G: a.G + b.G, otros: a.otros + b.otros };
  }

  var api = { contarBloque: contarBloque, nuevoEstado: nuevoEstado, resumir: resumir, partirEnLineas: partirEnLineas, sumar: sumar };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else raiz.ConteoADN = api;
})(typeof self !== 'undefined' ? self : this);
