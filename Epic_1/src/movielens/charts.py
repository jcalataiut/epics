"""US1.5 — gráficos interactivos (plotly) del dashboard.

Mismas consultas que el informe EDA (`eda.py`) y la misma paleta que sus figuras
estáticas (`report.py`). Los títulos los pone el dashboard (tarjetas), así que las
figuras no llevan título propio. Un solo eje y por gráfico; números en formato español.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from .eda import fmt_int, fmt_num, gini

# Paleta validada (skill dataviz, references/palette.md)
BLUE, ORANGE, AQUA, YELLOW = "#257de0", "#f47230", "#00b894", "#f2a600"
MAGENTA, GREEN, VIOLET, RED = "#ee7fac", "#008a17", "#6a4ce2", "#ec4647"
CATEGORICAL = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
INK, INK2, GRID, AXIS, MUTED = "#1f2328", "#5b6470", "#eceef1", "#c9ced6", "#a3a3a3"
SEQ = [[0.0, "#f4f9ff"], [0.15, "#cce3fd"], [0.35, "#84b9f3"], [0.55, "#338ced"],
       [0.75, "#2370cd"], [0.9, "#0f4a96"], [1.0, "#0e3d7e"]]
FONT = 'Inter, "Segoe UI", system-ui, -apple-system, sans-serif'

# Reacciones (explorador): divergente rojo ↔ azul con gris al centro
REACTION_COLORS = {"Le gustó": BLUE, "Neutral": MUTED, "No le gustó": RED}

pio.templates["epic1"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, size=12, color=INK2),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    colorway=CATEGORICAL, separators=",.",
    margin=dict(l=4, r=12, t=8, b=4),
    xaxis=dict(showgrid=False, zeroline=False, showline=True, linecolor=AXIS, ticks="outside", tickcolor=AXIS,
               ticklen=4, automargin=True, title=dict(font=dict(size=12, color=INK2), standoff=8)),
    yaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False, showline=False, automargin=True,
               title=dict(font=dict(size=12, color=INK2), standoff=8)),
    hoverlabel=dict(bgcolor="white", bordercolor=AXIS, font=dict(family=FONT, size=12, color=INK)),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, bgcolor="rgba(0,0,0,0)",
                font=dict(size=12, color=INK2), title=dict(text="")),
    bargap=0.28, hovermode="closest",
))
pio.templates.default = "epic1"


def _fig(height: int = 300) -> go.Figure:
    return go.Figure(layout=dict(height=height))


def _vline(fig: go.Figure, x: float, label: str, y_top: float, color: str = INK2) -> None:
    """Línea vertical de referencia dibujada como traza (segura en ejes logarítmicos)."""
    fig.add_trace(go.Scatter(x=[x, x], y=[0, y_top], mode="lines", line=dict(color=color, width=1, dash="dot"),
                             hoverinfo="skip", showlegend=False))
    fig.add_annotation(x=np.log10(x) if fig.layout.xaxis.type == "log" else x, y=0.02, yref="paper",
                       text=label, showarrow=False, xanchor="left", yanchor="bottom", xshift=4,
                       bgcolor="rgba(255,255,255,0.8)",
                       font=dict(size=11, color=color))


def _ccdf(counts) -> tuple[np.ndarray, np.ndarray]:
    s = np.sort(np.asarray(counts))
    xs = np.unique(s)
    return xs, 100 * (len(s) - np.searchsorted(s, xs, side="left")) / len(s)


def _log_ticks(vmax: float) -> tuple[list[float], list[str]]:
    vals = [10 ** e for e in range(int(np.log10(max(vmax, 10))) + 1)]
    return vals, [fmt_int(v) for v in vals]


def _pct_ticks(vmin: float) -> tuple[list[float], list[str]]:
    vals = [10.0 ** e for e in range(int(np.floor(np.log10(max(vmin, 1e-6)))), 3)]
    return vals, [(f"{v:g}".replace(".", ",") + "%") for v in vals]


# --------------------------------------------------------------------------- calificaciones
def rating_distribution(dist: pd.DataFrame, mean: float | None = None) -> go.Figure:
    fig = _fig(300)
    half = (dist["rating"] * 2) % 2 == 1
    for mask, color, name in [(~half, BLUE, "Estrella entera"), (half, ORANGE, "Media estrella")]:
        d = dist[mask]
        fig.add_trace(go.Bar(x=d["rating"], y=d["share_pct"], name=name, marker_color=color, width=0.38,
                             customdata=d["n"],
                             hovertemplate="Nota %{x:.1f}<br>%{y:.1f}% · %{customdata:,} ratings<extra></extra>"))
    if mean is not None and len(dist):
        fig.add_vline(x=mean, line=dict(color=INK2, width=1, dash="dot"))
        fig.add_annotation(x=mean, y=1, yref="paper", text=f"media {fmt_num(mean)}", showarrow=False,
                           xanchor="right", yanchor="top", xshift=-4, font=dict(size=11, color=INK2))
    fig.update_xaxes(tickvals=dist["rating"], ticktext=[fmt_num(r, 1) for r in dist["rating"]], title="Nota")
    fig.update_yaxes(ticksuffix="%", title="% de los ratings")
    fig.update_layout(barmode="overlay")
    return fig


def rating_share_heatmap(share: pd.DataFrame) -> go.Figure:
    fig = _fig(320)
    m = share.T.sort_index()          # eje categórico: la primera nota (0,5) queda abajo
    fig.add_trace(go.Heatmap(
        z=m.values, x=m.columns, y=[fmt_num(r, 1) for r in m.index], colorscale=SEQ, xgap=1, ygap=1,
        colorbar=dict(title=dict(text="% del año", side="right"), ticksuffix="%", thickness=10, outlinewidth=0),
        hovertemplate="%{x} · nota %{y}<br>%{z:.1f}% de los ratings del año<extra></extra>",
    ))
    fig.update_xaxes(title="Año del rating", showline=False, ticks="")
    fig.update_yaxes(title="Nota", showgrid=False, type="category")
    return fig


def mean_rating_hist(df: pd.DataFrame, color: str, label: str) -> go.Figure:
    fig = _fig(260)
    bins = np.arange(0.5, 5.0001, 0.1)
    counts, edges = np.histogram(df["mean_rating"], bins=bins)
    share = 100 * counts / max(len(df), 1)
    mids = (edges[:-1] + edges[1:]) / 2
    fig.add_trace(go.Bar(x=mids, y=share, marker_color=color, width=0.092,
                         hovertemplate=f"Nota media %{{x:.2f}}<br>%{{y:.1f}}% de los {label}<extra></extra>"))
    med = float(df["mean_rating"].median()) if len(df) else 0
    fig.add_vline(x=med, line=dict(color=INK2, width=1, dash="dot"))
    fig.add_annotation(x=med, y=1, yref="paper", text=f"mediana {fmt_num(med)}", showarrow=False, xanchor="left",
                       yanchor="top", xshift=4, font=dict(size=11, color=INK2))
    fig.update_xaxes(range=[0.5, 5.0], title="Nota media", dtick=0.5, tickformat=".1f")
    fig.update_yaxes(ticksuffix="%", title=f"% de los {label}")
    fig.update_layout(showlegend=False)
    return fig


def genre_volume(gs: pd.DataFrame) -> go.Figure:
    d = gs.sort_values("n").replace({"genre": {"(no genres listed)": "(sin género)"}})
    fig = _fig(max(320, 22 * len(d) + 40))
    fig.add_trace(go.Bar(x=d["n"], y=d["genre"], orientation="h", marker_color=BLUE, width=0.62,
                         hovertemplate="%{y}: %{x:,} ratings<extra></extra>"))
    fig.update_xaxes(title="Ratings", showgrid=True, gridcolor=GRID, showline=False)
    fig.update_yaxes(showgrid=False)
    return fig


def genre_relative(gs: pd.DataFrame, global_mean: float) -> go.Figure:
    d = gs.sort_values("n").replace({"genre": {"(no genres listed)": "(sin género)"}})
    diff = d["mean_rating"] - global_mean
    fig = _fig(max(320, 22 * len(d) + 40))
    fig.add_trace(go.Bar(x=diff, y=d["genre"], orientation="h", width=0.62,
                         marker_color=np.where(diff >= 0, BLUE, RED), customdata=d["mean_rating"],
                         hovertemplate="%{y}: nota media %{customdata:.2f} (%{x:+.2f})<extra></extra>"))
    lim = float(np.abs(diff).max() or 0.1) * 1.2
    fig.update_xaxes(range=[-lim, lim], title=f"Diferencia con la media global ({fmt_num(global_mean)})",
                     tickformat="+.2f", showgrid=True, gridcolor=GRID, showline=False, zeroline=True,
                     zerolinecolor=INK2, zerolinewidth=1)
    fig.update_yaxes(showgrid=False)
    return fig


def decades_volume(rd: pd.DataFrame) -> go.Figure:
    fig = _fig(280)
    fig.add_trace(go.Bar(x=rd["decade"], y=rd["n"], marker_color=BLUE, width=7, customdata=rd["movies"],
                         hovertemplate="Década %{x}: %{y:,} ratings · %{customdata:,} películas<extra></extra>"))
    fig.update_xaxes(title="Década de estreno", dtick=20)
    fig.update_yaxes(title="Ratings")
    return fig


def decades_mean(rd: pd.DataFrame, global_mean: float, min_ratings: int = 1000) -> go.Figure:
    d = rd[rd["n"] >= min_ratings]
    fig = _fig(280)
    fig.add_hline(y=global_mean, line=dict(color=INK2, width=1, dash="dot"))
    fig.add_trace(go.Scatter(x=d["decade"], y=d["mean_rating"], mode="lines+markers",
                             line=dict(color=BLUE, width=2), marker=dict(size=7, color=BLUE, line=dict(width=2, color="white")),
                             error_y=dict(type="data", array=d["ci95"], color=AXIS, thickness=1, width=3),
                             customdata=d["n"],
                             hovertemplate="Década %{x}: %{y:.2f} (± %{error_y.array:.3f})<br>%{customdata:,} ratings"
                                           "<extra></extra>"))
    fig.update_xaxes(title="Década de estreno", dtick=20)
    fig.update_yaxes(title="Nota media (± IC 95%)", tickformat=".2f")
    fig.update_layout(showlegend=False)
    return fig


# --------------------------------------------------------------------------- tiempo
def yearly_ratings(ya: pd.DataFrame) -> go.Figure:
    fig = _fig(260)
    fig.add_trace(go.Bar(x=ya["year"], y=ya["n"], marker_color=BLUE, hovertemplate="%{x}: %{y:,} ratings<extra></extra>"))
    fig.update_yaxes(title="Ratings")
    return fig


def yearly_users(ya: pd.DataFrame) -> go.Figure:
    fig = _fig(260)
    returning = ya["active_users"] - ya["new_users"]
    fig.add_trace(go.Bar(x=ya["year"], y=returning, name="Recurrentes", marker_color=BLUE,
                         hovertemplate="%{x}: %{y:,} usuarios recurrentes<extra></extra>"))
    fig.add_trace(go.Bar(x=ya["year"], y=ya["new_users"], name="Nuevos", marker_color=ORANGE,
                         hovertemplate="%{x}: %{y:,} usuarios nuevos<extra></extra>"))
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title="Usuarios activos")
    return fig


def yearly_mean(ya: pd.DataFrame, global_mean: float, min_ratings: int = 1000) -> go.Figure:
    d = ya[ya["n"] >= min_ratings]
    fig = _fig(260)
    fig.add_hline(y=global_mean, line=dict(color=INK2, width=1, dash="dot"),
                  annotation=dict(text=f"media global {fmt_num(global_mean)}", font=dict(size=11, color=INK2)),
                  annotation_position="bottom right")
    fig.add_trace(go.Scatter(x=d["year"], y=d["mean_rating"], mode="lines+markers", line=dict(color=BLUE, width=2),
                             marker=dict(size=6, color=BLUE, line=dict(width=1.5, color="white")), customdata=d["n"],
                             hovertemplate="%{x}: %{y:.2f} · %{customdata:,} ratings<extra></extra>"))
    fig.update_yaxes(title="Nota media", tickformat=".2f")
    fig.update_layout(showlegend=False)
    return fig


# --------------------------------------------------------------------------- popularidad
def activity_ccdf(user_n, movie_n, k: int | None = None) -> go.Figure:
    fig = _fig(340)
    vmax, vmin = 10, 100.0
    for counts, color, name in [(user_n, BLUE, "Usuarios"), (movie_n, ORANGE, "Películas")]:
        if len(counts) == 0:
            continue
        xs, ys = _ccdf(counts)
        vmax, vmin = max(vmax, xs.max()), min(vmin, ys.min())
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=2, shape="hv"), name=name,
                                 hovertemplate=f"%{{y:.3g}}% de los {name.lower()} tiene ≥ %{{x:,}} ratings<extra></extra>"))
    fig.update_xaxes(type="log", title="Cantidad de ratings (escala log)")
    tv, tt = _log_ticks(vmax)
    fig.update_xaxes(tickvals=tv, ticktext=tt)
    pv, pt = _pct_ticks(vmin)
    fig.update_yaxes(type="log", tickvals=pv, ticktext=pt, title="% con al menos X ratings")
    if k:
        _vline(fig, k, f"umbral {k}", 100)
    return fig


def lorenz(user_n, movie_n) -> go.Figure:
    fig = _fig(340)
    fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", line=dict(color=AXIS, width=1), hoverinfo="skip",
                             showlegend=False))
    for counts, color, name in [(user_n, BLUE, "Usuarios"), (movie_n, ORANGE, "Películas")]:
        s = np.sort(np.asarray(counts, dtype=float))
        if len(s) == 0:
            continue
        cum = np.concatenate([[0], np.cumsum(s) / s.sum()])
        idx = np.unique(np.linspace(0, len(s), 300).astype(int))
        fig.add_trace(go.Scatter(x=100 * idx / len(s), y=100 * cum[idx], mode="lines", line=dict(color=color, width=2),
                                 name=f"{name} · Gini {fmt_num(gini(s))}",
                                 hovertemplate=f"El %{{x:.1f}}% menos activo de los {name.lower()} "
                                               "suma el %{y:.1f}% de los ratings<extra></extra>"))
    fig.update_xaxes(range=[0, 100], ticksuffix="%", title="% acumulado (de menor a mayor actividad)",
                     showgrid=True, gridcolor=GRID)
    fig.update_yaxes(range=[0, 100], ticksuffix="%", title="% acumulado de ratings")
    return fig


def popularity_vs_rating(movies: pd.DataFrame, min_n: int) -> go.Figure:
    mv = movies[movies["n"] >= min_n]
    fig = _fig(340)
    if mv.empty:
        return fig
    x = np.log10(mv["n"].to_numpy())
    y = mv["mean_rating"].to_numpy()
    xb = np.linspace(x.min(), x.max() + 1e-9, 41)
    yb = np.linspace(0.5, 5.0, 37)
    h, _, _ = np.histogram2d(x, y, bins=[xb, yb])
    z = np.where(h.T > 0, np.log10(np.maximum(h.T, 1)), np.nan)
    zmax = max(float(np.nanmax(z)), 1)
    fig.add_trace(go.Heatmap(
        x=10 ** ((xb[:-1] + xb[1:]) / 2), y=(yb[:-1] + yb[1:]) / 2, z=z, colorscale=SEQ, zmin=0, zmax=zmax,
        customdata=h.T, hovertemplate="~%{x:,.0f} ratings · nota %{y:.2f}<br>%{customdata:,.0f} películas<extra></extra>",
        colorbar=dict(title=dict(text="Películas", side="right"), thickness=10, outlinewidth=0,
                      tickvals=list(range(int(zmax) + 1)), ticktext=[fmt_int(10 ** v) for v in range(int(zmax) + 1)]),
    ))
    edges = np.arange(np.floor(x.min() * 4) / 4, x.max() + 0.25, 0.25)
    mids, meds = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (x >= lo) & (x < hi)
        if sel.sum() >= 20:
            mids.append(10 ** ((lo + hi) / 2))
            meds.append(float(np.median(y[sel])))
    fig.add_trace(go.Scatter(x=mids, y=meds, mode="lines+markers", name="Mediana por tramo",
                             line=dict(color=ORANGE, width=2), marker=dict(size=6, color=ORANGE),
                             hovertemplate="~%{x:,.0f} ratings: mediana %{y:.2f}<extra></extra>"))
    tv, tt = _log_ticks(mv["n"].max())
    fig.update_xaxes(type="log", tickvals=tv, ticktext=tt, title="Ratings recibidos (escala log)")
    fig.update_yaxes(title="Nota media", range=[0.5, 5.0], showgrid=False)
    return fig


def sparsity_blocks(blocks: pd.DataFrame) -> go.Figure:
    fig = _fig(420)
    v = blocks.values
    z = np.where(v > 0, np.log10(np.where(v > 0, v, 1)), np.nan)
    pct = np.linspace(0, 100, blocks.shape[0] + 1)
    centers = (pct[:-1] + pct[1:]) / 2
    ticks = list(range(-4, 3))
    fig.add_trace(go.Heatmap(
        x=centers, y=centers, z=z, customdata=v, colorscale=SEQ, zmin=-4, zmax=2,
        hovertemplate="Usuarios p%{y:.0f} × películas p%{x:.0f}<br>densidad %{customdata:.4f}%<extra></extra>",
        colorbar=dict(title=dict(text="Densidad", side="right"), thickness=10, outlinewidth=0, tickvals=ticks,
                      ticktext=[f"{10 ** t:g}%".replace(".", ",") for t in ticks]),
    ))
    fig.update_xaxes(title="Películas, de más a menos populares (percentil)", ticksuffix="%", showline=False, ticks="")
    fig.update_yaxes(title="Usuarios, de más a menos activos (percentil)", ticksuffix="%", autorange="reversed",
                     showgrid=False)
    return fig


def threshold_retained(sweep: pd.DataFrame, k: int) -> go.Figure:
    fig = _fig(300)
    for col, color, name in [("ratings_kept_pct", BLUE, "Ratings"), ("users_kept_pct", ORANGE, "Usuarios"),
                             ("movies_kept_pct", AQUA, "Películas")]:
        fig.add_trace(go.Scatter(x=sweep["k"], y=sweep[col], mode="lines+markers", name=name,
                                 line=dict(color=color, width=2), marker=dict(size=7, line=dict(width=1.5, color="white")),
                                 hovertemplate=f"Umbral %{{x}}: se conserva el %{{y:.1f}}% de los {name.lower()}<extra></extra>"))
    fig.update_xaxes(type="log", tickvals=sweep["k"], ticktext=[str(v) for v in sweep["k"]], title="Umbral (escala log)")
    fig.update_yaxes(range=[0, 104], ticksuffix="%", title="% conservado")
    _vline(fig, k, f"vigente: {k}", 104)
    return fig


def threshold_density(sweep: pd.DataFrame, k: int) -> go.Figure:
    fig = _fig(300)
    fig.add_trace(go.Scatter(x=sweep["k"], y=sweep["density_pct"], mode="lines+markers", line=dict(color=BLUE, width=2),
                             marker=dict(size=7, line=dict(width=1.5, color="white")), showlegend=False,
                             hovertemplate="Umbral %{x}: densidad %{y:.3f}%<extra></extra>"))
    fig.update_xaxes(type="log", tickvals=sweep["k"], ticktext=[str(v) for v in sweep["k"]], title="Umbral (escala log)")
    fig.update_yaxes(ticksuffix="%", title="Densidad de la matriz", rangemode="tozero")
    _vline(fig, k, f"vigente: {k}", float(sweep["density_pct"].max()) * 1.05)
    return fig


def threshold_effect(before, after, k: int, entity: str) -> go.Figure:
    fig = _fig(300)
    vmax, vmin = 10, 100.0
    for counts, color, name in [(before, MUTED, "Validado"), (after, BLUE, "Limpio")]:
        xs, ys = _ccdf(counts)
        vmax, vmin = max(vmax, xs.max()), min(vmin, ys.min())
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=2, shape="hv"),
                                 name=f"{name} ({fmt_int(len(counts))})",
                                 hovertemplate=f"{name}: %{{y:.3g}}% con ≥ %{{x:,}} ratings<extra></extra>"))
    tv, tt = _log_ticks(vmax)
    pv, pt = _pct_ticks(vmin)
    fig.update_xaxes(type="log", tickvals=tv, ticktext=tt, title=f"Ratings por {entity} (escala log)")
    fig.update_yaxes(type="log", tickvals=pv, ticktext=pt, title="% con al menos X ratings")
    _vline(fig, k, f"umbral {k}", 100)
    return fig


# --------------------------------------------------------------------------- explorador
def compare_distribution(own: pd.DataFrame, overall: pd.DataFrame, own_label: str) -> go.Figure:
    """Distribución de notas de un usuario o película frente a la de todo el dataset."""
    fig = _fig(260)
    fig.add_trace(go.Bar(x=overall["rating"], y=overall["share_pct"], name="Todo el dataset", marker_color=GRID,
                         marker_line=dict(color=AXIS, width=1), width=0.42,
                         hovertemplate="Nota %{x:.1f}: %{y:.1f}% del dataset<extra></extra>"))
    fig.add_trace(go.Bar(x=own["rating"], y=own["share_pct"], name=own_label, marker_color=BLUE, width=0.24,
                         customdata=own["n"], hovertemplate="Nota %{x:.1f}: %{y:.1f}% (%{customdata:,})<extra></extra>"))
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(tickvals=overall["rating"], ticktext=[fmt_num(r, 1) for r in overall["rating"]], title="Nota")
    fig.update_yaxes(ticksuffix="%", title="% de los ratings")
    return fig


def user_genre_affinity(aff: pd.DataFrame, top: int = 12) -> go.Figure:
    d = aff.head(top).sort_values("vs_crowd").replace({"genre": {"(no genres listed)": "(sin género)"}})
    fig = _fig(max(240, 24 * len(d) + 40))
    fig.add_trace(go.Bar(x=d["vs_crowd"], y=d["genre"], orientation="h", width=0.6,
                         marker_color=np.where(d["vs_crowd"] >= 0, BLUE, RED), customdata=np.stack([d["n"], d["mean_rating"]], -1),
                         hovertemplate="%{y}: %{customdata[0]:,} ratings, media %{customdata[1]:.2f}<br>"
                                       "%{x:+.2f} frente al resto en las mismas películas<extra></extra>"))
    lim = float(np.abs(d["vs_crowd"]).max() or 0.1) * 1.2
    fig.update_xaxes(range=[-lim, lim], tickformat="+.1f", title="Su nota menos la nota media de esas películas",
                     showgrid=True, gridcolor=GRID, showline=False, zeroline=True, zerolinecolor=INK2)
    fig.update_yaxes(showgrid=False)
    return fig


def reactions_timeline(ur: pd.DataFrame) -> go.Figure:
    """Cada punto es una película calificada: fecha × nota, color según la reacción."""
    fig = _fig(280)
    jitter = np.random.default_rng(0).uniform(-0.12, 0.12, len(ur))
    for name, color in REACTION_COLORS.items():
        d = ur[ur["reaction"] == name]
        if d.empty:
            continue
        fig.add_trace(go.Scatter(
            x=d["date"], y=d["rating"] + jitter[d.index], mode="markers", name=name,
            marker=dict(size=7, color=color, opacity=0.75, line=dict(width=0.5, color="white")),
            customdata=np.stack([d["title"], d["rating"], d["movie_mean"]], -1),
            hovertemplate="<b>%{customdata[0]}</b><br>%{x|%d-%m-%Y} · su nota %{customdata[1]:.1f}"
                          " · media %{customdata[2]:.2f}<extra></extra>"))
    fig.update_yaxes(title="Nota", range=[0.2, 5.3], dtick=1)
    if len(ur):
        span = (pd.to_datetime(ur["date"]).max() - pd.to_datetime(ur["date"]).min()).days
        fig.update_xaxes(tickformat="%Y" if span > 730 else "%d-%m-%Y")
    return fig


def movie_yearly(my: pd.DataFrame) -> go.Figure:
    fig = _fig(260)
    fig.add_trace(go.Bar(x=my["year"], y=my["n"], marker_color=BLUE, customdata=my["mean_rating"],
                         hovertemplate="%{x}: %{y:,} ratings · media %{customdata:.2f}<extra></extra>"))
    fig.update_yaxes(title="Ratings por año", tickformat=",d")
    fig.update_layout(showlegend=False)
    return fig
