"""Punto 1.1: tiempo de ejecución en función de N.

Para el sistema SIN obstáculos, corre sim.app.SimulateMain con tiempo de sistema fijo tf=30s,
para N en un barrido, al menos --reps realizaciones independientes por N (posiciones iniciales
nuevas y sin semilla fija en cada una, como en TP2: "la aleatoriedad por defecto de la JVM").
Mide el tiempo de pared (wall-clock) del proceso SimulateMain en sí (no de GenerateMain, que se
corre antes sin cronometrar) vía time.perf_counter() alrededor del subprocess. Cada corrida usa
--saveEvery 1 (graba cada colisión, igual que el resto del TP), así que el tiempo medido incluye
ese I/O - es el tiempo real de correr el programa tal cual, no solo el cómputo de la física.
Grafica el promedio +- desvío estándar en función de N.

Las corridas son secuenciales (no en paralelo): correr varios `java` concurrentes en la misma
máquina distorsionaría la medición de tiempo de pared de cada uno.

Uso:
    python3 exec_time_vs_n.py --out output/exec_time_vs_n.png
    python3 exec_time_vs_n.py --n-min 10 --n-max 300 --n-step 10 --reps 10 --tmax 30 \
        --out output/exec_time_vs_n.png
"""
from __future__ import annotations

import argparse
import shutil
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


def time_one_run(n, l, w, tmax, workdir):
    particles = workdir / f"particles_N{n}.txt"
    props = workdir / f"properties_N{n}.txt"
    generate(n, l, w, particles, props)

    t0 = time.perf_counter()
    simulate(l, w, particles, props, particles, tmax, save_every=1)
    return time.perf_counter() - t0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-min", type=int, default=10)
    parser.add_argument("--n-max", type=int, default=300)
    parser.add_argument("--n-step", type=int, default=10)
    parser.add_argument("--reps", type=int, default=10, help="realizaciones independientes por N")
    parser.add_argument("--tmax", type=float, default=30.0, help="tf, tiempo de sistema fijo")
    parser.add_argument("--L", type=float, default=1.20)
    parser.add_argument("--W", type=float, default=0.68)
    parser.add_argument("--out", required=True, help="PNG de salida")
    parser.add_argument("--workdir", default=None,
                         help="directorio para los .txt temporales (default: uno nuevo en /tmp)")
    parser.add_argument("--keep-workdir", action="store_true",
                         help="no borrar el workdir temporal al terminar")
    args = parser.parse_args()

    ns = list(range(args.n_min, args.n_max + 1, args.n_step))

    own_tmp = args.workdir is None
    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="exec_time_vs_n_"))
    workdir.mkdir(parents=True, exist_ok=True)

    means, stds = [], []
    try:
        for n in ns:
            times = []
            for rep in range(args.reps):
                t = time_one_run(n, args.L, args.W, args.tmax, workdir)
                times.append(t)
                print(f"N={n} rep={rep + 1}/{args.reps} -> {t:.3f}s")
            times = np.array(times)
            mean = times.mean()
            std = times.std(ddof=1) if len(times) > 1 else 0.0
            means.append(mean)
            stds.append(std)
            print(f"N={n}: {mean:.3f}s +- {std:.3f}s (n={args.reps})")
    finally:
        if own_tmp and not args.keep_workdir:
            shutil.rmtree(workdir, ignore_errors=True)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(ns, means, yerr=stds, marker="o", capsize=3)
    ax.set_xlabel("N")
    ax.set_ylabel(f"tiempo de ejecución (s) hasta tf={args.tmax:g}s")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"Grafico guardado en {args.out}")


if __name__ == "__main__":
    main()
