# Cómo correr la evaluación (Fase 7)

Todo se ejecuta desde `C:\Emi\Semestre 8\CP Nube\ProyectoFinal` en PowerShell. Cada corrida agrega una fila a
`data\evaluacion.csv`. Al final, `informe_benchmark.py` arma la tabla (`data\evaluacion.md`) y los gráficos
(`data\evaluacion_*.png`).

## Ya medido: línea base en el Master (secuencial)

Genoma humano GRCh38 (3,11 GB), 3 repeticiones con bloques de 16 MB: 22,4 / 22,8 / 22,3 s, es decir, unos 141 MB/s.
Para superarla con celulares, el conjunto tendría que recibir los 3,11 GB por Wi-Fi a más de unos 140 MB/s en total.

## Antes de empezar

1. Arranca el Master (ventana de PowerShell que queda abierta):
   `cd master` y luego `..\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 5000`
2. Abre el dashboard (`http://localhost:5000`) y conecta los celulares con «Agregar dispositivo».
3. Deja las pantallas encendidas y las pestañas abiertas. No uses los celulares para otra cosa durante la corrida.
4. Mismas condiciones en todas las corridas: mismo Wi-Fi, misma distancia al router, mismo tamaño de bloque.

## Corridas distribuidas (otra ventana de PowerShell)

Archivo de 200 MB (rápido, sirve para ensayar y para ver la tendencia):

    .venv\Scripts\python tools\benchmark.py secuencial data\prueba_200mb.fna --reps 3
    .venv\Scripts\python tools\benchmark.py distribuido prueba_200mb.fna --celulares 1 --bloque-mb 4 --reps 3

Archivo de 3 GB (la prueba principal). Con 1 celular conectado:

    .venv\Scripts\python tools\benchmark.py distribuido GCA_000001405.29_GRCh38.p14_genomic.fna --celulares 1 --bloque-mb 8 --reps 2

Luego conecta el segundo celular y repite con `--celulares 2`; después, con el tercero, `--celulares 3`.
El programa espera a que haya al menos esa cantidad de celulares conectados y recién ahí inicia.
Si un celular se cae a mitad de corrida, la corrida igual termina (el Master reasigna sus bloques) y queda anotada;
anótalo en `--nota "se cayó un celular"` para explicarlo en el informe.

## Ajuste del tamaño de bloque (opcional)

Con 1 celular y el archivo de 200 MB, prueba `--bloque-mb 1`, `4`, `8` y `16`, y elige el mejor para la corrida de 3 GB.
Esa elección se hace con el archivo pequeño, antes de ver los resultados del grande.

## Informe

    .venv\Scripts\python tools\informe_benchmark.py

La tabla incluye tiempo medio y rango, MB/s, speedup (= T secuencial / T distribuido), eficiencia (= speedup / N),
el tiempo de transferencia aparte del de procesamiento, y si el conteo coincide con la referencia (exactitud).

## Cómo interpretar

- Speedup menor que 1 significa que el Master solo fue más rápido. Es un resultado válido y esperable si la red es el
  cuello de botella; se informa tal cual.
- La transferencia es la suma de los tiempos de descarga de cada celular. Corren en paralelo, así que esa suma puede
  superar al tiempo total.
- No se descarta ninguna corrida por salir mal. Si hay una corrida atípica, se informa junto con las demás.
