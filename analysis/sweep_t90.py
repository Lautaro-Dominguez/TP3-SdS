"""Punto 1.2: exploración del espacio de configuraciones de obstáculos.

Para cada configuración de una familia (un "barrido") corre M realizaciones independientes con
N=100 partículas y mide t90 - el tiempo en que Fu(t) = N_g(t)/N alcanza 0.9 - reportando

    <t90> = (1/M) sum_m t90^(m)
    sigma = sqrt( (1/(M-1)) sum_m (t90^(m) - <t90>)^2 )        (desvío estándar muestral)

contra la variable estudiada, y comparando contra la mesa vacía. El enunciado pide al menos 5
realizaciones por configuración.

t90 lo devuelve el propio motor en stdout ("t90 <valor> ng <goles>"), así que no hace falta
escribir ni parsear trayectorias: las corridas usan --saveEvery 0. Si Fu no llega a 0.9 antes de
tmax el motor reporta t90 = NaN (caso "censurado"), que es el que el enunciado manda rankear por
número promedio de goles a tmax.

Los barridos disponibles (ver obstacle_configs.py):
    b       radio de un obstáculo centrado
    a       posición de un obstáculo sobre el eje longitudinal
    c       n obstáculos de área total fija, n creciente
    d-xf    embudo hacia los arcos, variando la distancia a la pared
    d-delta embudo hacia los arcos, variando la luz respecto del arco
    vacia   solo la mesa vacía (referencia)

Uso:
    python3 analysis/sweep_t90.py --barrido b --out output/1_2b_radio.png
    python3 analysis/sweep_t90.py --barrido c --R1 0.10 --reps 10 --out output/1_2c_n.png
"""
from __future__ import annotations

import argparse
import math
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obstacle_configs as oc
from run_java import generate, _run

N_PARTICLES = 100


def _simulate_t90(in_path, props_path, obstacles, tmax, l, w, d):
    """Corre SimulateMain sin trayectoria y devuelve (t90, N_g(tmax)) leídos de stdout."""
    flags = {
        "L": l, "W": w, "d": d,
        "in": in_path, "props": props_path,
        "tmax": tmax, "saveEvery": 0,
    }
    if obstacles is not None:
        flags["obstacles"] = obstacles
    stdout = _run("sim.app.SimulateMain", flags)
    for line in reversed(stdout.strip().splitlines()):
        tokens = line.split()
        if len(tokens) == 4 and tokens[0] == "t90" and tokens[2] == "ng":
            return float(tokens[1]), int(tokens[3])
    raise RuntimeError(f"SimulateMain no reporto t90:\n{stdout}")


def one_realization(config_path, rep, seed, workdir, tmax, l, w, d, n=N_PARTICLES):
    """Una realización: estado inicial nuevo + simulación. Devuelve (t90, N_g(tmax))."""
    tag = f"{Path(config_path).stem if config_path else 'vacia'}_rep{rep}"
    particles = workdir / f"{tag}_p.txt"
    props = workdir / f"{tag}_props.txt"
    generate(n, l, w, particles, props, obstacles=config_path, seed=seed)
    try:
        return _simulate_t90(particles, props, config_path, tmax, l, w, d)
    finally:
        particles.unlink(missing_ok=True)
        props.unlink(missing_ok=True)


def measure(config, label, workdir, reps, tmax, seed0, jobs, l=oc.L, w=oc.W, d=oc.D,
            allow_empty=False):
    """M realizaciones de una configuración -> (<t90>, sigma, t90s, n_censuradas, <N_g(tmax)>).

    Devuelve None si la configuración viola las restricciones (i)/(ii) del enunciado o si el
    generador no logra ubicar las N partículas (la parte empírica de la restricción ii).
    """
    problems = oc.violations(config, l, w, allow_empty=allow_empty)
    if problems:
        print(f"  {label}: CONFIGURACION INVALIDA -> {problems[0]}")
        return None

    config_path = None
    if config:
        config_path = workdir / f"{label}.txt"
        oc.write(config_path, config)

    def run(rep):
        return one_realization(config_path, rep, seed0 + rep, workdir, tmax, l, w, d)

    try:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(run, range(reps)))
    except RuntimeError as exc:
        print(f"  {label}: no se pudo simular -> {str(exc).splitlines()[0]}")
        return None

    t90s = np.array([t for t, _ in results])
    ngs = np.array([ng for _, ng in results])
    finite = t90s[np.isfinite(t90s)]
    censored = len(t90s) - len(finite)

    if len(finite) == 0:
        print(f"  {label}: las {reps} realizaciones quedaron censuradas "
              f"(Fu < 0.9 a t={tmax:g}s), <N_g> = {ngs.mean():.1f}")
        return dict(label=label, mean=math.nan, std=math.nan, sem=math.nan, t90s=t90s,
                    censored=censored, ng_mean=float(ngs.mean()))

    mean = float(finite.mean())
    # Con una sola realización no censurada no hay dispersión que reportar: sigma es indefinido,
    # no cero (informar 0.00 sugeriría una medición perfectamente reproducible).
    std = float(finite.std(ddof=1)) if len(finite) > 1 else math.nan
    sem = std / math.sqrt(len(finite)) if len(finite) > 1 else math.nan
    flag = f"  [{censored}/{reps} censuradas]" if censored else ""
    print(f"  {label}: <t90> = {mean:6.2f} +- {std:5.2f} s (sigma)   "
          f"error de la media = {sem:4.2f} s{flag}")
    return dict(label=label, mean=mean, std=std, sem=sem, t90s=t90s,
                censored=censored, ng_mean=float(ngs.mean()))


def build_sweep(args):
    """Devuelve (nombre_variable, [(valor, etiqueta, configuracion), ...]) para el barrido pedido."""
    if args.barrido == "vacia":
        return "mesa vacia", [(0, "vacia", [])]  # se mide via --no-baseline + allow_empty

    if args.barrido == "b":
        radii = np.round(np.arange(args.r_min, args.r_max + 1e-12, args.r_step), 6)
        return "R [m]", [(float(R), f"b_R{R:.4f}", oc.single_centered(float(R)))
                         for R in radii]

    if args.barrido == "a":
        xs = np.round(np.linspace(args.R, oc.L - args.R, args.a_points), 6)
        return "x del obstaculo [m]", [(float(x), f"a_x{x:.4f}", oc.single_longitudinal(float(x), args.R))
                                        for x in xs]

    if args.barrido == "c":
        total_area = math.pi * args.R1 ** 2
        n_max = oc.max_n_fixed_area(total_area)
        ns = [n for n in args.c_ns if n <= n_max]
        skipped = [n for n in args.c_ns if n > n_max]
        if skipped:
            print(f"n omitidos por R(n) < r (n_max = {n_max}): {skipped}")
        return "n obstaculos (area total fija)", [
            (n, f"c_n{n}", oc.grid_fixed_area(n, total_area)) for n in ns]

    if args.barrido == "d-xf":
        xs = np.round(np.linspace(args.R + args.delta, args.xf_max, args.d_points), 6)
        return "x_f [m]", [(float(x), f"dxf_{x:.4f}", oc.funnel(float(x), args.R, args.delta))
                           for x in xs]

    if args.barrido == "d-delta":
        deltas = np.round(np.linspace(0.0, args.delta_max, args.d_points), 6)
        return "delta [m]", [(float(dl), f"ddelta_{dl:.4f}", oc.funnel(args.xf, args.R, float(dl)))
                             for dl in deltas]

    raise ValueError(f"barrido desconocido: {args.barrido}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--barrido", required=True,
                        choices=["b", "a", "c", "d-xf", "d-delta", "vacia"])
    parser.add_argument("--reps", type=int, default=10,
                        help="realizaciones por configuracion (el enunciado pide >= 5)")
    parser.add_argument("--tmax", type=float, default=100.0, help="t_max, igual al de la competencia")
    parser.add_argument("--seed0", type=int, default=1000, help="semilla base (seed = seed0 + rep)")
    parser.add_argument("--jobs", type=int, default=4,
                        help="corridas en paralelo; seguro porque se mide tiempo de simulacion, "
                             "no de ejecucion")
    parser.add_argument("--no-baseline", action="store_true", help="no correr la mesa vacia")
    # barrido b
    parser.add_argument("--r-min", type=float, default=0.02)
    parser.add_argument("--r-max", type=float, default=0.30)
    parser.add_argument("--r-step", type=float, default=0.02)
    # barrido a / d
    parser.add_argument("--R", type=float, default=0.10, help="radio fijo en los barridos a y d")
    parser.add_argument("--a-points", type=int, default=11)
    # barrido c
    parser.add_argument("--R1", type=float, default=0.10,
                        help="radio del obstaculo unico equivalente: A_tot = pi R1^2")
    parser.add_argument("--c-ns", type=int, nargs="+", default=[1, 2, 4, 6, 8, 12, 16, 24, 32])
    # barrido d
    parser.add_argument("--delta", type=float, default=0.02, help="luz respecto del arco (barrido d-xf)")
    parser.add_argument("--xf-max", type=float, default=0.30)
    parser.add_argument("--xf", type=float, default=0.15, help="x_f fijo (barrido d-delta)")
    parser.add_argument("--delta-max", type=float, default=0.10)
    parser.add_argument("--d-points", type=int, default=6)
    parser.add_argument("--out", required=True, help="PNG de salida")
    parser.add_argument("--csv", default=None, help="donde guardar los resultados (default: junto al PNG)")
    parser.add_argument("--configdir", default="output/configs",
                        help="donde guardar los .txt de cada configuracion (los reusa el punto 1.3)")
    args = parser.parse_args()

    if args.reps < 5:
        print(f"AVISO: --reps {args.reps} esta por debajo del minimo de 5 que pide el enunciado.")

    xlabel, sweep = build_sweep(args)
    configdir = Path(args.configdir)
    configdir.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="sweep_t90_"))

    print(f"Barrido '{args.barrido}': {len(sweep)} configuraciones x {args.reps} realizaciones "
          f"(N={N_PARTICLES}, tmax={args.tmax:g}s)")

    results = []
    try:
        for value, label, config in sweep:
            res = measure(config, label, workdir, args.reps, args.tmax, args.seed0, args.jobs,
                           allow_empty=(args.barrido == "vacia"))
            if res is not None:
                res["value"] = value
                res["config"] = config
                results.append(res)
                if config:
                    oc.write(configdir / f"{label}.txt", config)

        baseline = None
        if not args.no_baseline and args.barrido != "vacia":
            print("Referencia:")
            baseline = measure([], "vacia", workdir, args.reps, args.tmax, args.seed0,
                                args.jobs, allow_empty=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if not results:
        raise SystemExit("ninguna configuracion del barrido resulto valida")

    csv_path = Path(args.csv) if args.csv else Path(args.out).with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w") as f:
        # t90_desvio es sigma (lo que se grafica como barra de error). t90_error_medio es
        # sigma/sqrt(M): no se grafica, pero es el que corresponde mirar para decidir si dos
        # configuraciones difieren de verdad, porque sigma no baja al agregar realizaciones.
        f.write("variable,etiqueta,t90_medio,t90_desvio,t90_error_medio,"
                "realizaciones,censuradas,ng_medio\n")
        for res in results:
            f.write(f"{res['value']},{res['label']},{res['mean']},{res['std']},{res['sem']},"
                    f"{args.reps},{res['censored']},{res['ng_mean']}\n")
        if baseline:
            f.write(f"nan,vacia,{baseline['mean']},{baseline['std']},{baseline['sem']},"
                    f"{args.reps},{baseline['censored']},{baseline['ng_mean']}\n")

    xs = [res["value"] for res in results]
    means = [res["mean"] for res in results]
    stds = [res["std"] for res in results]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(xs, means, yerr=stds, marker="o", capsize=3, label="configuracion con obstaculos")
    if baseline and math.isfinite(baseline["mean"]):
        ax.axhline(baseline["mean"], color="tab:red", linestyle="--",
                   label=f"mesa vacia: {baseline['mean']:.2f} s")
        ax.fill_between([min(xs), max(xs)],
                        baseline["mean"] - baseline["std"], baseline["mean"] + baseline["std"],
                        color="tab:red", alpha=0.15)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(r"$\langle t_{90} \rangle$ [s]")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150)

    best = min((r for r in results if math.isfinite(r["mean"])), key=lambda r: r["mean"], default=None)
    if best:
        print(f"\nMinimo del barrido: {best['label']} ({xlabel} = {best['value']}) -> "
              f"<t90> = {best['mean']:.2f} +- {best['std']:.2f} s")
    print(f"Grafico -> {args.out}\nDatos   -> {csv_path}\nConfigs -> {configdir}/")


if __name__ == "__main__":
    main()
