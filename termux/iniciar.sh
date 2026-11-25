#!/data/data/com.termux/files/usr/bin/sh
# Arranca el Master en el celular.   sh termux/iniciar.sh            (detecta la IP del hotspot)
#                                    sh termux/iniciar.sh 192.168.43.1   (si la IP detectada es otra)
cd "$(dirname "$0")/../master"
[ -n "$1" ] && export FOG_IP="$1"
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock    # evita que Android duerma el proceso
echo "Master Fog ADN en el puerto 5000. Abre en Chrome de ESTE celular:  http://localhost:5000"
echo "Antes: activa el hotspot del celular y conecta los otros dos a el. Ctrl+C para detener."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
