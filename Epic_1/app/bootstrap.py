"""Preparación del entorno antes de cargar el dashboard (local o Streamlit Community Cloud).

1. Hace importable el paquete `movielens` desde `src/` aunque no esté instalado con `pip install -e .`
   (en Community Cloud solo se instala `app/requirements.txt`).
2. Copia a variables de entorno los secretos `EPIC1_*` de `st.secrets` (p. ej. límites de DuckDB).
3. Si faltan los datos procesados y hay un secreto `EPIC1_DATA_URL`, descarga el paquete de datos
   (`epic1_data.zip`, con `data/interim` y `data/processed`) y lo descomprime en la raíz del proyecto.
   Los Parquet pesan ~340 MB: no caben en git (límite de 100 MB por archivo en GitHub).
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def load_secrets() -> None:
    try:
        items = dict(st.secrets)
    except Exception:  # sin secrets.toml: ejecución local normal
        return
    for key, value in items.items():
        if key.startswith("EPIC1_") and isinstance(value, (str, int, float)):
            os.environ.setdefault(key, str(value))


@st.cache_resource(show_spinner=False)
def ensure_data() -> str:
    """Descarga los datos una vez por proceso si no están. Devuelve 'local', 'descargados' o 'sin datos'."""
    processed = ROOT / "data" / "processed" / "ratings.parquet"
    if processed.exists():
        return "local"
    url = os.environ.get("EPIC1_DATA_URL")
    if not url:
        return "sin datos"
    headers = {"User-Agent": "epic1-dashboard"}
    if token := os.environ.get("EPIC1_DATA_TOKEN"):   # p. ej. asset de un release en un repo privado
        headers |= {"Authorization": f"Bearer {token}", "Accept": "application/octet-stream"}
    with st.status("Descargando los datos del dashboard (~340 MB, solo al arrancar)…", expanded=False) as status:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data.zip"
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=600) as r, \
                    open(target, "wb") as fh:
                shutil.copyfileobj(r, fh, length=8 << 20)
            with zipfile.ZipFile(target) as zf:
                bad = [n for n in zf.namelist() if not n.startswith("data/") or ".." in Path(n).parts]
                if bad:
                    raise RuntimeError(f"El paquete de datos tiene rutas inesperadas: {bad[:3]}")
                zf.extractall(ROOT)
        status.update(label="Datos listos", state="complete")
    return "descargados"


load_secrets()
