"""Popularidad y dispersión: concentración de la actividad, sesgo de popularidad, matriz y umbral."""
import pandas as pd
import streamlit as st

import common as C
from movielens import charts
from movielens.config import KCORE_SWEEP
from movielens.eda import fmt_int, fmt_num, fmt_pct, gini, share_of_top

c = C.ctx()
C.page_header("Popularidad y dispersión",
              "Qué tan concentrada está la actividad y qué tan vacía está la matriz usuario × película.")
if not C.need_data(c):
    st.stop()
k = c.eda("kpis")
if k["ratings"] == 0:
    C.empty_selection()
    st.stop()
st.caption(f"Selección: {c.describe()}")

users, movies = c.eda("entity_stats", by="userId"), c.eda("entity_stats", by="movieId")
cols = st.columns(5)
cols[0].metric("Gini películas", fmt_num(gini(movies["n"])), help="0 = todas igual de calificadas; 1 = una concentra todo")
cols[1].metric("Gini usuarios", fmt_num(gini(users["n"])))
cols[2].metric("Top 10% películas", fmt_pct(share_of_top(movies["n"].to_numpy(), 10)), "de los ratings", delta_color="off", delta_arrow="off")
cols[3].metric("Mediana por película", fmt_int(movies["n"].median()), "ratings", delta_color="off", delta_arrow="off")
cols[4].metric("Sparsity", fmt_pct(k["sparsity_pct"], 2), "celdas vacías", delta_color="off", delta_arrow="off")

left, right = st.columns(2)
with left:
    C.chart(charts.activity_ccdf(users["n"], movies["n"], C.MIN_RATINGS), "Distribución de la actividad",
            "% de usuarios y películas con al menos X ratings (escala log-log).")
with right:
    C.chart(charts.lorenz(users["n"], movies["n"]), "Concentración de los ratings (curvas de Lorenz)",
            "Cuanto más lejos de la diagonal, más concentrada está la actividad.")

C.chart(charts.popularity_vs_rating(movies, C.MIN_RATINGS), "Popularidad y nota media",
        f"Cada celda cuenta películas con al menos {C.MIN_RATINGS} ratings; la línea es la mediana por tramo.",
        note="Las películas más calificadas también reciben mejores notas: para ordenar por calidad conviene "
             "una media contraída (shrinkage) y un mínimo de ratings como `serving.min_ratings`.")

with st.container(border=True):
    C.card_title("Rankings", f"Mejor valoradas entre las películas con al menos {C.SERVING_MIN} ratings "
                             "(`serving.min_ratings`) y más calificadas.")
    cfg = {"Ratings": C.INT, "Nota media": C.DEC2}
    ren = {"title": "Película", "genres": "Géneros", "n": "Ratings", "mean_rating": "Nota media"}
    left, right = st.columns(2)
    with left:
        st.markdown("**Mejor valoradas**")
        C.table(c.eda("best_rated", min_n=C.SERVING_MIN, limit=25).rename(columns=ren)
                [["Película", "Ratings", "Nota media"]], column_config=cfg, height=420)
    with right:
        st.markdown("**Más calificadas**")
        C.table(c.eda("top_movies", limit=25).rename(columns=ren)[["Película", "Ratings", "Nota media"]],
                column_config=cfg, height=420)

st.subheader("Dispersión de la matriz")
left, right = st.columns([1.1, 1])
with left:
    C.chart(charts.sparsity_blocks(c.eda("sparsity_blocks", bins=50)), "Dónde están los ratings",
            f"Densidad por bloques de 2% × 2%. Densidad global: {fmt_pct(k['density_pct'], 3)}.")
with right:
    sweep = pd.read_csv(KCORE_SWEEP) if KCORE_SWEEP.exists() else None
    if sweep is not None:
        C.chart(charts.threshold_retained(sweep, C.MIN_RATINGS), "Efecto del umbral de limpieza",
                "Qué se conserva al exigir un mínimo de ratings por usuario y película (datos validados).")
        C.chart(charts.threshold_density(sweep, C.MIN_RATINGS), "Densidad según el umbral")

if C.available().get("Validados") and C.available().get("Limpios"):
    st.subheader(f"Antes y después de la limpieza (umbral {C.MIN_RATINGS})")
    v = C.Ctx("Validados")
    cl = C.Ctx("Limpios")
    vu, vm = v.eda("entity_stats", by="userId", filtered=False), v.eda("entity_stats", by="movieId", filtered=False)
    cu, cm = cl.eda("entity_stats", by="userId", filtered=False), cl.eda("entity_stats", by="movieId", filtered=False)
    left, right = st.columns(2)
    with left:
        C.chart(charts.threshold_effect(vu["n"], cu["n"], C.MIN_RATINGS, "usuario"), "Usuarios")
    with right:
        C.chart(charts.threshold_effect(vm["n"], cm["n"], C.MIN_RATINGS, "película"), "Películas",
                note="La limpieza elimina la cola de películas con menos ratings que el umbral; "
                     "a los usuarios casi no los afecta.")
if sweep is not None:
    with st.expander("Tabla de sensibilidad del umbral"):
        C.table(sweep.rename(columns={"k": "Umbral", "ratings": "Ratings", "users": "Usuarios", "movies": "Películas",
                                      "density_pct": "Densidad %", "ratings_kept_pct": "Ratings conservados %",
                                      "users_kept_pct": "Usuarios conservados %",
                                      "movies_kept_pct": "Películas conservadas %", "iterations": "Iteraciones"})
                [["Umbral", "Ratings", "Usuarios", "Películas", "Ratings conservados %", "Usuarios conservados %",
                  "Películas conservadas %", "Densidad %", "Iteraciones"]],
                column_config={"Ratings": C.INT, "Usuarios": C.INT, "Películas": C.INT})
