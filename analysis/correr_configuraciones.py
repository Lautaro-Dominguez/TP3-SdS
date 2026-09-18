"""Punto 1.2: corrida final de las configuraciones representativas de cada barrido.

Para cada configuracion (y para la mesa vacia, que es la referencia del enunciado):

  1. escribe el archivo de obstaculos "x y R" - uno por configuracion, y QUEDA en disco, porque
     es el formato que pide el enunciado para la competencia y el que consume animate.py;
  2. corre 5 realizaciones independientes (estado inicial nuevo y semilla distinta en cada una);
  3. calcula t90 de cada realizacion leyendo el txt de trayectoria (t90_io.py) y reporta
     <t90> y su desvio estandar muestral;
  4. arma la animacion invocando analysis/animate.py sobre el txt de trayectoria de la primera
     realizacion mas el txt de obstaculos.

El reparto de tareas es el del TP: el motor Java solo simula y graba la trayectoria; todo el
post-procesamiento (t90, estadistica) y toda la visualizacion se hacen en Python a partir de esos
txt. La simulacion graba con --saveEvery 1, asi que el bloque donde Fu cruza 0.9 es exactamente
el del gol numero 90 y t90 no tiene error de discretizacion; la animacion submuestrea ese mismo
txt con el --stride de animate.py.

Uso:
    python3 analysis/correr_configuraciones.py --outdir output/final
"""
from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obstacle_configs as oc
from run_java import generate, simulate
from t90_io import curva_usadas, goles_para_t90

AQUI = Path(__file__).resolve().parent
N = 100


def configuraciones():
    """Una configuracion representativa por barrido, mas la mesa vacia como referencia."""
    a_tot = math.pi * 0.20 ** 2
    return [
        ("00_mesa_vacia", "Mesa vacia (referencia, K=0)", []),
        ("01_ganador", "Ganador: K=1, R=0.335 centrado", oc.single_centered(0.335)),
        ("02_descentrado", "K=1, R=0.335 descentrado (x=0.335)",
         oc.single_longitudinal(0.335, 0.335)),
        ("03_area_repartida", "K=16 en grilla, misma area total que R=0.20",
         oc.grid_fixed_area(16, a_tot)),
        ("04_embudo", "K=4, embudo hacia los arcos (R=0.08)", oc.funnel(0.10, 0.08, 0.02)),
    ]


def una_realizacion(nombre, cfg_path, rep, seed, workdir, tmax, save_every, conservar):
    """Genera, simula y devuelve (t90, N_g final, bloques, ruta o None si se borro)."""
    particles = workdir / f"{nombre}_rep{rep}_particles.txt"
    props = workdir / f"{nombre}_rep{rep}_properties.txt"
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


def animar(traj, cfg_path, destino, bloques, frames_objetivo, speed):
    """Invoca analysis/animate.py tal cual, sobre la trayectoria y los obstaculos."""
    stride = max(1, math.ceil(bloques / frames_objetivo))
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


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", default="output/final")
    parser.add_argument("--reps", type=int, default=5,
                        help="realizaciones por configuracion (el enunciado pide >= 5)")
    parser.add_argument("--tmax", type=float, default=100.0, help="igual al de la competencia")
    parser.add_argument("--save-every", type=int, default=1,
                        help="1 = un bloque por evento; da t90 exacto")
    parser.add_argument("--seed0", type=int, default=3000)
    parser.add_argument("--jobs", type=int, default=3,
                        help="realizaciones en paralelo (cada una escribe cientos de MB)")
    parser.add_argument("--frames", type=int, default=260, help="frames objetivo por animacion")
    parser.add_argument("--speed", type=float, default=8.0)
    parser.add_argument("--sin-animaciones", action="store_true")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    dir_cfg = outdir / "obstaculos"
    dir_gif = outdir / "animaciones"
    for d in (dir_cfg, dir_gif):
        d.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="config_final_"))

    if args.reps < 5:
        print(f"AVISO: --reps {args.reps} esta por debajo del minimo de 5 del enunciado.\n")

    filas, por_realizacion = [], []
    for nombre, descripcion, config in configuraciones():
        problemas = oc.violations(config, allow_empty=(not config))
        if problemas:
            print(f"{nombre}: CONFIGURACION INVALIDA -> {problemas[0]}")
            continue

        cfg_path = None
        if config:
            cfg_path = dir_cfg / f"{nombre}.txt"
            oc.write(cfg_path, config)

        print(f"{nombre}  |  {descripcion}")
        print(f"  K = {len(config)}"
              + (f"  ->  {cfg_path}" if cfg_path else "   (sin archivo de obstaculos)"))

        def corrida(rep):
            return una_realizacion(nombre, cfg_path, rep, args.seed0 + rep, workdir,
                                    args.tmax, args.save_every, conservar=(rep == 0))

        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            resultados = list(pool.map(corrida, range(args.reps)))

        t90s = np.array([r[0] for r in resultados])
        ngs = np.array([r[1] for r in resultados])
        finitos = t90s[np.isfinite(t90s)]
        censuradas = len(t90s) - len(finitos)

        for rep, (t, ng, _b, _p) in enumerate(resultados):
            detalle = f"{t:7.3f} s" if math.isfinite(t) else f"censurada (N_g = {ng})"
            print(f"    realizacion {rep + 1}/{args.reps}:  t90 = {detalle}")

        if len(finitos):
            media = float(finitos.mean())
            sigma = float(finitos.std(ddof=1)) if len(finitos) > 1 else math.nan
            aviso = f"   [{censuradas}/{args.reps} censuradas]" if censuradas else ""
            print(f"    <t90> = {media:.2f} +- {sigma:.2f} s (desvio estandar){aviso}")
        else:
            media = sigma = math.nan
            print(f"    todas censuradas (Fu < 0.9 a t = {args.tmax:g} s), "
                  f"<N_g> = {ngs.mean():.1f}")

        filas.append((nombre, descripcion, len(config), media, sigma, args.reps,
                      censuradas, float(ngs.mean())))
        for rep, (t, ng, _b, _p) in enumerate(resultados):
            por_realizacion.append((nombre, rep + 1, t, ng))

        traj = resultados[0][3]
        if not args.sin_animaciones and traj is not None:
            stride, log = animar(traj, cfg_path, dir_gif / f"{nombre}.gif",
                                  resultados[0][2], args.frames, args.speed)
            print(f"    animacion (stride {stride} sobre {resultados[0][2]} bloques): {log}")
        if traj is not None:
            traj.unlink(missing_ok=True)
            (workdir / f"{nombre}_rep0_properties.txt").unlink(missing_ok=True)
        print()

    # Un archivo con el resumen y otro con el detalle por realizacion: el segundo es el que
    # permite graficar la dispersion real y no solo la barra de error.
    csv_detalle = outdir / "t90_por_realizacion.csv"
    with open(csv_detalle, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["configuracion", "realizacion", "t90", "ng_final"])
        w.writerows(por_realizacion)

    # csv.writer y no un join a mano: las descripciones llevan comas y hay que escaparlas.
    csv_resumen = outdir / "t90_por_configuracion.csv"
    with open(csv_resumen, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["configuracion", "descripcion", "K", "t90_medio", "t90_desvio",
                    "realizaciones", "censuradas", "ng_medio"])
        w.writerows(filas)

    print("Resumen")
    for nombre, _desc, k, media, sigma, _r, cens, ng in filas:
        if math.isfinite(media):
            extra = f"   [{cens} censuradas]" if cens else ""
            print(f"  {nombre:20s} K={k:2d}   <t90> = {media:6.2f} +- {sigma:5.2f} s{extra}")
        else:
            print(f"  {nombre:20s} K={k:2d}   sin t90 (todas censuradas), <N_g> = {ng:.1f}")
    print(f"\nObstaculos -> {dir_cfg}/\nAnimaciones -> {dir_gif}/"
          f"\nDatos -> {csv_resumen}\n        {csv_detalle}")


if __name__ == "__main__":
    main()
