"""Grafo de gustos: películas conectadas cuando les gustan a las mismas personas (estilo Obsidian)."""
import pandas as pd
import streamlit as st

import common as C
import graph as G
from movielens.eda import fmt_int, fmt_num
from movielens.explore import LIKE

c = C.ctx()
C.page_header("Grafo de gustos",
              "Dos películas se conectan cuando les gustan a las mismas personas. Los grupos que se forman "
              "son gustos compartidos: la base de un recomendador item-item.")
if not C.need_data(c):
    st.stop()
st.caption(f"Selección: {c.describe()}")

cols = st.columns([1, 1, 1, 2])
n_movies = cols[0].slider("Películas", 50, 500, 250, step=25,
                          help="Las más gustadas dentro de la selección de la barra lateral.")
neighbors = cols[1].slider("Vecinas por película", 1, 8, 4, help="Conexiones más fuertes que se dibujan por nodo.")
min_sim = cols[2].slider("Similitud mínima", 0.05, 0.60, 0.15, step=0.05,
                         help="Coseno entre los conjuntos de usuarios a los que les gustó cada película.")

with st.spinner("Calculando similitudes…"):
    nodes, edges = c.explore("taste_graph", n_movies, neighbors, min_sim, filtered=True)
if nodes.empty:
    C.empty_selection()
    st.stop()

nodes["group"], nodes["color"] = zip(*nodes["genres"].map(G.genre_group))
vis_nodes = [{
    "id": int(r.movieId), "label": r.title, "color": r.color, "value": float(r.likes),
    "tip": G.tooltip(r.title, [("Género", r.group), ("Le gustó a", f"{fmt_int(r.likes)} usuarios"),
                               ("Nota media", fmt_num(r.mean_rating)), ("Conexiones", str(int(r.degree)))]),
} for r in nodes.itertuples()]
vis_edges = [{"from": int(e.source), "to": int(e.target), "value": float(e.similarity)} for e in edges.itertuples()]
G.render(vis_nodes, vis_edges, G.genre_legend(set(nodes["group"])), height=680)
st.markdown(f'<p class="note">Similitud = usuarios a los que les gustaron ambas (nota ≥ {fmt_num(LIKE, 1)}) '
            "dividido por la raíz del producto de los fans de cada una. Tamaño del nodo: cantidad de fans. "
            "Haz clic en un nodo para fijar su vecindario; clic en el fondo para soltarlo.</p>",
            unsafe_allow_html=True)

titles = nodes.set_index("movieId")["title"]
left, right = st.columns(2)
with left:
    with st.container(border=True):
        C.card_title("Conexiones más fuertes")
        top = edges.sort_values("similarity", ascending=False).head(15)
        C.table(pd.DataFrame({"Película A": top["source"].map(titles).to_numpy(),
                              "Película B": top["target"].map(titles).to_numpy(),
                              "Similitud": top["similarity"].to_numpy(), "Fans en común": top["common"].to_numpy()}),
                column_config={"Similitud": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1),
                               "Fans en común": C.INT})
with right:
    with st.container(border=True):
        C.card_title("Películas puente", "Las más conectadas: unen grupos de gustos distintos.")
        hubs = nodes.sort_values(["degree", "likes"], ascending=False).head(15)
        C.table(hubs.rename(columns={"title": "Película", "group": "Género", "degree": "Conexiones",
                                     "likes": "Fans"})[["Película", "Género", "Conexiones", "Fans"]],
                column_config={"Fans": C.INT, "Conexiones": st.column_config.NumberColumn(format="%d")})
