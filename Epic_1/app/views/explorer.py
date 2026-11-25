"""Explorador: un usuario y sus reacciones, o una película y su audiencia, con su vecindario de gustos."""
import pandas as pd
import streamlit as st

import common as C
import graph as G
from movielens import charts
from movielens.eda import fmt_int, fmt_num, fmt_pct
from movielens.explore import DISLIKE, LIKE, reaction

c = C.ctx()
C.page_header("Usuarios y películas",
              f"Qué calificó cada usuario y cómo reaccionó: le gustó (nota ≥ {fmt_num(LIKE, 1)}), "
              f"neutral o no le gustó (nota ≤ {fmt_num(DISLIKE, 1)}).")
if not C.need_data(c):
    st.stop()
st.caption(f"Datos {c.name.lower()}. Los filtros de la barra lateral no aplican a esta página.")
overall = c.eda("rating_distribution", filtered=False)
global_mean = c.eda("kpis", filtered=False)["mean_rating"]


def random_user() -> None:
    st.session_state["explore_user"] = c.explore("user_ids_sample", 1, 50, int(pd.Timestamp.now().value % 1_000_000))[0]


tab_user, tab_movie = st.tabs(["Usuario", "Película"])

# --------------------------------------------------------------------------- usuario
with tab_user:
    if "explore_user" not in st.session_state:
        st.session_state["explore_user"] = c.explore("user_ids_sample", 1, 300, 11)[0]
    left, mid, _ = st.columns([1.2, 0.8, 3])
    uid = left.number_input("ID de usuario", min_value=1, step=1, key="explore_user")
    mid.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
    mid.button("Usuario al azar", width="stretch", on_click=random_user)

    if not c.explore("user_exists", int(uid)):
        st.warning(f"El usuario {uid} no existe en los datos {c.name.lower()}.")
    else:
        p = c.explore("user_profile", int(uid))
        ur = c.explore("user_ratings", int(uid))
        cols = st.columns(5)
        cols[0].metric("Ratings", fmt_int(p["n"]))
        cols[1].metric("Nota media", fmt_num(p["mean_rating"]),
                       f"{p['mean_rating'] - global_mean:+.2f} vs. dataset".replace(".", ","), delta_color="off", delta_arrow="off")
        cols[2].metric("Le gustó", fmt_pct(p["like_pct"]), "de sus ratings", delta_color="off", delta_arrow="off")
        cols[3].metric("Más exigente", fmt_pct(100 * (ur["vs_crowd"] < 0).mean()),
                       "de sus películas", delta_color="off", delta_arrow="off",
                       help="Porcentaje de películas a las que les puso menos nota que la media del resto.")
        cols[4].metric("Activo", f"{p['first']:%Y}–{p['last']:%Y}")

        left, right = st.columns([1.4, 1])
        with left:
            C.chart(charts.reactions_timeline(ur), "Reacciones en el tiempo",
                    "Cada punto es una película calificada; pasa el mouse para ver cuál.")
        with right:
            dist = ur.groupby("rating").size().rename("n").reset_index()
            dist["share_pct"] = 100 * dist["n"] / dist["n"].sum()
            C.chart(charts.compare_distribution(dist, overall, f"Usuario {uid}"), "Sus notas frente al dataset")

        left, right = st.columns([1, 1.4])
        with left:
            C.chart(charts.user_genre_affinity(c.explore("user_genre_affinity", int(uid))), "Afinidad por género",
                    "Cuánto más (azul) o menos (rojo) que el resto puntúa las películas de cada género.")
        with right:
            with st.container(border=True):
                peers = c.explore("similar_users", int(uid), 5)
                C.card_title("Usuarios con gustos parecidos",
                             "Comparten películas que les gustaron (Jaccard). Aristas: reacción de cada usuario.")
                if peers.empty:
                    st.caption("No hay usuarios con suficientes películas en común.")
                else:
                    nb = c.explore("user_neighborhood", int(uid), peers["userId"].tolist(), 36)
                    jac = dict(zip(peers["userId"], peers["jaccard"]))
                    nodes = []
                    for u in [int(uid), *peers["userId"].tolist()]:
                        mine = u == int(uid)
                        nodes.append({"id": f"u{u}", "label": f"Usuario {u}", "shape": "diamond", "mass": 4,
                                      "color": "#ffffff" if mine else "#aab0ba", "value": 30 if mine else 18,
                                      "tip": G.tooltip(f"Usuario {u}", [("Similitud", "—" if mine else fmt_num(jac[u]))])})
                    mv = nb.drop_duplicates("movieId")
                    for _, r in mv.iterrows():
                        lbl, _ = G.genre_group(r["genres"])
                        nodes.append({"id": f"m{r.movieId}", "label": r["title"], "color": "#c9ced6", "value": 8,
                                      "tip": G.tooltip(r["title"], [("Género", lbl),
                                                                    ("Usuarios del grupo", str(int((nb.movieId == r.movieId).sum())))])})
                    edges = [{"from": f"u{r.userId}", "to": f"m{r.movieId}", "value": 1,
                              "color": charts.REACTION_COLORS[reaction(r.rating)]} for r in nb.itertuples()]
                    G.render(nodes, edges, [("Le gustó", charts.BLUE), ("Neutral", charts.MUTED),
                                            ("No le gustó", charts.RED)], height=470, label_threshold=14, physics={
                        "solver": "forceAtlas2Based",
                        "forceAtlas2Based": {"gravitationalConstant": -140, "centralGravity": 0.01,
                                             "springLength": 120, "springConstant": 0.04, "avoidOverlap": 0.6},
                        "stabilization": {"iterations": 400}, "minVelocity": 0.8})

        with st.expander(f"Todas sus calificaciones ({fmt_int(len(ur))})"):
            C.table(ur.sort_values("date", ascending=False).rename(columns={
                "title": "Película", "genres": "Géneros", "rating": "Nota", "date": "Fecha", "reaction": "Reacción",
                "movie_mean": "Media de la película", "vs_crowd": "Diferencia"})
                [["Fecha", "Película", "Nota", "Reacción", "Media de la película", "Diferencia", "Géneros"]],
                column_config={"Media de la película": C.DEC2, "Diferencia": st.column_config.NumberColumn(format="%+.2f"),
                               "Fecha": st.column_config.DateColumn(format="DD-MM-YYYY")})

# --------------------------------------------------------------------------- película
with tab_movie:
    left, right = st.columns([1, 2])
    text = left.text_input("Buscar película", value="", placeholder="Título en inglés, p. ej. Matrix")
    found = c.explore("search_movies", text, 60)
    if found.empty:
        st.info("Ninguna película coincide con la búsqueda.")
    else:
        options = dict(zip(found["movieId"], found["title"] + "  ·  " + found["n"].map(fmt_int) + " ratings"))
        mid = right.selectbox("Película", list(options), format_func=options.get)
        mp = c.explore("movie_profile", int(mid))
        st.markdown(" ".join(f'<span class="pill">{g}</span>' for g in mp["genres"].split("|")), unsafe_allow_html=True)
        cols = st.columns(5)
        cols[0].metric("Ratings", fmt_int(mp["n"]))
        cols[1].metric("Nota media", fmt_num(mp["mean_rating"]), f"mediana {fmt_num(mp['median_rating'], 1)}", delta_color="off", delta_arrow="off")
        cols[2].metric("Le gustó", fmt_pct(mp["like_pct"]))
        cols[3].metric("No le gustó", fmt_pct(mp["dislike_pct"]))
        cols[4].metric("Calificada", f"{mp['first']:%Y}–{mp['last']:%Y}")

        left, right = st.columns(2)
        with left:
            C.chart(charts.compare_distribution(c.explore("movie_rating_distribution", int(mid)), overall, "Esta película"),
                    "Distribución de sus notas", "Frente a la distribución de todo el dataset.")
        with right:
            C.chart(charts.movie_yearly(c.explore("movie_yearly", int(mid))), "Ratings por año")

        sim = c.explore("similar_movies", int(mid), 15, C.SERVING_MIN)
        left, right = st.columns([1, 1.3])
        with left:
            with st.container(border=True):
                C.card_title("A quienes les gustó, también les gustó",
                             f"Similitud coseno entre fans; películas con ≥ {C.SERVING_MIN} «le gustó».")
                C.table(sim.rename(columns={"title": "Película", "similarity": "Similitud", "common": "Fans en común"})
                        [["Película", "Similitud", "Fans en común"]],
                        column_config={"Similitud": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1),
                                       "Fans en común": C.INT}, height=470)
        with right:
            with st.container(border=True):
                C.card_title("Vecindario de gustos", "La película y sus vecinas; grosor de arista = similitud.")
                if sim.empty:
                    st.caption("Sin vecinas con suficientes fans en común.")
                else:
                    ids = [int(mid), *sim["movieId"].tolist()]
                    pairs = c.explore("pair_similarity", ids)
                    # se dibujan las aristas de la película elegida y, entre vecinas, solo las más fuertes
                    touches = (pairs["source"] == int(mid)) | (pairs["target"] == int(mid))
                    pairs = pairs[touches | (pairs["similarity"] >= pairs["similarity"].quantile(0.75))]
                    meta = pd.concat([pd.DataFrame([{"movieId": int(mid), "title": mp["title"], "genres": mp["genres"],
                                                     "similarity": 1.0}]), sim])
                    labels = set()
                    nodes = []
                    for r in meta.itertuples():
                        lbl, col = G.genre_group(r.genres)
                        labels.add(lbl)
                        center = r.movieId == int(mid)
                        nodes.append({"id": int(r.movieId), "label": r.title, "color": "#ffffff" if center else col,
                                      "value": 22 if center else 8 + 14 * r.similarity,
                                      "tip": G.tooltip(r.title, [("Grupo", lbl), ("Similitud", fmt_num(r.similarity))])})
                    edges = [{"from": int(r.source), "to": int(r.target), "value": float(r.similarity)}
                             for r in pairs.itertuples()]
                    G.render(nodes, edges, G.genre_legend(labels), height=470, label_threshold=12)
