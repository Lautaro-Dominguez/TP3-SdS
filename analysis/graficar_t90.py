"""Punto 1.2: grafico comparativo de <t90> por configuracion.

Lee los CSV que deja correr_configuraciones.py - el resumen (<t90> y su desvio estandar) y el
detalle por realizacion - y arma un grafico de barras ordenado de menor a mayor <t90>, con:

  - la barra de error del desvio estandar muestral sigma (la que pide el enunciado);
  - los t90 de cada realizacion superpuestos como puntos, para que se vea la dispersion real y no
    solo su resumen;
  - la mesa vacia como linea de referencia con su banda de +-sigma, que es contra lo que el
    enunciado manda comparar. La mesa vacia va aparte y no como una barra mas porque K=0 viola la
    restriccion (i) del enunciado: es referencia, no una configuracion presentable.

Uso:
    python3 analysis/graficar_t90.py --outdir output/final
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REFERENCIA = "00_mesa_vacia"


def leer(outdir):
    resumen = {}
    with open(outdir / "t90_por_configuracion.csv") as f:
        for fila in csv.DictReader(f):
            resumen[fila["configuracion"]] = dict(
                descripcion=fila["descripcion"],
                k=int(fila["K"]),
                media=float(fila["t90_medio"]),
                sigma=float(fila["t90_desvio"]),
                reps=int(fila["realizaciones"]),
            )

    detalle = defaultdict(list)
    ruta = outdir / "t90_por_realizacion.csv"
    if ruta.exists():
        with open(ruta) as f:
            for fila in csv.DictReader(f):
                detalle[fila["configuracion"]].append(float(fila["t90"]))
    return resumen, detalle


def etiqueta(nombre, datos):
    """Nombre corto de dos lineas para el eje x."""
    corto = nombre.split("_", 1)[1].replace("_", " ")
    return f"{corto}\nK = {datos['k']}"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", default="output/final")
    parser.add_argument("--out", default=None, help="PNG de salida (default: <outdir>/t90_comparativa.png)")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    resumen, detalle = leer(outdir)
    destino = Path(args.out) if args.out else outdir / "t90_comparativa.png"

    vacia = resumen.pop(REFERENCIA, None)
    ordenadas = sorted(resumen.items(), key=lambda kv: kv[1]["media"])
    nombres = [n for n, _ in ordenadas]
    medias = np.array([d["media"] for _, d in ordenadas])
    sigmas = np.array([d["sigma"] for _, d in ordenadas])

    # Verde solo la mejor; el resto en gris, y rojo las que son peores que la mesa vacia.
    colores = []
    for k, (_n, d) in enumerate(ordenadas):
        if k == 0:
            colores.append("tab:green")
        elif vacia and d["media"] > vacia["media"]:
            colores.append("tab:red")
        else:
            colores.append("tab:blue")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    xs = np.arange(len(nombres))
    ax.bar(xs, medias, yerr=sigmas, capsize=6, color=colores, alpha=0.85,
           edgecolor="black", linewidth=0.6, zorder=2)

    topes = []
    for x, nombre in zip(xs, nombres):
        puntos = detalle.get(nombre, [])
        finitos = [t for t in puntos if math.isfinite(t)]
        if finitos:
            ax.scatter(np.full(len(finitos), x) + np.linspace(-0.13, 0.13, len(finitos)),
                       finitos, s=22, color="black", zorder=4, alpha=0.75,
                       label="realizaciones" if x == 0 else None)
        # La etiqueta va arriba de todo lo dibujado en esa barra: no solo de media+sigma, porque
        # una realizacion puede caer mas alto que el extremo de la barra de error.
        topes.append(max([medias[x] + sigmas[x]] + finitos))

    tope = max(topes)
    ax.set_ylim(0, tope * 1.16)
    for x, (media, alto) in enumerate(zip(medias, topes)):
        ax.text(x, alto + tope * 0.035, f"{media:.1f}", ha="center", fontweight="bold", zorder=5)

    if vacia:
        ax.axhline(vacia["media"], color="tab:red", linestyle="--", linewidth=1.6, zorder=3,
                   label=f"mesa vacia (referencia): {vacia['media']:.2f} s")
        ax.axhspan(vacia["media"] - vacia["sigma"], vacia["media"] + vacia["sigma"],
                   color="tab:red", alpha=0.10, zorder=1)

    reps = next(iter(resumen.values()))["reps"] if resumen else 0
    ax.set_xticks(xs)
    ax.set_xticklabels([etiqueta(n, dict(ordenadas)[n]) for n in nombres], fontsize=9)
    ax.set_ylabel(r"$\langle t_{90} \rangle$ [s]")
    ax.set_title(f"$t_{{90}}$ por configuracion  (N = 100, {reps} realizaciones, "
                 r"barra de error: $\sigma$)")
    ax.grid(True, axis="y", alpha=0.3, zorder=0)
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150)
    print(f"Grafico guardado en {destino}")


if __name__ == "__main__":
    main()
