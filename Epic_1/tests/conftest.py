"""Datos sintéticos mínimos con la misma forma que ML-32M (tests en < 5 s)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from movielens import clean, ingest, profile, validate


def synthetic_tables(n_users: int = 30, n_movies: int = 20, seed: int = 7) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    pairs = [(u, m) for u in range(1, n_users + 1) for m in range(1, n_movies + 1) if rng.random() < 0.7]
    ratings = pd.DataFrame(pairs, columns=["userId", "movieId"])
    ratings["rating"] = rng.choice(np.arange(1, 11) / 2, size=len(ratings))
    ratings["timestamp"] = rng.integers(946_684_800, 1_600_000_000, size=len(ratings))  # 2000–2020
    genres = ["Comedy", "Drama", "Action|Thriller", "Comedy|Romance", "Animation|Children|Comedy"]
    movies = pd.DataFrame({
        "movieId": range(1, n_movies + 1),
        "title": [f"Película {i} (2001)" for i in range(1, n_movies + 1)],
        "genres": [genres[i % len(genres)] for i in range(n_movies)],
    })
    tags = ratings.sample(10, random_state=seed)[["userId", "movieId", "timestamp"]].assign(tag="buena")
    tags = tags[["userId", "movieId", "tag", "timestamp"]]
    links = pd.DataFrame({"movieId": movies["movieId"], "imdbId": [f"{i:07d}" for i in movies["movieId"]],
                          "tmdbId": movies["movieId"] + 1000})
    return {"ratings": ratings, "movies": movies, "tags": tags, "links": links}


def write_raw(raw_dir: Path, tables: dict[str, pd.DataFrame], checksums: bool = True) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, df in tables.items():
        path = raw_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        lines.append(f"{hashlib.md5(path.read_bytes()).hexdigest()}  {name}.csv")
    if checksums:
        (raw_dir / "checksums.txt").write_text("\n".join(lines) + "\n")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """params.yaml apuntando a tmp_path y reportes redirigidos (no toca reports/ reales)."""
    reports = tmp_path / "reports"
    paths = {
        "INTEGRITY_REPORT": reports / "quality" / "integrity.json",
        "CHECKS_REPORT": reports / "quality" / "checks.json",
        "QUALITY_METRICS": reports / "metrics" / "quality.json",
        "CLEAN_METRICS": reports / "metrics" / "clean.json",
        "KCORE_SWEEP": reports / "profile" / "kcore_sweep.csv",
        "CLEAN_REPORT": reports / "clean_report.md",
    }
    for module in (ingest, validate, clean, profile):
        for name, value in paths.items():
            if hasattr(module, name):
                monkeypatch.setattr(module, name, value)
    params = {
        "data": {"raw_dir": str(tmp_path / "raw"), "interim_dir": str(tmp_path / "interim"),
                 "processed_dir": str(tmp_path / "processed"), "min_ratings": 5},
        "serving": {"min_ratings": 10},
        "validation": {"verify_checksums": True, "rating_min": 0.5, "rating_max": 5.0, "rating_step": 0.5,
                       "min_date": "1995-01-01", "severity_overrides": {}},
        "clean": {"iterative": True, "max_iter": 50},
        "profile": {"k_values": [1, 5, 10]},
    }
    return {"tmp": tmp_path, "params": params, "paths": paths}
