"""Carga de params.yaml y resolución de rutas relativas a la raíz de la épica."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PARAMS_PATH = ROOT / "params.yaml"

# Rutas de reportes (versionados en git, no en caché DVC)
REPORTS = ROOT / "reports"
INTEGRITY_REPORT = REPORTS / "quality" / "integrity.json"
CHECKS_REPORT = REPORTS / "quality" / "checks.json"
QUALITY_METRICS = REPORTS / "metrics" / "quality.json"
CLEAN_METRICS = REPORTS / "metrics" / "clean.json"
KCORE_SWEEP = REPORTS / "profile" / "kcore_sweep.csv"
CLEAN_REPORT = REPORTS / "clean_report.md"   # informe corto de cada ejecución (US1.3 t2)


def duckdb_connect():
    """Conexión DuckDB con límites explícitos.

    Por defecto DuckDB usa todos los núcleos y ~80% de la RAM; en servidores compartidos
    (o con `ulimit -v`) eso falla con OutOfMemory incluso con datos pequeños.
    Ajustable con EPIC1_DUCKDB_THREADS / EPIC1_DUCKDB_MEMORY.
    """
    import duckdb

    threads = int(os.environ.get("EPIC1_DUCKDB_THREADS", min(8, os.cpu_count() or 1)))
    memory = os.environ.get("EPIC1_DUCKDB_MEMORY", "4GB")
    return duckdb.connect(config={"threads": threads, "memory_limit": memory})


def load_params(path: str | Path | None = None) -> dict:
    with open(path or PARAMS_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve(path: str | Path) -> Path:
    """Rutas de params.yaml son relativas a la raíz de Epic_1."""
    p = Path(path)
    return p if p.is_absolute() else (ROOT / p).resolve()
