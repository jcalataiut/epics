"""US1.3 t1 — cada control detecta exactamente lo que dice detectar.

Ejemplos pequeños con problemas conocidos (checklist de la tarea):
valores faltantes por columna en users/movies/ratings, notas fuera de escala,
ratings repetidos, IDs de usuario o película que no existen en la otra tabla.
"""
from __future__ import annotations

import pandas as pd
import pytest

from movielens.checks import connect, run_checks
from movielens.reporting import apply_overrides, summarize

from .conftest import synthetic_tables

VPARAMS = {"rating_min": 0.5, "rating_max": 5.0, "rating_step": 0.5, "min_date": "1995-01-01"}


def derive_users(ratings: pd.DataFrame) -> pd.DataFrame:
    """Igual que `ingest.derive_users` (una fila por userId, incluido un userId nulo si lo hay)."""
    g = ratings.groupby("userId", dropna=False)
    return pd.DataFrame({"userId": g.size().index, "n_ratings": g.size().to_numpy(),
                         "first_timestamp": g["timestamp"].min().to_numpy(),
                         "last_timestamp": g["timestamp"].max().to_numpy()})


def write_interim(tmp_path, tables, rename=None):
    """Escribe Parquet con los mismos tipos que produce `ingest` (enteros con nulos permitidos)."""
    d = tmp_path / "interim"
    d.mkdir(exist_ok=True)
    tables = dict(tables)
    tables.setdefault("users", derive_users(tables["ratings"]))
    types = {
        "ratings": {"userId": "Int32", "movieId": "Int32", "rating": "Float32", "timestamp": "Int64"},
        "tags": {"userId": "Int32", "movieId": "Int32", "timestamp": "Int64"},
        "movies": {"movieId": "Int32"}, "links": {"movieId": "Int32"},
        "users": {"userId": "Int32", "n_ratings": "Int64", "first_timestamp": "Int64", "last_timestamp": "Int64"},
    }
    for name, df in tables.items():
        df = df.astype(types[name])
        df.rename(columns=(rename or {}).get(name, {})).to_parquet(d / f"{name}.parquet", index=False)
    return d


def run_on(tmp_path, tables):
    return {r.id: r for r in run_checks(connect(write_interim(tmp_path, tables)), VPARAMS)}


def test_datos_validos_pasan_todo(tmp_path):
    results = run_on(tmp_path, synthetic_tables())
    assert all(r.passed for r in results.values()), [r.id for r in results.values() if not r.passed]
    assert summarize(list(results.values()))["status"] == "pass"


@pytest.mark.parametrize("bad_rating, check_id", [
    (0.0, "ratings_rating_range"),
    (5.5, "ratings_rating_range"),
    (-1.0, "ratings_rating_range"),
    (3.7, "ratings_rating_step"),
])
def test_notas_fuera_de_escala_bloquean(tmp_path, bad_rating, check_id):
    t = synthetic_tables()
    t["ratings"].loc[0, "rating"] = bad_rating
    r = run_on(tmp_path, t)[check_id]
    assert not r.passed and r.blocks and r.n_failed == 1
    assert r.sample and r.sample[0]["rating"] == pytest.approx(bad_rating, abs=1e-5)


def test_nota_media_estrella_es_valida(tmp_path):
    """D-01: 0.5 es parte de la escala oficial de ML-32M."""
    t = synthetic_tables()
    t["ratings"].loc[0, "rating"] = 0.5
    assert run_on(tmp_path, t)["ratings_rating_range"].passed


def test_con_la_regla_literal_1_a_5_media_estrella_bloquea(tmp_path):
    """Si el PO fija rating_min = 1.0 en params.yaml, una nota 0.5 detiene el pipeline."""
    t = synthetic_tables()
    t["ratings"].loc[0, "rating"] = 0.5
    results = run_checks(connect(write_interim(tmp_path, t)), {**VPARAMS, "rating_min": 1.0})
    r = next(x for x in results if x.id == "ratings_rating_range")
    assert r.blocks and r.n_failed == int((t["ratings"]["rating"] == 0.5).sum()) >= 1
    assert r.expected == "1.0 ≤ rating ≤ 5.0"


@pytest.mark.parametrize("table, column, value", [
    ("ratings", "userId", None), ("ratings", "movieId", None),
    ("ratings", "rating", None), ("ratings", "timestamp", None),
    ("movies", "movieId", None), ("movies", "title", ""), ("movies", "genres", None),
    ("users", "n_ratings", None), ("users", "first_timestamp", None), ("users", "last_timestamp", None),
])
def test_valor_faltante_en_cada_columna_bloquea(tmp_path, table, column, value):
    t = synthetic_tables()
    if table == "users":
        t["users"] = derive_users(t["ratings"])
    df = t[table].astype(object)
    df.loc[0, column] = value
    t[table] = df
    r = run_on(tmp_path, t)[f"{table}_{column}_missing"]
    assert not r.passed and r.blocks and r.n_failed == 1
    assert r.category == "Valores faltantes"


def test_duplicados_bloquean(tmp_path):
    t = synthetic_tables()
    dup = t["ratings"].iloc[[0]].assign(rating=1.0)
    t["ratings"] = pd.concat([t["ratings"], dup], ignore_index=True)
    r = run_on(tmp_path, t)["ratings_unique_pair"]
    assert not r.passed and r.blocks and r.n_failed == 1


def test_movie_id_duplicado_en_movies_bloquea(tmp_path):
    t = synthetic_tables()
    t["movies"] = pd.concat([t["movies"], t["movies"].iloc[[0]]], ignore_index=True)
    assert run_on(tmp_path, t)["movies_unique_id"].blocks


def test_movie_id_huerfano_en_ratings_bloquea(tmp_path):
    t = synthetic_tables()
    t["ratings"].loc[0, "movieId"] = 99_999
    r = run_on(tmp_path, t)["ratings_orphan_movie"]
    assert not r.passed and r.blocks and r.sample[0]["movieId"] == 99_999


@pytest.mark.parametrize("table, column, check_id", [
    ("tags", "movieId", "tags_orphan_movie"),
    ("tags", "userId", "tags_orphan_user"),
    ("links", "movieId", "links_orphan_movie"),
])
def test_ids_inexistentes_en_otras_tablas_bloquean(tmp_path, table, column, check_id):
    t = synthetic_tables()
    t[table].iloc[0, t[table].columns.get_loc(column)] = 99_999
    r = run_on(tmp_path, t)[check_id]
    assert not r.passed and r.blocks and r.sample[0][column] == 99_999


def test_usuario_de_ratings_que_no_existe_en_users_bloquea(tmp_path):
    t = synthetic_tables()
    users = derive_users(t["ratings"])
    t["users"] = users[users["userId"] != t["ratings"].loc[0, "userId"]]
    assert run_on(tmp_path, t)["ratings_orphan_user"].blocks


def test_el_po_puede_bajar_un_control_a_aviso(tmp_path):
    t = synthetic_tables()
    t["tags"].iloc[0, t["tags"].columns.get_loc("movieId")] = 99_999
    results = apply_overrides(list(run_on(tmp_path, t).values()), {"tags_orphan_movie": "warning"})
    assert summarize(results)["status"] == "warn"


def test_esquema_incorrecto_bloquea_y_corta(tmp_path):
    d = write_interim(tmp_path, synthetic_tables(), rename={"ratings": {"rating": "score"}})
    results = run_checks(connect(d), VPARAMS)
    assert [r.id for r in results if not r.passed] == ["ratings_schema"]
