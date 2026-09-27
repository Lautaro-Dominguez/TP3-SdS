"""Punto 1.2: generación y validación de configuraciones de obstáculos.

Una configuración es una lista de (x_k, y_k, R_k) - exactamente el formato del archivo que lee
sim.io.ObstacleFileIO y el que pide el enunciado para la competencia ("x_k y_k R_k" en metros,
separados por espacios, una línea por obstáculo).

La exploración se organiza en FAMILIAS de obstáculos. Cada familia deja UN parámetro variable
(la "variable estudiada" del enunciado, contra la que se grafica <t90>) y fija el resto:

  familia        parametro variable          queda fijo
  -------------  --------------------------  ----------------------------------------
  centro         R del obstaculo             centro en (L/2, W/2)
  desplazado     x del centro del obstaculo  R, y = W/2
  multiples      cantidad n de obstaculos    area total sum(pi R_k^2), disposicion en grilla
                 (n >= 2; el disco unico lo cubre "centro")
  embudo         R de los obstaculos         x_f (distancia a la pared), delta (luz del arco)

`familias()` devuelve ese registro; cada entrada sabe construir su configuracion a partir del
valor del parametro y cual es su rango valido. Los constructores de abajo son los ladrillos.

`validate` chequea las restricciones (i) y (ii) del enunciado que son puramente geométricas; la
parte de (ii) que dice "y tal que permita la generación de las N partículas" no se puede decidir
acá y se verifica en la práctica: GenerateMain falla si no logra ubicar las N partículas.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

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


# ---------------------------------------------------------------------------
# Registro de familias
# ---------------------------------------------------------------------------

@dataclass
class Familia:
    """Una familia de configuraciones con un unico parametro libre."""
    nombre: str
    descripcion: str
    etiqueta_parametro: str      # como se rotula el eje x del grafico
    fijos: str                   # que queda fijo, para el pie del grafico
    construir: Callable          # valor del parametro -> configuracion [(x, y, R), ...]
    valores: list                # barrido por defecto del parametro
    formato: str = "{:.4f}"      # como nombrar un valor en los archivos


def _valores_centro(l=L, w=W, r=R_PARTICLE, pasos=15):
    """R desde r hasta el maximo que entra centrado: R <= min(L, W)/2, acotado por el ancho."""
    return [round(v, 6) for v in _linspace(max(r, 0.02), min(l, w) / 2 - 0.005, pasos)]


def _valores_desplazado(radio, l=L, pasos=13):
    """x desde R hasta L-R: el obstaculo tiene que entrar entero (restriccion i)."""
    return [round(v, 6) for v in _linspace(radio, l - radio, pasos)]


def _valores_embudo(x_f, delta, w=W, d=D, r=R_PARTICLE, pasos=12):
    """R hasta donde el par de obstaculos sigue entrando: d/2 + 2R + delta <= W/2, y R <= x_f."""
    r_max = min((w / 2 - d / 2 - delta) / 2, x_f)
    return [round(v, 6) for v in _linspace(max(r, 0.02), r_max, pasos)]


def _linspace(a, b, n):
    if n < 2 or b <= a:
        return [a]
    paso = (b - a) / (n - 1)
    return [a + k * paso for k in range(n)]


def familias(radio_desplazado=0.335, area_total=None, x_embudo=0.15, delta_embudo=0.02,
             cantidades=None):
    """Registro de las cuatro familias, con sus parametros fijos configurables."""
    area_total = math.pi * 0.20 ** 2 if area_total is None else area_total
    # La familia arranca en n = 2, no en n = 1: con area total fija, n = 1 da un unico disco
    # centrado de R = sqrt(A_tot/pi), que es exactamente la familia "centro" con ese radio. Como
    # repartir el area siempre empeora, n = 1 ganaba el barrido y el "mejor caso de multiples
    # obstaculos" terminaba siendo un solo obstaculo. El disco unico ya lo cubre "centro".
    cantidades = [2, 4, 6, 8, 12, 16, 24, 32] if cantidades is None else cantidades

    return {
        "centro": Familia(
            nombre="centro",
            descripcion="Un obstaculo en el centro de la mesa",
            etiqueta_parametro="R [m]",
            fijos=f"centro fijo en ({L / 2:.2f}, {W / 2:.2f})",
            construir=lambda radio: single_centered(radio),
            valores=_valores_centro(),
        ),
        "desplazado": Familia(
            nombre="desplazado",
            descripcion="Un obstaculo desplazado sobre el eje horizontal",
            etiqueta_parametro="x del centro del obstaculo [m]",
            fijos=f"R = {radio_desplazado:.3f} m,  y = W/2 = {W / 2:.2f} m",
            construir=lambda x: single_longitudinal(x, radio_desplazado),
            valores=_valores_desplazado(radio_desplazado),
        ),
        "multiples": Familia(
            nombre="multiples",
            descripcion="Multiples obstaculos distribuidos en grilla",
            etiqueta_parametro="cantidad de obstaculos",
            fijos=(f"area total fija = {area_total:.4f} m2 "
                   f"(equivale a un unico R = {math.sqrt(area_total / math.pi):.3f} m)"),
            construir=lambda n: grid_fixed_area(int(n), area_total),
            valores=[n for n in cantidades if n <= max_n_fixed_area(area_total)],
            formato="{:.0f}",
        ),
        "embudo": Familia(
            nombre="embudo",
            descripcion="Cuatro obstaculos formando un embudo hacia los arcos",
            etiqueta_parametro="R [m]",
            fijos=f"x_f = {x_embudo:.2f} m,  delta = {delta_embudo:.2f} m",
            construir=lambda radio: funnel(x_embudo, radio, delta_embudo),
            valores=_valores_embudo(x_embudo, delta_embudo),
        ),
    }
