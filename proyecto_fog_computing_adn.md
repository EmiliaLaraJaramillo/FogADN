# Proyecto: Sistema de Fog Computing para procesamiento distribuido de ADN

Actúa como un ingeniero de software experto en **computación
distribuida, Fog Computing y desarrollo web**. Quiero que me guíes paso
a paso en el diseño y construcción de este proyecto académico. Prioriza
una solución funcional, técnicamente correcta y que podamos implementar
y probar; evita simular funcionalidades.

## 1. Objetivo

Desarrollar un sistema que distribuya el procesamiento de archivos de
ADN en formato `.fna` (de hasta aproximadamente **3 GB**) entre varios
teléfonos celulares conectados a la misma red Wi-Fi. El procesamiento
inicial consiste en contar las bases nitrogenadas **A, T, C y G**.

El proyecto debe demostrar distribución de tareas, concurrencia,
comunicación entre dispositivos, sincronización, monitoreo y tolerancia
a fallos.

## 2. Arquitectura propuesta: Master--Workers

### Master: computador o laptop

Será el nodo coordinador y alojará el backend y el dashboard web. Sus
responsabilidades serán:

-   Permitir la carga de archivos `.fna`.
-   Generar un código QR dinámico para incorporar celulares.
-   Reconocer, registrar y administrar los dispositivos conectados.
-   Dividir el archivo en bloques y distribuir las tareas.
-   Recibir, validar y consolidar los resultados parciales.
-   Monitorear el estado de los Workers y el avance del procesamiento.
-   Mostrar los resultados finales y el historial de ejecuciones.

### Workers: teléfonos celulares

Los celulares se conectarán a la misma red Wi-Fi que el Master. No se
debe requerir instalar una aplicación desde Play Store.

-   El usuario escanea el QR y accede desde el navegador a una página
    web móvil o PWA.
-   El celular solicita incorporarse a la sesión y queda registrado en
    el dashboard.
-   Recibe bloques de trabajo, procesa las bases A/T/C/G y devuelve
    resultados parciales.
-   Utiliza **JavaScript Web Workers** para ejecutar el procesamiento en
    segundo plano sin bloquear la interfaz.

### Cloud: posible integración futura

No implementar la nube en la primera versión. Sin embargo, diseñar el
sistema de forma modular para que posteriormente pueda integrarse un
servidor Linux externo destinado a almacenamiento, persistencia de
sesiones, historial y resultados, sin modificar la lógica principal de
distribución y procesamiento.

La arquitectura debe distinguir correctamente los niveles:

-   **Fog:** computador Master que coordina los recursos dentro de la
    red local.
-   **Edge:** teléfonos celulares que ejecutan el procesamiento.
-   **Cloud:** servicio externo opcional para una futura extensión.

## 3. Tecnologías sugeridas

-   **Frontend del dashboard:** React.
-   **Backend del Master:** Python con FastAPI.
-   **Comunicación Master--Workers:** WebSockets para actualizaciones y
    coordinación en tiempo real; HTTP puede utilizarse para operaciones
    que lo requieran.
-   **Interfaz de los celulares:** React y JavaScript.
-   **Concurrencia en los celulares:** JavaScript Web Workers.
-   **Código QR:** una librería compatible con React.
-   **Persistencia local:** SQLite o una alternativa ligera y modular.

Puedes proponer otras tecnologías si existe una justificación técnica
clara y se mantiene la viabilidad del proyecto.

## 4. Dashboard web

Quiero una interfaz limpia, elegante y profesional, inspirada en
Apple/macOS:

-   Fondo claro, tonos blancos y grises suaves.
-   Tarjetas con bordes sutiles, esquinas redondeadas y sombras ligeras.
-   Tipografía moderna, espacios amplios e iconografía consistente.
-   Animaciones discretas.
-   Evitar interfaces recargadas, colores excesivos o apariencia de
    plantilla genérica.

El dashboard debe incluir estas secciones:

### A. Panel principal

-   Nombre e identidad del proyecto.
-   Identificación del computador como Master.
-   Estado general del sistema.
-   Estado de la red.
-   Número de Workers conectados.
-   Fecha y hora.

### B. Carga de archivos

-   Área Drag & Drop y selector de archivos `.fna`.
-   Nombre y tamaño del archivo.
-   Validación del formato.
-   Estado de carga.
-   Opciones para iniciar o cancelar el procesamiento.

### C. Incorporación de dispositivos

-   Botón **"Agregar dispositivo"**.
-   Generación y visualización de un QR dinámico.
-   Instrucciones breves para conectar el celular.
-   Número de dispositivos conectados.

El QR debe dirigir a una URL local del Master e incluir un token
temporal de incorporación. Por ejemplo, una dirección conceptual como
`http://192.168.1.10:5000/worker?token=ABC123`. El QR facilita abrir la
página; la conexión real se establece mediante la red local. Considerar
validación del token y configuración del firewall.

### D. Tarjetas de Workers

Cada celular debe mostrarse en una tarjeta individual con la información
que el navegador permita obtener:

-   Identificador del Worker.
-   Modelo del dispositivo, si está disponible.
-   Sistema operativo o plataforma.
-   Navegador.
-   Número de núcleos lógicos, si está disponible.
-   Memoria estimada, si la API lo permite.
-   Estado: disponible, procesando, completado, desconectado o error.
-   Progreso individual.
-   Bloques procesados.
-   Tiempo de procesamiento.
-   Última comunicación.

**Importante:** no inventar información del hardware. Los navegadores
móviles restringen el acceso a ciertos datos; cuando un dato no esté
disponible, mostrar "No disponible".

### E. Procesamiento en tiempo real

Mostrar:

-   Archivo y tamaño.
-   Número de bloques generados.
-   Workers participantes.
-   Bloques pendientes, asignados y completados.
-   Progreso global e individual.
-   Tiempo transcurrido.
-   Velocidad de procesamiento en MB/s.
-   Tareas asignadas a cada Worker.

Los datos deben actualizarse en tiempo real mediante WebSockets.

### F. Resultados

Mostrar el conteo final de A, T, C y G, además del total de bases
procesadas.

Incluir también:

-   Nombre del archivo.
-   Fecha y hora de inicio y finalización.
-   Duración total.
-   Número de Workers participantes.
-   Tamaño del archivo.
-   Número de bloques.
-   Velocidad promedio.
-   Estado de la ejecución.
-   Opciones para exportar resultados en CSV y JSON.

### G. Historial

Registrar ejecuciones anteriores con archivo, fecha, duración, número de
Workers, estado y resultados.

## 5. Procesamiento del archivo

El sistema debe estar preparado para archivos `.fna` de hasta
aproximadamente 3 GB. Por ello:

-   Utilizar lectura **streaming/progresiva**; nunca cargar el archivo
    completo en memoria RAM.
-   Comenzar con bloques configurables de aproximadamente **16 MB** y
    ajustar el tamaño mediante pruebas.
-   Procesar correctamente el formato FASTA: ignorar encabezados y
    contar únicamente las bases válidas A, T, C y G.
-   Manejar correctamente los límites entre bloques y las líneas del
    archivo.
-   Generar identificadores únicos para las tareas.
-   Utilizar una cola dinámica de tareas: cuando un Worker termina un
    bloque, recibe otro disponible. No asumir que todos los celulares
    tienen la misma capacidad.
-   Cada Worker debe devolver el identificador de la tarea, el
    identificador del dispositivo, los conteos parciales y métricas
    relevantes.
-   El Master debe validar los resultados y evitar contabilizar dos
    veces una misma tarea.

### Tolerancia a fallos

Implementar mecanismos básicos para:

-   Detectar desconexiones mediante heartbeat o mensajes periódicos.
-   Identificar tareas que quedaron en ejecución cuando un Worker se
    desconecta.
-   Devolver esas tareas a la cola de pendientes y reasignarlas.
-   Evitar resultados duplicados mediante identificadores de tarea y
    validaciones idempotentes.

### Consideraciones de rendimiento

-   El archivo original permanece en el computador Master; solo se
    envían fragmentos a los celulares por la red Wi-Fi local.
-   La transferencia de datos puede convertirse en el principal cuello
    de botella, por lo que debe medirse por separado del tiempo de
    procesamiento.
-   Adaptar el tamaño de los bloques a las capacidades de los
    dispositivos.
-   Considerar que los navegadores móviles pueden limitar la memoria
    disponible y suspender pestañas en segundo plano.
-   Empezar las pruebas con archivos pequeños y aumentar progresivamente
    el tamaño hasta aproximarse a 3 GB.

## 6. Concurrencia y distribución

Distinguir claramente dos conceptos:

1.  **Distribución:** el Master reparte tareas entre diferentes
    teléfonos.
2.  **Concurrencia local:** cada teléfono puede procesar mediante
    JavaScript Web Workers para no bloquear su interfaz.

No afirmar que JavaScript Web Workers equivalen a hilos nativos de
Android. Explicar sus capacidades y limitaciones reales.

## 7. Evaluación del proyecto

Implementar pruebas comparativas con:

-   Procesamiento secuencial en el computador Master.
-   Procesamiento distribuido con 1 celular.
-   Procesamiento distribuido con 2 celulares.
-   Procesamiento distribuido con 3 celulares.
-   Procesamiento distribuido con 4 o más celulares, según
    disponibilidad.

Medir y comparar:

-   Tiempo total.
-   Speedup.
-   Eficiencia.
-   Velocidad en MB/s.
-   Tiempo de transferencia.
-   Exactitud de los resultados.

No asumir que agregar celulares siempre mejora el rendimiento: la
transferencia por Wi-Fi y las capacidades de cada dispositivo pueden
reducir o incluso anular la ganancia.

## 8. Criterios de diseño

Mantener separadas las responsabilidades de:

-   Procesamiento de archivos.
-   Coordinación y asignación de tareas.
-   Comunicación entre nodos.
-   Gestión de Workers.
-   Persistencia e historial.
-   Interfaz web.

Diseñar interfaces y módulos que permitan incorporar almacenamiento o
servicios Cloud en el futuro sin rehacer el núcleo del sistema.

No depender de servicios externos para que funcione la primera versión.
La primera versión debe operar completamente dentro de la red local.

## 9. Forma de trabajo solicitada

Quiero que trabajemos por fases y que me expliques las decisiones
técnicas con claridad, porque es un proyecto académico que debo
implementar, probar y defender.

**Primero**, analiza la arquitectura propuesta, identifica riesgos y
limitaciones, define cómo se comunicarán los nodos, qué información
intercambiarán y cómo se organizará el proyecto. Presenta también una
estructura de carpetas y un plan de implementación por fases.

**Después**, construye el sistema progresivamente. En cada fase:

-   Explica qué vamos a desarrollar y por qué.
-   Indica qué archivos crear o modificar.
-   Proporciona el código completo necesario.
-   Da instrucciones concretas para ejecutar y probar.
-   Incluye pruebas para verificar que la funcionalidad realmente
    trabaja.
-   Espera mi confirmación antes de avanzar a la siguiente fase.

No generes todo el proyecto de una sola vez ni avances sin validar las
etapas anteriores.

## Prioridades

1.  Que el procesamiento distribuido entre celulares sea real y
    verificable.
2.  Que la arquitectura aplique correctamente los conceptos de Fog
    Computing.
3.  Que el sistema soporte archivos grandes mediante streaming.
4.  Que exista comunicación, coordinación y monitoreo en tiempo real.
5.  Que el dashboard tenga una apariencia profesional y clara.
6.  Que la arquitectura permita integrar Cloud en el futuro, sin
    implementarla ahora.
