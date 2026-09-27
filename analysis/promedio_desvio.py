"""Calcula promedio y desvío estándar de una lista de números pasados por parámetro - pensado
para agregar los <t90> de las 5 realizaciones del punto 1.4 (competencia), aunque acepta
cualquier cantidad de números.

Uso:
    python3 promedio_desvio.py 12.34 15.67 13.21 14.05 12.98
"""
from __future__ import annotations

import argparse

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("numeros", type=float, nargs="+", help="valores a promediar")
    args = parser.parse_args()

    valores = np.array(args.numeros)
    promedio = valores.mean()
    desvio = valores.std(ddof=1) if len(valores) > 1 else 0.0

    print(f"n = {len(valores)}")
    print(f"promedio = {promedio:.6f}")
    print(f"desvio estandar = {desvio:.6f}")


if __name__ == "__main__":
    main()
