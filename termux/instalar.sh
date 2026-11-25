#!/data/data/com.termux/files/usr/bin/sh
# Instala lo necesario para correr el Master en Termux (Android). Se ejecuta una sola vez:  sh termux/instalar.sh
set -e
cd "$(dirname "$0")/.."

echo "==> 1/3 Paquetes de Termux"
pkg update -y
pkg install -y python git

echo "==> 2/3 Librerias de Python"
# Camino A: pydantic ya compilado por Termux (evita compilar Rust en el celular).
if pkg install -y python-pydantic >/dev/null 2>&1; then
    echo "   pydantic desde Termux: OK"
    pip install --no-cache-dir fastapi uvicorn websockets segno || { echo "   fallo pip con fastapi moderno"; METODO_A_FALLO=1; }
else
    METODO_A_FALLO=1
fi
# Camino B: versiones antiguas 100% Python (no necesitan compilar nada).
if [ -n "$METODO_A_FALLO" ]; then
    echo "   usando versiones puras de Python (plan B)"
    pip install --no-cache-dir "fastapi==0.99.1" "pydantic<2" uvicorn websockets segno
fi

echo "==> 3/3 Comprobacion"
cd master
python -c "from app.main import app; print('Master importa bien')"
cd ..
echo
echo "Listo. Para arrancar:  sh termux/iniciar.sh"
