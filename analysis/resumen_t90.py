"""Punto 1.4: analiza UNA trayectoria ya simulada (no corre nada nuevo) e imprime por consola
cada conversión fresca->usada con la fracción rojas/totales en ese instante, y al final el t90.

Reusa t90_io.curva_usadas/goles_para_t90 - misma convención de t90 que el resto del TP
(t90 = min{t : Fu(t) >= 0.9}, umbral en enteros exactos), leyendo el archivo en streaming.

Uso:
    python3 resumen_t90.py --traj output/particles.txt --n 100
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t90_io import curva_usadas, goles_para_t90


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traj", required=True, help="trayectoria .txt ya simulada")
    parser.add_argument("--n", type=int, required=True, help="N total de particulas")
    args = parser.parse_args()

    ts, usadas = curva_usadas(args.traj)
    if not ts:
        raise SystemExit(f"{args.traj} no tiene bloques")

    objetivo = goles_para_t90(args.n)
    anterior = 0
    t90 = math.nan
    for t, u in zip(ts, usadas):
        if u > anterior:
            print(f"t={t:.6f}s -> {u}/{args.n} rojas (Fu={u / args.n:.4f})")
            anterior = u
        if math.isnan(t90) and u >= objetivo:
            t90 = t

    print()
    if math.isnan(t90):
        print(f"t90: no alcanzado (Fu final = {usadas[-1]}/{args.n} = {usadas[-1] / args.n:.4f})")
    else:
        print(f"t90 = {t90:.6f}s")


if __name__ == "__main__":
    main()
