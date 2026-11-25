// Verifica que el conteo en JavaScript (el del celular) da lo mismo que Python.
// Uso: node tools/probar_conteo_js.js data/prueba_5mb.fna [tamanoBloque]
// Sale con código 0 si coincide con <archivo>.esperado.json y con las pruebas de casos límite; 1 si no.
const fs = require('fs');
const path = require('path');
const { contarBloque, nuevoEstado, resumir, partirEnLineas, sumar } = require('../web/worker/conteo-nucleo.js');

function contar(buf, trozo) {
  const e = nuevoEstado();
  for (let d = 0; d < buf.length; d += trozo) contarBloque(buf, d, Math.min(d + trozo, buf.length), e);
  return resumir(e.hist);
}
function igual(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
let fallos = 0;
function verifica(nombre, obtenido, esperado) {
  const ok = igual(obtenido, esperado);
  if (!ok) { fallos++; console.error('FALLA', nombre, obtenido, esperado); } else console.log('ok', nombre);
}

// Casos límite (los mismos que en master/tests/test_fasta.py)
const T = (s) => Buffer.from(s, 'latin1');
verifica('basico', contar(T('>seq1 ATCG ATCG\nACGTacgtNN\nRYk\n'), 1 << 20), { A: 2, T: 2, C: 2, G: 2, otros: 5 });
verifica('crlf y sin salto final', contar(T('>x\r\nAC\r\nGT'), 1 << 20), { A: 1, T: 1, C: 1, G: 1, otros: 0 });
verifica('vacío', contar(T(''), 1 << 20), { A: 0, T: 0, C: 0, G: 0, otros: 0 });
verifica('encabezado con bases', contar(T('>AAAA\n>TTTT\n'), 1 << 20), { A: 0, T: 0, C: 0, G: 0, otros: 0 });
verifica('encabezado partido en trozos de 1 byte', contar(T('>seq1 ATCG\nACGT\n>otro\nTT'), 1), { A: 1, T: 3, C: 1, G: 1, otros: 0 });
verifica('> en medio de línea no es encabezado', contar(T('AC>GT\n'), 1 << 20), { A: 1, T: 1, C: 1, G: 1, otros: 1 });

// Conteo en paralelo: partir en N rangos y sumar debe dar exactamente lo mismo que contar todo junto
function contarEnPartes(buf, n) {
  const partes = partirEnLineas(buf, n);
  let pos = 0, suma = { A: 0, T: 0, C: 0, G: 0, otros: 0 };
  for (const [d, h] of partes) {
    if (d !== pos || h <= d) return { error: 'rangos no contiguos', partes };
    pos = h;
    const e = nuevoEstado();
    contarBloque(buf.subarray(d, h), 0, h - d, e);
    suma = sumar(suma, resumir(e.hist));
  }
  if (pos !== buf.length) return { error: 'no cubre todo el bloque', pos };
  return suma;
}
function verificaPartes(nombre, buf) {
  const entero = contar(buf, 1 << 20);
  for (let n = 1; n <= 12; n++) {
    const r = contarEnPartes(buf, n);
    if (!igual(r, entero)) { fallos++; console.error('FALLA partes', nombre, 'n=' + n, r, entero); return; }
  }
  console.log('ok partes 1..12 ' + nombre);
}
verificaPartes('basico', T('>seq1 ATCG ATCG\nACGTacgtNN\nRYk\n'));
verificaPartes('crlf y sin salto final', T('>x\r\nAC\r\nGT'));
verificaPartes('muchos encabezados', T('>a\n>b\nAC\n>c AAAA\nGT\n>d\n\n>e\nTTTT'));
verificaPartes('una sola línea larga', T('ACGT'.repeat(1000)));
verificaPartes('vacío', T(''));
verificaPartes('solo encabezado', T('>solo un encabezado sin salto'));

const archivo = process.argv[2];
if (archivo) {
  const esperado = JSON.parse(fs.readFileSync(archivo + '.esperado.json', 'utf8')).esperado;
  const datos = fs.readFileSync(archivo);
  const t0 = Date.now();
  const r = contar(datos, parseInt(process.argv[3] || String(1 << 20), 10));
  const s = (Date.now() - t0) / 1000;
  verificaPartes(path.basename(archivo), datos);
  verifica(path.basename(archivo) + ' (' + (datos.length / 1048576).toFixed(1) + ' MB, ' + (datos.length / 1048576 / s).toFixed(0) + ' MB/s en Node)', r, esperado);
}
process.exit(fallos ? 1 : 0);
