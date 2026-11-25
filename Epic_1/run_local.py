"""Arranque local en un comando, en Windows, macOS o Linux (sin `make`).

    python run_local.py                 # entorno + pipeline (si está el dataset) + dashboard
    python run_local.py --port 8600     # otro puerto
    python run_local.py --skip-pipeline # abre el dashboard con los datos que ya existen

Pasos:
  1. Crea `.venv/` e instala las versiones fijadas en requirements.txt (solo la primera vez
     o cuando cambia requirements.txt).
  2. Si encuentra el dataset crudo (`data.raw_dir` en params.yaml, por defecto ../ml-32m),
     ejecuta `dvc repro`; si no, usa los datos procesados que ya estén en data/.
  3. Abre el dashboard en el navegador (http://localhost:8501).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
DATASET_URL = "https://files.grouplens.org/datasets/movielens/ml-32m.zip"


def run(cmd: list, env: dict | None = None) -> int:
    print("$", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.call([str(c) for c in cmd], cwd=ROOT, env=env)


def ensure_env() -> None:
    stamp = VENV / ".installed"
    req = ROOT / "requirements.txt"
    if stamp.exists() and stamp.stat().st_mtime >= req.stat().st_mtime:
        return
    if not PY.exists():
        print(f"Creando entorno virtual en {VENV} …")
        venv.create(VENV, with_pip=True)
    print("Instalando dependencias (la primera vez tarda unos minutos) …")
    if run([PY, "-m", "pip", "install", "-q", "--upgrade", "pip"]) or \
            run([PY, "-m", "pip", "install", "-q", "-r", req, "-e", "."]):
        sys.exit("No se pudieron instalar las dependencias. Revisa el mensaje de pip más arriba.")
    stamp.touch()


def ensure_scm() -> None:
    """DVC necesita un repositorio git; si no hay (p. ej. al descomprimir el .zip), se crea uno."""
    if (ROOT / ".git").exists():
        return
    if shutil.which("git"):
        run(["git", "init", "-q"])
    else:
        run([PY, "-m", "dvc", "config", "--local", "core.no_scm", "true"])


def raw_dataset() -> Path:
    out = subprocess.check_output(
        [str(PY), "-c", "from movielens.config import load_params, resolve; "
                        "print(resolve(load_params()['data']['raw_dir']))"], cwd=ROOT, text=True)
    return Path(out.strip())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8501)
    ap.add_argument("--skip-pipeline", action="store_true", help="no ejecutar dvc repro")
    args = ap.parse_args()

    if sys.version_info < (3, 11):
        sys.exit(f"Se necesita Python 3.11 o superior (tienes {sys.version.split()[0]}).")
    ensure_env()
    ensure_scm()

    env = {**os.environ, "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS", "4")}
    raw = raw_dataset()
    processed = ROOT / "data" / "processed" / "ratings.parquet"
    if args.skip_pipeline:
        pass
    elif (raw / "ratings.csv").exists():
        if run([PY, "-m", "dvc", "repro"], env=env):
            print("\nEl pipeline se detuvo: el dashboard lo muestra en 'Calidad de datos'.\n")
    elif processed.exists():
        print(f"\nNo está el dataset crudo en {raw}: se usan los datos procesados incluidos en data/.\n")
    else:
        sys.exit(f"Falta el dataset. Descárgalo de {DATASET_URL} y descomprímelo en {raw.parent}, "
                 f"de modo que exista {raw / 'ratings.csv'}.")

    print(f"\nDashboard: http://localhost:{args.port}  (Ctrl+C para detenerlo)\n")
    sys.exit(run([PY, "-m", "streamlit", "run", "app/dashboard.py", "--server.port", args.port,
                  "--server.headless", "false", "--server.showEmailPrompt", "false"], env=env))


if __name__ == "__main__":
    main()
