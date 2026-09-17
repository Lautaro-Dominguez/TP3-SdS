"""Punto 1.2: generación y validación de configuraciones de obstáculos.

Una configuración es una lista de (x_k, y_k, R_k) - exactamente el formato del archivo que lee
sim.io.ObstacleFileIO y el que pide el enunciado para la competencia ("x_k y_k R_k" en metros,
separados por espacios, una línea por obstáculo).

Cada barrido de la exploración es una familia de configuraciones parametrizada por una única
variable (la "variable estudiada" contra la que se grafica <t90>):

  (b) single_centered(R)          -> varía el radio de un obstáculo centrado
  (a) single_longitudinal(x, R)   -> varía la posición de un obstáculo sobre el eje longitudinal
  (c) grid_fixed_area(n, A_tot)   -> varía n con area total fija
  (d) funnel(x_f, R, delta)       -> embudo de 4 obstáculos hacia los arcos

`validate` chequea las restricciones (i) y (ii) del enunciado que son puramente geométricas; la
parte de (ii) que dice "y tal que permita la generación de las N partículas" no se puede decidir
acá y se verifica en la práctica: GenerateMain falla si no logra ubicar las N partículas.
"""
from __future__ import annotations

import math

L = 1.20
W = 0.68
D = 0.20
R_PARTICLE = 0.0175


def single_centered(radius, l=L, w=W):
    """(b) Un obstáculo en el centro de la mesa. Variable estudiada: radius."""
    return [(l / 2, w / 2, radius)]


def single_longitudinal(x, radius, w=W):
    """(a) Un obstáculo sobre el eje longitudinal (y = W/2). Variable estudiada: x."""
    return [(x, w / 2, radius)]


def grid_partition(n, l=L, w=W):
    """Elige (n_x, n_y) con n_x * n_y = n y relación de aspecto lo más cercana posible a L:W.

    Fijar esta regla es lo que hace que el barrido (c) mida n y no la disposición: a igual n,
    disposiciones distintas dan resultados distintos, así que la disposición no puede quedar
    librada al criterio de cada caso.
    """
    target = l / w
    best = None
    for nx in range(1, n + 1):
        if n % nx:
            continue
        ny = n // nx
        err = abs(nx / ny - target)
        if best is None or err < best[0]:
            best = (err, nx, ny)
    return best[1], best[2]


def grid_fixed_area(n, total_area, l=L, w=W):
    """(c) n obstáculos iguales de área total fija, en los centros de una grilla n_x x n_y.

    R(n) = sqrt(A_tot / (n * pi)), y los centros parten la mesa en n celdas iguales:
        x_i = L (i + 1/2) / n_x,  y_j = W (j + 1/2) / n_y
    Es simétrica respecto de ambos ejes y para n=1 devuelve exactamente el centro de la mesa,
    así que el barrido (c) empalma con el (b).
    """
    radius = math.sqrt(total_area / (n * math.pi))
    nx, ny = grid_partition(n, l, w)
    return [(l * (i + 0.5) / nx, w * (j + 0.5) / ny, radius)
            for i in range(nx) for j in range(ny)]


def funnel(x_f, radius, delta, l=L, w=W, d=D):
    """(d) Embudo hacia los arcos: 2 obstáculos por arco, simétricos respecto de y = W/2.

    h = d/2 + radius + delta es la distancia al eje: con delta >= 0 el obstáculo no invade la
    boca del arco (su borde interno queda a delta del extremo del arco).
    """
    h = d / 2 + radius + delta
    return [(x_f, w / 2 + h, radius), (x_f, w / 2 - h, radius),
            (l - x_f, w / 2 + h, radius), (l - x_f, w / 2 - h, radius)]


def max_n_fixed_area(total_area, r=R_PARTICLE):
    """n máximo del barrido (c): el mayor n con R(n) >= r, es decir n <= A_tot / (pi r^2)."""
    return int(total_area / (math.pi * r * r))


def violations(config, l=L, w=W, r=R_PARTICLE, allow_empty=False):
    """Devuelve la lista de restricciones (i)/(ii) violadas; vacía si la configuración es válida.

    `allow_empty=True` habilita K=0, que el enunciado prohíbe para una configuración presentable
    pero es justamente la mesa vacía contra la que manda comparar.
    """
    problems = []
    if not config and not allow_empty:
        problems.append("K = 0: el enunciado exige K > 0 obstáculos")
    for k, (x, y, radius) in enumerate(config):
        if radius < r:
            problems.append(f"obstaculo {k}: R={radius:.6f} < r={r:.6f}")
        if not (radius <= x <= l - radius and radius <= y <= w - radius):
            problems.append(
                f"obstaculo {k}: centro ({x:.4f}, {y:.4f}) con R={radius:.4f} no entra entero "
                f"en el dominio {l:.2f} x {w:.2f}")
    for k in range(len(config)):
        for j in range(k + 1, len(config)):
            xk, yk, rk = config[k]
            xj, yj, rj = config[j]
            dist = math.hypot(xk - xj, yk - yj)
            if dist <= rk + rj:
                problems.append(
                    f"obstaculos {k} y {j} se solapan: d={dist:.6f} <= R{k}+R{j}={rk + rj:.6f}")
    return problems


def write(path, config):
    """Escribe la configuración en el formato 'x y R' que leen ObstacleFileIO y la competencia."""
    with open(path, "w") as f:
        for x, y, radius in config:
            f.write(f"{x:.6f} {y:.6f} {radius:.6f}\n")
