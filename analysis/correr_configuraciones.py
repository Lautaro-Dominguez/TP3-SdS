"""Punto 1.2: corrida final comparando el MEJOR caso de cada familia de obstaculos.

Las configuraciones no estan escritas a mano: se leen de los CSV que deja barrido_familia.py y,
para cada familia, se toma el valor del parametro que minimizo <t90>. Asi el grafico comparativo
siempre refleja el ultimo barrido y no puede quedar desfasado de el.

Para cada una (y para la mesa vacia, que es la referencia del enunciado):
  1. escribe su archivo de obstaculos "x y R";
  2. corre 5 realizaciones independientes;
  3. calcula t90 de cada una leyendo el txt de trayectoria (t90_io.py) y reporta <t90> y sigma.

Estas corridas usan --saveEvery 1 (un bloque por evento), asi que t90 es exacto: son pocas
configuraciones y el costo se paga. Los barridos, que son cientos de corridas, usan 10.

Las animaciones no se rehacen aca: cada familia ya deja las de su mejor y su peor caso en
output/familias/<familia>/animaciones/.

Uso:
    python3 analysis/correr_configuraciones.py --outdir output/final
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obstacle_configs as oc
from run_java import generate, simulate
from t90_io import curva_usadas, goles_para_t90

N = 100


def mejor_de_cada_familia(dir_familias):
    """Lee los CSV de los barridos y devuelve la mejor configuracion de cada familia."""
    registro = oc.familias()
    elegidas = [("00_mesa_vacia", "Mesa vacia (referencia, K=0)", [])]

    for nombre, familia in registro.items():
        csv_path = Path(dir_familias) / nombre / f"t90_vs_{nombre}.csv"
        if not csv_path.exists():
            print(f"AVISO: falta {csv_path}; se omite la familia '{nombre}'. "
                  f"Corre antes: python3 analysis/barrido_familia.py --familia {nombre}")
            continue
        mejor = None
        with open(csv_path) as f:
            for fila in csv.DictReader(f):
                if fila["etiqueta"] == "mesa_vacia":
                    continue
                try:
                    valor, media = float(fila[familia.etiqueta_parametro]), float(fila["t90_medio"])
                except ValueError:
                    continue
                if math.isfinite(media) and (mejor is None or media < mejor[1]):
                    mejor = (valor, media)
        if mejor is None:
            print(f"AVISO: la familia '{nombre}' no tiene ningun t90 finito; se omite.")
            continue
        valor, media = mejor
        etiqueta_valor = familia.formato.format(valor)
        elegidas.append((
            f"{len(elegidas):02d}_{nombre}",
            f"{familia.descripcion} | {familia.etiqueta_parametro} = {etiqueta_valor}",
            familia.construir(valor)))
    return elegidas


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


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", default="output/final")
    parser.add_argument("--dir-familias", default="output/familias",
                        help="de donde leer los CSV de los barridos por familia")
    parser.add_argument("--reps", type=int, default=5,
                        help="realizaciones por configuracion (el enunciado pide >= 5)")
    parser.add_argument("--tmax", type=float, default=100.0, help="igual al de la competencia")
    parser.add_argument("--save-every", type=int, default=1,
                        help="1 = un bloque por evento; da t90 exacto")
    parser.add_argument("--seed0", type=int, default=None,
                        help="sin valor (lo normal) cada realizacion sortea su condicion inicial;\n"
                             "con un entero se vuelve reproducible (semilla = seed0 + rep)")
    parser.add_argument("--jobs", type=int, default=3,
                        help="realizaciones en paralelo (cada una escribe cientos de MB)")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    dir_cfg = outdir / "obstaculos"
    dir_cfg.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="config_final_"))

    if args.reps < 5:
        print(f"AVISO: --reps {args.reps} esta por debajo del minimo de 5 del enunciado.\n")

    filas, por_realizacion = [], []
    for nombre, descripcion, config in mejor_de_cada_familia(args.dir_familias):
        problemas = oc.violations(config, allow_empty=(not config))
        if problemas:
            print(f"{nombre}: CONFIGURACION INVALIDA -> {problemas[0]}")
            continue

        # Solo las configuraciones con obstaculos llevan archivo: la mesa vacia es la referencia
        # del enunciado, no una configuracion de obstaculos, y se simula y anima sin --obstacles.
        cfg_path = None
        if config:
            cfg_path = dir_cfg / f"{nombre}.txt"
            oc.write(cfg_path, config)

        print(f"{nombre}  |  {descripcion}")
        print(f"  K = {len(config)}"
              + (f"  ->  {cfg_path}" if cfg_path else "   (mesa vacia: sin archivo de obstaculos)"))

        def corrida(rep):
            semilla = None if args.seed0 is None else args.seed0 + rep
            return una_realizacion(nombre, cfg_path, rep, semilla, workdir,
                                    args.tmax, args.save_every, conservar=False)

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
    print(f"\nObstaculos -> {dir_cfg}/"
          f"\nDatos -> {csv_resumen}\n        {csv_detalle}")
    print("Animaciones del mejor y peor caso de cada familia: "
          "output/familias/<familia>/animaciones/")


if __name__ == "__main__":
    main()
