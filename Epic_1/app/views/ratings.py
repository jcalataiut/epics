"""Calificaciones: escala, uso de las notas en el tiempo, sesgos por usuario y película, géneros y décadas."""
import streamlit as st

import common as C
from movielens import charts

c = C.ctx()
C.page_header("Calificaciones", "Cómo califican los usuarios: escala, evolución en el tiempo, sesgos y contenido.")
if not C.need_data(c):
    st.stop()
k = c.eda("kpis")
if k["ratings"] == 0:
    C.empty_selection()
    st.stop()
st.caption(f"Selección: {c.describe()}")

left, right = st.columns(2)
with left:
    C.chart(charts.rating_distribution(c.eda("rating_distribution"), k["mean_rating"]),
            "Distribución de las notas", "La escala va de 0,5 a 5,0 en medias estrellas (decisión D-01).")
with right:
    C.chart(charts.rating_share_heatmap(c.eda("rating_share_by_year")),
            "Uso de cada nota por año", "Cada columna suma 100%. Las medias estrellas aparecen en 2003.")

st.subheader("Sesgos de usuarios y películas")
users, movies = c.eda("entity_stats", by="userId"), c.eda("entity_stats", by="movieId")
movies_k = movies[movies["n"] >= C.MIN_RATINGS]
left, right = st.columns(2)
with left:
    C.chart(charts.mean_rating_hist(users, charts.BLUE, "usuarios"), "Nota media por usuario",
            "Los usuarios tienden a ser generosos.")
with right:
    C.chart(charts.mean_rating_hist(movies_k, charts.ORANGE, "películas"), "Nota media por película",
            f"Películas con al menos {C.MIN_RATINGS} ratings.",
            note="La diferencia entre ambas medianas indica que se califican más las películas buenas: "
                 "un modelo necesita sesgos por usuario y por película.")

st.subheader("Evolución en el tiempo")
ya = c.eda("yearly_activity")
left, right = st.columns(2)
with left:
    C.chart(charts.yearly_users(ya), "Usuarios activos por año", "Nuevos (primer rating ese año) y recurrentes.")
with right:
    C.chart(charts.yearly_mean(ya, k["mean_rating"]), "Nota media por año", "Años con al menos 1.000 ratings.")

st.subheader("Contenido")
gs = c.eda("genre_stats")
left, right = st.columns(2)
with left:
    C.chart(charts.genre_volume(gs), "Ratings por género")
with right:
    C.chart(charts.genre_relative(gs, k["mean_rating"]), "Nota media relativa por género",
            "Azul: sobre la media global. Rojo: bajo la media.")
rd = c.eda("release_decade_stats")
left, right = st.columns(2)
with left:
    C.chart(charts.decades_volume(rd), "Ratings según década de estreno", "Año tomado del título de la película.")
with right:
    C.chart(charts.decades_mean(rd, k["mean_rating"]), "Nota media según década de estreno",
            "Décadas con al menos 1.000 ratings, con intervalo de confianza del 95%.",
            note="Las películas antiguas que se siguen viendo son los clásicos: su nota está inflada por supervivencia.")

with st.expander("Datos de las tablas"):
    t1, t2, t3 = st.tabs(["Notas", "Años", "Géneros"])
    with t1:
        C.table(c.eda("rating_distribution").rename(columns={"rating": "Nota", "n": "Ratings", "share_pct": "% del total"}),
                column_config={"Ratings": C.INT, "% del total": C.DEC2})
    with t2:
        C.table(ya.rename(columns={"year": "Año", "n": "Ratings", "active_users": "Usuarios activos",
                                   "new_users": "Usuarios nuevos", "movies": "Películas", "mean_rating": "Nota media"})
                [["Año", "Ratings", "Usuarios activos", "Usuarios nuevos", "Películas", "Nota media"]],
                column_config={"Ratings": C.INT, "Usuarios activos": C.INT, "Usuarios nuevos": C.INT,
                               "Películas": C.INT, "Nota media": C.DEC2})
    with t3:
        C.table(gs.rename(columns={"genre": "Género", "n": "Ratings", "mean_rating": "Nota media",
                                   "sd_rating": "Desviación estándar"}),
                column_config={"Ratings": C.INT, "Nota media": C.DEC2, "Desviación estándar": C.DEC2})
