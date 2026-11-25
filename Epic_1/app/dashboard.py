"""US1.5 — Dashboard de ratings y calidad de datos de MovieLens 32M.

«I want a visual dashboard of the ratings and the data quality so that the team can
understand the data without running notebooks.»

Arranque: `make dashboard` (desde Epic_1/). Este archivo arma la navegación y la barra
lateral de filtros (US1.5 t3); cada página vive en `app/views/`. Los números salen de las
mismas consultas del EDA (`movielens.eda`) y de los reportes que escribe el pipeline DVC.
"""
from __future__ import annotations

import streamlit as st

import bootstrap  # noqa: F401  (src/ en sys.path y secretos EPIC1_* → entorno; ver docs/DEPLOY.md)

st.set_page_config(page_title="MovieLens 32M · Datos", page_icon=":material/movie:", layout="wide",
                   initial_sidebar_state="expanded")
bootstrap.ensure_data()

import common as C  # noqa: E402  (después de preparar el entorno)

st.markdown(C.CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- barra lateral (US1.5 t3)
def reset_filters() -> None:
    for key in ("f_years", "f_genres", "f_ratings", "f_threshold"):
        st.session_state.pop(key, None)


with st.sidebar:
    st.markdown("### MovieLens 32M")
    avail = C.available()
    name = None
    if avail:
        name = st.segmented_control("Datos", list(avail), default=next(iter(avail)), key="f_dataset",
                                    help=C.DATASET_HELP) or next(iter(avail))
        path, version = str(C.DATASETS[name]), C.data_version(C.DATASETS[name])
        (y_lo, y_hi) = C.q("eda", "year_bounds", path, version, None)
        genres_all = C.q("eda", "genre_list", path, version, None)

        st.markdown("**Filtros**")
        threshold = st.slider(
            "Umbral mínimo de ratings", 1, 200, 1, key="f_threshold",
            help=("Conserva solo usuarios y películas con al menos N ratings en los datos elegidos. "
                  f"El pipeline limpia con `data.min_ratings` = {C.MIN_RATINGS}; los rankings usan "
                  f"`serving.min_ratings` = {C.SERVING_MIN}."))
        st.multiselect("Géneros", genres_all, key="f_genres", placeholder="Todos los géneros")
        years = st.slider("Año del rating", y_lo, y_hi, (y_lo, y_hi), key="f_years")
        ratings = st.select_slider("Notas", C.RATING_STEPS, (0.5, 5.0), key="f_ratings",
                                   format_func=lambda v: f"{v:.1f}".replace(".", ","))
        st.session_state["f_years_effective"] = None if tuple(years) == (y_lo, y_hi) else tuple(years)
        st.session_state["f_ratings_effective"] = None if tuple(ratings) == (0.5, 5.0) else tuple(ratings)
        st.button("Restablecer filtros", on_click=reset_filters, width="stretch", type="secondary")
    else:
        st.warning("No hay datos procesados. Ejecuta `make pipeline`.")

    kind, _ = C.pipeline_status()
    label = {"pass": "al día", "warn": "con avisos", "fail": "detenido", "missing": "sin ejecutar"}[kind]
    h = C.data_hash()
    st.markdown(
        f'<div class="sb-foot">Pipeline: <b>{label}</b><br>'
        f'Versión de datos limpios: <code>{h or "—"}</code><br>'
        f'Umbral de limpieza: {C.MIN_RATINGS} · Rankings: ≥ {C.SERVING_MIN}</div>',
        unsafe_allow_html=True)

st.session_state["ctx"] = C.Ctx(name)

# --------------------------------------------------------------------------- navegación
pages = {
    "Análisis": [
        st.Page("views/overview.py", title="Resumen", icon=":material/dashboard:", default=True),
        st.Page("views/ratings.py", title="Calificaciones", icon=":material/star_half:"),
        st.Page("views/popularity.py", title="Popularidad y dispersión", icon=":material/scatter_plot:"),
    ],
    "Exploración": [
        st.Page("views/explorer.py", title="Usuarios y películas", icon=":material/person_search:"),
        st.Page("views/taste_graph.py", title="Grafo de gustos", icon=":material/hub:"),
    ],
    "Datos": [
        st.Page("views/quality.py", title="Calidad de datos", icon=":material/verified:"),
        st.Page("views/pipeline.py", title="Pipeline", icon=":material/account_tree:"),
    ],
}
st.navigation(pages, position="sidebar").run()
