"""US1.5 — las consultas del dashboard/notebook respetan los filtros."""
from __future__ import annotations

import numpy as np
import pytest

from movielens import eda, ingest

from .conftest import synthetic_tables, write_raw


@pytest.fixture
def con(workspace):
    p, tmp = workspace["params"], workspace["tmp"]
    tables = synthetic_tables()
    write_raw(tmp / "raw", tables)
    assert ingest.run(p)[0] == 0
    return eda.open_db(tmp / "interim"), tables


def test_kpis_sin_filtros(con):
    c, t = con
    k = eda.kpis(c)
    r = t["ratings"]
    assert k["ratings"] == len(r)
    assert k["users"] == r["userId"].nunique() and k["movies"] == r["movieId"].nunique()
    assert k["mean_rating"] == pytest.approx(r["rating"].mean(), rel=1e-5)


def test_filtro_por_nota(con):
    c, t = con
    k = eda.kpis(c, eda.Filters(ratings=(4.0, 5.0)))
    assert k["ratings"] == (t["ratings"]["rating"] >= 4.0).sum()


def test_filtro_por_genero(con):
    c, t = con
    comedy = t["movies"][t["movies"]["genres"].str.contains("Comedy")]["movieId"]
    k = eda.kpis(c, eda.Filters(genres=("Comedy",)))
    assert k["ratings"] == t["ratings"]["movieId"].isin(comedy).sum()
    assert set(eda.genre_stats(c, eda.Filters(genres=("Comedy",)))["genre"]) == {"Comedy"}


def test_filtro_por_anio(con):
    c, t = con
    years = (t["ratings"]["timestamp"].astype("datetime64[s]")).dt.year
    k = eda.kpis(c, eda.Filters(years=(2005, 2010)))
    assert k["ratings"] == years.between(2005, 2010).sum()


def test_filtro_vacio_no_rompe(con):
    c, _ = con
    k = eda.kpis(c, eda.Filters(years=(1990, 1991)))
    assert k["ratings"] == 0 and k["density_pct"] == 0.0


def test_ccdf_y_curva_de_popularidad():
    counts = np.array([1, 2, 2, 10, 50])
    cc = eda.ccdf(counts)
    assert cc["share_pct"].iloc[0] == 100.0 and cc["share_pct"].is_monotonic_decreasing
    pc = eda.popularity_curve(counts)
    assert pc["ratings_pct"].iloc[-1] == pytest.approx(100.0)
    assert eda.share_of_top(counts, 20) == pytest.approx(100 * 50 / 65)


def test_filtro_por_umbral_de_ratings(con):
    """US1.5 t3: el umbral deja solo usuarios y películas con al menos N ratings."""
    c, t = con
    r = t["ratings"]
    n = 12
    keep_u = r.groupby("userId").size().loc[lambda x: x >= n].index
    keep_m = r.groupby("movieId").size().loc[lambda x: x >= n].index
    expected = r[r["userId"].isin(keep_u) & r["movieId"].isin(keep_m)]
    assert eda.kpis(c, eda.Filters(min_ratings=n))["ratings"] == len(expected) < len(r)


def test_graficos_del_dashboard_se_construyen(con):
    from movielens import charts
    c, _ = con
    users, movies = eda.entity_stats(c, by="userId"), eda.entity_stats(c, by="movieId")
    mean = eda.kpis(c)["mean_rating"]
    ya = eda.yearly_activity(c)
    figs = [
        charts.rating_distribution(eda.rating_distribution(c), mean),
        charts.rating_share_heatmap(eda.rating_share_by_year(c)),
        charts.mean_rating_hist(users, charts.BLUE, "usuarios"),
        charts.yearly_ratings(ya), charts.yearly_users(ya), charts.yearly_mean(ya, mean, min_ratings=1),
        charts.genre_volume(eda.genre_stats(c)), charts.genre_relative(eda.genre_stats(c), mean),
        charts.decades_volume(eda.release_decade_stats(c)), charts.decades_mean(eda.release_decade_stats(c), mean, 1),
        charts.activity_ccdf(users["n"], movies["n"], 5), charts.lorenz(users["n"], movies["n"]),
        charts.popularity_vs_rating(movies, 5), charts.sparsity_blocks(eda.sparsity_blocks(c, bins=4)),
    ]
    assert all(len(fig.data) >= 1 for fig in figs)


def test_explorador_y_grafo_de_gustos(con):
    from movielens import explore
    c, t = con
    r = t["ratings"]
    uid = int(r["userId"].iloc[0])
    assert explore.user_profile(c, uid)["n"] == (r["userId"] == uid).sum()
    ur = explore.user_ratings(c, uid)
    assert len(ur) == (r["userId"] == uid).sum() and set(ur["reaction"]) <= {"Le gustó", "Neutral", "No le gustó"}
    sim = explore.similar_movies(c, 1, top=5, min_likes=1)
    assert sim["similarity"].between(0, 1).all() and 1 not in set(sim["movieId"])
    nodes, edges = explore.taste_graph(c, eda.Filters(), n_movies=10, neighbors=3, min_similarity=0.0)
    assert len(nodes) == 10 and edges["similarity"].between(0, 1).all()
    assert (edges.groupby("source").size() <= 10).all() and (edges["source"] < edges["target"]).all()
    peers = explore.similar_users(c, uid, top=3, min_common=1)
    assert uid not in set(peers["userId"]) and peers["jaccard"].between(0, 1).all()


# ------------------------------------------------ informe EDA formal (notebook, US1.5 t1)
def test_gini_extremos():
    assert eda.gini(np.array([5, 5, 5, 5])) == pytest.approx(0.0)
    assert eda.gini(np.array([0, 0, 0, 12])) == pytest.approx(0.75)   # (n-1)/n


def test_nuevas_consultas_cuadran_con_los_totales(con):
    c, t = con
    r = t["ratings"]
    share = eda.rating_share_by_year(c)
    assert np.allclose(share.sum(axis=1), 100)
    ya = eda.yearly_activity(c)
    assert ya["n"].sum() == len(r) and ya["new_users"].sum() == r["userId"].nunique()
    users = eda.entity_stats(c, by="userId")
    assert users["n"].sum() == len(r) and len(users) == r["userId"].nunique()
    dec = eda.release_decade_stats(c)            # títulos sintéticos "(2001)"
    assert dec["decade"].tolist() == [2000] and dec["n"].sum() == len(r)


def test_bloques_de_dispersion(con):
    c, _ = con
    b = eda.sparsity_blocks(c, bins=4)
    assert b.shape == (4, 4)
    # densidades válidas y el bloque más denso (activos × populares) supera la densidad global
    k = eda.kpis(c)
    assert (b.values >= 0).all() and (b.values <= 100).all()
    assert b.values.max() >= k["density_pct"]


def test_figuras_del_informe_se_construyen(con):
    from movielens import report as R
    c, _ = con
    users, movies = eda.entity_stats(c, by="userId"), eda.entity_stats(c, by="movieId")
    mean = eda.kpis(c)["mean_rating"]
    ya = eda.yearly_activity(c)
    figs = [
        R.fig_rating_distribution(eda.rating_distribution(c), mean),
        R.fig_rating_share_by_year(eda.rating_share_by_year(c)),
        R.fig_mean_rating_histograms(users, movies, 5),
        R.fig_activity_ccdf(users["n"], movies["n"], 5),
        R.fig_concentration(users["n"], movies["n"]),
        R.fig_popularity_vs_rating(movies, 5),
        R.fig_yearly_activity(ya),
        R.fig_yearly_mean(ya, mean, min_ratings=1),
        R.fig_genres(eda.genre_stats(c), mean),
        R.fig_release_decades(eda.release_decade_stats(c), mean, min_ratings=1),
        R.fig_sparsity_blocks(eda.sparsity_blocks(c, bins=4), eda.kpis(c)["density_pct"]),
    ]
    for fig in figs:
        assert fig.axes and fig.get_facecolor()[:3] == (1.0, 1.0, 1.0)   # fondo blanco: legible en tema oscuro
