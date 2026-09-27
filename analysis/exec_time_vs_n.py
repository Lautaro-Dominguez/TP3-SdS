"""Punto 1.1: tiempo de ejecución en función de N.

Para el sistema SIN obstáculos, corre sim.app.SimulateMain con tiempo de sistema fijo tf=30s,
para N en un barrido de a --step (N = step, 2*step, 3*step, ...), al menos --reps realizaciones
independientes por N (posiciones iniciales nuevas y sin semilla fija en cada una, como en TP2:
"la aleatoriedad por defecto de la JVM"). Mide el tiempo de pared (wall-clock) del proceso
SimulateMain en sí (no de GenerateMain, que se corre antes sin cronometrar) vía
time.perf_counter() alrededor del subprocess. Cada corrida usa --saveEvery 1 (graba cada
colisión, igual que el resto del TP), así que el tiempo medido incluye ese I/O - es el tiempo
real de correr el programa tal cual, no solo el cómputo de la física.

El N máximo de la barrida no se fija a mano: cada repetición individual (un par
generate+simulate) tiene un timeout de --timeout-min minutos. En cuanto UNA repetición de un N
se pasa de ese timeout, O el generador no logra ubicar las N partículas sin superposición
(ParticlePlacer agota sus intentos cuando la densidad pedida ya es demasiado alta para la mesa -
GenerateMain sale con RuntimeError en vez de colgarse), ese N se descarta entero (no se grafica,
aunque otras repeticiones suyas ya hayan terminado) y la barrida corta ahí - el N anterior, que
sí completó todas sus --reps realizaciones, queda como el máximo.

Genera dos gráficos a partir de --out: uno en escala lineal (el path tal cual) y otro en
escala log-log ("{stem}_log{suffix}"), útil para leer la complejidad algorítmica de la curva.

Las corridas son secuenciales (no en paralelo): correr varios `java` concurrentes en la misma
máquina distorsionaría la medición de tiempo de pared de cada uno.

Uso:
    python3 exec_time_vs_n.py --out output/exec_time_vs_n.png
    python3 exec_time_vs_n.py --step 10 --reps 10 --tmax 30 --timeout-min 10 \
        --out output/exec_time_vs_n.png
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_java import generate, simulate


def time_one_run(n, l, w, tmax, workdir, timeout_min):
    """Corre una realización (generate + simulate) con un timeout propio de timeout_min
    minutos, contado desde que arranca esta función. Devuelve el tiempo de pared (s) de
    SimulateMain solo, o deja propagar subprocess.TimeoutExpired si no llega a tiempo."""
    particles = workdir / f"particles_N{n}.txt"
    props = workdir / f"properties_N{n}.txt"
    deadline = time.perf_counter() + timeout_min * 60

    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        raise subprocess.TimeoutExpired(cmd="generate", timeout=timeout_min * 60)
    generate(n, l, w, particles, props, timeout=remaining)

    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        raise subprocess.TimeoutExpired(cmd="simulate", timeout=timeout_min * 60)
    t0 = time.perf_counter()
    simulate(l, w, particles, props, particles, tmax, save_every=1, timeout=remaining)
    return time.perf_counter() - t0


def save_plot(ns, means, stds, out_path, tmax, reps, log_scale):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(ns, means, yerr=stds, marker="o", capsize=3)
    if log_scale:
        ax.set_xscale("log")
        ax.set_yscale("log")
    ax.set_xlabel("N")
    ax.set_ylabel(f"tiempo de ejecución (s) hasta tf={tmax:g}s")
    ax.set_title(f"Tiempo de ejecución vs N (sin obstáculos, {reps} realizaciones/N)"
                 + (" - escala log-log" if log_scale else ""))
    ax.grid(True, which="both" if log_scale else "major", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Grafico guardado en {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=int, default=10, help="incremento de N (N = step, 2*step, ...)")
    parser.add_argument("--reps", type=int, default=10, help="realizaciones independientes por N")
    parser.add_argument("--tmax", type=float, default=30.0, help="tf, tiempo de sistema fijo")
    parser.add_argument("--timeout-min", type=float, default=10.0,
                         help="timeout (minutos) por CADA realización individual")
    parser.add_argument("--L", type=float, default=1.20)
    parser.add_argument("--W", type=float, default=0.68)
    parser.add_argument("--out", required=True, help="PNG de salida (escala lineal); "
                         "la version log-log se guarda junto con sufijo _log")
    parser.add_argument("--workdir", default=None,
                         help="directorio para los .txt temporales (default: uno nuevo en /tmp)")
    parser.add_argument("--keep-workdir", action="store_true",
                         help="no borrar el workdir temporal al terminar")
    args = parser.parse_args()

    own_tmp = args.workdir is None
    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="exec_time_vs_n_"))
    workdir.mkdir(parents=True, exist_ok=True)

    ns, means, stds = [], [], []
    try:
        n = args.step
        while True:
            times = []
            give_up_reason = None
            for rep in range(args.reps):
                try:
                    t = time_one_run(n, args.L, args.W, args.tmax, workdir, args.timeout_min)
                except subprocess.TimeoutExpired:
                    give_up_reason = f"una repeticion supero el timeout de {args.timeout_min:g} min"
                    break
                except RuntimeError as exc:
                    # Generalmente ParticlePlacer agotando sus intentos (densidad demasiado alta
                    # para que las N partículas entren sin superponerse) - GenerateMain sale con
                    # returncode != 0 y run_java._run lo envuelve en RuntimeError. Tratarlo igual
                    # que un timeout: este N no se puede completar, se corta la barrida acá.
                    give_up_reason = f"GenerateMain/SimulateMain fallaron: {exc}"
                    break
                times.append(t)
                print(f"N={n} rep={rep + 1}/{args.reps} -> {t:.3f}s")

            if give_up_reason is not None:
                print(f"N={n}: {give_up_reason} - se descarta este N y se corta la barrida aca.")
                break

            times = np.array(times)
            mean = times.mean()
            std = times.std(ddof=1) if len(times) > 1 else 0.0
            ns.append(n)
            means.append(mean)
            stds.append(std)
            print(f"N={n}: {mean:.3f}s +- {std:.3f}s (n={args.reps})")
            n += args.step
    finally:
        if own_tmp and not args.keep_workdir:
            shutil.rmtree(workdir, ignore_errors=True)

    if not ns:
        raise SystemExit(
            f"Ni N={args.step} completo sus {args.reps} realizaciones (timeout o fallo del "
            f"generador) - no hay nada para graficar.")

    print(f"N maximo alcanzado: {ns[-1]}")

    out = Path(args.out)
    log_out = out.with_name(out.stem + "_log" + out.suffix)
    save_plot(ns, means, stds, out, args.tmax, args.reps, log_scale=False)
    save_plot(ns, means, stds, log_out, args.tmax, args.reps, log_scale=True)


if __name__ == "__main__":
    main()
