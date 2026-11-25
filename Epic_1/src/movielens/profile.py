"""Etapa `profile` (US1.5 t1) — sensibilidad del k-core para el panel de sparsity.

Calcula, sobre los datos validados, cuánto se conserva y qué densidad resulta
para cada k de `profile.k_values` (k_user = k_item = k). Le da al PO la
evidencia para discutir el valor de `data.min_ratings` sin correr notebooks.

Salida: reports/profile/kcore_sweep.csv (también como `dvc plots`).
"""
from __future__ import annotations

import sys

import pandas as pd
import pyarrow.parquet as pq

from .config import KCORE_SWEEP, load_params, resolve
from .kcore import kcore_mask, matrix_stats


def run(params: dict) -> int:
    src = resolve(params["data"]["interim_dir"])
    ratings = pq.read_table(src / "ratings.parquet", columns=["userId", "movieId"])
    users, items = ratings["userId"].to_numpy(), ratings["movieId"].to_numpy()
    base = matrix_stats(users, items)

    rows = []
    for k in params["profile"]["k_values"]:
        res = kcore_mask(users, items, k, k, iterative=True, max_iter=params["clean"].get("max_iter", 50))
        st = matrix_stats(users[res.mask], items[res.mask])
        rows.append({
            "k": k, **st, "iterations": res.iterations,
            "ratings_kept_pct": round(100 * st["ratings"] / base["ratings"], 2),
            "users_kept_pct": round(100 * st["users"] / base["users"], 2),
            "movies_kept_pct": round(100 * st["movies"] / base["movies"], 2),
        })
        print(f"   k={k:>4}: ratings={st['ratings']:>11,} users={st['users']:>8,} "
              f"movies={st['movies']:>7,} densidad={st['density_pct']}%")
    KCORE_SWEEP.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(KCORE_SWEEP, index=False)
    return 0


def main() -> None:
    sys.exit(run(load_params()))


if __name__ == "__main__":
    main()
