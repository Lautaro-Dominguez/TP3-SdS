"""Punto 1.2: mapa de calor de <t90> variando R y X a la vez (un unico obstaculo).

Las familias "centro" y "desplazado" son dos cortes 1D del mismo espacio de dos parametros: el
radio R del obstaculo y la posicion X de su centro sobre el eje horizontal (con y = W/2 fijo).
Este script barre los dos a la vez y dibuja <t90> como mapa de calor, con lo que se ve de una
sola pasada donde esta el minimo y como se combinan ambos efectos.

No todas las celdas existen: la restriccion (i) del enunciado exige que el obstaculo entre entero
en el dominio, o sea R <= X <= L - R. Las celdas fuera de esa region no se simulan y quedan en
blanco - no son "malas", son geometricamente imposibles.

Uso:
    python3 analysis/mapa_calor.py --outdir output/mapa_calor
    python3 analysis/mapa_calor.py --n-r 8 --n-x 9 --reps 5 --outdir output/mapa_calor
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
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obstacle_configs as oc
from simulacion import medir


def graficar(radios, equis, malla, outdir):
    """Dibuja el mapa de calor; separado de la simulacion para poder regraficar."""
    fig, ax = plt.subplots(figsize=(9, 5.5))
    # Paleta tipo matriz de riesgo: verde (mejor) -> amarillo -> naranja -> rojo (peor). Es
    # secuencial y monotona en luminancia, asi que el orden se lee igual sin mirar la escala.
    cmap = LinearSegmentedColormap.from_list(
        "riesgo", ["#8DC163", "#F2C94C", "#E8833A", "#CE2B37"])
    cmap.set_bad("white")
    im = ax.imshow(np.ma.masked_invalid(malla), origin="lower", aspect="auto", cmap=cmap,
                   extent=(equis[0] - (equis[1] - equis[0]) / 2,
                           equis[-1] + (equis[1] - equis[0]) / 2,
                           radios[0] - (radios[1] - radios[0]) / 2,
                           radios[-1] + (radios[1] - radios[0]) / 2))
    barra = fig.colorbar(im, ax=ax)
    barra.set_label(r"$\langle t_{90} \rangle$ [s]")

    for i, radio in enumerate(radios):
        for j, x in enumerate(equis):
            if math.isnan(malla[i, j]):
                continue
            # Contraste por luminancia de la celda, no por su valor: con esta paleta el
            # amarillo del medio necesita texto negro y el rojo del extremo, blanco.
            r, g, b, _ = cmap(im.norm(malla[i, j]))
            luminancia = 0.299 * r + 0.587 * g + 0.114 * b
            ax.text(x, radio, f"{malla[i, j]:.0f}", ha="center", va="center", fontsize=7,
                    color="black" if luminancia > 0.55 else "white")

    if np.isfinite(malla).any():
        i, j = np.unravel_index(np.nanargmin(malla), malla.shape)
        print(f"\nMinimo del mapa: R = {radios[i]:.4f} m, X = {equis[j]:.4f} m  ->  "
              f"<t90> = {malla[i, j]:.2f} s")

    ax.set_xlabel("X del centro del obstaculo [m]")
    ax.set_ylabel("R [m]")
    fig.text(0.5, 0.005, "N = 100   |   blanco: el obstaculo no entra entero en el dominio "
                          "(restriccion i)", ha="center", fontsize=9, color="dimgray")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(outdir / "mapa_calor.png", dpi=150)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", default="output/mapa_calor")
    parser.add_argument("--n-r", type=int, default=8, help="valores de R")
    parser.add_argument("--n-x", type=int, default=9, help="valores de X")
    parser.add_argument("--r-min", type=float, default=0.05)
    parser.add_argument("--r-max", type=float, default=0.335)
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--tmax", type=float, default=100.0)
    parser.add_argument("--save-every", type=int, default=10)
    parser.add_argument("--seed0", type=int, default=None,
                        help="sin valor (lo normal) cada realizacion sortea su condicion inicial;\n"
                             "con un entero se vuelve reproducible (semilla = seed0 + rep)")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--desde-csv", action="store_true",
                        help="regrafica desde mapa_calor.csv sin volver a simular")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="mapa_calor_"))

    if args.desde_csv:
        filas = []
        with open(outdir / "mapa_calor.csv") as f:
            for fila in csv.DictReader(f):
                filas.append([float(fila["R"]), float(fila["X"]), float(fila["t90_medio"]),
                              float(fila["t90_desvio"]), int(fila["realizaciones"]),
                              int(fila["censuradas"]), float(fila["ng_medio"])])
        radios = np.array(sorted({f[0] for f in filas}))
        equis = np.array(sorted({f[1] for f in filas}))
        malla = np.full((len(radios), len(equis)), np.nan)
        for radio, x, media, *_ in filas:
            malla[np.argmin(abs(radios - radio)), np.argmin(abs(equis - x))] = media
        print(f"Regraficando desde {outdir / 'mapa_calor.csv'} ({len(filas)} celdas)")
        graficar(radios, equis, malla, outdir)
        return

    radios = np.round(np.linspace(args.r_min, args.r_max, args.n_r), 6)
    equis = np.round(np.linspace(0.05, oc.L - 0.05, args.n_x), 6)
    malla = np.full((len(radios), len(equis)), np.nan)

    total = sum(1 for radio in radios for x in equis if radio <= x <= oc.L - radio)
    print(f"Mapa de calor: {len(radios)} R x {len(equis)} X = {malla.size} celdas, "
          f"{total} dentro del dominio, {args.reps} realizaciones cada una\n")

    filas = []
    hechas = 0
    try:
        for i, radio in enumerate(radios):
            for j, x in enumerate(equis):
                if not (radio <= x <= oc.L - radio):
                    continue     # el obstaculo no entra entero: restriccion (i)
                etiqueta = f"R{radio:.4f}_X{x:.4f}"
                res = medir(oc.single_longitudinal(x, radio), etiqueta, workdir, args.reps,
                            args.tmax, args.seed0, args.save_every, args.jobs)
                hechas += 1
                if res.get("invalida"):
                    print(f"  [{hechas}/{total}] {etiqueta}: INVALIDA -> {res['invalida']}")
                    continue
                malla[i, j] = res["media"]
                filas.append([radio, x, res["media"], res["sigma"], res["reps"],
                              res["censuradas"], res["ng_medio"]])
                texto = ("censurada" if math.isnan(res["media"])
                         else f"<t90> = {res['media']:6.2f} s")
                print(f"  [{hechas}/{total}] R = {radio:.3f}  X = {x:.3f}  ->  {texto}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    with open(outdir / "mapa_calor.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["R", "X", "t90_medio", "t90_desvio", "realizaciones", "censuradas",
                    "ng_medio"])
        w.writerows(filas)

    graficar(radios, equis, malla, outdir)
    print(f"Salida -> {outdir}/")


if __name__ == "__main__":
    main()
