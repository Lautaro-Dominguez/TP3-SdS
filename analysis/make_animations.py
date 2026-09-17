"""Punto 1.2: animaciones de las configuraciones representativas de cada barrido.

NO reimplementa el dibujo de la mesa: importa `render_frames` y `frame_durations_ms` de
animate.py y los usa tal cual, así la mesa, el arco, los obstáculos y el código de color
(azul = fresca, rojo = usada) salen del mismo renderer que el resto del TP. Todo lo que se agrega
va compuesto POR ENCIMA de esos frames, ubicando la mesa en píxeles a partir de sus propias
paredes (`ubicar_mesa`), de modo que se puede dibujar en coordenadas de simulación sin tocar
animate.py.

Qué agrega:
  - placa de título con el <t90> +- sigma medido en el barrido (30 realizaciones), no el de esta
    corrida suelta;
  - estela de posiciones registradas: los últimos estados guardados de cada partícula, con
    opacidad decreciente. Son posiciones REALES del txt dibujadas como puntos - no se unen con
    segmentos, porque entre dos bloques guardados puede haber colisiones y la recta que los une
    sería una trayectoria inventada (el mismo criterio por el que animate.py no interpola);
  - destello en el arco cada vez que una partícula convierte, y marcador de goles por arco -
    hasta ahora un gol era invisible (una partícula se volvía roja en algún lado);
  - barra de progreso de Fu con la marca del 90%: el instante en que la cruza es t90;
  - CONGELADO en t90, con cartel, para que el número que se está minimizando sea un momento del
    video;
  - comparativa lado a lado y grilla de las cinco, a RELOJ COMPARTIDO, con una carrera de barras
    que muestra las cinco Fu(t) sobre un mismo eje.

Para el reloj compartido se eligen, entre los bloques realmente guardados, los más cercanos a una
grilla uniforme de tiempos: se re-ordenan estados que ya existen en el txt, nunca se interpola
una posición por MRU.

Uso:
    python3 analysis/make_animations.py --outdir output/animaciones
"""
from __future__ import annotations

import argparse
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obstacle_configs as oc
from animate import frame_durations_ms, render_frames
from billar_io import read_trajectory
from run_java import generate, simulate

N = 100
TMAX = 45.0
SEED = 2024
K90 = (9 * N + 9) // 10

ROJO, GRIS, NEGRO = (214, 39, 40), (120, 120, 120), (20, 20, 20)
PALETA = [(31, 119, 180), (44, 160, 44), (214, 39, 40), (255, 127, 14), (148, 103, 189)]


def fuente(tam, negrita=False):
    nombre = "Arial Bold.ttf" if negrita else "Arial.ttf"
    try:
        return ImageFont.truetype(f"/System/Library/Fonts/Supplemental/{nombre}", tam)
    except OSError:
        return ImageFont.load_default()


def escenas():
    """Configuración representativa de cada barrido. <t90> +- sigma vienen del barrido (M=30)."""
    a_tot_c = math.pi * 0.20 ** 2
    return [
        ("00_mesa_vacia", "Mesa vacia (referencia)", "K = 0", 22.20, 3.06, []),
        ("01_ganador", "GANADOR", "K = 1,  R = 0.335 centrado", 15.30, 1.87,
         oc.single_centered(0.335)),
        ("02_descentrado", "Mismo disco, descentrado", "K = 1,  x = 0.335", 53.52, 11.63,
         oc.single_longitudinal(0.335, 0.335)),
        ("03_laberinto", "Area fija repartida", "K = 16,  misma area total que R = 0.20",
         42.31, 4.00, oc.grid_fixed_area(16, a_tot_c)),
        ("04_embudo", "Embudo hacia los arcos", "K = 4,  R = 0.08", 34.34, 3.41,
         oc.funnel(0.10, 0.08, 0.02)),
    ]


def simular(nombre, config, workdir, save_every, tmax=TMAX, seed=SEED):
    cfg_path = None
    if config:
        cfg_path = workdir / f"{nombre}_obs.txt"
        oc.write(cfg_path, config)
    particles = workdir / f"{nombre}_p.txt"
    props = workdir / f"{nombre}_props.txt"
    generate(N, oc.L, oc.W, particles, props, obstacles=cfg_path, seed=seed)
    simulate(oc.L, oc.W, particles, props, particles, tmax, save_every, d=oc.D, obstacles=cfg_path)
    return particles, cfg_path


def recortar(frame):
    diff = ImageChops.difference(frame, Image.new(frame.mode, frame.size, (255, 255, 255)))
    caja = diff.getbbox()
    return frame.crop(caja) if caja else frame


def ubicar_mesa(frame):
    """Bordes de la mesa en píxeles: sus paredes son las únicas líneas oscuras largas del frame.

    Permite pasar de coordenadas de simulación a píxeles sin conocer nada de la figura interna de
    matplotlib que arma animate.py.
    """
    oscuro = np.asarray(frame.convert("RGB")).astype(int).sum(axis=2) < 200
    filas, cols = oscuro.sum(axis=1), oscuro.sum(axis=0)
    ys = np.flatnonzero(filas > 0.6 * filas.max())
    xs = np.flatnonzero(cols > 0.6 * cols.max())
    return xs.min(), ys.min(), xs.max(), ys.max()


def a_pixel(caja, x, y):
    x0, y0, x1, y1 = caja
    return x0 + (x / oc.L) * (x1 - x0), y1 - (y / oc.W) * (y1 - y0)


def superponer(frame, caja, estela, destellos, radio_px):
    """Dibuja la estela de posiciones registradas y los destellos de gol sobre el frame."""
    capa = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    for edad, (posiciones, usadas) in enumerate(estela):
        peso = (edad + 1) / (len(estela) + 1)
        alfa = int(70 * peso)
        rp = max(1.0, radio_px * (0.30 + 0.45 * peso))
        for (x, y), usada in zip(posiciones, usadas):
            px, py = a_pixel(caja, x, y)
            color = (214, 39, 40, alfa) if usada else (31, 119, 180, alfa)
            d.ellipse([px - rp, py - rp, px + rp, py + rp], fill=color)
    for x, y, edad, total in destellos:
        px, py = a_pixel(caja, x, y)
        rad = radio_px * (1.6 + 3.4 * edad / total)
        alfa = int(230 * (1 - edad / total))
        d.ellipse([px - rad, py - rad, px + rad, py + rad], outline=(255, 190, 0, alfa), width=3)
    return Image.alpha_composite(frame.convert("RGBA"), capa).convert("RGB")


def encabezado(frame, titulo, subtitulo, usadas, t, goles_izq, goles_der, congelado=None,
               alto=84):
    lienzo = Image.new("RGB", (frame.width, frame.height + alto), "white")
    lienzo.paste(frame, (0, alto))
    d = ImageDraw.Draw(lienzo)
    d.text((14, 6), titulo, fill="black", font=fuente(20, negrita=True))
    d.text((14, 31), subtitulo, fill=GRIS, font=fuente(12))

    marcador = f"arco izq {goles_izq:3d}   |   arco der {goles_der:3d}      t = {t:5.2f} s"
    f17 = fuente(15, negrita=True)
    d.text((frame.width - 14 - d.textlength(marcador, font=f17), 8), marcador,
           fill="black", font=f17)

    x0, x1, y0, alto_barra = 14, frame.width - 14, 56, 15
    fu = usadas / N
    d.rectangle([x0, y0, x1, y0 + alto_barra], fill=(238, 238, 238), outline=(190, 190, 190))
    if fu > 0:
        d.rectangle([x0, y0, x0 + (x1 - x0) * fu, y0 + alto_barra], fill=ROJO)
    xm = x0 + (x1 - x0) * 0.9
    d.line([xm, y0 - 4, xm, y0 + alto_barra + 4], fill="black", width=2)
    d.text((xm + 5, y0 - 2), "90%", fill="black", font=fuente(11, negrita=True))
    d.text((x0 + 5, y0 + 2), f"Fu = {fu:.2f}   ({usadas}/{N} usadas)",
           fill="white" if fu > 0.35 else GRIS, font=fuente(11, negrita=True))

    if congelado is not None:
        capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
        dd = ImageDraw.Draw(capa)
        texto = f"t90 = {congelado:.1f} s"
        ft = fuente(46, negrita=True)
        tw = dd.textlength(texto, font=ft)
        cx, cy = lienzo.width / 2, alto + frame.height / 2
        dd.rectangle([cx - tw / 2 - 26, cy - 44, cx + tw / 2 + 26, cy + 30],
                     fill=(255, 255, 255, 232), outline=(214, 39, 40, 255), width=4)
        dd.text((cx - tw / 2, cy - 36), texto, fill=(214, 39, 40, 255), font=ft)
        sub = "Fu alcanza 0.90"
        fs = fuente(16, negrita=True)
        dd.text((cx - dd.textlength(sub, font=fs) / 2, cy + 8), sub, fill=NEGRO, font=fs)
        lienzo = Image.alpha_composite(lienzo.convert("RGBA"), capa).convert("RGB")
    return lienzo


def placa(tam, titulo, subtitulo, t90_medio, sigma):
    """Placa de presentación con el resultado del barrido, no el de esta realización suelta."""
    lienzo = Image.new("RGB", tam, "white")
    d = ImageDraw.Draw(lienzo)
    cx, cy = tam[0] / 2, tam[1] / 2
    for texto, ft, dy, color in [
        (titulo, fuente(44, True), -90, NEGRO),
        (subtitulo, fuente(22), -30, GRIS),
        (f"<t90> = {t90_medio:.2f} +- {sigma:.2f} s", fuente(34, True), 24, ROJO),
        ("promedio sobre 30 realizaciones   |   barra de error: desvio estandar",
         fuente(15), 76, GRIS),
    ]:
        d.text((cx - d.textlength(texto, font=ft) / 2, cy + dy), texto, fill=color, font=ft)
    return lienzo


def en_grilla_temporal(items, ts, objetivos):
    ts = np.asarray(ts)
    return [items[int(np.argmin(np.abs(ts - t)))] for t in objetivos]


def carrera(ancho, nombres, fracciones, colores, alto_fila=26):
    """Carrera de barras: las Fu(t) de todas las configuraciones sobre un mismo eje."""
    alto = alto_fila * len(nombres) + 34
    lienzo = Image.new("RGB", (ancho, alto), "white")
    d = ImageDraw.Draw(lienzo)
    d.text((14, 4), "carrera de Fu(t)", fill=NEGRO, font=fuente(15, negrita=True))
    x0, x1 = 250, ancho - 70
    for k, (nombre, fu, color) in enumerate(zip(nombres, fracciones, colores)):
        y = 26 + k * alto_fila
        d.text((14, y + 3), nombre[:34], fill=NEGRO, font=fuente(13))
        d.rectangle([x0, y, x1, y + 16], fill=(240, 240, 240), outline=(200, 200, 200))
        if fu > 0:
            d.rectangle([x0, y, x0 + (x1 - x0) * fu, y + 16], fill=color)
        d.text((x1 + 8, y + 2), f"{fu:.2f}", fill=NEGRO, font=fuente(13, negrita=True))
    xm = x0 + (x1 - x0) * 0.9
    d.line([xm, 22, xm, alto - 6], fill="black", width=2)
    d.text((xm + 4, 8), "90%", fill="black", font=fuente(11, negrita=True))
    return lienzo


def guardar_gif(destino, frames, duraciones):
    frames[0].save(destino, format="GIF", save_all=True, append_images=frames[1:],
                   duration=duraciones, loop=0, optimize=True)
    print(f"  {destino}  ({len(frames)} frames, {sum(duraciones) / 1000:.1f}s de video, "
          f"{destino.stat().st_size / 1e6:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", default="output/animaciones")
    parser.add_argument("--save-every", type=int, default=120)
    parser.add_argument("--max-frames", type=int, default=260)
    parser.add_argument("--speed", type=float, default=4.0)
    parser.add_argument("--frames-compartidos", type=int, default=220)
    parser.add_argument("--largo-estela", type=int, default=6)
    parser.add_argument("--frames-destello", type=int, default=6)
    parser.add_argument("--frames-congelado", type=int, default=14)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="animaciones_"))
    render = {}

    for nombre, titulo, subtitulo, t90_medio, sigma, config in escenas():
        traj, cfg_path = simular(nombre, config, workdir, args.save_every)
        ts_all, pos_all, col_all, _sp, _th = read_trajectory(traj)
        usadas_all = [sum(1 for c in cs if c == "rojo") for cs in col_all]
        t90 = next((t for t, u in zip(ts_all, usadas_all) if u >= K90), None)
        pie = f"t90 = {t90:.1f} s" if t90 else f"no alcanza Fu = 0.9 en {TMAX:g} s"
        print(f"{titulo} ({pie})")

        stride = max(1, math.ceil(len(ts_all) / args.max_frames))
        idxs = list(range(0, len(ts_all), stride))
        frames, ts = render_frames(traj, oc.L, oc.W, oc.R_PARTICLE, oc.D,
                                    obstacles_path=cfg_path, stride=stride)
        frames = [recortar(f) for f in frames]
        caja = ubicar_mesa(frames[0])
        radio_px = (oc.R_PARTICLE / oc.L) * (caja[2] - caja[0])

        # ts_video lleva los frames del GIF individual (incluye los repetidos del congelado);
        # ts queda intacta porque es la que usa el reloj compartido para sincronizar paneles.
        compuestos, ts_video, destellos, izq, der, congelado_ya = [], [], [], 0, 0, False
        for k, (i, frame, t) in enumerate(zip(idxs, frames, ts)):
            usadas_mask = np.array([c == "rojo" for c in col_all[i]])
            if k > 0:
                previas = np.array([c == "rojo" for c in col_all[idxs[k - 1]]])
                for j in np.flatnonzero(usadas_mask & ~previas):
                    x, y = pos_all[i][j]
                    destellos.append([x, y, 0, args.frames_destello])
                    if x < oc.L / 2:
                        izq += 1
                    else:
                        der += 1

            estela = [(pos_all[idxs[m]], [c == "rojo" for c in col_all[idxs[m]]])
                      for m in range(max(0, k - args.largo_estela), k)]
            con_capa = superponer(frame, caja, estela, destellos, radio_px)
            compuestos.append(encabezado(con_capa, titulo, f"{subtitulo}   |   {pie}",
                                         usadas_all[i], t, izq, der))
            ts_video.append(t)

            destellos = [[x, y, e + 1, tot] for x, y, e, tot in destellos if e + 1 < tot]

            if not congelado_ya and t90 is not None and usadas_all[i] >= K90:
                congelado_ya = True
                helado = encabezado(con_capa, titulo, f"{subtitulo}   |   {pie}",
                                     usadas_all[i], t, izq, der, congelado=t90)
                compuestos.extend([helado] * args.frames_congelado)
                ts_video.extend([t] * args.frames_congelado)

        tam = compuestos[0].size
        intro = placa(tam, titulo, subtitulo, t90_medio, sigma)
        duraciones = [1600.0] + frame_durations_ms(ts_video, args.speed, 20.0, 1000 / 15)
        guardar_gif(outdir / f"{nombre}.gif", [intro] + compuestos, duraciones)
        render[nombre] = dict(frames=frames, caja=caja, radio_px=radio_px, ts=list(ts),
                               idxs=idxs, pos=pos_all, col=col_all, usadas=usadas_all,
                               titulo=titulo, subtitulo=subtitulo, pie=pie)

    objetivos = np.linspace(0, TMAX, args.frames_compartidos)
    paso_ms = max(20.0, (objetivos[1] - objetivos[0]) / args.speed * 1000)

    def panel(clave, t):
        e = render[clave]
        pos = np.argmin(np.abs(np.asarray(e["ts"][:len(e["frames"])]) - t))
        i = e["idxs"][pos]
        estela = [(e["pos"][e["idxs"][m]], [c == "rojo" for c in e["col"][e["idxs"][m]]])
                  for m in range(max(0, pos - 4), pos)]
        f = superponer(e["frames"][pos], e["caja"], estela, [], e["radio_px"])
        izq = sum(1 for j, c in enumerate(e["col"][i]) if c == "rojo" and e["pos"][i][j][0] < oc.L / 2)
        return (encabezado(f, e["titulo"], f"{e['subtitulo']}   |   {e['pie']}",
                           e["usadas"][i], t, izq, e["usadas"][i] - izq),
                e["usadas"][i] / N)

    print("Comparativa a reloj compartido")
    compuestos = []
    for t in objetivos:
        (a, _), (b, _) = panel("00_mesa_vacia", t), panel("01_ganador", t)
        lienzo = Image.new("RGB", (a.width + b.width + 24, a.height + 34), "white")
        lienzo.paste(a, (0, 34)); lienzo.paste(b, (a.width + 24, 34))
        d = ImageDraw.Draw(lienzo)
        d.text((14, 8), f"RELOJ COMPARTIDO     t = {t:5.2f} s", fill=NEGRO, font=fuente(19, True))
        d.line([a.width + 12, 34, a.width + 12, lienzo.height], fill=(210, 210, 210), width=2)
        compuestos.append(lienzo)
    guardar_gif(outdir / "05_comparativa_vacia_vs_ganador.gif", compuestos,
                [paso_ms] * len(compuestos))

    print("Grilla de las cinco configuraciones")
    claves = [n for n, *_ in escenas()]
    nombres = [e[1] for e in escenas()]
    compuestos = []
    for t in objetivos:
        paneles, fracciones = zip(*(panel(c, t) for c in claves))
        pw, ph = paneles[0].size
        cols, filas = 2, 3
        barras = carrera(pw, nombres, fracciones, PALETA)
        lienzo = Image.new("RGB", (cols * pw + (cols + 1) * 14,
                                    filas * ph + (filas + 1) * 14 + 34 + barras.height), "white")
        ImageDraw.Draw(lienzo).text((16, 8), f"RELOJ COMPARTIDO     t = {t:5.2f} s",
                                     fill=NEGRO, font=fuente(21, True))
        for k, p in enumerate(paneles):
            fila, col = divmod(k, cols)
            lienzo.paste(p, (14 + col * (pw + 14), 48 + fila * (ph + 14)))
        # las cinco escenas dejan libre el sexto lugar de la grilla 2x3: ahi va la carrera
        hueco_fila, hueco_col = divmod(len(paneles), cols)
        lienzo.paste(barras, (14 + hueco_col * (pw + 14), 48 + hueco_fila * (ph + 14)))
        compuestos.append(lienzo)
    guardar_gif(outdir / "06_grilla_cinco_configuraciones.gif", compuestos,
                [paso_ms] * len(compuestos))


if __name__ == "__main__":
    main()
