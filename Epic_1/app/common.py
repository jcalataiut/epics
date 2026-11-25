"""Utilidades compartidas por las páginas del dashboard: datos, caché, filtros, estado y estilo."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from movielens import eda, explore
from movielens.config import CHECKS_REPORT, CLEAN_METRICS, INTEGRITY_REPORT, ROOT, load_params, resolve
from movielens.reporting import load_report

PARAMS = load_params()
MIN_RATINGS = int(PARAMS["data"]["min_ratings"])
SERVING_MIN = int(PARAMS.get("serving", {}).get("min_ratings", 50))
DATASETS = {
    "Limpios": resolve(PARAMS["data"]["processed_dir"]),
    "Validados": resolve(PARAMS["data"]["interim_dir"]),
}
DATASET_HELP = (f"**Limpios**: salida de US1.3 t2, usuarios y películas con ≥ {MIN_RATINGS} ratings "
                f"(`data.min_ratings`).  \n**Validados**: todos los ratings que pasaron los controles de US1.3 t1.")
RATING_STEPS = [x / 2 for x in range(1, 11)]
MODULES = {"eda": eda, "explore": explore}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1440px;}
h1 {font-size: 1.6rem !important; font-weight: 650 !important; letter-spacing: -0.015em; margin-bottom: 0 !important;}
h2 {font-size: 1.15rem !important; font-weight: 600 !important; letter-spacing: -0.01em; margin-top: 1.4rem !important;}
h3 {font-size: 1rem !important; font-weight: 600 !important;}
.page-sub {color: #5b6470; font-size: 0.92rem; margin: 0.25rem 0 1.1rem 0;}
.page-sub code {font-size: 0.82rem;}
.card-title {font-weight: 600; font-size: 0.95rem; color: #1f2328; margin: 0 0 0.1rem 0;}
.card-sub {font-size: 0.8rem; color: #6b7280; margin: 0 0 0.4rem 0;}
.note {font-size: 0.78rem; color: #6b7280; margin-top: -0.4rem;}
[data-testid="stMetric"] {background: #fff; border: 1px solid #e3e6ea; border-radius: 8px; padding: 12px 16px;}
[data-testid="stMetricLabel"] p {font-size: 0.74rem !important; text-transform: uppercase; letter-spacing: 0.05em;
                                  color: #5b6470 !important; font-weight: 500;}
[data-testid="stMetricValue"] {font-size: 1.55rem !important; font-weight: 600; color: #1f2328;}
[data-testid="stMetricDelta"] {font-size: 0.78rem !important;}
.status {display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 8px; font-size: 0.88rem;
         border: 1px solid; margin-bottom: 1rem;}
.status b {font-weight: 600;}
.status .dot {width: 8px; height: 8px; border-radius: 50%; flex: none;}
.status.pass {background: #f2f9f3; border-color: #cfe8d3; color: #1d5b28;} .status.pass .dot {background: #0aac23;}
.status.warn {background: #fff8eb; border-color: #f6e0b0; color: #7a5200;} .status.warn .dot {background: #f2a600;}
.status.fail {background: #fdf1f1; border-color: #f3c9c9; color: #8a1c1c;} .status.fail .dot {background: #dc3c3d;}
.status.missing {background: #f5f6f8; border-color: #e3e6ea; color: #3d4450;} .status.missing .dot {background: #a3a3a3;}
.pill {display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 0.74rem; font-weight: 500;
       border: 1px solid #e3e6ea; color: #3d4450; background: #f5f6f8; margin-right: 4px;}
section[data-testid="stSidebar"] .sb-foot {font-size: 0.76rem; color: #6b7280; line-height: 1.45;}
[data-testid="stExpander"] details {border-radius: 8px;}
</style>
"""


# --------------------------------------------------------------------------- datos y caché
def data_version(path: Path) -> float:
    p = Path(path) / "ratings.parquet"
    return p.stat().st_mtime if p.exists() else 0.0


@st.cache_resource(show_spinner=False, max_entries=4)
def db(path: str, version: float):
    return eda.open_db(path)


@st.cache_data(show_spinner=False, max_entries=512)
def q(module: str, fn: str, path: str, version: float, fkey: tuple | None, *args, **kw):
    """Consulta cacheada por (función, dataset, versión de los datos, filtros, argumentos)."""
    con = db(path, version)
    func = getattr(MODULES[module], fn)
    return func(con, eda.Filters(*fkey), *args, **kw) if fkey is not None else func(con, *args, **kw)


def available() -> dict[str, Path]:
    return {k: v for k, v in DATASETS.items() if eda.has_data(v)}


class Ctx:
    """Dataset y filtros vigentes (los fija la barra lateral)."""

    def __init__(self, name: str | None):
        self.name = name
        self.path = DATASETS.get(name) if name else None
        self.version = data_version(self.path) if self.path else 0.0
        ss = st.session_state
        self.years = ss.get("f_years_effective")
        self.genres = tuple(ss.get("f_genres", ()))
        self.ratings = ss.get("f_ratings_effective")
        self.min_ratings = int(ss.get("f_threshold", 1)) or 1

    @property
    def ready(self) -> bool:
        return self.path is not None

    @property
    def fkey(self) -> tuple:
        return (self.years, self.genres, self.ratings, self.min_ratings if self.min_ratings > 1 else None)

    @property
    def filtered(self) -> bool:
        return any(v not in (None, (), 1) for v in self.fkey)

    def eda(self, fn: str, *args, filtered: bool = True, **kw):
        return q("eda", fn, str(self.path), self.version, self.fkey if filtered else (None, (), None, None), *args, **kw)

    def explore(self, fn: str, *args, filtered: bool = False, **kw):
        return q("explore", fn, str(self.path), self.version, self.fkey if filtered else None, *args, **kw)

    def describe(self) -> str:
        parts = [f"datos {self.name.lower()}"]
        if self.years:
            parts.append(f"{self.years[0]}–{self.years[1]}")
        if self.genres:
            parts.append(", ".join(self.genres))
        if self.ratings:
            parts.append(f"notas {eda.fmt_num(self.ratings[0], 1)}–{eda.fmt_num(self.ratings[1], 1)}")
        if self.min_ratings > 1:
            parts.append(f"umbral ≥ {self.min_ratings} ratings")
        return " · ".join(parts)


def ctx() -> Ctx:
    return st.session_state["ctx"]


# --------------------------------------------------------------------------- estado del pipeline
def reports() -> tuple[dict | None, dict | None, dict | None]:
    return load_report(INTEGRITY_REPORT), load_report(CHECKS_REPORT), load_report(CLEAN_METRICS)


def data_hash(short: bool = True) -> str | None:
    try:
        lock = yaml.safe_load((ROOT / "dvc.lock").read_text(encoding="utf-8"))
        out = next(o["md5"] for o in lock["stages"]["clean"]["outs"] if o["path"] == PARAMS["data"]["processed_dir"])
        return out.split(".")[0][:8] if short else out
    except (FileNotFoundError, KeyError, StopIteration, TypeError, yaml.YAMLError):
        return None


def validation_is_stale() -> bool:
    """¿`validate` revisó otra versión de data/interim que la que produjo `ingest`? (hashes de dvc.lock)"""
    try:
        stages = yaml.safe_load((ROOT / "dvc.lock").read_text(encoding="utf-8"))["stages"]
    except (FileNotFoundError, KeyError, TypeError, yaml.YAMLError):
        return False
    interim = PARAMS["data"]["interim_dir"]

    def md5(stage: str, kind: str):
        return next((e.get("md5") for e in stages.get(stage, {}).get(kind, []) if e.get("path") == interim), None)

    produced, validated = md5("ingest", "outs"), md5("validate", "deps")
    return produced is not None and produced != validated


def pipeline_status() -> tuple[str, str]:
    integrity, checks, _ = reports()
    reps = [r for r in (integrity, checks) if r]
    if not reps:
        return "missing", "Todavía no hay reportes de calidad. Ejecuta <code>make pipeline</code>."
    blocking = sum(r.get("n_blocking_failed", 0) for r in reps)
    warnings = sum(r.get("n_warnings", 0) for r in reps)
    total = sum(r.get("n_checks", 0) for r in reps)
    passed = sum(r.get("n_passed", 0) for r in reps)
    when = max(r.get("generated_at", "") for r in reps).replace("T", " ")[:16]
    if blocking:
        return "fail", (f"<b>Pipeline detenido.</b> {blocking} control(es) bloqueante(s) fallaron en la última ejecución "
                        f"({when} UTC). Los gráficos muestran los últimos datos limpios aprobados.")
    if not checks or validation_is_stale():
        return "warn", (f"<b>Validación desactualizada.</b> Los controles no corresponden a los datos actuales "
                        f"({when} UTC). Ejecuta <code>make pipeline</code>.")
    if warnings:
        return "warn", f"<b>Pipeline al día con avisos.</b> {passed} de {total} controles pasan · {warnings} aviso(s) · {when} UTC."
    return "pass", f"<b>Pipeline al día.</b> {passed} de {total} controles de calidad pasan · última ejecución {when} UTC."


def status_banner() -> None:
    kind, msg = pipeline_status()
    st.markdown(f'<div class="status {kind}"><span class="dot"></span><span>{msg}</span></div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- presentación
def page_header(title: str, sub: str) -> None:
    st.title(title)
    st.markdown(f'<p class="page-sub">{sub}</p>', unsafe_allow_html=True)


def card_title(title: str, sub: str | None = None) -> None:
    st.markdown(f'<p class="card-title">{title}</p>' + (f'<p class="card-sub">{sub}</p>' if sub else ""),
                unsafe_allow_html=True)


def chart(fig, title: str | None = None, sub: str | None = None, note: str | None = None) -> None:
    with st.container(border=True):
        if title:
            card_title(title, sub)
        st.plotly_chart(fig, width="stretch", theme=None,
                        config={"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]})
        if note:
            st.markdown(f'<p class="note">{note}</p>', unsafe_allow_html=True)


def table(df: pd.DataFrame, **kw) -> None:
    """Tabla con números en el formato del navegador (decimales redondeados a 2)."""
    floats = df.select_dtypes("float").columns
    st.dataframe(df.assign(**{c: df[c].round(2) for c in floats}), hide_index=True, width="stretch", **kw)


def need_data(c: Ctx) -> bool:
    if not c.ready:
        st.info("No hay datos procesados. Ejecuta `make pipeline` y vuelve a cargar la página.")
        return False
    return True


def empty_selection() -> None:
    st.warning("Ningún rating cumple los filtros seleccionados. Amplía el rango en la barra lateral.")


INT = st.column_config.NumberColumn(format="localized")
DEC2 = st.column_config.NumberColumn(format="localized")
