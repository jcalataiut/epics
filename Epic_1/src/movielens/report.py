"""US1.5 t1 — figuras y tablas estáticas del informe EDA (notebook).

El dashboard usa gráficos interactivos (plotly, `eda.fig_*`); el informe usa figuras
estáticas de matplotlib con estilo de reporte: se ven igual en VS Code (tema claro u
oscuro), en GitHub y al exportar a PDF. Ambos consumen las mismas consultas de `eda.py`.

Convenciones: paleta validada (skill dataviz) — azul, naranja, aqua en ese orden; rampa
secuencial azul; divergente azul↔rojo con gris al centro. Un solo eje y por panel (sin
doble eje). Números con formato español (1.234,5).
"""
from __future__ import annotations

from functools import wraps

import matplotlib as mpl
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.figure import Figure
from matplotlib.ticker import FixedLocator, FuncFormatter, LogLocator, NullFormatter

from . import eda
from .eda import fmt_int, fmt_num, fmt_pct

# Paleta (references/palette.md del skill dataviz)
BLUE, ORANGE, AQUA, RED = "#257de0", "#f47230", "#00b894", "#ec4647"
INK, INK2, GRID, AXIS, NEUTRAL = "#191919", "#666666", "#e7e7e7", "#c2c2c2", "#efefef"
BLUES = LinearSegmentedColormap.from_list(
    "blues_seq", ["#f4f9ff", "#cce3fd", "#84b9f3", "#338ced", "#2370cd", "#0f4a96", "#0e3d7e"])

WIDTH = 9.0   # pulgadas: ancho de página de un informe

RC = {
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "figure.dpi": 110, "savefig.dpi": 150, "figure.constrained_layout.use": True,
    "font.family": "DejaVu Sans", "font.size": 9.5, "text.color": INK,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.titlepad": 10, "axes.titlecolor": INK,
    "axes.labelsize": 9.5, "axes.labelcolor": INK2, "axes.edgecolor": AXIS, "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "axes.prop_cycle": mpl.cycler(color=[BLUE, ORANGE, AQUA]),
    "xtick.color": INK2, "ytick.color": INK2, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
    "xtick.major.size": 3, "ytick.major.size": 0,
    "legend.frameon": False, "legend.fontsize": 8.5, "lines.linewidth": 2.0,
}


def styled(fn):
    """Aplica el estilo de informe mientras se construye la figura."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with mpl.rc_context(RC):
            return fn(*args, **kwargs)
    return wrapper


# ------------------------------------------------------------------ formato de ejes
def _compact(v: float) -> str:
    """2.000.000 → '2 M'; 25.000 → '25 mil'."""
    if abs(v) >= 1e6:
        return f"{fmt_num(v / 1e6, 1).replace(',0', '')} M"
    if abs(v) >= 1e4:
        return f"{fmt_int(v / 1e3)} mil"
    return fmt_int(v)


def _pct_label(v: float) -> str:
    """100 → '100%'; 2,5 → '2,5%'; 0,001 → '0,001%' (sin redondear a cero)."""
    if v == 0:
        return "0%"
    if abs(v) >= 10:
        return f"{fmt_int(v)}%"
    return f"{v:.3g}".replace(".", ",") + "%"


COMPACT = FuncFormatter(lambda v, _: _compact(v))
INT = FuncFormatter(lambda v, _: fmt_int(v))
PCT = FuncFormatter(lambda v, _: _pct_label(v))
DEC1 = FuncFormatter(lambda v, _: fmt_num(v, 1))


def _log_axis(axis, fmt=INT) -> None:
    axis.set_major_locator(LogLocator(base=10))
    axis.set_major_formatter(fmt)
    axis.set_minor_formatter(NullFormatter())


def _vline(ax, x: float, label: str, color: str = INK2, y: float = 0.98, ha: str = "left") -> None:
    ax.axvline(x, color=color, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.annotate(label, xy=(x, y), xycoords=("data", "axes fraction"), xytext=(4 if ha == "left" else -4, 0),
                textcoords="offset points", ha=ha, va="top", fontsize=8.5, color=INK2)


# ------------------------------------------------------------------ 3. calificaciones
@styled
def fig_rating_distribution(dist: pd.DataFrame, mean: float) -> Figure:
    fig = Figure(figsize=(WIDTH, 3.4))
    ax = fig.subplots()
    half = (dist["rating"] * 2) % 2 == 1
    for mask, color, label in [(~half, BLUE, "Estrella entera"), (half, ORANGE, "Media estrella")]:
        ax.bar(dist.loc[mask, "rating"], dist.loc[mask, "share_pct"], width=0.36, color=color, label=label)
    top = dist["share_pct"].idxmax()
    ax.annotate(fmt_pct(dist["share_pct"][top]), (dist["rating"][top], dist["share_pct"][top]),
                xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8.5)
    _vline(ax, mean, f"media {fmt_num(mean)}", ha="right")
    ax.set_xticks(dist["rating"], [fmt_num(r, 1) for r in dist["rating"]])
    ax.yaxis.set_major_formatter(PCT)
    ax.set(xlabel="Nota (estrellas)", ylabel="% de los ratings", title="Distribución de las notas")
    ax.legend(loc="upper left")
    return fig


@styled
def fig_rating_share_by_year(share: pd.DataFrame, half_star_year: int | None = 2003) -> Figure:
    fig = Figure(figsize=(WIDTH, 3.6))
    ax = fig.subplots()
    ax.grid(False)
    m = share.T.sort_index(ascending=False)          # filas: nota (5,0 arriba); columnas: año
    im = ax.imshow(m.values, aspect="auto", cmap=BLUES, vmin=0, vmax=np.ceil(m.values.max() / 5) * 5,
                   interpolation="nearest")
    ax.set_yticks(range(len(m.index)), [fmt_num(r, 1) for r in m.index])
    years = list(m.columns)
    xt = [i for i, y in enumerate(years) if y % 5 == 0]
    ax.set_xticks(xt, [str(years[i]) for i in xt])
    if half_star_year in years:
        x = years.index(half_star_year) - 0.5
        ax.axvline(x, color=ORANGE, lw=1.5)
        ax.annotate("medias estrellas\ndisponibles", xy=(x, 0), xytext=(4, 2), textcoords="offset points",
                    ha="left", va="top", fontsize=8.5, color=INK, annotation_clip=False)
    cb = fig.colorbar(im, ax=ax, shrink=0.9, pad=0.01, format=PCT)
    cb.set_label("% de los ratings del año", color=INK2)
    cb.outline.set_visible(False)
    ax.set(xlabel="Año del rating", ylabel="Nota", title="Uso de cada nota a lo largo del tiempo")
    for s in ax.spines.values():
        s.set_visible(False)
    return fig


@styled
def fig_mean_rating_histograms(users: pd.DataFrame, movies: pd.DataFrame, min_n: int = 10) -> Figure:
    fig = Figure(figsize=(WIDTH, 3.2))
    axs = fig.subplots(1, 2, sharey=True)
    bins = np.arange(0.5, 5.0001, 0.1)
    mv = movies[movies["n"] >= min_n]
    for ax, df, color, title in [(axs[0], users, BLUE, f"Usuarios (n = {fmt_int(len(users))})"),
                                 (axs[1], mv, ORANGE, f"Películas con ≥ {min_n} ratings (n = {fmt_int(len(mv))})")]:
        w = np.full(len(df), 100 / max(len(df), 1))
        ax.hist(df["mean_rating"], bins=bins, weights=w, color=color, edgecolor="white", linewidth=0.4)
        med = float(df["mean_rating"].median())
        _vline(ax, med, f"mediana {fmt_num(med)}")
        ax.set(xlabel="Nota media", title=title, xlim=(0.5, 5.0))
        ax.xaxis.set_major_formatter(DEC1)
    axs[0].yaxis.set_major_formatter(PCT)
    axs[0].set_ylabel("% del grupo")
    return fig


# ------------------------------------------------------------------ 4. actividad y popularidad
@styled
def fig_activity_ccdf(user_n: np.ndarray, movie_n: np.ndarray, k: int | None = None) -> Figure:
    fig = Figure(figsize=(WIDTH, 3.6))
    ax = fig.subplots()
    ax.grid(True, axis="both")
    for counts, color, label in [(user_n, BLUE, "Usuarios"), (movie_n, ORANGE, "Películas")]:
        s = np.sort(np.asarray(counts))
        xs = np.unique(s)
        share = 100 * (len(s) - np.searchsorted(s, xs, side="left")) / len(s)
        ax.step(xs, share, where="post", color=color, label=label)
    if k:
        _vline(ax, k, f"k = {k}", y=0.45)
    ax.set_xscale("log")
    ax.set_yscale("log")
    _log_axis(ax.xaxis)
    _log_axis(ax.yaxis, PCT)
    ax.set_ylim(top=130)
    ax.set(xlabel="X = cantidad de ratings (escala log)", ylabel="% con al menos X ratings (escala log)",
           title="Distribución de la actividad: usuarios y películas")
    ax.legend(loc="upper right")
    return fig


def _lorenz(counts: np.ndarray, points: int = 400) -> tuple[np.ndarray, np.ndarray]:
    s = np.sort(np.asarray(counts, dtype=float))
    cum = np.concatenate([[0], np.cumsum(s) / s.sum()])
    idx = np.unique(np.linspace(0, len(s), points).astype(int))
    return 100 * idx / len(s), 100 * cum[idx]


@styled
def fig_concentration(user_n: np.ndarray, movie_n: np.ndarray) -> Figure:
    fig = Figure(figsize=(5.4, 4.6))
    ax = fig.subplots()
    ax.grid(True, axis="both")
    ax.plot([0, 100], [0, 100], color=AXIS, lw=1)
    ax.annotate("igualdad perfecta", (60, 60), rotation=0, xytext=(6, -10), textcoords="offset points",
                fontsize=8.5, color=INK2)
    for counts, color, label in [(user_n, BLUE, "Usuarios"), (movie_n, ORANGE, "Películas")]:
        x, y = _lorenz(counts)
        ax.plot(x, y, color=color, label=f"{label} (Gini {fmt_num(eda.gini(counts))})")
    ax.set(xlim=(0, 100), ylim=(0, 100), aspect="equal",
           xlabel="% acumulado de entidades (de menor a mayor actividad)", ylabel="% acumulado de ratings",
           title="Curvas de Lorenz de la actividad")
    ax.xaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_formatter(PCT)
    ax.legend(loc="upper left")
    return fig


@styled
def fig_popularity_vs_rating(movies: pd.DataFrame, min_n: int = 10) -> Figure:
    mv = movies[movies["n"] >= min_n]
    fig = Figure(figsize=(WIDTH, 3.8))
    ax = fig.subplots()
    ax.grid(False)
    x = np.log10(mv["n"].to_numpy())
    hb = ax.hexbin(x, mv["mean_rating"], gridsize=(48, 24), cmap=BLUES, bins="log", mincnt=1, linewidths=0.2,
                   edgecolors="white")
    edges = np.arange(np.floor(x.min() * 4) / 4, x.max() + 0.25, 0.25)
    mid, med = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (x >= lo) & (x < hi)
        if sel.sum() >= 20:
            mid.append((lo + hi) / 2)
            med.append(float(np.median(mv["mean_rating"].to_numpy()[sel])))
    ax.plot(mid, med, color=ORANGE, marker="o", ms=4, label="Mediana por tramo de popularidad")
    rho = mv[["n", "mean_rating"]].corr(method="spearman").iloc[0, 1]
    ax.xaxis.set_major_locator(FixedLocator([1, 2, 3, 4, 5]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_int(10 ** v)))
    ax.yaxis.set_major_formatter(DEC1)
    cb = fig.colorbar(hb, ax=ax, shrink=0.9, pad=0.01, format=INT)
    cb.set_label("Películas por celda (escala log)", color=INK2)
    cb.outline.set_visible(False)
    ax.set(xlabel="Ratings recibidos (escala log)", ylabel="Nota media",
           title=f"Popularidad y nota media de las películas (ρ de Spearman = {fmt_num(rho)})")
    ax.legend(loc="lower right")
    return fig


# ------------------------------------------------------------------ 5. dinámica temporal
@styled
def fig_yearly_activity(ya: pd.DataFrame) -> Figure:
    fig = Figure(figsize=(WIDTH, 6.4))
    axs = fig.subplots(3, 1, sharex=True)
    axs[0].bar(ya["year"], ya["n"], color=BLUE, width=0.7)
    axs[0].set(title="Ratings por año", ylabel="Ratings")
    returning = ya["active_users"] - ya["new_users"]
    axs[1].bar(ya["year"], returning, color=BLUE, width=0.7, label="Usuarios que ya habían calificado")
    axs[1].bar(ya["year"], ya["new_users"], bottom=returning, color=ORANGE, width=0.7, label="Usuarios nuevos")
    axs[1].set(title="Usuarios activos por año", ylabel="Usuarios")
    axs[1].legend(loc="upper center", ncols=2)
    axs[2].bar(ya["year"], ya["movies"], color=BLUE, width=0.7)
    axs[2].set(title="Películas distintas calificadas por año", ylabel="Películas", xlabel="Año del rating")
    for ax in axs:
        ax.yaxis.set_major_formatter(COMPACT)
    return fig


@styled
def fig_yearly_mean(ya: pd.DataFrame, global_mean: float, min_ratings: int = 1000) -> Figure:
    d = ya[ya["n"] >= min_ratings]
    fig = Figure(figsize=(WIDTH, 3.2))
    ax = fig.subplots()
    ax.plot(d["year"], d["mean_rating"], color=BLUE, marker="o", ms=4, label="Nota media del año")
    ax.axhline(global_mean, color=INK2, lw=1, ls=(0, (4, 3)), label=f"Media global ({fmt_num(global_mean)})")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_num(v, 2)))
    ax.margins(y=0.18)
    ax.set(xlabel="Año del rating", ylabel="Nota media", title="Nota media por año")
    ax.legend(loc="upper left", ncols=2)
    return fig


# ------------------------------------------------------------------ 6. contenido
@styled
def fig_genres(gs: pd.DataFrame, global_mean: float) -> Figure:
    d = gs.sort_values("n").replace({"genre": {"(no genres listed)": "(sin género)"}})
    fig = Figure(figsize=(WIDTH, 5.6))
    axs = fig.subplots(1, 2, sharey=True, width_ratios=[1.1, 1])
    y = np.arange(len(d))
    axs[0].barh(y, d["n"], color=BLUE, height=0.62)
    axs[0].set_yticks(y, d["genre"])
    axs[0].xaxis.set_major_formatter(COMPACT)
    axs[0].set(xlabel="Ratings", title="Volumen de ratings por género")
    diff = d["mean_rating"] - global_mean
    axs[1].barh(y, diff, color=np.where(diff >= 0, BLUE, RED), height=0.62)
    axs[1].axvline(0, color=INK2, lw=1)
    lim = float(np.abs(diff).max()) * 1.25
    axs[1].set_xlim(-lim, lim)
    axs[1].xaxis.set_major_formatter(FuncFormatter(lambda v, _: ("+" if v > 0 else "") + fmt_num(v, 2)))
    axs[1].set(xlabel=f"Diferencia con la media global ({fmt_num(global_mean)})",
               title="Nota media relativa por género")
    for ax in axs:
        ax.grid(True, axis="x")
        ax.grid(False, axis="y")
    return fig


@styled
def fig_release_decades(rd: pd.DataFrame, global_mean: float, min_ratings: int = 1000) -> Figure:
    fig = Figure(figsize=(WIDTH, 3.4))
    axs = fig.subplots(1, 2)
    axs[0].bar(rd["decade"], rd["n"], width=7, color=BLUE)
    axs[0].yaxis.set_major_formatter(COMPACT)
    axs[0].set(xlabel="Década de estreno", ylabel="Ratings", title="Ratings según década de estreno")
    d = rd[rd["n"] >= min_ratings]
    axs[1].errorbar(d["decade"], d["mean_rating"], yerr=d["ci95"], fmt="o-", color=BLUE, ms=4, capsize=2,
                    elinewidth=1)
    axs[1].axhline(global_mean, color=INK2, lw=1, ls=(0, (4, 3)))
    axs[1].annotate(f"media global {fmt_num(global_mean)}", (d["decade"].iloc[0], global_mean), xytext=(0, -4),
                    textcoords="offset points", ha="left", va="top", fontsize=8.5, color=INK2)
    axs[1].yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_num(v, 2)))
    axs[1].set(xlabel="Década de estreno", ylabel="Nota media (± IC 95%)",
               title="Nota media según década de estreno")
    for ax in axs:
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v)}"))
    return fig


# ------------------------------------------------------------------ 7. dispersión y k-core
@styled
def fig_sparsity_blocks(blocks: pd.DataFrame, global_density: float) -> Figure:
    fig = Figure(figsize=(6.4, 5.2))
    ax = fig.subplots()
    ax.grid(False)
    vals = np.ma.masked_less_equal(blocks.values, 0)
    cmap = BLUES.with_extremes(bad=NEUTRAL)
    vmax = 10 ** np.ceil(np.log10(vals.max()))
    im = ax.imshow(vals, cmap=cmap, norm=LogNorm(vmin=vmax / 1e4, vmax=vmax), interpolation="nearest",
                   extent=(0, 100, 100, 0))
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(FixedLocator([0, 25, 50, 75, 100]))
        axis.set_major_formatter(PCT)
    cb = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02, format=PCT)
    cb.set_label(f"Densidad del bloque (escala log); global = {fmt_num(global_density, 3)}%", color=INK2)
    cb.outline.set_visible(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set(xlabel="Películas, de más a menos populares (percentil)",
           ylabel="Usuarios, de más a menos activos (percentil)", title="Dónde están los ratings en la matriz")
    return fig


@styled
def fig_kcore_sensitivity(sweep: pd.DataFrame, k_current: int) -> Figure:
    fig = Figure(figsize=(WIDTH, 3.5))
    axs = fig.subplots(1, 2)
    for col, color, label in [("ratings_kept_pct", BLUE, "Ratings"), ("users_kept_pct", ORANGE, "Usuarios"),
                              ("movies_kept_pct", AQUA, "Películas")]:
        axs[0].plot(sweep["k"], sweep[col], color=color, marker="o", ms=4, label=label)
    axs[0].set(ylim=(0, 105), ylabel="% conservado", title="Qué se conserva según k")
    axs[0].yaxis.set_major_formatter(PCT)
    axs[0].legend(loc="lower left")
    axs[1].plot(sweep["k"], sweep["density_pct"], color=BLUE, marker="o", ms=4)
    axs[1].yaxis.set_major_formatter(PCT)
    axs[1].set(ylabel="Densidad de la matriz", title="Densidad según k")
    for ax in axs:
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(FixedLocator(sweep["k"].tolist()))
        ax.xaxis.set_major_formatter(INT)
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel("k (mínimo de ratings por usuario y película, escala log)")
        _vline(ax, k_current, f"k actual = {k_current}", y=0.98 if ax is axs[1] else 0.16)
    return fig


@styled
def fig_kcore_effect(before: dict[str, np.ndarray], after: dict[str, np.ndarray], k: int) -> Figure:
    fig = Figure(figsize=(WIDTH, 3.4))
    axs = fig.subplots(1, 2, sharey=True)
    for ax, key, title in [(axs[0], "users", "Usuarios"), (axs[1], "movies", "Películas")]:
        ax.grid(True, axis="both")
        for counts, color, label in [(before[key], AXIS, "Validado"), (after[key], BLUE, f"Limpio (k-core {k})")]:
            s = np.sort(np.asarray(counts))
            xs = np.unique(s)
            share = 100 * (len(s) - np.searchsorted(s, xs, side="left")) / len(s)
            ax.step(xs, share, where="post", color=color, label=f"{label}: {fmt_int(len(s))}")
        _vline(ax, k, f"k = {k}", y=0.45)
        ax.set_xscale("log")
        ax.set_yscale("log")
        _log_axis(ax.xaxis)
        _log_axis(ax.yaxis, PCT)
        ax.set(xlabel="X = cantidad de ratings (escala log)", title=title)
        ax.legend(loc="upper right")
    axs[0].set_ylabel("% con al menos X ratings")
    return fig


# ------------------------------------------------------------------ tablas
def table(df: pd.DataFrame, caption: str, formats: dict | None = None, left: list[str] | None = None):
    """Tabla con título numerado y números en formato español.

    Las columnas de `left` (por defecto, la primera) se alinean a la izquierda; el resto, que son
    cifras, a la derecha.
    """
    left = [df.columns[0]] if left is None else left
    sty = df.style.set_caption(caption).hide(axis="index")
    sty = sty.format(precision=2, thousands=".", decimal=",", na_rep="—")
    if formats:
        sty = sty.format(formats, na_rep="—")
    sty = sty.set_properties(**{"text-align": "right"}).set_properties(subset=left, **{"text-align": "left"})
    styles = [
        {"selector": "caption", "props": "caption-side: top; text-align: left; font-weight: 600; padding: 0 0 6px 0;"},
        {"selector": "th.col_heading", "props": "text-align: right;"},
    ]
    sty = sty.set_table_styles(styles)
    return sty.set_table_styles({c: [{"selector": "th", "props": "text-align: left;"}] for c in left},
                                overwrite=False)
