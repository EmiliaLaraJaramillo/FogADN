# Fog ADN · conteo distribuido de bases (A, T, C, G) con celulares

Un computador (Master) reparte bloques de un archivo `.fna` entre celulares conectados a la misma red Wi-Fi. Cada celular
abre una página web, cuenta las bases en un Web Worker y devuelve el resultado. No se instala nada en los celulares.

## Requisitos

- Windows con **Python 3.10 o superior** (https://www.python.org/downloads/, marca «Add python.exe to PATH»).
  Comprueba con: `python --version`
- Conexión a internet solo para instalar las librerías (una vez).
- Los celulares y el computador, en la **misma red Wi-Fi** (un router propio o el punto de acceso móvil de Windows;
  las redes de universidades suelen bloquear la comunicación entre dispositivos).

## Instalación (una sola vez)

Abre PowerShell dentro de la carpeta descomprimida (clic derecho en la carpeta → «Abrir en Terminal»), o usa `cd` hacia
ella, y ejecuta:

    python -m venv .venv
    .venv\Scripts\python -m pip install -r master\requirements.txt

## Abrir el puerto en el firewall (una sola vez)

PowerShell **como administrador**:

    netsh advfirewall firewall add rule name="Fog Master" dir=in action=allow protocol=TCP localport=5000 profile=any

## Ejecutar

    cd master
    ..\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 5000

Deja esa ventana abierta (se apaga con `Ctrl+C`). Luego abre en el navegador del computador: **http://localhost:5000**

1. En el panel izquierdo elige un archivo de «Archivos recientes» (o arrastra uno `.fna`) y el tamaño de bloque.
2. Pulsa **Agregar dispositivo** y escanea el QR con el celular (misma red Wi-Fi). Si el QR no abre, elige otra IP en
   el selector de la ventana del QR.
3. Pulsa **Iniciar procesamiento**. Los celulares pueden entrar o salir en cualquier momento.
4. Los resultados se ven en vivo y quedan en el historial; se pueden exportar a CSV y JSON.

## Archivos de prueba

En `data\` hay tres archivos pequeños (`prueba1.fna`, `ecoli_k12.fna` de 4,5 MB y `prueba_5mb.fna`). Para crear uno más
grande con conteo conocido (sirve para verificar exactitud):

    .venv\Scripts\python tools\generar_fna.py data\prueba_200mb.fna --mb 200

Los archivos `.fna` reales (por ejemplo del NCBI) se copian a la carpeta `data\` y aparecen en el dashboard.

## Pruebas automáticas (opcional)

    .venv\Scripts\python -m pip install -r master\requirements-dev.txt
    .venv\Scripts\python -m pytest master\tests -q

## Evaluación de rendimiento

Ver `EVALUACION.md` (secuencial frente a 1, 2, 3 celulares) y `PLAN.md` (arquitectura y decisiones).

## Si algo falla

- *El celular no abre la página:* comprueba que esté en la misma Wi-Fi, que el firewall tenga la regla de arriba y
  prueba otra IP en el selector del QR.
- *«No se reconoce python»:* reinstala Python marcando «Add python.exe to PATH» y abre una PowerShell nueva.
- *El puerto 5000 está ocupado:* cierra la otra ventana del Master, o usa otro puerto con `--port 5001` (y la regla de
  firewall con ese puerto; el QR usa el puerto configurado con la variable `FOG_PUERTO`: `$env:FOG_PUERTO=5001` antes de
  arrancar).
