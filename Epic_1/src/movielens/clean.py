"""Etapa `clean` (US1.3 t2) — aplica el umbral del EDA y guarda los datos limpios.

Regla: cada usuario y cada película del set limpio tiene al menos `data.min_ratings`
ratings (params.yaml). Quitar películas puede dejar usuarios bajo el umbral y viceversa,
así que el filtro se repite hasta que nadie quede por debajo (k-core iterativo, D-02).

Pre-condición: `validate` no reportó fallas bloqueantes (reports/metrics/quality.json).
Post-condición: el resultado cumple el umbral (si no, exit 1).

Salidas:
  data/processed/{ratings,movies,movie_genres,users}.parquet   (versionadas por DVC, hash en dvc.lock)
  reports/metrics/clean.json                                    (métricas: `dvc metrics show/diff`)
  reports/clean_report.md                                       (informe corto de la ejecución)
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .config import (CHECKS_REPORT, CLEAN_METRICS, CLEAN_REPORT, INTEGRITY_REPORT, QUALITY_METRICS, load_params,
                     resolve)
from .ingest import derive_users
from .kcore import kcore_mask, matrix_stats, satisfies_kcore
from .reporting import load_report, write_json


def _n(x: float | int) -> str:
    return f"{int(x):,}".replace(",", ".")


def _pct(a: float, b: float) -> float:
    return round(100 * a / b, 2) if b else 0.0


def write_markdown_report(metrics: dict) -> None:
    """Informe corto: problemas que encontró cada control y ratings eliminados por el umbral."""
    checks = [c for r in (load_report(INTEGRITY_REPORT), load_report(CHECKS_REPORT)) if r for c in r["checks"]]
    b, a = metrics["before"], metrics["after"]
    lines = [
        "# Informe de limpieza",
        "",
        f"Ejecución: {metrics['generated_at']} UTC · umbral `data.min_ratings` = {metrics['min_ratings']}",
        "",
        "## 1. Controles de calidad (US1.3 t1)",
        "",
        f"{sum(c['passed'] for c in checks)} de {len(checks)} controles pasan. "
        "Problemas encontrados por cada control:",
        "",
        "| Control | Tabla | Severidad | Problemas | Resultado |",
        "|---|---|---|---:|---|",
    ]
    for c in checks:
        sev = "bloqueante" if c["severity"] == "blocking" else "aviso"
        lines.append(f"| {c['name']} | {c['table']} | {sev} | {_n(c['n_failed'])} | "
                     f"{'pasa' if c['passed'] else 'FALLA'} |")
    lines += [
        "",
        f"## 2. Filtro por umbral (US1.3 t2): usuarios y películas con ≥ {metrics['min_ratings']} ratings",
        "",
        "| | Antes | Después | Eliminados | % eliminado |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, label in (("ratings", "Ratings"), ("users", "Usuarios"), ("movies", "Películas")):
        removed = b[key] - a[key]
        share = f"{_pct(removed, b[key]):.2f}".replace(".", ",")
        lines.append(f"| {label} | {_n(b[key])} | {_n(a[key])} | {_n(removed)} | {share}% |")
    lines += [
        "",
        f"Densidad de la matriz: {str(b['density_pct']).replace('.', ',')}% → "
        f"{str(a['density_pct']).replace('.', ',')}%. "
        f"El filtro convergió en {metrics['iterations']} iteraciones:",
        "",
        "| Iteración | Ratings | Usuarios | Películas |",
        "|---:|---:|---:|---:|",
        *[f"| {h['iteration']} | {_n(h['ratings'])} | {_n(h['users'])} | {_n(h['items'])} |"
          for h in metrics["history"]],
        "",
        "Datos limpios en `data/processed/` (versión en `dvc.lock`). Métricas: `dvc metrics show`.",
        "",
    ]
    CLEAN_REPORT.parent.mkdir(parents=True, exist_ok=True)
    CLEAN_REPORT.write_text("\n".join(lines), encoding="utf-8")


def run(params: dict) -> int:
    gate = load_report(QUALITY_METRICS)
    if not gate or gate.get("blocking_failed", 1) > 0:
        print(">> clean: la validación (US1.3 t1) no está aprobada; no se generan datos limpios.")
        return 1

    k = int(params["data"]["min_ratings"])
    cp = params.get("clean", {})
    src = resolve(params["data"]["interim_dir"])
    dst = resolve(params["data"]["processed_dir"])
    dst.mkdir(parents=True, exist_ok=True)

    ratings = pq.read_table(src / "ratings.parquet")
    users = ratings["userId"].to_numpy()
    items = ratings["movieId"].to_numpy()
    before = matrix_stats(users, items)

    res = kcore_mask(users, items, k, k, cp.get("iterative", True), cp.get("max_iter", 50))
    clean = ratings.filter(pa.array(res.mask))
    cu, ci = clean["userId"].to_numpy(), clean["movieId"].to_numpy()
    after = matrix_stats(cu, ci)

    if not satisfies_kcore(cu, ci, k, k):
        print(f">> clean: el resultado NO cumple el umbral data.min_ratings = {k}.")
        return 1

    kept_movies = pa.array(np.unique(ci), type=pa.int32())
    for name in ("movies", "movie_genres"):
        tbl = pq.read_table(src / f"{name}.parquet")
        pq.write_table(tbl.filter(pc.is_in(tbl["movieId"], kept_movies)), dst / f"{name}.parquet", compression="zstd")
    pq.write_table(clean, dst / "ratings.parquet", compression="zstd")
    pq.write_table(derive_users(clean), dst / "users.parquet", compression="zstd")

    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "min_ratings": k, "iterative": cp.get("iterative", True),
        "iterations": res.iterations, "converged": res.converged,
        "before": before, "after": after,
        "removed": {key: before[key] - after[key] for key in ("ratings", "users", "movies")},
        "retained_pct": {key: _pct(after[key], before[key]) for key in ("ratings", "users", "movies")},
        "history": res.history,
    }
    write_json(CLEAN_METRICS, {key: v for key, v in metrics.items() if key != "generated_at"})
    write_markdown_report(metrics)

    print(f">> clean: umbral data.min_ratings = {k}; convergió en {res.iterations} iteraciones")
    for key in ("ratings", "users", "movies"):
        print(f"   {key:8} {before[key]:>12,} -> {after[key]:>12,}  "
              f"(eliminados {before[key] - after[key]:,}; se conserva {_pct(after[key], before[key])}%)")
    print(f"   densidad {before['density_pct']}% -> {after['density_pct']}%")
    print(f"   informe: {CLEAN_REPORT.relative_to(CLEAN_REPORT.parents[1])}")
    return 0


def main() -> None:
    sys.exit(run(load_params()))


if __name__ == "__main__":
    main()
