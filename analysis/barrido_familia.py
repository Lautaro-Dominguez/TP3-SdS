"""Punto 1.2: barrido de una familia de obstaculos sobre su parametro variable.

Cada familia (ver obstacle_configs.familias()) deja UN parametro libre y fija el resto. Este
script recorre ese parametro y, para cada valor:

  - arma la configuracion y la valida contra las restricciones (i) y (ii) del enunciado;
  - corre --reps realizaciones independientes y mide <t90> y su desvio estandar sigma;
  - deja el txt de obstaculos de esa configuracion.

Al terminar grafica <t90> vs el parametro (con la mesa vacia como referencia) y anima el MEJOR y
el PEOR caso del barrido llamando a analysis/animate.py sobre el txt de trayectoria mas el txt de
obstaculos. La animacion corresponde a la realizacion 1 de ese punto del barrido: misma semilla,
misma condicion inicial.

Familias disponibles: centro, desplazado, multiples, embudo.

Uso:
    python3 analysis/barrido_familia.py --familia centro  --outdir output/familias
    python3 analysis/barrido_familia.py --familia embudo  --reps 5 --outdir output/familias
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
from simulacion import animar, leyenda_arriba, medir


def barrer(familia, args, workdir, dir_cfg):
    """Mide todos los valores del parametro. Devuelve la lista de resultados validos."""
    resultados = []
    for valor in familia.valores:
        etiqueta = f"{familia.nombre}_{familia.formato.format(valor)}"
        res = medir(familia.construir(valor), etiqueta, workdir, args.reps, args.tmax,
                    args.seed0, args.save_every, args.jobs, dir_config=dir_cfg)
        res["valor"] = valor
        if res.get("invalida"):
            print(f"  {etiqueta}: INVALIDA -> {res['invalida']}")
            continue
        sigma = "  n/d" if math.isnan(res["sigma"]) else f"{res['sigma']:5.2f}"
        if math.isnan(res["media"]):
            print(f"  {familia.etiqueta_parametro} = {valor}: censurada, "
                  f"<N_g> = {res['ng_medio']:.1f}")
        else:
            print(f"  {familia.etiqueta_parametro} = {valor}: "
                  f"<t90> = {res['media']:6.2f} +- {sigma} s")
        resultados.append(res)
    return resultados


def graficar(familia, resultados, vacia, destino, con_pie=True):
    """<t90> vs el parametro variable. Sin titulo y con la leyenda fuera del area de datos."""
    validos = [r for r in resultados if math.isfinite(r["media"])]
    censurados = [r for r in resultados if not math.isfinite(r["media"])]

    fig, ax = plt.subplots(figsize=(8, 5))
    xs = [r["valor"] for r in validos]
    ys = [r["media"] for r in validos]
    es = [0.0 if math.isnan(r["sigma"]) else r["sigma"] for r in validos]
    ax.errorbar(xs, ys, yerr=es, marker="o", capsize=3, zorder=3,
                label=familia.descripcion.lower())

    if vacia and math.isfinite(vacia["media"]):
        ax.axhline(vacia["media"], color="tab:red", linestyle="--", linewidth=1.5, zorder=2,
                   label=f"mesa vacia (referencia): {vacia['media']:.2f} s")
        ax.axhspan(vacia["media"] - vacia["sigma"], vacia["media"] + vacia["sigma"],
                   color="tab:red", alpha=0.10, zorder=1)

    if censurados and validos:
        tope = max(np.array(ys) + np.array(es))
        ax.scatter([r["valor"] for r in censurados], [tope] * len(censurados),
                   marker="^", color="dimgray", zorder=4,
                   label=r"sin $t_{90}$ (censurada)")

    ax.set_xlabel(familia.etiqueta_parametro)
    ax.set_ylabel(r"$\langle t_{90} \rangle$ [s]")
    ax.grid(True, alpha=0.3)
    leyenda_arriba(ax, ncol=3 if censurados else 2)
    if con_pie:
        fig.text(0.5, 0.005, f"N = 100   |   fijo: {familia.fijos}",
                 ha="center", fontsize=9, color="dimgray")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150)
    plt.close(fig)


def extremos(resultados):
    """(mejor, peor). Una configuracion censurada es el peor caso posible."""
    validos = [r for r in resultados if math.isfinite(r["media"])]
    censurados = [r for r in resultados if not math.isfinite(r["media"])]
    mejor = min(validos, key=lambda r: r["media"]) if validos else None
    if censurados:
        peor = min(censurados, key=lambda r: r["ng_medio"])
    else:
        peor = max(validos, key=lambda r: r["media"]) if validos else None
    return mejor, peor


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--familia", required=True,
                        choices=["centro", "desplazado", "multiples", "embudo"])
    parser.add_argument("--outdir", default="output/familias")
    parser.add_argument("--reps", type=int, default=5,
                        help="realizaciones por valor del parametro (el enunciado pide >= 5)")
    parser.add_argument("--tmax", type=float, default=100.0)
    parser.add_argument("--save-every", type=int, default=10,
                        help="cada cuantos eventos graba el motor (ver simulacion.py)")
    parser.add_argument("--seed0", type=int, default=None,
                        help="sin valor (lo normal) cada realizacion sortea su condicion inicial;\n"
                             "con un entero se vuelve reproducible (semilla = seed0 + rep)")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--frames", type=int, default=260)
    parser.add_argument("--speed", type=float, default=8.0)
    parser.add_argument("--sin-animaciones", action="store_true")
    # parametros que quedan FIJOS en cada familia
    parser.add_argument("--radio-desplazado", type=float, default=0.335)
    parser.add_argument("--area-total", type=float, default=None)
    parser.add_argument("--x-embudo", type=float, default=0.15)
    parser.add_argument("--delta-embudo", type=float, default=0.02)
    args = parser.parse_args()

    if args.reps < 5:
        print(f"AVISO: --reps {args.reps} esta por debajo del minimo de 5 del enunciado.\n")

    familia = oc.familias(radio_desplazado=args.radio_desplazado, area_total=args.area_total,
                          x_embudo=args.x_embudo, delta_embudo=args.delta_embudo)[args.familia]
    base = Path(args.outdir) / familia.nombre
    dir_cfg = base / "obstaculos"
    dir_gif = base / "animaciones"
    for d in (dir_cfg, dir_gif):
        d.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix=f"familia_{familia.nombre}_"))

    print(f"Familia '{familia.nombre}': {familia.descripcion}")
    print(f"  parametro variable: {familia.etiqueta_parametro}  "
          f"({len(familia.valores)} valores)")
    print(f"  fijo: {familia.fijos}")
    print(f"  {args.reps} realizaciones por valor, tmax = {args.tmax:g} s\n")

    try:
        resultados = barrer(familia, args, workdir, dir_cfg)
        print("\n  mesa vacia (referencia):")
        vacia = medir([], "mesa_vacia", workdir, args.reps, args.tmax, args.seed0,
                      args.save_every, args.jobs, permitir_vacia=True)
        print(f"    <t90> = {vacia['media']:.2f} +- {vacia['sigma']:.2f} s")

        if not resultados:
            raise SystemExit("ninguna configuracion de la familia resulto valida")

        destino = base / f"t90_vs_{familia.nombre}.png"
        graficar(familia, resultados, vacia, destino)

        with open(base / f"t90_vs_{familia.nombre}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([familia.etiqueta_parametro, "etiqueta", "t90_medio", "t90_desvio",
                        "realizaciones", "censuradas", "ng_medio"])
            for r in resultados:
                w.writerow([r["valor"], r["etiqueta"], r["media"], r["sigma"],
                            r["reps"], r["censuradas"], r["ng_medio"]])
            w.writerow(["", "mesa_vacia", vacia["media"], vacia["sigma"],
                        vacia["reps"], vacia["censuradas"], vacia["ng_medio"]])

        mejor, peor = extremos(resultados)
        print(f"\n  MEJOR: {familia.etiqueta_parametro} = {mejor['valor']}  "
              f"-> <t90> = {mejor['media']:.2f} s")
        if math.isfinite(peor["media"]):
            print(f"  PEOR:  {familia.etiqueta_parametro} = {peor['valor']}  "
                  f"-> <t90> = {peor['media']:.2f} s")
        else:
            print(f"  PEOR:  {familia.etiqueta_parametro} = {peor['valor']}  "
                  f"-> censurada, <N_g> = {peor['ng_medio']:.1f}")

        if not args.sin_animaciones:
            for rotulo, r in (("mejor", mejor), ("peor", peor)):
                res = medir(r["config"], f"{rotulo}_{r['etiqueta']}", workdir, 1, args.tmax,
                            args.seed0, args.save_every, 1, dir_config=dir_cfg,
                            conservar_primera=True)
                stride, log = animar(res["traj"], res["cfg_path"],
                                     dir_gif / f"{rotulo}_{r['etiqueta']}.gif",
                                     res["bloques"], args.frames, args.speed)
                print(f"  animacion {rotulo} (stride {stride}): {log}")
                res["traj"].unlink(missing_ok=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print(f"\nSalida -> {base}/")


if __name__ == "__main__":
    main()
