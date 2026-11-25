"""Resumen: indicadores clave, estado del pipeline y las vistas principales (US1.5 t1)."""
import streamlit as st

import common as C
from movielens import charts
from movielens.eda import fmt_int, fmt_num, fmt_pct

c = C.ctx()
C.page_header("Resumen", "Estado de los datos de calificaciones de MovieLens 32M que usará el recomendador.")
C.status_banner()
if not C.need_data(c):
    st.stop()

k = c.eda("kpis")
if k["ratings"] == 0:
    C.empty_selection()
    st.stop()
base = c.eda("kpis", filtered=False)
st.caption(f"Selección: {c.describe()}")

cols = st.columns(5)
share = (lambda key: f"{fmt_pct(100 * k[key] / base[key])} del total") if c.filtered else (lambda key: None)
cols[0].metric("Ratings", fmt_int(k["ratings"]), share("ratings"), delta_color="off", delta_arrow="off")
cols[1].metric("Usuarios", fmt_int(k["users"]), share("users"), delta_color="off", delta_arrow="off")
cols[2].metric("Películas", fmt_int(k["movies"]), share("movies"), delta_color="off", delta_arrow="off")
cols[3].metric("Nota media", fmt_num(k["mean_rating"]), f"mediana {fmt_num(k['median_rating'], 1)}", delta_color="off", delta_arrow="off")
cols[4].metric("Densidad", fmt_pct(k["density_pct"], 3), help="ratings / (usuarios × películas)")

left, right = st.columns(2)
with left:
    C.chart(charts.rating_distribution(c.eda("rating_distribution"), k["mean_rating"]),
            "Distribución de las notas", "Porcentaje de ratings por nota; en naranja, las medias estrellas.")
with right:
    ya = c.eda("yearly_activity")
    C.chart(charts.yearly_ratings(ya), "Ratings por año", "Volumen de calificaciones según la fecha en que se emitieron.")

left, right = st.columns([1, 1])
with left:
    gs = c.eda("genre_stats")
    C.chart(charts.genre_volume(gs), "Ratings por género", "Una película puede tener varios géneros.")
with right:
    with st.container(border=True):
        C.card_title("Películas destacadas",
                     f"Mejor valoradas entre las que tienen al menos {C.SERVING_MIN} ratings (`serving.min_ratings`).")
        top = c.eda("top_movies", limit=12)
        best = c.eda("best_rated", min_n=C.SERVING_MIN, limit=12)
        tab_best, tab_pop = st.tabs(["Mejor valoradas", "Más calificadas"])
        cfg = {"Ratings": C.INT, "Nota media": C.DEC2}
        with tab_best:
            C.table(best.rename(columns={"title": "Película", "n": "Ratings", "mean_rating": "Nota media"})
                    [["Película", "Ratings", "Nota media"]], column_config=cfg, height=458)
        with tab_pop:
            C.table(top.head(12).rename(columns={"title": "Película", "n": "Ratings", "mean_rating": "Nota media"})
                    [["Película", "Ratings", "Nota media"]], column_config=cfg, height=458)

_, _, clean = C.reports()
if clean:
    st.subheader("Limpieza aplicada")
    b, a = clean["before"], clean["after"]
    cols = st.columns(4)
    cols[0].metric("Umbral (data.min_ratings)", clean.get("min_ratings", C.MIN_RATINGS))
    cols[1].metric("Ratings eliminados", fmt_int(b["ratings"] - a["ratings"]),
                   f"-{fmt_pct(100 * (b['ratings'] - a['ratings']) / b['ratings'], 2)}", delta_color="off", delta_arrow="off")
    cols[2].metric("Películas eliminadas", fmt_int(b["movies"] - a["movies"]),
                   f"-{fmt_pct(100 * (b['movies'] - a['movies']) / b['movies'])}", delta_color="off", delta_arrow="off")
    cols[3].metric("Densidad tras limpiar", fmt_pct(a["density_pct"], 3),
                   f"antes {fmt_pct(b['density_pct'], 3)}", delta_color="off", delta_arrow="off")
