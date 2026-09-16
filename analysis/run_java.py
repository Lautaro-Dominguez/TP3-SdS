"""Invoca sim.app.GenerateMain / sim.app.SimulateMain directamente con `java` (usando las
clases ya compiladas en out/), sin pasar por ningún build system en cada corrida. El motor Java
en sí no se modifica: esto solo lo invoca como subproceso, igual que se haría a mano desde la
línea de comandos.

Requiere haber corrido `javac -d out $(find src -name "*.java")` en TP3/ al menos una vez.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLASSES = REPO_ROOT / "out"


def _run(main_class, flags):
    if not CLASSES.exists():
        raise SystemExit(
            f'No existe {CLASSES} - corre `javac -d out $(find src -name "*.java")` en '
            f"{REPO_ROOT} antes de usar este script.")
    cmd = ["java", "-cp", str(CLASSES), main_class]
    for key, value in flags.items():
        cmd += [f"--{key}", str(value)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{main_class} fallo (args={flags}):\n{result.stdout}\n{result.stderr}")
    return result.stdout


def generate(n, l, w, out_state, out_props, r=None, m=None, v0=None, obstacles=None, seed=None):
    flags = {"N": n, "L": l, "W": w, "outState": out_state, "outProps": out_props}
    if r is not None:
        flags["r"] = r
    if m is not None:
        flags["m"] = m
    if v0 is not None:
        flags["v0"] = v0
    if obstacles is not None:
        flags["obstacles"] = obstacles
    if seed is not None:
        flags["seed"] = seed
    return _run("sim.app.GenerateMain", flags)


def simulate(l, w, in_path, props_path, out_path, tmax, save_every, d=None, obstacles=None):
    flags = {
        "L": l,
        "W": w,
        "in": in_path,
        "props": props_path,
        "out": out_path,
        "tmax": tmax,
        "saveEvery": save_every,
    }
    if d is not None:
        flags["d"] = d
    if obstacles is not None:
        flags["obstacles"] = obstacles
    return _run("sim.app.SimulateMain", flags)
