import json
import random
import sys
from pathlib import Path

import pytest


from app.fasta.bloques import iterar_bloques, leer_bloque  # noqa: E402
from app.fasta.conteo import contar_bloque, sumar  # noqa: E402
from app.fasta.secuencial import contar_archivo  # noqa: E402
import generar_fna  # noqa: E402


def referencia_ingenua(texto: str) -> dict:
    """Implementación lenta y obvia, línea por línea, para contrastar."""
    c = {"A": 0, "T": 0, "C": 0, "G": 0, "otros": 0}
    for linea in texto.splitlines():
        if linea.startswith(">"):
            continue
        for ch in linea:
            u = ch.upper()
            if u in "ATCG":
                c[u] += 1
            elif not ch.isspace():
                c["otros"] += 1
    return c


def test_conteo_basico_y_encabezado_ignorado():
    datos = b">seq1 ATCG ATCG\nACGTacgtNN\nRYk\n"
    assert contar_bloque(datos) == {"A": 2, "T": 2, "C": 2, "G": 2, "otros": 5}


def test_sin_salto_final_y_con_crlf():
    assert contar_bloque(b">x\r\nAC\r\nGT") == {"A": 1, "T": 1, "C": 1, "G": 1, "otros": 0}


def test_bloque_vacio():
    assert contar_bloque(b"") == {"A": 0, "T": 0, "C": 0, "G": 0, "otros": 0}


def test_encabezado_con_bases_no_cuenta():
    assert contar_bloque(b">AAAA\n>TTTT\n") == {"A": 0, "T": 0, "C": 0, "G": 0, "otros": 0}


@pytest.mark.parametrize("tamano", [1, 7, 50, 64, 1000, 10**6])
def test_bloques_cubren_el_archivo_y_cortan_en_salto_de_linea(tmp_path, tamano):
    ruta = tmp_path / "a.fna"
    ruta.write_bytes(b">uno\nACGTACGT\nACG\n>dos largo encabezado\nTTTTGGGG\nCC")
    bloques = list(iterar_bloques(str(ruta), tamano))
    assert bloques[0].offset == 0
    for a, b in zip(bloques, bloques[1:]):
        assert a.offset + a.longitud == b.offset
    assert bloques[-1].offset + bloques[-1].longitud == ruta.stat().st_size
    contenido = ruta.read_bytes()
    for b in bloques[:-1]:                       # todos terminan justo después de un salto de línea
        assert contenido[b.offset + b.longitud - 1:b.offset + b.longitud] == b"\n"
    assert [b.indice for b in bloques] == list(range(len(bloques)))


@pytest.mark.parametrize("tamano", [1, 5, 33, 100, 4096])
def test_suma_de_bloques_igual_a_conteo_total(tmp_path, tamano):
    rng = random.Random(7)
    lineas = []
    for i in range(40):
        lineas.append(f">seq{i} ACGT descripción")
        for _ in range(rng.randint(1, 12)):
            lineas.append("".join(rng.choice("ACGTacgtNnRY") for _ in range(rng.randint(1, 90))))
    texto = "\n".join(lineas)                    # sin salto final a propósito
    ruta = tmp_path / "b.fna"
    ruta.write_bytes(texto.encode())
    total = {"A": 0, "T": 0, "C": 0, "G": 0, "otros": 0}
    for b in iterar_bloques(str(ruta), tamano):
        total = sumar(total, contar_bloque(leer_bloque(str(ruta), b.offset, b.longitud)))
    assert total == referencia_ingenua(texto)


def test_linea_mas_larga_que_el_bloque(tmp_path):
    ruta = tmp_path / "c.fna"
    ruta.write_bytes(b">h\n" + b"ACGT" * 100_000 + b"\n")
    bloques = list(iterar_bloques(str(ruta), 1000))
    assert len(bloques) == 1                      # el corte se extiende hasta el salto de línea que cierra la línea larga
    assert contar_archivo(str(ruta), 1000)["conteo"]["A"] == 100_000


def test_generador_y_conteo_secuencial_coinciden(tmp_path):
    ruta = str(tmp_path / "g.fna")
    info = generar_fna.generar(ruta, mb=3, ancho=80, semilla=1)
    for tamano in (64 * 1024, 1024 * 1024, 16 * 1024 * 1024):
        r = contar_archivo(ruta, tamano)
        assert r["conteo"] == info["esperado"]
        assert r["bytes"] == info["bytes"]
    assert json.loads(Path(ruta + ".esperado.json").read_text())["esperado"] == info["esperado"]
