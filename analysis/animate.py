"""Animación del billar-metegol.

Lee un particles.txt YA GENERADO (no corre nada nuevo - toma el archivo de texto como input).
Representa cada partícula como un círculo de radio r, coloreado según su estado ("azul" =
fresca, "rojo" = usada), sobre la mesa L x W con el arco marcado en cada pared corta y, si se
pasa --obstacles, los obstáculos fijos como círculos grises.

Cada frame del GIF es exactamente un bloque del txt - nunca se calcula ni se muestra una
posición intermedia por MRU entre dos bloques guardados. Como el motor es event-driven (el Δt
entre bloques es irregular, no un paso fijo), cada frame se mantiene en pantalla un tiempo
proporcional al Δt real hasta el próximo bloque (--speed controla la escala real-time -> video),
en vez de una duración fija por frame: así un tramo largo sin colisiones se ve como una espera
larga y no como una interpolación continua de movimiento que no está en los datos.

Uso:
    python3 animate.py --traj ../output/particles.txt --obstacles ../output/obstacles.txt \
        --out ../output/animacion.gif
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from billar_io import read_obstacles, read_trajectory

COLOR_MAP = {"azul": "tab:blue", "rojo": "tab:red"}


def render_frames(traj_path, l, w, r, d, obstacles_path=None, stride=1):
    """Dibuja un frame (PIL Image) por cada bloque del txt (subsampleado por stride) y devuelve
    (frames, ts_used) - ts_used son los t_e reales de los bloques efectivamente dibujados, en el
    mismo orden, para que el caller derive las duraciones de cada frame a partir de esos Δt
    reales sin inventar ningún tiempo que no esté en el archivo."""
    ts, positions, colors, _speeds, _thetas = read_trajectory(traj_path)
    idxs = list(range(0, len(ts), stride))
    n = positions[idxs[0]].shape[0]

    fig, ax = plt.subplots(figsize=(8, 8 * w / l))
    ax.set_xlim(0, l)
    ax.set_ylim(0, w)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])

    ax.add_patch(Rectangle((0, 0), l, w, fill=False, edgecolor="black", linewidth=1.5, zorder=1))
    for x_wall in (0, l):
        ax.plot([x_wall, x_wall], [w / 2 - d / 2, w / 2 + d / 2],
                 color="gold", linewidth=5, solid_capstyle="butt", zorder=2)

    if obstacles_path:
        for ox, oy, orad in read_obstacles(obstacles_path):
            ax.add_patch(Circle((ox, oy), orad, facecolor="lightgray", edgecolor="dimgray", zorder=3))

    circles = [Circle((0, 0), r, edgecolor="black", linewidth=0.3, zorder=4) for _ in range(n)]
    for circle in circles:
        ax.add_patch(circle)
    title = ax.set_title("")

    def used_count(cs):
        return sum(1 for c in cs if c == "rojo")

    frames = []
    ts_used = []
    for i in idxs:
        pos = positions[i]
        col = colors[i]
        for circle, (x, y), c in zip(circles, pos, col):
            circle.center = (x, y)
            circle.set_facecolor(COLOR_MAP[c])
        title.set_text(f"t = {ts[i]:.3f} s | usadas: {used_count(col)}/{n}")

        fig.canvas.draw()
        w_px, h_px = fig.canvas.get_width_height()
        buf = np.asarray(fig.canvas.buffer_rgba()).reshape(h_px, w_px, 4)
        frames.append(Image.fromarray(buf).convert("RGB"))
        ts_used.append(ts[i])

    plt.close(fig)
    return frames, ts_used


def frame_durations_ms(ts_used, speed, min_duration_ms, fallback_ms):
    """Duración (ms) de cada frame = Δt real hasta el próximo bloque, escalado por --speed y
    con un piso de min_duration_ms (los visores de GIF no manejan bien frames de ~0ms). El
    último frame no tiene un "próximo" del cual derivar su Δt, así que usa fallback_ms."""
    durations = []
    for k in range(len(ts_used)):
        if k + 1 < len(ts_used):
            dt = ts_used[k + 1] - ts_used[k]
            durations.append(max(min_duration_ms, (dt / speed) * 1000))
        else:
            durations.append(fallback_ms)
    return durations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traj", required=True, help="particles.txt ya generado")
    parser.add_argument("--L", type=float, default=1.20)
    parser.add_argument("--W", type=float, default=0.68)
    parser.add_argument("--d", type=float, default=0.20, help="longitud del arco")
    parser.add_argument("--r", type=float, default=0.0175, help="radio de partícula")
    parser.add_argument("--obstacles", default=None, help="obstaculos.txt (opcional)")
    parser.add_argument("--out", required=True, help="archivo de salida (.gif)")
    parser.add_argument("--stride", type=int, default=1, help="tomar 1 de cada N bloques del txt")
    parser.add_argument("--speed", type=float, default=1.0,
                         help="factor de velocidad real -> video (1.0 = tiempo real, 2.0 = el doble de rápido)")
    parser.add_argument("--min-duration", type=float, default=20.0,
                         help="piso de duración por frame en ms (evita frames casi instantáneos)")
    parser.add_argument("--fps", type=int, default=15,
                         help="solo se usa como duración del último frame, que no tiene un Δt real siguiente")
    args = parser.parse_args()

    frames, ts_used = render_frames(
        args.traj, args.L, args.W, args.r, args.d,
        obstacles_path=args.obstacles, stride=args.stride,
    )
    durations = frame_durations_ms(ts_used, args.speed, args.min_duration, 1000 / args.fps)

    frames[0].save(
        args.out, format="GIF", save_all=True, append_images=frames[1:],
        duration=durations, loop=0,
    )
    print(f"Animacion guardada en {args.out} ({len(frames)} frames, {sum(durations) / 1000:.2f}s de video)")


if __name__ == "__main__":
    main()
