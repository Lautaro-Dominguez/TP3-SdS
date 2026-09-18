"""Cálculo de Fu(t) y t90 a partir del archivo de trayectoria que escribe el motor.

El motor de simulación solo simula y graba la trayectoria; todo el post-procesamiento vive acá.
Del txt se lee, bloque por bloque, el tiempo de sistema t_e del header y la columna de color, y de
ahí salen las magnitudes que define el enunciado:

    N_g(t) = cantidad de particulas "rojo" (usadas) en el bloque de tiempo t
    Fu(t)  = N_g(t) / N
    t90    = min { t : Fu(t) >= 0.9 }

Con N = 100, t90 es el instante del gol numero 90. El umbral se calcula en aritmetica entera
(k = ceil(9N/10)) para no depender de como redondee 0.9*N en punto flotante.

No se usa billar_io.read_trajectory a proposito: esa funcion arma los arrays de posiciones de
TODOS los bloques, y un txt grabado con --saveEvery 1 tiene decenas de miles de bloques. Para t90
solo hace falta la columna de color, asi que se recorre el archivo en streaming sin construir
nada por particula.
"""
from __future__ import annotations

import math

USADA = "rojo"


def goles_para_t90(n):
    """Menor cantidad de goles k con k/n >= 0.9, es decir ceil(9n/10), en enteros exactos."""
    return (9 * n + 9) // 10


def curva_usadas(path):
    """Recorre la trayectoria y devuelve (ts, usadas): un par por bloque guardado."""
    ts, usadas = [], []
    t_actual, cuenta, abierto = None, 0, False
    with open(path) as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            campos = linea.split()
            if len(campos) == 1:                      # header: t_e del bloque
                if abierto:
                    ts.append(t_actual)
                    usadas.append(cuenta)
                t_actual, cuenta, abierto = float(campos[0]), 0, True
            elif len(campos) == 5 and abierto:        # x y v color theta
                if campos[3] == USADA:
                    cuenta += 1
    if abierto:
        ts.append(t_actual)
        usadas.append(cuenta)
    return ts, usadas


def t90_de_trayectoria(path, n):
    """(t90, N_g final). t90 es NaN si Fu nunca llega a 0.9 en lo simulado (caso censurado)."""
    ts, usadas = curva_usadas(path)
    if not ts:
        raise ValueError(f"{path} no tiene bloques")
    objetivo = goles_para_t90(n)
    for t, u in zip(ts, usadas):
        if u >= objetivo:
            return t, usadas[-1]
    return math.nan, usadas[-1]
