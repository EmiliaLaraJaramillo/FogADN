"""Provisional hasta tener el dashboard (Fase 5): muestra el QR de incorporación y, si se pide, inicia el procesamiento.

    python tools/qr_temporal.py                       # solo QR (abre una página en el navegador)
    python tools/qr_temporal.py --iniciar ecoli_k12.fna --bloque-mb 4
    python tools/qr_temporal.py --ip 192.168.100.14   # elegir la IP de la red por donde se conectan los celulares
"""
import argparse
import json
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def main(a):
    base = f"http://127.0.0.1:{a.puerto}"
    tk = json.loads(urllib.request.urlopen(base + "/api/token" + (f"?ip={a.ip}" if a.ip else "")).read())
    print("URL del celular :", tk["url"])
    print("IPs del Master  :", ", ".join(tk["ips"]), "(elige con --ip la de tu Wi-Fi si el QR no abre)")
    print(f"El token vence en {int(tk['vigencia_s'] // 60)} min; los celulares ya unidos no se ven afectados.")
    if a.iniciar:
        cuerpo = dict(archivo=a.iniciar, tamano_bloque=int(a.bloque_mb * 1024 * 1024))
        req = urllib.request.Request(base + "/api/sesion/iniciar", data=json.dumps(cuerpo).encode(),
                                     headers={"Content-Type": "application/json"})
        s = json.loads(urllib.request.urlopen(req).read())
        print(f"Sesión iniciada: {s['archivo']}, {s['bloques']} bloques")
    pagina = RAIZ / "data" / "qr.html"
    pagina.write_text(f"""<!doctype html><meta charset="utf-8"><title>QR Fog ADN</title>
<body style="font-family:-apple-system,Segoe UI,sans-serif;text-align:center;background:#f5f5f7;padding:40px">
<h2>Escanea con el celular</h2><div style="background:#fff;display:inline-block;padding:16px;border-radius:18px"><div style="width:300px;height:300px">{tk["qr_svg"]}</div></div>
<p style="color:#6e6e73">{tk['url']}</p></body>""", encoding="utf-8")
    webbrowser.open(pagina.as_uri())


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--puerto", type=int, default=5000)
    p.add_argument("--ip")
    p.add_argument("--iniciar")
    p.add_argument("--bloque-mb", type=float, default=16)
    main(p.parse_args())
