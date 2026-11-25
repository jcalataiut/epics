"""Pipeline: etapas DVC, parámetros vigentes y cómo ejecutar cada paso (US1.5 t3)."""
import subprocess

import pandas as pd
import streamlit as st
import yaml

import common as C
from movielens.config import PARAMS_PATH, ROOT

C.page_header("Pipeline", "El dashboard no calcula reglas propias: muestra lo que produce el pipeline versionado con DVC.")

DOT = """digraph {
  rankdir=LR; bgcolor="transparent"; nodesep=0.35; ranksep=0.5;
  node [shape=box, style="rounded,filled", fontname="Inter", fontsize=11, color="#c9ced6", fillcolor="#ffffff",
        fontcolor="#1f2328", margin="0.18,0.08"];
  edge [color="#8b919c", arrowsize=0.6];
  raw [label="ml-32m/*.csv", fillcolor="#f5f6f8"];
  ingest [label="ingest\\nintegridad · Parquet"];
  validate [label="validate\\ncontroles US1.3 t1", color="#257de0"];
  clean [label="clean\\numbral US1.3 t2", color="#257de0"];
  profile [label="profile\\nsensibilidad"];
  out [label="data/processed\\n+ clean_report.md", fillcolor="#f2f7fe"];
  app [label="dashboard", fillcolor="#f5f6f8"];
  raw -> ingest -> validate -> clean -> out -> app; validate -> profile -> app;
}"""
left, right = st.columns([1.3, 1])
with left:
    with st.container(border=True):
        C.card_title("Etapas", "Si una etapa falla, DVC no ejecuta las siguientes.")
        st.graphviz_chart(DOT, width="stretch")
with right:
    with st.container(border=True):
        C.card_title("Cómo ejecutar")
        st.code("make dashboard     # todo: entorno + pipeline + este panel\n"
                "make pipeline      # solo el pipeline (dvc repro)\n"
                "make clean-data    # solo hasta la limpieza (dvc repro clean)\n"
                "make test          # tests con ejemplos de problemas conocidos\n"
                "make metrics       # dvc metrics show", language="bash")
        st.markdown(f"Para cambiar el umbral: editar `data.min_ratings` (hoy **{C.MIN_RATINGS}**) en `params.yaml` "
                    "y ejecutar `make clean-data`; DVC solo vuelve a correr `clean`.")

stages = yaml.safe_load((ROOT / "dvc.yaml").read_text(encoding="utf-8"))["stages"]
C.table(pd.DataFrame([{
    "Etapa": name, "Qué hace": s.get("desc", ""), "Comando": s["cmd"],
    "Parámetros": ", ".join(p if isinstance(p, str) else ", ".join(p) for p in s.get("params", [])),
} for name, s in stages.items()]))

left, right = st.columns(2)
with left:
    with st.container(border=True):
        C.card_title("params.yaml vigente", "Toda regla de negocio vive aquí.")
        st.code(PARAMS_PATH.read_text(encoding="utf-8"), language="yaml")
with right:
    with st.container(border=True):
        C.card_title("¿Los datos están al día?", "Compara código, datos y parámetros con dvc.lock.")
        if st.button("Ejecutar dvc status"):
            try:
                out = subprocess.run(["dvc", "status"], cwd=ROOT, capture_output=True, text=True, timeout=180)
                txt = (out.stdout or out.stderr).strip()
                (st.success if "up to date" in txt else st.warning)(
                    "Todo al día." if "up to date" in txt else "Hay etapas pendientes: ejecuta `make pipeline`.")
                st.code(txt or "(sin salida)", language=None)
            except FileNotFoundError:
                st.info("DVC no está instalado en este entorno (por ejemplo, en Streamlit Community Cloud). "
                        "Ejecuta `make status` en una copia local.")
            except subprocess.TimeoutExpired as exc:
                st.error(f"No se pudo ejecutar dvc: {exc}")
        st.markdown("**Documentación**  \n`README.md` · `docs/BACKLOG.md` (historias, criterios, evidencia) · "
                    "`docs/DECISIONS.md` (decisiones D-01…)")
