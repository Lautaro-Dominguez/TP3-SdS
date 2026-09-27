"""Punto 1.2: goles, Fu(t) y t90 del MEJOR y el PEOR caso de cada familia.

Para cada familia lee su CSV de barrido, identifica el valor del parametro que minimiza y el que
maximiza <t90>, y para cada uno de esos dos extremos:

  1. reconstruye la configuracion y deja su archivo de obstaculos;
  2. corre UNA simulacion con --saveEvery 1 (un bloque por evento), asi los instantes de gol son
     exactos y no quedan redondeados al proximo bloque guardado;
  3. escribe la tabla de goles (instante, N_g/N, Fu) y el grafico de Fu(t) - la misma salida que
     analysis/goles.py, cuyas funciones se reutilizan.

Los extremos se sacan del CSV y no de los archivos mejor_*/peor_* que haya en disco, porque esos
quedan de corridas anteriores: si un barrido se repite con otra cantidad de realizaciones, el
ganador cambia y los archivos viejos siguen ahi.

Ojo con la realizacion: como el TP corre sin semilla fija, esta simulacion es una realizacion
NUEVA, distinta de la que se animo y de las que promedio el barrido. Su t90 es un valor suelto;
el <t90> +- sigma de la familia se anota al pie del grafico para poder ubicarlo.

Uso:
    python3 analysis/goles_extremos.py --dir-familias output/familias
    python3 analysis/goles_extremos.py --familia centro --dir-familias output/familias
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obstacle_configs as oc
from goles import cantidad_de_particulas, goles, graficar
from run_java import generate, simulate
from t90_io import curva_usadas, goles_para_t90

N = 100


def pie_de_grafico(n, media, sigma):
    """Pie del grafico de Fu(t): solo N y el <t90> del barrido."""
    return (f"N = {n}   |   "
            rf"barrido: $\langle t_{{90}} \rangle$ = {media:.2f} $\pm$ {sigma:.2f} s")


def releer_goles(txt):
    """Reconstruye (ts, usadas, n, t90, media, sigma) desde un *_goles.txt ya escrito.

    Fu(t) solo cambia en los goles, asi que la tabla guardada alcanza para redibujar exactamente
    la misma curva escalonada sin volver a simular - importante porque, al correr sin semilla,
    una simulacion nueva daria otra realizacion.
    """
    texto = Path(txt).read_text()
    media, sigma = (float(v) for v in
                    re.search(r"barrido: <t90> = ([\d.]+) \+- ([\d.]+) s", texto).groups())
    n, t_final = re.search(r"N = (\d+) particulas, \d+ bloques, t final = ([\d.]+) s",
                           texto).groups()
    n, t_final = int(n), float(t_final)

    ts, usadas = [0.0], [0]
    for t, ng in re.findall(r"^\s*\d+\s+([\d.]+)\s+(\d+) / \d+\s+[\d.]+\s*$",
                            texto, re.MULTILINE):
        ts.append(float(t))
        usadas.append(int(ng))
    ts.append(t_final)
    usadas.append(usadas[-1])

    hallazgo = re.search(r"^t90 = ([\d.]+) s", texto, re.MULTILINE)
    t90 = float(hallazgo.group(1)) if hallazgo else math.nan
    return ts, usadas, n, t90, media, sigma


def regraficar(dir_familias, nombres):
    """Redibuja los Fu(t) desde los *_goles.txt existentes, sin simular."""
    for nombre in nombres:
        for txt in sorted((Path(dir_familias) / nombre / "extremos").glob("*_goles.txt")):
            ts, usadas, n, t90, media, sigma = releer_goles(txt)
            destino = txt.with_name(txt.name.replace("_goles.txt", "_fu.png"))
            graficar(ts, usadas, n, t90, destino, pie=pie_de_grafico(n, media, sigma))


def extremos_del_csv(familia, csv_path):
    """(mejor, peor) segun el CSV: cada uno como (valor del parametro, <t90>, sigma, etiqueta).

    Una configuracion censurada (sin t90) es el peor caso posible; entre varias censuradas gana
    la de menos goles, que es el criterio de desempate del enunciado.
    """
    filas, censuradas = [], []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            if r["etiqueta"] == "mesa_vacia":
                continue
            valor = float(r[familia.etiqueta_parametro])
            media, sigma = float(r["t90_medio"]), float(r["t90_desvio"])
            registro = (valor, media, sigma, r["etiqueta"], float(r["ng_medio"]))
            (filas if math.isfinite(media) else censuradas).append(registro)

    if not filas and not censuradas:
        return None, None
    mejor = min(filas, key=lambda x: x[1]) if filas else None
    peor = (min(censuradas, key=lambda x: x[4]) if censuradas
            else max(filas, key=lambda x: x[1]))
    return mejor, peor


def procesar(familia, rotulo, registro, base, workdir, tmax, jobs_irrelevante=None):
    """Simula ese extremo una vez y deja el txt de goles y el grafico de Fu(t)."""
    valor, media, sigma, etiqueta, _ng = registro
    config = familia.construir(valor)
    problemas = oc.violations(config)
    if problemas:
        print(f"  {rotulo}: configuracion invalida -> {problemas[0]}")
        return None

    dir_cfg, dir_out = base / "extremos", base / "extremos"
    dir_cfg.mkdir(parents=True, exist_ok=True)
    cfg_path = dir_cfg / f"{rotulo}_{etiqueta}.txt"
    oc.write(cfg_path, config)

    particles = workdir / f"{rotulo}_{etiqueta}_p.txt"
    props = workdir / f"{rotulo}_{etiqueta}_props.txt"
    generate(N, oc.L, oc.W, particles, props, obstacles=cfg_path)
    simulate(oc.L, oc.W, particles, props, particles, tmax, 1, d=oc.D, obstacles=cfg_path)

    n = cantidad_de_particulas(particles)
    ts, usadas = curva_usadas(particles)
    objetivo = goles_para_t90(n)
    t90 = next((t for t, u in zip(ts, usadas) if u >= objetivo), math.nan)
    registros = goles(ts, usadas)

    txt = dir_out / f"{rotulo}_{etiqueta}_goles.txt"
    with open(txt, "w") as f:
        f.write(f"Familia '{familia.nombre}' - caso {rotulo.upper()}\n")
        f.write(f"{familia.etiqueta_parametro} = {familia.formato.format(valor)}   "
                f"(K = {len(config)})\n")
        f.write(f"fijo: {familia.fijos}\n")
        f.write(f"barrido: <t90> = {media:.2f} +- {sigma:.2f} s\n")
        f.write(f"N = {n} particulas, {len(ts)} bloques, t final = {ts[-1]:.6f} s\n")
        f.write(f"umbral de t90: N_g >= {objetivo}\n\n")
        f.write(f"{'gol':>5}  {'t [s]':>12}  {'N_g / N':>12}  {'Fu(t)':>7}\n")
        for numero, t, ng, _sim in registros:
            f.write(f"{numero:>5}  {t:>12.6f}  {ng:>6} / {n:<5}  {ng / n:>7.3f}\n")
        f.write("\n" + (f"t90 = {t90:.6f} s\n" if math.isfinite(t90)
                        else f"t90 no definido: Fu llego a {usadas[-1] / n:.3f} en {tmax:g} s\n"))

    pie = pie_de_grafico(n, media, sigma)
    graficar(ts, usadas, n, t90, dir_out / f"{rotulo}_{etiqueta}_fu.png", pie=pie)

    particles.unlink(missing_ok=True)
    props.unlink(missing_ok=True)
    suelto = f"{t90:.3f} s" if math.isfinite(t90) else "no definido"
    print(f"  {rotulo:5s} {etiqueta:22s} barrido <t90> = {media:6.2f} s   "
          f"esta realizacion: {suelto}")
    return txt


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir-familias", default="output/familias")
    parser.add_argument("--familia", default=None,
                        choices=["centro", "desplazado", "multiples", "embudo"],
                        help="solo esta familia (por defecto, las cuatro)")
    parser.add_argument("--tmax", type=float, default=100.0)
    parser.add_argument("--regraficar", action="store_true",
                        help="redibuja los Fu(t) desde los *_goles.txt ya escritos, sin simular")
    args = parser.parse_args()

    registro = oc.familias()
    nombres = [args.familia] if args.familia else list(registro)

    if args.regraficar:
        regraficar(args.dir_familias, nombres)
        print(f"\nSalida -> {args.dir_familias}/<familia>/extremos/")
        return

    workdir = Path(tempfile.mkdtemp(prefix="goles_extremos_"))

    for nombre in nombres:
        familia = registro[nombre]
        base = Path(args.dir_familias) / nombre
        csv_path = base / f"t90_vs_{nombre}.csv"
        if not csv_path.exists():
            print(f"{nombre}: falta {csv_path}; corre antes barrido_familia.py --familia {nombre}")
            continue

        mejor, peor = extremos_del_csv(familia, csv_path)
        print(f"\nFamilia '{nombre}'  ({familia.etiqueta_parametro})")
        for rotulo, reg in (("mejor", mejor), ("peor", peor)):
            if reg is None:
                print(f"  {rotulo}: sin datos")
                continue
            procesar(familia, rotulo, reg, base, workdir, args.tmax)

    print(f"\nSalida -> {args.dir_familias}/<familia>/extremos/")


if __name__ == "__main__":
    main()
