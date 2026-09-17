"""Punto 1.3: desplazamiento cuadrático medio (DCM) y coeficiente de difusión D.

Para una realización, el DCM en cada instante guardado es el desplazamiento cuadrático de cada
partícula respecto de su propia posición inicial, promediado sobre las N partículas móviles
(frescas y usadas - ninguna deja de moverse):

    DCM(t) = mean_i [ (x_i(t) - x_i(0))^2 + (y_i(t) - y_i(0))^2 ]

La mesa es un dominio acotado (paredes reflectantes), así que el DCM no crece linealmente para
siempre como en una difusión libre: al cabo de unos segundos las partículas ya exploraron casi
toda el área disponible y el DCM satura en una meseta, mucho antes de t90. El ajuste lineal
(siguiendo el método de cuadrados mínimos: minimizar E(c) = sum_i [y_i - f(x_i,c)]^2) solo tiene
sentido en la ventana temprana donde el DCM todavía crece aproximadamente derecho - se fija a mano
con --fit-tmax tras inspeccionar el gráfico, no se detecta automáticamente.

El ajuste usa ordenada al origen libre (no se fuerza DCM=c1*t): aunque DCM(0)=0 exactamente, la
curva ya tiene curvatura continua incluso en la ventana temprana, y forzar la recta por el origen
sesga la pendiente hacia arriba a medida que la ventana crece (verificado en la práctica: con
--fit-tmax > ~2s la diferencia entre ordenada libre y forzada ya es de decenas de %).

En 2D: DCM(t) = 4 D t + c0  =>  D = pendiente / 4.

Uso:
    python3 analysis/msd.py --traj output/particles.txt --fit-tmax 3.0 --out output/msd_vacia.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from billar_io import read_trajectory


def compute_msd(traj_path):
    """Devuelve (ts, msd): un DCM por bloque guardado, relativo al bloque t=0 de esa trayectoria."""
    ts, positions, colors, _speeds, _thetas = read_trajectory(traj_path)
    p0 = positions[0]
    msd = np.array([np.mean(np.sum((p - p0) ** 2, axis=1)) for p in positions])
    return ts, msd


def fit_D(ts, msd, fit_tmax):
    """Ajuste lineal (ordenada libre) de DCM vs t en la ventana [0, fit_tmax]. Devuelve (D, c0, c1)."""
    mask = ts <= fit_tmax
    if mask.sum() < 2:
        raise ValueError(f"fit_tmax={fit_tmax} deja menos de 2 puntos (t_final={ts[-1]:.3f}s)")
    c1, c0 = np.polyfit(ts[mask], msd[mask], 1)
    return c1 / 4.0, c0, c1


def plot_msd(ts, msd, fit_tmax, D, c0, c1, title, out_path):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(ts, msd, lw=1, color="tab:blue", label="DCM(t)")
    tt = np.linspace(0, fit_tmax, 50)
    ax.plot(tt, c0 + c1 * tt, color="tab:green", lw=2, label=f"ajuste: D={D:.5f}")
    ax.axvline(fit_tmax, color="gray", ls=":", alpha=0.6)
    ax.set_xlabel("t [s]")
    ax.set_ylabel("DCM(t) [m^2]")
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--traj", required=True, help="particles.txt ya generado")
    parser.add_argument("--fit-tmax", type=float, required=True,
                         help="ventana [0, fit-tmax] para el ajuste lineal (elegida a mano)")
    parser.add_argument("--out", required=True, help="PNG de salida")
    parser.add_argument("--csv", default=None, help="donde guardar (t, msd) - default junto al PNG")
    parser.add_argument("--label", default=None, help="título del gráfico (default: nombre del --traj)")
    args = parser.parse_args()

    ts, msd = compute_msd(args.traj)
    D, c0, c1 = fit_D(ts, msd, args.fit_tmax)

    csv_path = Path(args.csv) if args.csv else Path(args.out).with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w") as f:
        f.write("t,msd\n")
        for t, m in zip(ts, msd):
            f.write(f"{t},{m}\n")

    label = args.label or Path(args.traj).stem
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    plot_msd(ts, msd, args.fit_tmax, D, c0, c1, label, args.out)

    print(f"D = {D:.6f} m^2/s  (c0={c0:.6f}, pendiente={c1:.6f}, ventana=[0,{args.fit_tmax}]s)")
    print(f"Grafico -> {args.out}\nDatos   -> {csv_path}")


if __name__ == "__main__":
    main()
