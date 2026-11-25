"""US1.5 — consultas del explorador de usuarios y películas y del grafo de gustos.

Una «reacción» es la nota que un usuario le dio a una película:
  le gustó (nota ≥ LIKE), neutral, no le gustó (nota ≤ DISLIKE).

Similitud entre películas: coseno sobre los usuarios a los que les gustaron
  sim(i, j) = |A_i ∩ A_j| / sqrt(|A_i| · |A_j|),  A_x = usuarios con nota ≥ LIKE en x.
Es la base de un recomendador item-item; el grafo de gustos la dibuja.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from .eda import Filters

LIKE = 4.0
DISLIKE = 2.0


def reaction(rating: float) -> str:
    if rating >= LIKE:
        return "Le gustó"
    if rating <= DISLIKE:
        return "No le gustó"
    return "Neutral"


def _df(con: duckdb.DuckDBPyConnection, sql: str, params: dict | None = None) -> pd.DataFrame:
    return con.cursor().execute(sql, params or {}).df()


def _primary_genre(genres: pd.Series) -> pd.Series:
    return genres.fillna("").str.split("|").str[0].replace({"(no genres listed)": "Sin género", "": "Sin género"})


# --------------------------------------------------------------------------- usuarios
def user_ids_sample(con, n: int = 1, min_ratings: int = 50, seed: int | None = None) -> list[int]:
    """Usuarios al azar con al menos `min_ratings` ratings (para el botón «usuario al azar»)."""
    ids = _df(con, "SELECT userId FROM user_n WHERE n >= $m ORDER BY userId", {"m": min_ratings})["userId"]
    if ids.empty:
        return []
    return [int(x) for x in np.random.default_rng(seed).choice(ids.to_numpy(), size=min(n, len(ids)), replace=False)]


def user_exists(con, user_id: int) -> bool:
    return bool(_df(con, "SELECT 1 FROM user_n WHERE userId = $u", {"u": user_id}).shape[0])


def user_profile(con, user_id: int) -> dict:
    row = _df(con, """SELECT count(*) AS n, avg(rating) AS mean_rating, stddev_samp(rating) AS sd_rating,
                             min(make_timestamp(timestamp * 1000000))::DATE AS first,
                             max(make_timestamp(timestamp * 1000000))::DATE AS last,
                             avg(CASE WHEN rating >= $like THEN 1 ELSE 0 END) * 100 AS like_pct
                      FROM ratings WHERE userId = $u""", {"u": user_id, "like": LIKE}).iloc[0]
    return row.to_dict()


def user_ratings(con, user_id: int) -> pd.DataFrame:
    """Ratings del usuario con la nota media de cada película (para comparar su reacción con la del resto)."""
    df = _df(con, """SELECT m.movieId, m.title, m.genres, r.rating,
                            make_timestamp(r.timestamp * 1000000)::DATE AS date,
                            s.n AS movie_ratings, s.mean_rating AS movie_mean
                     FROM ratings r JOIN movies m USING (movieId) JOIN movie_n s USING (movieId)
                     WHERE r.userId = $u ORDER BY r.timestamp""", {"u": user_id})
    df["vs_crowd"] = df["rating"] - df["movie_mean"]
    df["reaction"] = df["rating"].map(reaction)
    return df


def user_genre_affinity(con, user_id: int) -> pd.DataFrame:
    """Por género: cuántas veces lo calificó y cuánto se aparta su nota de la media del resto en esas películas."""
    return _df(con, """SELECT g.genre, count(*) AS n, avg(r.rating) AS mean_rating,
                              avg(r.rating - s.mean_rating) AS vs_crowd
                       FROM ratings r JOIN movie_genres g USING (movieId) JOIN movie_n s USING (movieId)
                       WHERE r.userId = $u GROUP BY 1 ORDER BY n DESC""", {"u": user_id})


def similar_users(con, user_id: int, top: int = 5, min_common: int = 5) -> pd.DataFrame:
    """Usuarios con gustos parecidos: Jaccard sobre las películas que les gustaron."""
    return _df(con, """WITH mine AS (SELECT movieId FROM ratings WHERE userId = $u AND rating >= $like),
                            n_mine AS (SELECT count(*) AS n FROM mine),
                            common AS (SELECT r.userId, count(*) AS common FROM ratings r JOIN mine USING (movieId)
                                       WHERE r.rating >= $like AND r.userId <> $u GROUP BY 1 HAVING count(*) >= $mc),
                            liked AS (SELECT userId, count(*) AS n_liked FROM ratings
                                      WHERE rating >= $like AND userId IN (SELECT userId FROM common) GROUP BY 1)
                       SELECT c.userId, c.common, l.n_liked,
                              c.common / (l.n_liked + (SELECT n FROM n_mine) - c.common) AS jaccard
                       FROM common c JOIN liked l USING (userId)
                       ORDER BY jaccard DESC LIMIT $top""",
               {"u": user_id, "like": LIKE, "top": top, "mc": min_common})


def user_neighborhood(con, user_id: int, peers: list[int], max_movies: int = 40) -> pd.DataFrame:
    """Ratings del usuario y sus pares sobre películas que comparten (aristas del grafo usuario–película).

    Mitad películas que al usuario le gustaron y mitad que no, para que se vean ambas reacciones.
    """
    group = [user_id, *peers]
    return _df(con, """WITH g AS (SELECT * FROM ratings WHERE list_contains($group, userId)),
                            cand AS (SELECT movieId, count(*) AS k,
                                            max(CASE WHEN userId = $u THEN rating END) AS own
                                     FROM g GROUP BY 1 HAVING bool_or(userId = $u) AND count(*) >= 2),
                            ranked AS (SELECT *, row_number() OVER (PARTITION BY own >= $like
                                                                    ORDER BY k DESC, movieId) AS rk FROM cand),
                            shared AS (SELECT movieId FROM ranked WHERE rk <= $mx / 2)
                       SELECT g.userId, g.movieId, g.rating, m.title, m.genres
                       FROM g JOIN shared USING (movieId) JOIN movies m USING (movieId)""",
               {"group": group, "u": user_id, "mx": max_movies, "like": LIKE})


# --------------------------------------------------------------------------- películas
def search_movies(con, text: str = "", limit: int = 50) -> pd.DataFrame:
    """Películas cuyo título contiene `text` (sin distinguir mayúsculas), las más calificadas primero."""
    return _df(con, """SELECT m.movieId, m.title, m.genres, s.n, s.mean_rating
                       FROM movies m JOIN movie_n s USING (movieId)
                       WHERE $t = '' OR m.title ILIKE '%' || $t || '%'
                       ORDER BY s.n DESC LIMIT $lim""", {"t": text.strip(), "lim": limit})


def movie_profile(con, movie_id: int) -> dict:
    row = _df(con, """SELECT m.title, m.genres, count(*) AS n, avg(r.rating) AS mean_rating,
                             median(r.rating) AS median_rating,
                             avg(CASE WHEN r.rating >= $like THEN 1 ELSE 0 END) * 100 AS like_pct,
                             avg(CASE WHEN r.rating <= $dislike THEN 1 ELSE 0 END) * 100 AS dislike_pct,
                             min(make_timestamp(r.timestamp * 1000000))::DATE AS first,
                             max(make_timestamp(r.timestamp * 1000000))::DATE AS last
                      FROM ratings r JOIN movies m USING (movieId) WHERE movieId = $m GROUP BY ALL""",
              {"m": movie_id, "like": LIKE, "dislike": DISLIKE})
    return row.iloc[0].to_dict() if len(row) else {}


def movie_rating_distribution(con, movie_id: int) -> pd.DataFrame:
    df = _df(con, "SELECT rating, count(*) AS n FROM ratings WHERE movieId = $m GROUP BY 1 ORDER BY 1", {"m": movie_id})
    df["share_pct"] = 100 * df["n"] / df["n"].sum() if len(df) else 0.0
    return df


def movie_yearly(con, movie_id: int) -> pd.DataFrame:
    return _df(con, """SELECT year, count(*) AS n, avg(rating) AS mean_rating
                       FROM ratings WHERE movieId = $m GROUP BY 1 ORDER BY 1""", {"m": movie_id})


def similar_movies(con, movie_id: int, top: int = 15, min_likes: int = 50) -> pd.DataFrame:
    """Películas más parecidas por coseno de «le gustó» (item-item)."""
    return _df(con, """WITH fans AS (SELECT userId FROM ratings WHERE movieId = $m AND rating >= $like),
                            n_fans AS (SELECT count(*) AS n FROM fans),
                            co AS (SELECT r.movieId, count(*) AS common FROM ratings r JOIN fans USING (userId)
                                   WHERE r.rating >= $like AND r.movieId <> $m GROUP BY 1),
                            likes AS (SELECT movieId, count(*) AS n_likes FROM ratings
                                      WHERE rating >= $like AND movieId IN (SELECT movieId FROM co) GROUP BY 1)
                       SELECT co.movieId, m.title, m.genres, co.common, l.n_likes,
                              co.common / sqrt(l.n_likes * (SELECT n FROM n_fans)) AS similarity
                       FROM co JOIN likes l USING (movieId) JOIN movies m USING (movieId)
                       WHERE l.n_likes >= $ml
                       ORDER BY similarity DESC LIMIT $top""",
               {"m": movie_id, "like": LIKE, "top": top, "ml": min_likes})


# --------------------------------------------------------------------------- grafo de gustos
def taste_graph(con, f: Filters = Filters(), n_movies: int = 250, neighbors: int = 4,
                min_similarity: float = 0.15) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Grafo película–película.

    Nodos: las `n_movies` películas con más «le gustó» dentro de los filtros.
    Aristas: para cada película, sus `neighbors` vecinas más similares (coseno ≥ `min_similarity`).
    """
    where, params = f.sql()
    params.update({"like": LIKE, "n": n_movies})
    nodes = con.cursor().execute(f"""
        WITH r AS (SELECT * FROM ratings {where}),
             top AS (SELECT movieId, count(*) FILTER (WHERE rating >= $like) AS likes, count(*) AS n,
                            avg(rating) AS mean_rating
                     FROM r GROUP BY 1 ORDER BY likes DESC LIMIT $n)
        SELECT top.*, m.title, m.genres FROM top JOIN movies m USING (movieId)""", params).df()
    if nodes.empty:
        return nodes, pd.DataFrame(columns=["source", "target", "similarity"])
    params2 = {k: v for k, v in params.items() if k != "n"} | {"ids": nodes["movieId"].tolist()}
    pairs = con.cursor().execute(f"""
        WITH r AS (SELECT * FROM ratings {where}),
             pos AS (SELECT userId, movieId FROM r WHERE rating >= $like AND list_contains($ids, movieId))
        SELECT a.movieId AS source, b.movieId AS target, count(*) AS common
        FROM pos a JOIN pos b ON a.userId = b.userId AND a.movieId < b.movieId
        GROUP BY 1, 2""", params2).df()
    likes = nodes.set_index("movieId")["likes"]
    pairs["similarity"] = pairs["common"] / np.sqrt(likes.loc[pairs["source"]].to_numpy()
                                                    * likes.loc[pairs["target"]].to_numpy())
    pairs = pairs[pairs["similarity"] >= min_similarity]
    # top-k vecinos por nodo (en ambas direcciones) para un grafo legible
    both = pd.concat([pairs.rename(columns={"source": "a", "target": "b"}),
                      pairs.rename(columns={"source": "b", "target": "a"})])
    keep = both.sort_values("similarity", ascending=False).groupby("a").head(neighbors)
    keep = keep.assign(source=keep[["a", "b"]].min(axis=1), target=keep[["a", "b"]].max(axis=1))
    edges = keep.drop_duplicates(["source", "target"])[["source", "target", "similarity", "common"]]
    nodes["genre"] = _primary_genre(nodes["genres"])
    nodes["degree"] = nodes["movieId"].map(pd.concat([edges["source"], edges["target"]]).value_counts()).fillna(0)
    return nodes, edges.reset_index(drop=True)


def pair_similarity(con, movie_ids: list[int]) -> pd.DataFrame:
    """Coseno de «le gustó» entre todos los pares de un conjunto pequeño de películas."""
    if len(movie_ids) < 2:
        return pd.DataFrame(columns=["source", "target", "similarity", "common"])
    df = _df(con, """WITH pos AS (SELECT userId, movieId FROM ratings
                                  WHERE rating >= $like AND list_contains($ids, movieId)),
                          likes AS (SELECT movieId, count(*) AS n FROM pos GROUP BY 1)
                     SELECT a.movieId AS source, b.movieId AS target, count(*) AS common
                     FROM pos a JOIN pos b ON a.userId = b.userId AND a.movieId < b.movieId
                     GROUP BY 1, 2""", {"like": LIKE, "ids": [int(x) for x in movie_ids]})
    likes = _df(con, """SELECT movieId, count(*) AS n FROM ratings
                        WHERE rating >= $like AND list_contains($ids, movieId) GROUP BY 1""",
                {"like": LIKE, "ids": [int(x) for x in movie_ids]}).set_index("movieId")["n"]
    df["similarity"] = df["common"] / np.sqrt(likes.loc[df["source"]].to_numpy() * likes.loc[df["target"]].to_numpy())
    return df
