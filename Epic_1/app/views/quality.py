"""Calidad de datos (US1.5 t2): controles de US1.3 t1 y resultado de la limpieza de US1.3 t2."""
import pandas as pd
import streamlit as st

import common as C
from movielens.config import CLEAN_REPORT
from movielens.eda import fmt_int, fmt_pct

C.page_header("Calidad de datos",
              "Controles que corre el pipeline antes de limpiar. Si uno bloqueante falla, el pipeline se detiene "
              "y no se generan datos limpios. Esta página no depende de los filtros.")
C.status_banner()
integrity, checks, clean = C.reports()
all_checks = [dict(ch, stage=stage) for stage, rep in (("ingest", integrity), ("validate", checks)) if rep
              for ch in rep.get("checks", [])]
if not all_checks:
    st.info("Todavía no hay reportes. Ejecuta `make pipeline`.")
    st.stop()

df = pd.DataFrame(all_checks)
df["category"] = df["category"].replace("", "Otros").fillna("Otros")
failed_block = (~df["passed"]) & (df["severity"] == "blocking")
cols = st.columns(4)
cols[0].metric("Controles", len(df))
cols[1].metric("Pasan", int(df["passed"].sum()))
cols[2].metric("Bloqueantes que fallan", int(failed_block.sum()))
cols[3].metric("Avisos", int(((~df["passed"]) & (df["severity"] == "warning")).sum()))

# ------------------------------------------------------------------ checklist de US1.3 t1
st.subheader("Checklist US1.3 · tarea 1")
CHECKLIST = [
    ("Valores faltantes en cada columna de users, movies y ratings", ["Valores faltantes"]),
    ("Notas fuera de la escala", ["Rango"]),
    ("Ratings repetidos usuario–película", ["Duplicados"]),
    ("IDs de usuario y película que no existen en las otras tablas", ["IDs inexistentes"]),
    ("Archivos íntegros y con el esquema esperado", ["Archivos", "Esquema"]),
    ("Fechas plausibles (aviso, no detiene)", ["Fechas"]),
]
rows = []
for label, cats in CHECKLIST:
    sel = df[df["category"].isin(cats)]
    ok = bool(sel["passed"].all()) if len(sel) else None
    rows.append({"Requisito": label, "Controles": len(sel), "Problemas encontrados": int(sel["n_failed"].sum()),
                 "Estado": "Sin datos" if ok is None else ("Cumple" if ok else
                                                           ("Falla" if (sel["severity"] == "blocking").any() else "Aviso"))})
C.table(pd.DataFrame(rows), column_config={"Problemas encontrados": C.INT})
st.markdown('<p class="note">La escala válida se configura en <code>validation.rating_min</code> / '
            '<code>rating_max</code> (params.yaml). MovieLens usa medias estrellas de 0,5 a 5,0 (decisión D-01).</p>',
            unsafe_allow_html=True)

# ------------------------------------------------------------------ detalle
st.subheader("Detalle de los controles")
f1, f2, f3 = st.columns([1.2, 1, 1])
cat = f1.multiselect("Categoría", sorted(df["category"].unique()), placeholder="Todas")
table_f = f2.multiselect("Tabla", sorted(df["table"].unique()), placeholder="Todas")
only_failed = f3.toggle("Solo los que fallan", value=bool((~df["passed"]).any()))
mask = df["category"].isin(cat) if cat else pd.Series(True, index=df.index)
if table_f:
    mask &= df["table"].isin(table_f)
view = df[mask]
if only_failed:
    view = view[~view["passed"]]
C.table(pd.DataFrame({
    "Resultado": view["passed"].map({True: "Pasa", False: "Falla"}).where(view["passed"] | (view["severity"] == "blocking"), "Aviso"),
    "Control": view["name"], "Tabla": view["table"], "Categoría": view["category"],
    "Severidad": view["severity"].map({"blocking": "Bloqueante", "warning": "Aviso"}),
    "Regla": view["expected"].where(~view["id"].str.endswith("_md5"), "MD5 = " + view["expected"].str[:10] + "…"),
    "Filas que incumplen": view["n_failed"], "Etapa": view["stage"],
}), column_config={"Filas que incumplen": C.INT}, height=min(36 * (len(view) + 1) + 3, 620))

for ch in [x for x in all_checks if not x["passed"] and x.get("sample")]:
    with st.expander(f"{ch['name']} · {fmt_int(ch['n_failed'])} filas · ejemplos"):
        C.table(pd.DataFrame(ch["sample"]))

# ------------------------------------------------------------------ limpieza (US1.3 t2)
st.subheader("Limpieza por umbral · US1.3 tarea 2")
if not clean:
    st.caption("Sin informe de limpieza: el pipeline no llegó a la etapa `clean`.")
else:
    b, a = clean["before"], clean["after"]
    k = clean.get("min_ratings", C.MIN_RATINGS)
    st.markdown(f"Se eliminan los usuarios y películas con menos de **{k} ratings** (`data.min_ratings`), "
                f"repitiendo el filtro hasta que todos cumplen ({clean['iterations']} iteraciones).")
    left, right = st.columns([1.3, 1])
    with left:
        C.table(pd.DataFrame([{
            "": lbl, "Antes": b[key], "Después": a[key], "Eliminados": b[key] - a[key],
            "% eliminado": 100 * (b[key] - a[key]) / b[key] if b[key] else 0.0,
        } for key, lbl in (("ratings", "Ratings"), ("users", "Usuarios"), ("movies", "Películas"))]),
            column_config={"Antes": C.INT, "Después": C.INT, "Eliminados": C.INT,
                           "% eliminado": st.column_config.NumberColumn(format="%.2f%%")})
    with right:
        C.table(pd.DataFrame(clean["history"]).rename(columns={"iteration": "Iteración", "ratings": "Ratings",
                                                               "users": "Usuarios", "items": "Películas"}),
                column_config={"Ratings": C.INT, "Usuarios": C.INT, "Películas": C.INT})
    st.markdown(f'<p class="note">Densidad {fmt_pct(b["density_pct"], 3)} → {fmt_pct(a["density_pct"], 3)}. '
                f'Datos limpios versionados con DVC (<code>{C.data_hash() or "—"}</code> en dvc.lock).</p>',
                unsafe_allow_html=True)
    if CLEAN_REPORT.exists():
        st.download_button("Descargar informe de limpieza (.md)", CLEAN_REPORT.read_bytes(),
                           file_name="clean_report.md", mime="text/markdown")
