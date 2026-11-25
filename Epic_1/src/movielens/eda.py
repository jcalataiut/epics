"""US1.5 t1 — Consultas del EDA compartidas por el notebook y el dashboard.

Una sola fuente de verdad para los números: `notebooks/01_eda_ratings.ipynb`
(figuras en `report.py`) y el dashboard (figuras en `charts.py`) llaman a estas
funciones, así lo que el equipo ve en el dashboard es lo que se analizó en el EDA.

Las consultas usan DuckDB directamente sobre Parquet: 32M filas se filtran y
agregan en < 1 s sin cargarlas en memoria (ver D-04).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from .config import duckdb_connect


# --------------------------------------------------------------------------- formato
def fmt_int(n: float | int) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def fmt_num(x: float, d: int = 2) -> str:
    return f"{x:,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_pct(x: float, d: int = 1) -> str:
    return f"{fmt_num(x, d)}%"


# --------------------------------------------------------------------------- datos
def open_db(data_dir: str | Path) -> duckdb.DuckDBPyConnection:
    """Vistas `ratings` (+ columna year), `movies` y `movie_genres` sobre los Parquet."""
    d = Path(data_dir)
    con = duckdb_connect()
    con.execute(
        f"CREATE VIEW ratings AS SELECT *, year(make_timestamp(timestamp * 1000000)) AS year "
        f"FROM read_parquet('{(d / 'ratings.parquet').as_posix()}')"
    )
    con.execute(f"CREATE VIEW movies AS SELECT * FROM read_parquet('{(d / 'movies.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW movie_genres AS SELECT * FROM read_parquet('{(d / 'movie_genres.parquet').as_posix()}')")
    # Actividad por usuario y película: la usan el filtro de umbral y el explorador (≈ 0,5 s en ML-32M)
    con.execute("CREATE TABLE user_n AS SELECT userId, count(*) AS n, avg(rating) AS mean_rating "
                "FROM ratings GROUP BY 1")
    con.execute("CREATE TABLE movie_n AS SELECT movieId, count(*) AS n, avg(rating) AS mean_rating "
                "FROM ratings GROUP BY 1")
    return con


def has_data(data_dir: str | Path) -> bool:
    d = Path(data_dir)
    return all((d / f"{t}.parquet").exists() for t in ("ratings", "movies", "movie_genres"))


@dataclass(frozen=True)
class Filters:
    years: tuple[int, int] | None = None
    genres: tuple[str, ...] = ()
    ratings: tuple[float, float] | None = None
    min_ratings: int | None = None   # umbral: usuarios y películas con al menos N ratings (US1.5 t3)

    def sql(self) -> tuple[str, dict]:
        clauses, params = [], {}
        if self.years:
            y0, y1 = self.years
            clauses.append("timestamp >= $ts0 AND timestamp < $ts1")
            params["ts0"] = int(datetime(y0, 1, 1, tzinfo=timezone.utc).timestamp())
            params["ts1"] = int(datetime(y1 + 1, 1, 1, tzinfo=timezone.utc).timestamp())
        if self.ratings:
            clauses.append("rating BETWEEN $r0 AND $r1")
            params["r0"], params["r1"] = float(self.ratings[0]), float(self.ratings[1])
        if self.genres:
            clauses.append("movieId IN (SELECT movieId FROM movie_genres WHERE list_contains($genres, genre))")
            params["genres"] = list(self.genres)
        if self.min_ratings and self.min_ratings > 1:
            clauses.append("userId IN (SELECT userId FROM user_n WHERE n >= $min_n) "
                           "AND movieId IN (SELECT movieId FROM movie_n WHERE n >= $min_n)")
            params["min_n"] = int(self.min_ratings)
        return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


def _q(con: duckdb.DuckDBPyConnection, body: str, f: Filters, extra: dict | None = None) -> pd.DataFrame:
    """Ejecuta `body` con un CTE `r` = ratings filtrados."""
    where, params = f.sql()
    params.update(extra or {})
    return con.cursor().execute(f"WITH r AS (SELECT * FROM ratings {where}) {body}", params).df()


def year_bounds(con: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    lo, hi = con.cursor().execute("SELECT min(year), max(year) FROM ratings").fetchone()
    return int(lo), int(hi)


def genre_list(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.cursor().execute("SELECT genre FROM movie_genres GROUP BY 1 ORDER BY count(*) DESC").fetchall()
    return [g for (g,) in rows]


def kpis(con: duckdb.DuckDBPyConnection, f: Filters = Filters()) -> dict:
    row = _q(con, """SELECT count(*) AS ratings, count(DISTINCT userId) AS users,
                            count(DISTINCT movieId) AS movies, avg(rating) AS mean_rating,
                            median(rating) AS median_rating FROM r""", f).iloc[0]
    out = {k: (float(v) if v == v and v is not None else 0.0) for k, v in row.items()}
    cells = out["users"] * out["movies"]
    out["density_pct"] = 100 * out["ratings"] / cells if cells else 0.0
    out["sparsity_pct"] = 100 - out["density_pct"] if cells else 0.0
    return out


def rating_distribution(con, f: Filters = Filters()) -> pd.DataFrame:
    df = _q(con, "SELECT rating, count(*) AS n FROM r GROUP BY 1 ORDER BY 1", f)
    df["share_pct"] = 100 * df["n"] / df["n"].sum() if len(df) else 0.0
    return df


def yearly(con, f: Filters = Filters()) -> pd.DataFrame:
    return _q(con, "SELECT year, count(*) AS n, avg(rating) AS mean_rating FROM r GROUP BY 1 ORDER BY 1", f)


def genre_stats(con, f: Filters = Filters()) -> pd.DataFrame:
    sel = "WHERE list_contains($sel, g.genre)" if f.genres else ""
    extra = {"sel": list(f.genres)} if f.genres else None
    return _q(con, f"""SELECT g.genre, count(*) AS n, avg(r.rating) AS mean_rating,
                              stddev_samp(r.rating) AS sd_rating
                       FROM r JOIN movie_genres g USING (movieId) {sel}
                       GROUP BY 1 ORDER BY n DESC""", f, extra)


def activity_counts(con, f: Filters = Filters(), by: str = "userId") -> np.ndarray:
    assert by in ("userId", "movieId")
    return _q(con, f"SELECT count(*) AS n FROM r GROUP BY {by}", f)["n"].to_numpy()


def top_movies(con, f: Filters = Filters(), limit: int = 20) -> pd.DataFrame:
    return _q(con, """SELECT m.movieId, m.title, m.genres, count(*) AS n, avg(r.rating) AS mean_rating
                      FROM r JOIN movies m USING (movieId)
                      GROUP BY ALL ORDER BY n DESC LIMIT $limit""", f, {"limit": limit})


def best_rated(con, f: Filters = Filters(), min_n: int = 50, limit: int = 20) -> pd.DataFrame:
    """Mejor nota media entre películas con al menos `min_n` ratings (umbral `serving.min_ratings`)."""
    return _q(con, """SELECT m.movieId, m.title, m.genres, count(*) AS n, avg(r.rating) AS mean_rating
                      FROM r JOIN movies m USING (movieId)
                      GROUP BY ALL HAVING count(*) >= $min_n
                      ORDER BY mean_rating DESC, n DESC LIMIT $limit""", f, {"min_n": min_n, "limit": limit})


def ccdf(counts: np.ndarray, points: int = 160) -> pd.DataFrame:
    """% de entidades con al menos x ratings, en una grilla logarítmica de x."""
    if len(counts) == 0:
        return pd.DataFrame({"x": [], "share_pct": []})
    s = np.sort(counts)
    xs = np.unique(np.round(np.logspace(0, np.log10(s[-1]), points)).astype(int))
    share = 100 * (len(s) - np.searchsorted(s, xs, side="left")) / len(s)
    return pd.DataFrame({"x": xs, "share_pct": share})


def popularity_curve(item_counts: np.ndarray, points: int = 300) -> pd.DataFrame:
    """Curva de concentración: % de películas (más populares primero) vs % acumulado de ratings."""
    if len(item_counts) == 0:
        return pd.DataFrame({"movies_pct": [], "ratings_pct": []})
    s = np.sort(item_counts)[::-1]
    cum = np.cumsum(s) / s.sum()
    idx = np.unique(np.linspace(0, len(s) - 1, points).astype(int))
    return pd.DataFrame({"movies_pct": 100 * (idx + 1) / len(s), "ratings_pct": 100 * cum[idx]})


def share_of_top(item_counts: np.ndarray, top_pct: float = 10.0) -> float:
    if len(item_counts) == 0:
        return 0.0
    s = np.sort(item_counts)[::-1]
    n = max(1, int(round(len(s) * top_pct / 100)))
    return 100 * s[:n].sum() / s.sum()


# ------------------------------------------------- análisis adicionales del informe EDA
def gini(counts: np.ndarray) -> float:
    """Coeficiente de Gini de la actividad: 0 = todos igual de activos, 1 = uno concentra todo."""
    s = np.sort(np.asarray(counts, dtype=float))
    if len(s) == 0 or s.sum() == 0:
        return 0.0
    n = len(s)
    return float((n + 1 - 2 * (np.cumsum(s) / s.sum()).sum()) / n)


def mean_ci(mean: pd.Series, sd: pd.Series, n: pd.Series, z: float = 1.96) -> pd.Series:
    """Semiancho del intervalo de confianza normal (95% por defecto) de una media."""
    return z * sd.fillna(0) / np.sqrt(n.clip(lower=1))


def rating_share_by_year(con, f: Filters = Filters()) -> pd.DataFrame:
    """% de cada nota dentro de cada año (filas: año; columnas: nota)."""
    df = _q(con, "SELECT year, rating, count(*) AS n FROM r GROUP BY 1, 2", f)
    if df.empty:
        return pd.DataFrame()
    t = df.pivot(index="year", columns="rating", values="n").fillna(0).sort_index()
    return 100 * t.div(t.sum(axis=1), axis=0)


def entity_stats(con, f: Filters = Filters(), by: str = "userId") -> pd.DataFrame:
    """Por usuario o película: cantidad de ratings y nota media."""
    assert by in ("userId", "movieId")
    return _q(con, f"SELECT {by} AS id, count(*) AS n, avg(rating) AS mean_rating FROM r GROUP BY 1", f)


def yearly_activity(con, f: Filters = Filters()) -> pd.DataFrame:
    """Por año: ratings, usuarios activos, usuarios nuevos, películas calificadas y nota media (± IC 95%)."""
    df = _q(con, """SELECT year, count(*) AS n, count(DISTINCT userId) AS active_users,
                           count(DISTINCT movieId) AS movies, avg(rating) AS mean_rating,
                           stddev_samp(rating) AS sd_rating
                    FROM r GROUP BY 1 ORDER BY 1""", f)
    new = _q(con, """SELECT first_year AS year, count(*) AS new_users
                     FROM (SELECT userId, min(year) AS first_year FROM r GROUP BY 1) GROUP BY 1""", f)
    df = df.merge(new, on="year", how="left").fillna({"new_users": 0})
    df["ci95"] = mean_ci(df["mean_rating"], df["sd_rating"], df["n"])
    return df


def release_decade_stats(con, f: Filters = Filters()) -> pd.DataFrame:
    """Por década de estreno (año entre paréntesis al final del título): ratings, películas y nota media."""
    df = _q(con, r""", m AS (SELECT movieId,
                                TRY_CAST(regexp_extract(title, '\((\d{4})\)\s*$', 1) AS INTEGER) AS release_year
                                FROM movies)
                     SELECT (release_year // 10) * 10 AS decade, count(*) AS n,
                            count(DISTINCT movieId) AS movies, avg(rating) AS mean_rating,
                            stddev_samp(rating) AS sd_rating
                     FROM r JOIN m USING (movieId)
                     WHERE release_year BETWEEN 1870 AND 2030
                     GROUP BY 1 ORDER BY 1""", f)
    df["ci95"] = mean_ci(df["mean_rating"], df["sd_rating"], df["n"])
    return df


def sparsity_blocks(con, f: Filters = Filters(), bins: int = 50) -> pd.DataFrame:
    """Densidad de la matriz por bloques: usuarios ordenados por actividad y películas por popularidad,
    cada eje dividido en `bins` grupos del mismo tamaño. Devuelve una matriz bins×bins con la densidad en %."""
    where, params = f.sql()
    params["bins"] = bins
    sql = f"""WITH r AS (SELECT userId, movieId FROM ratings {where}),
              u AS (SELECT userId, ntile($bins) OVER (ORDER BY count(*) DESC, userId) AS ub FROM r GROUP BY userId),
              i AS (SELECT movieId, ntile($bins) OVER (ORDER BY count(*) DESC, movieId) AS ib FROM r GROUP BY movieId),
              nu AS (SELECT ub, count(*) AS n_users FROM u GROUP BY 1),
              ni AS (SELECT ib, count(*) AS n_movies FROM i GROUP BY 1),
              c AS (SELECT ub, ib, count(*) AS n FROM r JOIN u USING (userId) JOIN i USING (movieId) GROUP BY 1, 2)
              SELECT nu.ub, ni.ib, coalesce(c.n, 0) AS n, n_users, n_movies
              FROM nu CROSS JOIN ni LEFT JOIN c ON c.ub = nu.ub AND c.ib = ni.ib"""
    df = con.cursor().execute(sql, params).df()
    df["density_pct"] = 100 * df["n"] / (df["n_users"] * df["n_movies"])
    return df.pivot(index="ub", columns="ib", values="density_pct").sort_index().sort_index(axis=1)
