"""Arma las tablas y gráficos de la evaluación a partir de data/evaluacion.csv.

    python tools/informe_benchmark.py            # solo secuencial y celulares reales
    python tools/informe_benchmark.py --incluir-simulado

Salidas: data/evaluacion.md (tabla por archivo) y data/evaluacion_<archivo>.png (tiempo, speedup y eficiencia).
Definiciones:  speedup = T_secuencial / T_distribuido;  eficiencia = speedup / N celulares.
T_secuencial es el promedio de las repeticiones del Master solo con el mismo archivo. La transferencia es la suma de los
tiempos de descarga de bloques medidos en cada celular (corren en paralelo, por eso puede superar al tiempo total);
el procesamiento es la suma de los tiempos de conteo en los Web Workers.
"""
import argparse
import csv
import os
import statistics as st
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATOS = Path(os.environ.get("FOG_EVAL_DIR", RAIZ / "data"))


def coma(x, d=1):
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",") if x == x else "—"


def main(a):
    filas = list(csv.DictReader(open(DATOS / "evaluacion.csv", encoding="utf-8-sig")))
    modos = {"secuencial", "distribuido"} | ({"simulado"} if a.incluir_simulado else set())
    filas = [f for f in filas if f["modo"] in modos]
    por_archivo = defaultdict(list)
    for f in filas:
        por_archivo[f["archivo"]].append(f)
    salida = ["# Evaluación comparativa\n"]
    for archivo, fs in por_archivo.items():
        grupos = defaultdict(list)
        for f in fs:
            grupos[(f["modo"], int(f["celulares"]), int(f["bloque_mb"]))].append(f)
        seq = [float(f["tiempo_s"]) for f in fs if f["modo"] == "secuencial"]
        t_seq = st.mean(seq) if seq else float("nan")
        tam = int(fs[0]["bytes"])
        salida.append(f"## {archivo} ({coma(tam / 2**20, 1)} MB)\n")
        salida.append("| Configuración | Bloque (MB) | Reps | Tiempo medio (s) | Rango (s) | MB/s | Speedup | Eficiencia | Transferencia (s, suma) | Procesamiento (s, suma) | % transferencia | Exacto |")
        salida.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        filas_tabla = []
        for (modo, n, bloque), g in sorted(grupos.items(), key=lambda kv: (kv[0][0] != "secuencial", kv[0][1], kv[0][2])):
            t = [float(x["tiempo_s"]) for x in g]
            tm = st.mean(t)
            mbs = tam / 2**20 / tm
            ta = st.mean(float(x["t_lectura_o_transf_s"]) for x in g)
            tb = st.mean(float(x["t_conteo_o_proceso_s"]) for x in g)
            ok = [x["exacto"] for x in g]
            exacto = "sí" if all(e == "True" for e in ok) else ("no" if any(e == "False" for e in ok) else "sin referencia")
            if modo == "secuencial":
                nombre, sp, ef, pct = "Master (secuencial)", "1,00", "—", "—"
                ta_s, tb_s = f"{coma(ta, 1)} (lectura)", f"{coma(tb, 1)} (conteo)"
            else:
                nombre = f"{n} celular{'es' if n != 1 else ''}" + (" (simulado)" if modo == "simulado" else "")
                spd = t_seq / tm
                sp, ef = coma(spd, 2), coma(spd / n, 2)
                pct = coma(100 * ta / (ta + tb), 0) + " %" if ta + tb else "—"
                ta_s, tb_s = coma(ta, 1), coma(tb, 1)
                filas_tabla.append((n, tm, spd, spd / n, modo))
            salida.append(f"| {nombre} | {bloque} | {len(g)} | {coma(tm, 1)} | {coma(min(t), 1)}–{coma(max(t), 1)} | {coma(mbs, 1)} | {sp} | {ef} | {ta_s} | {tb_s} | {pct} | {exacto} |")
        salida.append("")
        if filas_tabla and seq:
            grafico(archivo, t_seq, filas_tabla)
    texto = "\n".join(salida) + "\n"
    (DATOS / "evaluacion.md").write_text(texto, encoding="utf-8")
    print(texto)


def grafico(archivo, t_seq, filas):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ns = sorted({f[0] for f in filas})
    prom = {n: [f for f in filas if f[0] == n] for n in ns}
    tiempos = [st.mean(f[1] for f in prom[n]) for n in ns]
    sp = [st.mean(f[2] for f in prom[n]) for n in ns]
    ef = [st.mean(f[3] for f in prom[n]) for n in ns]
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    lila, gris = "#7a4de0", "#6e6e73"
    etiquetas = ["Master"] + [str(n) for n in ns]
    ax[0].bar(etiquetas, [t_seq] + tiempos, color=[gris] + [lila] * len(ns))
    ax[0].set_title("Tiempo total (s)"); ax[0].set_xlabel("Celulares (Master = secuencial)")
    ax[1].plot(ns, sp, "o-", color=lila); ax[1].axhline(1, color=gris, ls="--", lw=1, label="sin mejora (1×)")
    ax[1].set_title("Speedup"); ax[1].set_xlabel("Celulares"); ax[1].set_xticks(ns); ax[1].legend(frameon=False)
    ax[2].plot(ns, ef, "o-", color=lila); ax[2].axhline(1, color=gris, ls="--", lw=1)
    ax[2].set_title("Eficiencia (speedup / N)"); ax[2].set_xlabel("Celulares"); ax[2].set_xticks(ns)
    for x in ax:
        x.spines[["top", "right"]].set_visible(False)
    fig.suptitle(archivo, fontsize=10, color=gris)
    fig.tight_layout()
    fig.savefig(DATOS / f"evaluacion_{Path(archivo).stem[:40]}.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--incluir-simulado", action="store_true")
    main(p.parse_args())
