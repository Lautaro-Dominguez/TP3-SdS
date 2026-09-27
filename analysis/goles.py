"""Punto 1.2: goles, Fu(t) y t90 de UNA simulacion, a partir de su archivo de trayectoria.

Toma el .txt que dejo el motor y, sin volver a simular nada, reconstruye lo que define el
enunciado:

    N_g(t) = cantidad de particulas "rojo" (usadas) en el instante t
    Fu(t)  = N_g(t) / N            (fraccion de particulas usadas)
    t90    = min { t : Fu(t) >= 0.9 }

Imprime una linea por gol -el instante en que ocurrio, N_g/N y Fu- y al final t90. Ademas grafica
Fu(t) como funcion escalonada, que es lo que realmente es: se mantiene constante entre goles y
salta 1/N en cada uno.

Sobre la resolucion temporal: el motor graba un bloque cada --saveEvery eventos, asi que el
instante que se reporta para cada gol es el del bloque donde N_g aumento. Con --saveEvery 1 (un
bloque por evento) ese instante es exacto; con valores mayores queda redondeado hacia adelante
hasta el proximo bloque guardado, y varios goles pueden caer en el mismo bloque (el script lo
avisa cuando pasa).

Uso:
    python3 analysis/goles.py --traj output/particles.txt
    python3 analysis/goles.py --traj output/particles.txt --out output/fu_vs_t.png
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t90_io import curva_usadas, goles_para_t90


def cantidad_de_particulas(path):
    """N = cantidad de filas del primer bloque (una por particula)."""
    n = 0
    with open(path) as f:
        f.readline()                       # header con t_e del primer bloque
        for linea in f:
            if len(linea.split()) != 5:    # empezo el bloque siguiente
                break
            n += 1
    return n


def goles(ts, usadas):
    """Un registro por gol: (numero de gol, instante, N_g, cuantos goles cayeron en ese bloque).

    Se detecta por los aumentos de N_g entre bloques consecutivos, porque el archivo guarda el
    estado del sistema y no los eventos.
    """
    registros = []
    previas = usadas[0] if usadas else 0
    for k, (t, u) in enumerate(zip(ts, usadas)):
        nuevos = u - previas if k > 0 else u
        for i in range(nuevos):
            registros.append((len(registros) + 1, t, previas + i + 1, nuevos))
        previas = u
    return registros


def graficar(ts, usadas, n, t90, destino, pie=None):
    """Fu(t) escalonada, con el umbral 0.9 y t90 marcados. Sin titulo, leyenda fuera del grafico."""
    fu = [u / n for u in usadas]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(ts, fu, drawstyle="steps-post", linewidth=1.6, color="tab:blue",
            label=r"$F_u(t) = N_g(t)\,/\,N$")
    ax.axhline(0.9, color="tab:red", linestyle="--", linewidth=1.4, label=r"$F_u = 0.9$")
    if t90 is not None and math.isfinite(t90):
        ax.axvline(t90, color="tab:green", linestyle=":", linewidth=1.6,
                   label=rf"$t_{{90}} = {t90:.2f}$ s")
        ax.plot([t90], [0.9], marker="o", color="tab:green", zorder=5)

    ax.set_xlabel("t [s]")
    ax.set_ylabel(r"$F_u(t)$")
    ax.set_ylim(0, 1.02)
    ax.set_xlim(0, ts[-1])
    ax.grid(True, alpha=0.3)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 1.01),
              ncol=3, frameon=False, fontsize=9)
    fig.text(0.5, 0.005, pie or f"N = {n}   |   una realizacion", ha="center", fontsize=9,
             color="dimgray")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150)
    print(f"\nGrafico de Fu(t) -> {destino}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--traj", required=True, help="archivo de trayectoria ya simulado")
    parser.add_argument("--N", type=int, default=None,
                        help="cantidad de particulas (por defecto se cuenta del archivo)")
    parser.add_argument("--out", default=None,
                        help="PNG de Fu(t) (por defecto: fu_vs_t.png junto a la trayectoria)")
    parser.add_argument("--sin-grafico", action="store_true")
    args = parser.parse_args()

    traj = Path(args.traj)
    n = args.N or cantidad_de_particulas(traj)
    ts, usadas = curva_usadas(traj)
    if not ts:
        raise SystemExit(f"{traj} no tiene bloques")

    registros = goles(ts, usadas)
    objetivo = goles_para_t90(n)
    t90 = next((t for t, u in zip(ts, usadas) if u >= objetivo), math.nan)

    print(f"Trayectoria: {traj}")
    print(f"N = {n} particulas,  {len(ts)} bloques guardados,  t final = {ts[-1]:.6f} s")
    print(f"Umbral de t90: N_g >= {objetivo}  (= ceil(0.9 N))\n")
    print(f"{'gol':>5}  {'t [s]':>12}  {'N_g / N':>12}  {'Fu(t)':>7}")
    for numero, t, ng, simultaneos in registros:
        aviso = f"   <- {simultaneos} goles en este bloque" if simultaneos > 1 else ""
        print(f"{numero:>5}  {t:>12.6f}  {ng:>6} / {n:<5}  {ng / n:>7.3f}{aviso}")

    print()
    if math.isfinite(t90):
        print(f"t90 = {t90:.6f} s        (Fu alcanza 0.9 con el gol numero {objetivo})")
    else:
        print(f"t90: no definido - Fu(t) llego solo a {usadas[-1] / n:.3f} "
              f"({usadas[-1]}/{n}) en los {ts[-1]:.2f} s simulados")

    if not args.sin_grafico:
        destino = Path(args.out) if args.out else traj.parent / "fu_vs_t.png"
        graficar(ts, usadas, n, t90, destino)


if __name__ == "__main__":
    main()
