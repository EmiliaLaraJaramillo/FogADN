# Fog ADN · conteo distribuido de bases (A, T, C, G) con celulares

Un **celular Master** (Android) reparte bloques de un archivo `.fna` entre otros celulares (Edge) conectados a su hotspot.
Cada celular abre una página web, cuenta las bases con **todos sus hilos** (Web Workers) y devuelve solo cuatro números.
No se instala nada en los celulares trabajadores: basta el navegador (Safari en iPhone, Chrome en Android).

El Master también puede correr en un computador con Windows (ver «Alternativa: Master en el computador»).

## Cómo funciona

1. El Master parte el archivo en bloques (de 1 a 16 MB, cortados siempre al final de una línea).
2. Cada celular se une escaneando un QR, pide un bloque, lo descarga por HTTP y lo cuenta.
3. El celular parte el bloque en tantas partes como hilos tenga, las cuenta en paralelo y suma el resultado.
4. Devuelve al Master los conteos de A, T, C, G (y «otros»); el Master suma y muestra todo en vivo.
5. Si un celular se cae, sus bloques vuelven a la cola y los reparte a los demás. El resultado final es exacto.

## Qué se ve en el dashboard del Master

- **Guía arriba, en tres pasos** (Conectar celulares → Elegir archivo → Procesar). Un solo botón grande cambia según el
  momento: «Agregar dispositivo», «Elegir archivo», «Iniciar procesamiento», «Cancelar» o «Procesar de nuevo».
- **Cifras en vivo:** A, T, C, G y el total suben con animación y un «+N» cada vez que llega un bloque; cada base muestra
  su porcentaje. También velocidad (MB/s), tiempo, bloques pendientes / asignados / completados y un mapa de bloques.
- **Envío de paquetes:** el Master a la izquierda y un carril por celular. Se ve el bloque viajando al celular
  («Bloque 3 · 1,0 MB»), el resultado volviendo («+1 035 680 bases») y, si un celular se cae, el bloque que regresa a
  la cola. Debajo, una tabla con hora, bloque, celular, evento, tamaño, tiempos de descarga y de conteo.
- **Características de cada celular al conectarse:** tipo (iPhone, Android…), sistema, navegador, **hilos del procesador**,
  **hilos contando bases**, memoria, pantalla, GPU, idioma y zona horaria; más su velocidad de descarga y de conteo.
  Lo que el navegador no entrega aparece como «No disponible» (nada se inventa). En iPhone, Safari no informa el modelo
  exacto ni la memoria, pero sí los hilos, la pantalla (por ejemplo `390×844 @3x`) y la GPU.
- **Resultado e historial:** cada ejecución queda guardada y se exporta a CSV y JSON.

El dashboard se adapta a pantalla de celular: en vertical se ven los tres pasos y, mientras procesa, se esconden para
dejar a la vista el procesamiento.

## Master en un celular Android (Termux)

Necesitas un celular **Android** para el Master y dos celulares más (cualquier modelo, también iPhone) como trabajadores.
iPhone no sirve como Master: iOS no permite que una página o app actúe de servidor.

### Instalación (una sola vez, con internet)

1. Instala **Termux desde F-Droid** (https://f-droid.org). La versión de Play Store está desactualizada y no funciona.
2. Abre Termux y ejecuta:

       pkg update -y && pkg install -y git
       git clone https://github.com/EmiliaLaraJaramillo/FogADN.git
       cd FogADN
       sh termux/instalar.sh

   Al final debe decir **«Master importa bien»**. El script primero intenta usar `pydantic` ya compilado por Termux y,
   si no está disponible, instala versiones antiguas escritas solo en Python (no compila nada).
3. Si el proyecto cambia después: `cd ~/FogADN && git pull`.

### Cada vez que lo uses

1. **Activa el hotspot** del celular Master (Ajustes → Zona Wi-Fi / Punto de acceso) y conecta los otros dos celulares a él.
   En el Master no hace falta internet.
2. En Termux: `cd ~/FogADN && sh termux/iniciar.sh`. Deja Termux abierto (el script pide wake-lock; conviene quitar la
   optimización de batería a Termux en Ajustes de Android y mantener el Master cargando).
3. En **Chrome del mismo celular** abre **http://localhost:5000**.
4. Sigue la guía de arriba:
   - **Paso 1:** pulsa «Agregar dispositivo». Aparece un QR en la pantalla del Master; cada celular trabajador lo
     escanea con la cámara y se abre la página. En cuanto se conecta, su tarjeta aparece con sus características.
   - **Paso 2:** elige un archivo de la lista o súbelo con «Subir un archivo .fna» (abre el selector de archivos del
     celular). También puedes copiar el `.fna` a la carpeta `data/` (ver abajo).
   - **Paso 3:** elige el tamaño de cada paquete y pulsa «Iniciar procesamiento».
5. Mantén **las pantallas de los celulares trabajadores encendidas y la pestaña abierta**: iOS y Android suspenden los
   Web Workers si la pantalla se apaga.

### Si el QR sale con una IP incorrecta

En el celular Master las IPs pueden ser varias (datos móviles, hotspot). El Master pone primero la del hotspot, pero si el
QR no abre en los otros celulares: elige otra en «Red del Master» dentro de la ventana del QR, o arranca indicando la IP:

    sh termux/iniciar.sh 192.168.43.1

Para ver las IPs del celular: `ifconfig` (o `ip addr`) en Termux. La del hotspot suele ser `192.168.43.1` u otra terminada en `.1`.

### Pasar archivos `.fna` al Master

- **Desde el dashboard:** «Subir un archivo .fna» (lo más simple).
- **Desde Termux:** ejecuta una vez `termux-setup-storage` y copia el archivo, por ejemplo:
  `cp ~/storage/downloads/mi_archivo.fna ~/FogADN/data/`

## Alternativa: Master en el computador (Windows)

Útil para desarrollar y probar. Requiere **Python 3.10 o superior** (https://www.python.org/downloads/, marca «Add python.exe
to PATH»); comprueba con `python --version`. Los celulares y el computador deben estar en la misma red Wi-Fi (un router
propio o el punto de acceso móvil de Windows; las redes de universidades suelen bloquear la comunicación entre dispositivos).

Instalación (PowerShell dentro de la carpeta del proyecto, una sola vez):

    python -m venv .venv
    .venv\Scripts\python -m pip install -r master\requirements.txt

Abrir el puerto en el firewall (PowerShell **como administrador**, una sola vez):

    netsh advfirewall firewall add rule name="Fog Master" dir=in action=allow protocol=TCP localport=5000 profile=any

Ejecutar (deja la ventana abierta; se apaga con `Ctrl+C`) y abre **http://localhost:5000**:

    cd master
    ..\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 5000

Después se usa igual que arriba: guía de tres pasos, QR y procesamiento.

## Archivos de prueba

En `data/` hay tres archivos pequeños (`prueba1.fna`, `ecoli_k12.fna` de 4,5 MB y `prueba_5mb.fna`). Para crear uno más
grande con conteo conocido (sirve para verificar exactitud):

    python tools/generar_fna.py data/prueba_200mb.fna --mb 200

Los archivos `.fna` reales (por ejemplo del NCBI) se copian a `data/` y aparecen en el dashboard. Un genoma grande
(varios GB) funciona, pero con un Master móvil conviene probar primero con archivos pequeños.

## Pruebas automáticas (opcional, en el computador)

    .venv\Scripts\python -m pip install -r master\requirements-dev.txt
    .venv\Scripts\python -m pytest master\tests -q
    node tools\probar_conteo_js.js data\prueba_5mb.fna

La prueba con navegador real (Edge; el segundo celular entra con la sesión en marcha y el primero se cae a mitad) es
`python tools/prueba_e2e_navegador.py prueba_5mb.fna`; con `--hilos N` simula un celular con N hilos.

## Evaluación de rendimiento

Ver `EVALUACION.md` (secuencial frente a 1, 2, 3 celulares) y `PLAN.md` (arquitectura y decisiones). Esos números se
midieron con el Master en un computador: con el Master en un celular conviene repetir el benchmark.

## Si algo falla

- *El celular no abre la página:* comprueba que esté conectado al hotspot (o a la misma Wi-Fi) del Master, y prueba otra
  IP en «Red del Master» del QR. En Windows revisa además la regla de firewall de arriba.
- *«Enlace vencido» en el celular:* el QR dura 5 minutos; pulsa «Generar un código nuevo» y escanéalo otra vez.
- *El dashboard dice «Esperando celulares»:* no hay ningún celular conectado; agrega uno con el QR.
- *Un celular se queda quieto:* la pantalla se apagó o la pestaña pasó a segundo plano. Reábrela: se reconecta sola y el
  Master reasigna sus bloques mientras tanto.
- *`instalar.sh` falla en Termux:* copia el mensaje de error; el script ya prueba dos formas de instalar las librerías.
- *Termux se cierra con la pantalla apagada:* quita la optimización de batería a Termux y no cierres la notificación de
  Termux (la del wake-lock).
- *«No se reconoce python» (Windows):* reinstala Python marcando «Add python.exe to PATH» y abre una PowerShell nueva.
- *El puerto 5000 está ocupado:* cierra el otro Master o usa otro puerto: `FOG_PUERTO=5001 sh termux/iniciar.sh` en Termux, o
  `$env:FOG_PUERTO=5001` y `--port 5001` en Windows (con la misma regla de firewall para ese puerto).
