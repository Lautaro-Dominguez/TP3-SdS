# TP3 — Billar-Metegol: generador + motor de simulación

Java plano, sin dependencias externas ni Maven — solo `javac`/`java`.

## Compilar

Desde `TP3/`:

```bash
javac -d out $(find src -name "*.java")
```

Esto compila todo a `out/`. No hace falta recompilar entre corridas mientras no cambie el código.

## 1) Generar el estado inicial

```bash
java -cp out sim.app.GenerateMain --N 100 \
    [--L 1.20] [--W 0.68] [--r 0.0175] [--m 0.025] [--v0 1.0] \
    [--obstacles obstaculos.txt] [--seed 42] \
    [--outState output/particles.txt] [--outProps output/properties.txt]
```

- `--N` es el único flag obligatorio.
- `--L`/`--W` (largo/ancho de la mesa), `--r` (radio de partícula), `--m` (masa), `--v0` (módulo
  de velocidad inicial) tienen como default los valores fijos del enunciado — normalmente no
  hace falta pasarlos.
- `--obstacles` es opcional: un `.txt` con una línea `x y R` por obstáculo (ver formato abajo). Si
  se omite, la mesa se genera sin obstáculos.
- `--seed` es opcional (si no se pasa, usa `System.nanoTime()` — no reproducible entre corridas).
- Ubica las N partículas sin superponerse entre sí ni con los obstáculos, todas "frescas"
  (azules), con ángulo uniforme en `[0, 2π)` y velocidad de módulo `v0`.
- Escribe dos archivos: el de trayectoria (`--outState`, bloque inicial `t=0`) y el de
  propiedades (`--outProps`, masa y radio por partícula).

## 2) Correr la simulación

```bash
java -cp out sim.app.SimulateMain \
    [--L 1.20] [--W 0.68] [--d 0.20] \
    [--in output/particles.txt] [--props output/properties.txt] [--obstacles obstaculos.txt] \
    [--tmax 100] [--saveEvery 1] [--out output/particles.txt]
```

- `--L`/`--W`/`--d` (longitud del arco) deben coincidir con los usados al generar.
- `--in`/`--props`/`--obstacles` apuntan a los archivos del paso 1 (mismo `--obstacles`, si se
  usó uno).
- `--tmax`: tiempo de **sistema** (no de ejecución) hasta el cual simular. Si se omite, corre
  hasta que el 100% de las partículas queden usadas.
- `--saveEvery`: cada cuántos eventos aceptados se graba un bloque de estado en el archivo de
  trayectoria (default 1 = graba todos). Con `--saveEvery 1` se puede reconstruir `Fu(t)`/`t90`
  con precisión exacta; con valores mayores el archivo pesa menos pero se pierde resolución
  temporal entre eventos.
- `--out` (default: igual a `--in`): el archivo de trayectoria se extiende in-place agregando un
  bloque por cada guardado — si se pasa un `--out` distinto, primero copia el bloque inicial ahí.
- Al final imprime cantidad de eventos procesados, tiempo de sistema alcanzado y partículas
  usadas.

## 3) Animar (Python)

Todo vive en `analysis/`. Requiere `numpy` y `matplotlib` (`pip install --user numpy matplotlib`).
Lee el `.txt` que ya escribió el motor Java — no reimplementa nada de `sim/`.

```bash
python3 analysis/animate.py --traj output/particles.txt \
    [--obstacles output/obstaculos.txt] \
    [--L 1.20] [--W 0.68] [--d 0.20] [--r 0.0175] \
    --out output/animacion.gif [--stride 1] [--speed 1.0] [--min-duration 20] [--fps 15]
```

- `--traj` y `--out` son obligatorios; el resto tiene como default los valores fijos del
  enunciado.
- `--L`/`--W`/`--d`/`--r` deben coincidir con los usados al generar/simular.
- `--obstacles` es opcional — si la corrida tuvo obstáculos, dibuja cada uno como un círculo gris
  fijo.
- `--stride N` anima 1 de cada N bloques guardados (útil si se corrió con `--saveEvery 1` y el
  archivo tiene muchos bloques) — sigue usando solo bloques reales del txt, nunca posiciones
  intermedias calculadas por MRU.
- Cada frame es exactamente un bloque del archivo; como el Δt entre bloques es irregular
  (motor event-driven), cada uno se mantiene en pantalla un tiempo proporcional a su Δt real en
  vez de una duración fija — `--speed` escala tiempo real de simulación a tiempo de video (1.0 =
  tiempo real), `--min-duration` pone un piso en ms para que un Δt casi nulo no genere un frame
  ilegible, y `--fps` solo define cuánto dura en pantalla el último frame (no tiene un Δt real
  siguiente del cual derivar su duración).
- Dibuja las paredes, el arco (segmento dorado) en cada pared corta, los obstáculos (si los hay)
  y una partícula por círculo — azul mientras está fresca, rojo desde que toca el arco por
  primera vez. El título de cada frame muestra `t` y la fracción de partículas ya usadas.

## 4) Punto 1.1 — tiempo de ejecución vs N

Requiere `numpy` y `matplotlib` (igual que el punto anterior). Corre `GenerateMain`/
`SimulateMain` como subproceso vía `analysis/run_java.py` y cronometra cada corrida con
`time.perf_counter()`.

```bash
python3 analysis/exec_time_vs_n.py \
    [--n-min 10] [--n-max 300] [--n-step 10] [--reps 10] [--tmax 30] \
    [--L 1.20] [--W 0.68] --out output/exec_time_vs_n.png
```

- Sin obstáculos, mesa y radio reales de la consigna. `N` va de `--n-min` a `--n-max` en pasos de
  `--n-step` — el rango por default (10 a 300) es el máximo razonable para esta mesa: con
  `r=0.0175` fijo, `N=2000` (como pide literalmente la letra del punto 1.1) necesitaría más del
  200% de densidad de empaquetamiento en los 0.816 m² de la mesa, imposible incluso con
  empaquetamiento hexagonal perfecto (máximo teórico ~90.7%, `N≈769`).
- Por cada `N`, corre `--reps` realizaciones independientes (posición inicial nueva y sin semilla
  fija en cada una) hasta el tiempo de sistema fijo `--tmax` (`tf`), midiendo solo el tiempo de
  `SimulateMain` (la generación previa no se cronometra). Cada corrida graba con `--saveEvery 1`,
  como el resto del TP, así que el tiempo medido incluye ese I/O.
- Grafica el tiempo de ejecución promedio por `N` con barras de error (desvío estándar muestral
  entre las `--reps` realizaciones).
- Las corridas son secuenciales para no distorsionar la medición de tiempo de pared.

## Formato de archivos

**Trayectoria** (`particles.txt`): crece en bloques, uno por cada guardado.
```
t_e
x1 y1 v1 color1 theta1
...
xn yn vn colorn thetan
```
El header de cada bloque es el tiempo real de sistema `t_e` (no un índice), `v` es el módulo de
la velocidad, `theta` el ángulo en `[0, 2π)`, y `color` es `"azul"` (fresca) o `"rojo"` (usada —
ya tocó el arco al menos una vez).

**Propiedades** (`properties.txt`): una línea por partícula, sin header, mismo orden que las filas
de la trayectoria.
```
m1 r1
...
mn rn
```

**Obstáculos** (`obstaculos.txt`, opcional, entrada externa — no la genera este programa):
```
x1 y1 R1
...
xm ym Rm
```
