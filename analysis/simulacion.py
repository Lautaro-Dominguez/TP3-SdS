"""Nucleo compartido: correr realizaciones y medir <t90>.

Lo usan el barrido por familia, el mapa de calor y la corrida final de configuraciones, para que
los tres midan exactamente de la misma forma.

Reparto de tareas (el del TP): el motor Java solo simula y graba la trayectoria; t90 se calcula
acá, en Python, leyendo ese txt (t90_io.py). La trayectoria se borra apenas se le extrajo t90,
salvo que se pida conservarla para animarla.

Semillas: por defecto NO se fija ninguna (seed0 = None). Cada realizacion arranca de una
condicion inicial nueva, con la aleatoriedad por defecto de la JVM (GenerateMain cae en
System.nanoTime() si no recibe --seed), igual que el punto 1.1. Pasando un seed0 entero se vuelve
reproducible: la realizacion `rep` usa la semilla seed0 + rep. Eso sirve para depurar, pero no es
el modo en que se corre el TP.

Sobre --saveEvery: el motor graba un bloque cada N eventos, asi que t90 queda cuantizado al
intervalo entre bloques guardados. Medido con N=100: saveEvery 1 da t90 = 23.0991 s (exacto, un
bloque por evento) y saveEvery 10 da 23.1046 s - 0.0055 s de diferencia, unas 400 veces menos que
el desvio estandar entre realizaciones (~2 s), a cambio de correr 6 veces mas rapido y ocupar 9
veces menos disco. Por eso los barridos usan 10 y las configuraciones finales, que son pocas,
usan 1.
"""
from __future__ import annotations

import math
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obstacle_configs as oc
from run_java import generate, simulate
from t90_io import curva_usadas, goles_para_t90

AQUI = Path(__file__).resolve().parent
N = 100


def realizacion(etiqueta, cfg_path, rep, seed, workdir, tmax, save_every, conservar=False):
    """Una realizacion completa. Devuelve (t90, N_g final, cantidad de bloques, ruta o None).

    `seed` None => GenerateMain no recibe --seed y sortea la condicion inicial por su cuenta.
    """
    particles = workdir / f"{etiqueta}_rep{rep}_particles.txt"
    props = workdir / f"{etiqueta}_rep{rep}_properties.txt"
    generate(N, oc.L, oc.W, particles, props, obstacles=cfg_path, seed=seed)
    simulate(oc.L, oc.W, particles, props, particles, tmax, save_every,
             d=oc.D, obstacles=cfg_path)

    ts, usadas = curva_usadas(particles)
    objetivo = goles_para_t90(N)
    t90 = next((t for t, u in zip(ts, usadas) if u >= objetivo), math.nan)

    if conservar:
        return t90, usadas[-1], len(ts), particles
    props.unlink(missing_ok=True)
    particles.unlink(missing_ok=True)
    return t90, usadas[-1], len(ts), None


def medir(config, etiqueta, workdir, reps, tmax, seed0, save_every, jobs,
          dir_config=None, conservar_primera=False, permitir_vacia=False):
    """reps realizaciones de una configuracion -> dict con <t90>, sigma y el detalle.

    `seed0` None (lo normal) => cada realizacion sortea su propia condicion inicial.

    Devuelve None si la configuracion viola las restricciones (i)/(ii) del enunciado, o si el
    generador no logra ubicar las N particulas (la parte empirica de la restriccion ii).
    """
    problemas = oc.violations(config, allow_empty=permitir_vacia)
    if problemas:
        return dict(etiqueta=etiqueta, invalida=problemas[0])

    cfg_path = None
    if config:
        destino = Path(dir_config) if dir_config else workdir
        destino.mkdir(parents=True, exist_ok=True)
        cfg_path = destino / f"{etiqueta}.txt"
        oc.write(cfg_path, config)

    def corrida(rep):
        semilla = None if seed0 is None else seed0 + rep
        return realizacion(etiqueta, cfg_path, rep, semilla, workdir, tmax, save_every,
                            conservar=(conservar_primera and rep == 0))

    try:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            resultados = list(pool.map(corrida, range(reps)))
    except RuntimeError as exc:
        return dict(etiqueta=etiqueta, invalida=str(exc).splitlines()[0])

    t90s = np.array([r[0] for r in resultados])
    ngs = np.array([r[1] for r in resultados])
    finitos = t90s[np.isfinite(t90s)]
    censuradas = int(len(t90s) - len(finitos))

    if len(finitos) == 0:
        media = sigma = math.nan
    else:
        media = float(finitos.mean())
        # Con una sola realizacion no censurada no hay dispersion que reportar: sigma indefinido.
        sigma = float(finitos.std(ddof=1)) if len(finitos) > 1 else math.nan

    return dict(etiqueta=etiqueta, invalida=None, config=config, cfg_path=cfg_path,
                media=media, sigma=sigma, t90s=t90s, censuradas=censuradas,
                ng_medio=float(ngs.mean()), reps=reps,
                traj=resultados[0][3], bloques=resultados[0][2])


def linea_resumen(res):
    """Una linea legible con el resultado de medir()."""
    if res.get("invalida"):
        return f"{res['etiqueta']}: INVALIDA -> {res['invalida']}"
    if math.isnan(res["media"]):
        return (f"{res['etiqueta']}: las {res['reps']} realizaciones censuradas "
                f"(Fu < 0.9), <N_g> = {res['ng_medio']:.1f}")
    aviso = f"   [{res['censuradas']}/{res['reps']} censuradas]" if res["censuradas"] else ""
    sigma = "  n/d" if math.isnan(res["sigma"]) else f"{res['sigma']:5.2f}"
    return f"{res['etiqueta']}: <t90> = {res['media']:6.2f} +- {sigma} s{aviso}"


def animar(traj, cfg_path, destino, bloques, frames=260, speed=8.0):
    """Invoca analysis/animate.py tal cual sobre la trayectoria y el txt de obstaculos.

    El --stride se elige para que la animacion quede en ~`frames` cuadros sea cual sea la
    cantidad de bloques que grabo la corrida; animate.py sigue mostrando solo bloques reales del
    txt, nunca posiciones interpoladas.
    """
    stride = max(1, math.ceil(bloques / frames))
    cmd = [sys.executable, str(AQUI / "animate.py"),
           "--traj", str(traj), "--out", str(destino),
           "--L", str(oc.L), "--W", str(oc.W), "--d", str(oc.D), "--r", str(oc.R_PARTICLE),
           "--stride", str(stride), "--speed", str(speed)]
    if cfg_path is not None:
        cmd += ["--obstacles", str(cfg_path)]
    salida = subprocess.run(cmd, capture_output=True, text=True)
    if salida.returncode != 0:
        raise RuntimeError(f"animate.py fallo:\n{salida.stdout}\n{salida.stderr}")
    return stride, salida.stdout.strip()


def leyenda_arriba(ax, ncol=2):
    """Leyenda fuera del area de datos, donde iria el titulo: nunca tapa el grafico."""
    manejadores, etiquetas = ax.get_legend_handles_labels()
    if etiquetas:
        ax.legend(manejadores, etiquetas, loc="lower center", bbox_to_anchor=(0.5, 1.01),
                  ncol=ncol, frameon=False, fontsize=9)
