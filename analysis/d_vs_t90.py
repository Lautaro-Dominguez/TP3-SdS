"""Punto 1.3: D vs <t90> para la mesa vacía y todas las configuraciones del punto 1.2.

Reusa los mismos barridos de `sweep_t90.py` (misma `build_sweep`, mismos defaults) para que cada
punto D vs t90 corresponda exactamente a una configuración ya explorada en 1.2, y así el
scatter final sea comparable punto a punto.

Para cada configuración:
  - <t90> y su desvío: `sweep_t90.measure` con --reps realizaciones completas (igual que 1.2).
  - D: UNA realización nueva (el enunciado pide "para una realización"), simulada solo hasta
    --fit-tmax + margen (no hace falta correrla hasta el final: el DCM ya satura mucho antes de
    t90, ver `msd.py`), y ajustada con `msd.fit_D` en la ventana [0, --fit-tmax].

Uso:
    python3 analysis/d_vs_t90.py --fit-tmax 3.0 --reps 5 --out output/d_vs_t90.png
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obstacle_configs as oc
from msd import compute_msd, fit_D
from run_java import generate, simulate
from sweep_t90 import build_sweep, measure

BARRIDOS = ["b", "a", "c", "d-xf", "d-delta"]
MARKERS = {"b": "o", "a": "s", "c": "^", "d-xf": "D", "d-delta": "v", "vacia": "*"}
COLORS = {"b": "tab:blue", "a": "tab:orange", "c": "tab:green", "d-xf": "tab:purple",
          "d-delta": "tab:brown", "vacia": "tab:red"}


def default_sweep_args():
    """Namespace con los mismos defaults que el parser de sweep_t90.py, para las 5 familias."""
    return argparse.Namespace(
        r_min=0.02, r_max=0.30, r_step=0.02,
        R=0.10, a_points=11,
        R1=0.10, c_ns=[1, 2, 4, 6, 8, 12, 16, 24, 32],
        delta=0.02, xf_max=0.30, xf=0.15, delta_max=0.10, d_points=6,
    )


def measure_D(config, label, workdir, fit_tmax, seed, l, w, d, n=100, margin=1.0):
    """UNA realización, simulada solo hasta fit_tmax+margin. Devuelve D o None si es invalida."""
    if oc.violations(config, l, w, allow_empty=True):
        return None
    config_path = None
    if config:
        config_path = workdir / f"{label}_D.txt"
        oc.write(config_path, config)
    particles = workdir / f"{label}_D_p.txt"
    props = workdir / f"{label}_D_props.txt"
    try:
        generate(n, l, w, particles, props, obstacles=config_path, seed=seed)
        simulate(l, w, particles, props, particles, tmax=fit_tmax + margin, save_every=1,
                 d=d, obstacles=config_path)
        ts, msd = compute_msd(particles)
        D, _c0, _c1 = fit_D(ts, msd, fit_tmax)
        return D
    finally:
        particles.unlink(missing_ok=True)
        props.unlink(missing_ok=True)
        if config_path:
            config_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fit-tmax", type=float, required=True,
                         help="ventana [0, fit-tmax] para el ajuste de D (elegida a mano, ver msd.py)")
    parser.add_argument("--reps", type=int, default=5, help="realizaciones para <t90> (igual que 1.2)")
    parser.add_argument("--tmax", type=float, default=100.0, help="tmax para <t90>, igual al de competencia")
    parser.add_argument("--seed0", type=int, default=1000)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--out", required=True, help="PNG de salida (scatter D vs t90)")
    parser.add_argument("--csv", default=None, help="default: junto al PNG")
    args = parser.parse_args()

    sweep_args = default_sweep_args()
    l, w, d = oc.L, oc.W, oc.D
    workdir = Path(tempfile.mkdtemp(prefix="d_vs_t90_"))

    points = [("vacia", "vacia", [])]
    for barrido in BARRIDOS:
        sweep_args.barrido = barrido
        _xlabel, sweep = build_sweep(sweep_args)
        for _value, label, config in sweep:
            points.append((barrido, label, config))

    results = []
    try:
        for barrido, label, config in points:
            allow_empty = barrido == "vacia"
            t90_res = measure(config, label, workdir, args.reps, args.tmax, args.seed0, args.jobs,
                               l=l, w=w, d=d, allow_empty=allow_empty)
            if t90_res is None:
                continue
            # semilla de D independiente de --reps: si dependiera de reps, cambiar reps por otro
            # motivo (ej. mas precision en t90) cambiaria la unica realizacion que define D.
            D = measure_D(config, label, workdir, args.fit_tmax, args.seed0 + 10_000, l, w, d)
            if D is None:
                continue
            results.append(dict(barrido=barrido, label=label, t90=t90_res["mean"],
                                 t90_std=t90_res["std"], D=D))
            print(f"  {label}: D={D:.5f}  <t90>={t90_res['mean']:.2f}+-{t90_res['std']:.2f}s")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if not results:
        raise SystemExit("ningun punto valido")

    csv_path = Path(args.csv) if args.csv else Path(args.out).with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w") as f:
        f.write("barrido,etiqueta,D,t90_medio,t90_desvio\n")
        for r in results:
            f.write(f"{r['barrido']},{r['label']},{r['D']},{r['t90']},{r['t90_std']}\n")

    fig, ax = plt.subplots(figsize=(8, 6))
    for barrido in ["vacia"] + BARRIDOS:
        pts = [r for r in results if r["barrido"] == barrido and r["t90"] == r["t90"]]  # descarta NaN
        if not pts:
            continue
        ax.errorbar([r["D"] for r in pts], [r["t90"] for r in pts],
                     yerr=[r["t90_std"] for r in pts],
                     fmt=MARKERS[barrido], color=COLORS[barrido], label=barrido, alpha=0.8,
                     markersize=9 if barrido == "vacia" else 6)
    ax.set_xlabel(r"D [m$^2$/s]")
    ax.set_ylabel(r"$\langle t_{90} \rangle$ [s]")
    ax.set_title(f"t90 vs D (ajuste D en ventana [0,{args.fit_tmax}]s)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"\nGrafico -> {args.out}\nDatos   -> {csv_path}")


if __name__ == "__main__":
    main()
