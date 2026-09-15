"""Utilidades compartidas por los scripts de análisis del TP3.

Lee el formato de trayectoria que escribe sim.io.StateFileIO: un bloque por instante guardado,
con una línea de header (el tiempo real de sistema t_e, no un índice) seguida de una línea
"x y v color theta" por partícula, y el formato de obstáculos ("x y R" por línea). No se toca ni
se reimplementa el motor Java - esto solo lee los .txt que ya produce.
"""
from __future__ import annotations

import numpy as np


def read_trajectory(path):
    """Devuelve (ts, positions, colors, speeds, thetas).

    - ts: array de floats, un valor de t_e por bloque
    - positions: lista de arrays (N, 2), uno por bloque
    - colors: lista de listas de str ("azul"/"rojo"), una por bloque
    - speeds: lista de arrays (N,), uno por bloque
    - thetas: lista de arrays (N,), uno por bloque
    """
    with open(path) as f:
        lines = [line.strip() for line in f if line.strip()]

    ts = []
    positions = []
    colors = []
    speeds = []
    thetas = []
    i = 0
    while i < len(lines):
        t = float(lines[i])
        i += 1
        xs, ys, vs, cs, ths = [], [], [], [], []
        while i < len(lines) and len(lines[i].split()) == 5:
            x, y, v, color, theta = lines[i].split()
            xs.append(float(x))
            ys.append(float(y))
            vs.append(float(v))
            cs.append(color)
            ths.append(float(theta))
            i += 1
        ts.append(t)
        positions.append(np.column_stack([xs, ys]) if xs else np.empty((0, 2)))
        colors.append(cs)
        speeds.append(np.array(vs))
        thetas.append(np.array(ths))
    return np.array(ts), positions, colors, speeds, thetas


def read_obstacles(path):
    """Devuelve una lista de (x, y, R), una por línea del archivo de obstáculos."""
    obstacles = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            x, y, r = (float(v) for v in line.split())
            obstacles.append((x, y, r))
    return obstacles
