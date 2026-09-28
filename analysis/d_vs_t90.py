"""Punto 1.3: D vs <t90> para la MEJOR configuracion de cada familia (+ mesa vacia).

Pasos:
  1. Seleccion. Para cada familia se toman los --candidatos mejores valores del barrido de 1.2
     (leidos de output/familias/<familia>/t90_vs_<familia>.csv, hecho con pocas realizaciones) y se
     los vuelve a medir con --reps-seleccion realizaciones. El mejor es el de menor <t90> de esta
     segunda medicion: con 5 realizaciones el ruido (~2-3 s) es del orden de la diferencia entre
     vecinos, asi que la primera medicion solo sirve para preseleccionar.
  2. Medicion final. La configuracion elegida (y la mesa vacia) se corre --reps veces: <t90> y su
     desvio salen de las --reps realizaciones y D sale SOLO de la primera (el enunciado pide el DCM
     "para una realizacion"). Esa primera se graba con --saveEvery 1 para tener el DCM sin perder
     resolucion temporal.
  3. D = pendiente / 4 del ajuste lineal (ordenada libre) de DCM(t) en [0, --t-fit], ver msd.py. El
     mismo --t-fit vale para todas las familias.

Uso:
    python3 analysis/d_vs_t90.py --t-fit 2.0 --outdir output/d_vs_t90
"""
from __future__ import annotations

import argparse
import csv
import math
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obstacle_configs as oc
from msd import compute_msd, fit_D
from simulacion import medir

FAMILIAS = ["centro", "desplazado", "multiples", "embudo"]
COLORES = {"vacia": "tab:red", "centro": "tab:blue", "desplazado": "tab:orange",
           "multiples": "tab:green", "embudo": "tab:purple"}
MARCADORES = {"vacia": "*", "centro": "o", "desplazado": "s", "multiples": "^", "embudo": "D"}


def candidatos(familia, k, indir):
    """Los k valores del parametro con menor <t90> segun el barrido de 1.2 (ignora censuradas)."""
    with open(Path(indir) / familia.nombre / f"t90_vs_{familia.nombre}.csv") as f:
        filas = [r for r in csv.reader(f)][1:]
    validas = [(float(r[2]), float(r[0])) for r in filas
               if r[1] != "mesa_vacia" and r[2] not in ("", "nan")]
    return [valor for _t90, valor in sorted(validas)[:k]]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--t-fit", type=float, required=True,
                        help="ventana [0, t-fit] del ajuste de D, la misma para todas las familias")
    parser.add_argument("--indir", default="output/familias", help="salida de barrido_familia.py")
    parser.add_argument("--outdir", default="output/d_vs_t90")
    parser.add_argument("--candidatos", type=int, default=4)
    parser.add_argument("--reps-seleccion", type=int, default=20)
    parser.add_argument("--reps", type=int, default=5, help="realizaciones de la medicion final")
    parser.add_argument("--tmax", type=float, default=100.0)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="d_vs_t90_"))
    fams = oc.familias()

    elegidas = [("vacia", "mesa vacia", [])]
    try:
        for nombre in FAMILIAS:
            fam = fams[nombre]
            mejor = None
            print(f"{nombre}: seleccion entre {args.candidatos} candidatos, "
                  f"{args.reps_seleccion} realizaciones c/u")
            for valor in candidatos(fam, args.candidatos, args.indir):
                cfg = fam.construir(valor)
                res = medir(cfg, f"sel_{nombre}_{fam.formato.format(valor)}", workdir,
                            args.reps_seleccion, args.tmax, None, 10, args.jobs)
                if res.get("invalida") or math.isnan(res["media"]):
                    continue
                print(f"  {fam.etiqueta_parametro} = {valor}: <t90> = {res['media']:.2f} "
                      f"+- {res['sigma']:.2f} s")
                if mejor is None or res["media"] < mejor[0]:
                    mejor = (res["media"], valor, cfg)
            print(f"  -> mejor: {mejor[1]}\n")
            elegidas.append((nombre, f"{nombre} ({fam.formato.format(mejor[1])})", mejor[2]))

        filas, curvas = [], []
        for nombre, rotulo, cfg in elegidas:
            res = medir(cfg, f"final_{nombre}", workdir, args.reps, args.tmax, None, 1,
                        args.jobs, dir_config=outdir / "obstaculos", conservar_primera=True,
                        permitir_vacia=(nombre == "vacia"))
            ts, dcm = compute_msd(res["traj"])
            D, c0, c1 = fit_D(ts, dcm, args.t_fit)
            res["traj"].unlink(missing_ok=True)
            print(f"{rotulo}: <t90> = {res['media']:.2f} +- {res['sigma']:.2f} s   D = {D:.5f}")
            filas.append((nombre, rotulo, res["media"], res["sigma"], D))
            curvas.append((nombre, rotulo, ts, dcm, c0, c1))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    with open(outdir / "d_vs_t90.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["familia", "configuracion", "t90_medio", "t90_desvio", "D", "t_fit"])
        for nombre, rotulo, media, sigma, D in filas:
            w.writerow([nombre, rotulo, media, sigma, D, args.t_fit])

    fig, ax = plt.subplots(figsize=(7, 5))
    for nombre, rotulo, media, sigma, D in filas:
        ax.errorbar(D, media, yerr=sigma, fmt=MARCADORES[nombre], color=COLORES[nombre],
                    capsize=3, markersize=11 if nombre == "vacia" else 8, label=rotulo)
    ax.set_xlabel(r"D [m$^2$/s]")
    ax.set_ylabel(r"$\langle t_{90} \rangle$ [s]")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "d_vs_t90.png", dpi=150)

    fig, ax = plt.subplots(figsize=(8, 5))
    for nombre, rotulo, ts, dcm, c0, c1 in curvas:
        ax.plot(ts, dcm, color=COLORES[nombre], lw=1, label=rotulo)
        tt = np.linspace(0, args.t_fit, 20)
        ax.plot(tt, c0 + c1 * tt, color="black", lw=1.5)
    ax.axvline(args.t_fit, color="gray", ls=":")
    ax.set_xlim(0, max(6 * args.t_fit, 12))
    ax.set_xlabel("t [s]")
    ax.set_ylabel(r"DCM [m$^2$]")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "dcm_mejores.png", dpi=150)
    print(f"\nSalida -> {outdir}/")


if __name__ == "__main__":
    main()
