# Plan del proyecto: Fog Computing para conteo distribuido de ADN

Fase 0 (análisis). Las fases siguientes se construyen una a una, y cada una espera tu confirmación.

## 1. Arquitectura

```
   Cloud (futuro, no se implementa)      interfaz Storage (hoy: SQLite local)
                    ▲
   ┌────────────────┴─────────────────┐
   │ FOG · Master (laptop, FastAPI)   │  archivo .fna (se queda aquí, lectura por streaming)
   │  - cola de tareas y planificador │  - HTTP: sirve bloques y la web
   │  - registro de workers, tokens   │  - WebSocket: control y monitoreo
   │  - consolidación e historial     │
   └───────┬─────────────┬────────────┘
      Wi-Fi local     Wi-Fi local
   ┌───────┴───┐   ┌─────┴─────┐
   │ EDGE      │   │ EDGE      │   navegador del celular (PWA)
   │ Worker 1  │   │ Worker 2  │   página → Web Worker (cuenta A/T/C/G)
   └───────────┘   └───────────┘
```

Un solo origen: el Master sirve en el puerto 5000 el dashboard (`/`), la página del celular (`/worker`), la API (`/api`)
y el WebSocket (`/ws`). Así no hay CORS y el QR apunta a una única URL.

## 2. Comunicación

- **WebSocket (`/ws/worker`, `/ws/dashboard`)**: mensajes JSON de control. Son pequeños.
- **HTTP (`GET /api/blocks/{task_id}`)**: el celular descarga el bloque binario. No se envían 16 MB por WebSocket: no se
  bloquea el canal de control (heartbeat) mientras se transfiere, y se puede medir la transferencia por separado.
- **Flujo del worker (pull)**: el celular pide trabajo cuando está libre. La cola dinámica surge sola: el que termina
  primero recibe más, sin suponer capacidades iguales.

Mensajes (JSON, campo `type`):

| De → a | `type` | Contenido |
|---|---|---|
| worker → master | `hello` | token, `worker_id` guardado en localStorage (si existe), capacidades que el navegador permite (`hardwareConcurrency`, `deviceMemory`, `userAgent`, plataforma; ausentes = «No disponible») |
| master → worker | `welcome` | `worker_id`, intervalo de heartbeat, URL base |
| worker → master | `heartbeat` | `worker_id`, estado, progreso |
| worker → master | `request_task` | `worker_id` |
| master → worker | `task` | `task_id`, `session_id`, `offset`, `length`, URL del bloque |
| master → worker | `no_task` | sin trabajo pendiente (espera) |
| worker → master | `result` | `task_id`, `worker_id`, conteos A/T/C/G, bytes, `t_transfer_ms`, `t_proceso_ms` |
| master → worker | `ack` / `reject` | resultado aceptado o duplicado/inválido |
| master → dashboard | `state` | estado completo o diferencial (workers, bloques, progreso, MB/s) |

Estados de una tarea: `pendiente → asignada → completada`. Si el worker se cae, `asignada → pendiente`.

## 3. Decisiones técnicas y por qué

1. **Bloques alineados a salto de línea.** El Master lee `offset..offset+16 MB` y extiende hasta el siguiente `\n`.
   Cada bloque empieza al inicio de una línea. Así ninguna línea de encabezado (`>`) queda partida y el conteo es exacto.
   Dentro del bloque se ignoran las líneas que empiezan con `>`.
2. **Cuenta de bases.** Solo A, T, C, G. Las minúsculas (soft-masking) se cuentan como la misma base; N, IUPAC y otros se
   reportan aparte como «otros», sin entrar al total de A/T/C/G. Se documenta y se prueba.
3. **El Master nunca carga el archivo entero.** Lee por `seek` y bloque. Los offsets se generan perezosamente (no hay lista
   de 190 tareas en memoria hasta que haga falta, aunque 3 GB / 16 MB son solo ~190 tareas).
4. **Idempotencia.** `task_id` único por (sesión, índice de bloque). El resultado se acepta solo si la tarea está
   `asignada` a ese worker o `pendiente` por reasignación y aún no `completada`. Un duplicado recibe `reject` y no suma.
5. **Tolerancia a fallos.** Heartbeat cada 3 s; un worker sin señal por 10 s se marca `desconectado` y sus tareas
   `asignadas` vuelven a la cola. Si reaparece con un resultado de una tarea ya reasignada, se aplica la regla anterior.
6. **Procesamiento del celular.** La página descarga el bloque como `ArrayBuffer` y se lo pasa (transferible, sin copia)
   al Web Worker, que cuenta con una tabla de búsqueda sobre `Uint8Array`. Los Web Workers dan ejecución en segundo plano
   respecto de la interfaz; no son hilos nativos de Android ni garantizan paralelismo por núcleo. El navegador puede
   suspenderlos.
7. **Persistencia.** SQLite detrás de una interfaz `Storage` (sesiones, tareas, resultados). Una implementación Cloud
   futura sustituye esa clase sin tocar el planificador.
8. **Pila (simplificada el 24-11 por pedido de «lo más sencillo y con menos recursos»).** Python 3.12 + FastAPI + Uvicorn
   + NumPy en el Master; HTML, CSS y JavaScript sin paso de compilación para el dashboard y la página del celular (sin
   Node ni React: menos instalación y nada que construir); QR generado en el Master con `segno` (SVG); Web Workers
   nativos. Las secciones A-G del dashboard no cambian.
9. **Sistema dinámico.** Los celulares entran y salen en cualquier momento, también con el procesamiento en marcha. Un
   celular nuevo se registra por QR y empieza a pedir bloques de la cola; uno que se desconecta devuelve sus bloques
   asignados a la cola, que toma otro. Como el reparto es por demanda, no hay una asignación fija que rehacer. Se
   demuestra con una prueba: sumar un celular a mitad de corrida y quitar otro, con el conteo final exacto.

## 4. Riesgos y limitaciones (a declarar en la defensa)

| Riesgo | Efecto | Mitigación |
|---|---|---|
| **El Wi-Fi es el cuello de botella.** Contar bases en un celular es mucho más rápido que mover el bloque por Wi-Fi. | Probablemente el speedup sea < 1 frente al Master secuencial. | Medir transferencia y proceso por separado; reportar el resultado tal como sale; no tocar la prueba para que «gane». |
| Aislamiento de clientes en redes Wi-Fi (universidad, casa con «AP isolation») | Los celulares no ven el Master. | Usar el hotspot de un celular o un router propio; verificar con `ping` antes. |
| Firewall de Windows | Bloquea el puerto 5000. | Regla de entrada para el puerto 5000 en red privada. |
| Contexto no seguro (HTTP) | `navigator.deviceMemory` y Wake Lock no están disponibles. | Mostrar «No disponible»; pedir mantener la pantalla encendida; documentarlo. |
| Pestaña en segundo plano o pantalla apagada | El navegador suspende la página y el worker deja de latir. | Heartbeat + reasignación; recomendación de pantalla activa. |
| Varias interfaces de red en el laptop (VPN, adaptadores virtuales) | El QR puede apuntar a una IP que el celular no alcanza. | Detectar la IP de la red local y permitir elegirla en el dashboard. |
| Memoria del navegador móvil | Bloques de 16 MB pueden fallar en equipos modestos. | Tamaño de bloque configurable; pruebas con 4, 8 y 16 MB. |
| Token en la URL | Cualquiera en la red con el enlace se une. | Token temporal (expira en minutos) y de un solo propósito; se renueva al abrir «Agregar dispositivo». |

## 5. Estructura de carpetas

```
ProyectoFinal/
  PLAN.md  proyecto_fog_computing_adn.md  README.md
  master/
    app/
      main.py            arranque FastAPI, rutas estáticas
      config.py          puerto, tamaño de bloque, tiempos de heartbeat
      fasta/             lector por streaming, bloques alineados, conteo (sin red)
      scheduler/         cola de tareas, estados, reasignación
      workers/           registro, heartbeat, tokens
      transport/         WebSocket y rutas HTTP de bloques
      storage/           interfaz Storage + SQLite
      export/            CSV y JSON
    tests/               pytest
  web/
    dashboard/           index.html, estilos y JS: panel, carga, QR, tarjetas, tiempo real, resultados, historial
    worker/              página del celular (worker.html) y conteo.js (Web Worker)
  tools/
    generar_fna.py       crea archivos .fna de prueba (con respuesta conocida)
    benchmark.py         secuencial y distribuido, tablas de speedup
  data/                  archivos de prueba y base SQLite (no se versionan)
```

## 6. Fases

- [x] **Fase 1: motor de archivos** (hecha 24-11) (sin red). Generador de `.fna` con conteo conocido, lector por streaming, bloques
  alineados, conteo secuencial de referencia, pruebas (bordes de bloque, encabezados, minúsculas, N, sin salto final).
- [x] **Fase 2: Master mínimo (hecha 24-11).** FastAPI, sesiones, tokens, registro de workers, WebSocket, heartbeat, descarga de bloques.
  Prueba con un cliente Python simulado solo para el protocolo.
- [x] **Fase 3: página del celular (hecha 24-11, falta probar con celulares reales).** Escaneo, `hello`, Web Worker de conteo, ciclo pedir-descargar-contar-enviar.
  Prueba real de extremo a extremo con un celular y un archivo pequeño; se compara con el conteo secuencial.
- [ ] **Fase 4: tolerancia a fallos e idempotencia.** Matar un celular a media tarea, duplicados, reconexión. Pruebas.
- [x] **Fase 5: dashboard (hecha 24-11; sin sección G, que va en la Fase 6).** Secciones A-F con diseño estilo macOS, QR dinámico, tarjetas de workers, tiempo real.
- [x] **Fase 6: persistencia e historial (hecha 24-11).** SQLite, historial (G), exportación CSV/JSON.
- [~] **Fase 7: evaluación (herramientas listas y línea base medida; faltan las corridas con celulares, ver EVALUACION.md).** Secuencial frente a 1, 2, 3 y 4 celulares; tiempo total, speedup, eficiencia, MB/s,
  transferencia, exactitud; escalar hasta cerca de 3 GB; ajuste del tamaño de bloque.
- [ ] **Fase 8: cierre.** README de ejecución, diagrama final, notas para la defensa.

## 7. Datos de entrada (respondido)

Tiene un `.fna` real de ~3 GB y uno pequeño; el profesor dejó la tecnología abierta. Falta: cuántos celulares y qué
red (router u hotspot) usará en la Fase 3.

## 8. (original) Qué necesitaba antes de la Fase 1

1. Cuántos celulares reales tendrás para las pruebas y si hay un router o hotspot disponible.
2. Si tienes un `.fna` real (por ejemplo del NCBI) o prefieres solo los generados.
3. Si el profesor exige alguna tecnología distinta de la propuesta.
