"""Componente de grafo interactivo (estilo Obsidian) para Streamlit.

Usa vis-network 9.1.9 (Apache-2.0/MIT), copiado en `app/static/` e incrustado en la
página: funciona sin acceso a CDN. Fuerzas tipo ForceAtlas2, etiquetas que aparecen al
acercarse, resaltado de vecinos al pasar el mouse y buscador de nodos.
"""
from __future__ import annotations

import html
import json
from functools import lru_cache
from pathlib import Path

import streamlit as st

VIS_JS = Path(__file__).parent / "static" / "vis-network.min.js"


@lru_cache(maxsize=1)
def _vis() -> str:
    return VIS_JS.read_text(encoding="utf-8")


def _js(obj) -> str:
    """JSON seguro para incrustar en <script> (los títulos vienen de los datos)."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def tooltip(title: str, rows: list[tuple[str, str]]) -> str:
    body = "".join(f"<div><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>" for k, v in rows)
    return f"<strong>{html.escape(title)}</strong>{body}"


def render(nodes: list[dict], edges: list[dict], legend: list[tuple[str, str]], height: int = 640,
           caption: str = "", physics: dict | None = None, label_threshold: int = 9) -> None:
    """nodes: {id, label, color, value, tip, shape?}; edges: {from, to, value?, color?}; legend: [(texto, color)]."""
    options = {
        "autoResize": True,
        "nodes": {
            "shape": "dot", "borderWidth": 0,
            "font": {"color": "#d4d6db", "size": 13, "face": "Inter, Segoe UI, sans-serif",
                     "strokeWidth": 3, "strokeColor": "#1b1d21"},
            "scaling": {"min": 5, "max": 26, "label": {"enabled": True, "min": 11, "max": 20,
                                                       "drawThreshold": label_threshold, "maxVisible": 22}},
        },
        "edges": {
            "smooth": False, "color": {"color": "rgba(170,176,186,0.22)", "highlight": "rgba(220,224,230,0.9)",
                                       "hover": "rgba(220,224,230,0.6)"},
            "scaling": {"min": 0.6, "max": 3.2}, "selectionWidth": 0.6,
        },
        "physics": physics or {
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {"gravitationalConstant": -46, "centralGravity": 0.012, "springLength": 90,
                                 "springConstant": 0.06, "damping": 0.5, "avoidOverlap": 0.35},
            "stabilization": {"enabled": True, "iterations": 350, "updateInterval": 50},
            "minVelocity": 0.8,
        },
        "interaction": {"hover": True, "tooltipDelay": 80, "hideEdgesOnDrag": True, "multiselect": False,
                        "navigationButtons": False, "keyboard": False},
    }
    legend_html = "".join(
        f'<span class="lg"><i style="background:{c}"></i>{html.escape(t)}</span>' for t, c in legend)
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<style>
  html,body{{margin:0;height:100%;background:#1b1d21;font-family:Inter,"Segoe UI",system-ui,sans-serif;}}
  #wrap{{position:relative;height:{height}px;border-radius:8px;overflow:hidden;background:#1b1d21;}}
  #net{{position:absolute;inset:0;}}
  .bar{{position:absolute;left:12px;right:12px;top:10px;display:flex;gap:8px;align-items:center;z-index:2;}}
  .bar input{{flex:0 1 240px;min-width:120px;background:#26292f;border:1px solid #3a3e46;color:#e6e7ea;border-radius:6px;
             padding:6px 10px;font-size:13px;outline:none;}}
  .bar input:focus{{border-color:#5d8fd6;}}
  .bar .meta{{margin-left:auto;color:#8b919c;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
  .legend{{position:absolute;left:12px;bottom:10px;right:12px;display:flex;flex-wrap:wrap;gap:4px 14px;z-index:2;}}
  .lg{{color:#aeb3bc;font-size:12px;display:inline-flex;align-items:center;gap:6px;}}
  .lg i{{width:9px;height:9px;border-radius:50%;display:inline-block;}}
  .vis-tooltip{{position:absolute;background:#26292f!important;color:#e6e7ea!important;border:1px solid #3a3e46!important;
               border-radius:6px!important;padding:8px 10px!important;font-size:12px!important;max-width:320px;
               white-space:normal!important;box-shadow:0 4px 14px rgba(0,0,0,.35);}}
  .vis-tooltip strong{{display:block;margin-bottom:4px;font-size:13px;color:#fff;}}
  .vis-tooltip div{{display:flex;justify-content:space-between;gap:12px;color:#aeb3bc;}}
  .vis-tooltip b{{color:#e6e7ea;font-weight:500;}}
  #loading{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#8b919c;font-size:13px;}}
</style></head><body>
<div id="wrap">
  <div class="bar"><input id="q" list="names" placeholder="Buscar nodo…" autocomplete="off">
    <datalist id="names"></datalist><span class="meta" id="meta"></span></div>
  <div id="loading">Calculando la disposición…</div>
  <div id="net"></div>
  <div class="legend">{legend_html}</div>
</div>
<script>{_vis()}</script>
<script>
const RAW_N = {_js(nodes)};
const RAW_E = {_js(edges)};
const DIM = "rgba(110,115,125,0.18)";
function tip(h){{ const d=document.createElement("div"); d.innerHTML=h; return d; }}
const nodes = new vis.DataSet(RAW_N.map(n => ({{...n, title: tip(n.tip), color: {{background:n.color,border:n.color,
  highlight:{{background:n.color,border:"#ffffff"}}, hover:{{background:n.color,border:"#ffffff"}}}}, base:n.color}})));
const edges = new vis.DataSet(RAW_E.map((e,i) => ({{id:i, ...e, base:e.color || null,
  color: e.color ? {{color:e.color, highlight:e.color, hover:e.color}} : undefined}})));
const net = new vis.Network(document.getElementById("net"), {{nodes, edges}}, {json.dumps(options)});
document.getElementById("meta").textContent =
  `${{RAW_N.length}} nodos · ${{RAW_E.length}} conexiones{(' · ' + html.escape(caption)) if caption else ''}`;
document.getElementById("meta").title = "Arrastra para mover, rueda para acercar, pasa el mouse para ver vecinos, clic para fijar.";
// Las fuerzas solo se usan para calcular la disposición: una vez estable, el grafo queda quieto.
// Al arrastrar un nodo se reactivan un momento para que sus vecinos lo acompañen, y se vuelven a apagar.
let settleTimer = null;
function freeze(){{ net.setOptions({{physics: {{enabled: false}}}}); document.getElementById("loading").style.display="none"; }}
let fitted = false;
function firstFreeze(){{ freeze(); if (!fitted) {{ fitted = true; net.fit({{animation: false}}); }} }}
net.once("stabilizationIterationsDone", firstFreeze);
setTimeout(firstFreeze, 6000);
net.on("dragStart", p => {{ if (p.nodes.length) {{ clearTimeout(settleTimer); net.setOptions({{physics: {{enabled: true}}}}); }} }});
net.on("dragEnd", p => {{ if (p.nodes.length) {{ settleTimer = setTimeout(freeze, 1200); }} }});

let pinned = null;
function highlight(id){{
  if (id === null) {{
    nodes.update(RAW_N.map(n => ({{id:n.id, color:{{background:n.color,border:n.color}}, font:{{color:"#d4d6db"}}}})));
    edges.update(edges.get().map(e => ({{id:e.id, hidden:false}})));
    return;
  }}
  const keep = new Set([id, ...net.getConnectedNodes(id)]);
  nodes.update(RAW_N.map(n => keep.has(n.id)
    ? {{id:n.id, color:{{background:n.color,border:n.id===id?"#ffffff":n.color}}, font:{{color:"#ffffff"}}}}
    : {{id:n.id, color:{{background:DIM,border:DIM}}, font:{{color:"rgba(0,0,0,0)"}}}}));
  const ce = new Set(net.getConnectedEdges(id));
  edges.update(edges.get().map(e => ({{id:e.id, hidden: !ce.has(e.id)}})));
}}
net.on("hoverNode", p => {{ if (pinned === null) highlight(p.node); }});
net.on("blurNode", () => {{ if (pinned === null) highlight(null); }});
net.on("click", p => {{ pinned = p.nodes.length ? p.nodes[0] : null; highlight(pinned); }});

const dl = document.getElementById("names");
RAW_N.slice().sort((a,b) => a.label.localeCompare(b.label)).forEach(n => {{
  const o = document.createElement("option"); o.value = n.label; dl.appendChild(o); }});
document.getElementById("q").addEventListener("change", ev => {{
  const n = RAW_N.find(x => x.label.toLowerCase() === ev.target.value.trim().toLowerCase());
  if (!n) return;
  pinned = n.id; highlight(n.id); net.selectNodes([n.id]);
  net.focus(n.id, {{scale: 1.3, animation: {{duration: 600, easingFunction: "easeInOutQuad"}}}});
}});
</script></body></html>"""
    st.iframe(page, height=height + 4)


# Grupos de género para colorear nodos (paleta validada; el grupo más específico gana)
GENRE_GROUPS = [
    ("Animación e infantil", {"Animation", "Children"}, "#00b894"),
    ("Terror", {"Horror"}, "#ec4647"),
    ("Ciencia ficción y fantasía", {"Sci-Fi", "Fantasy"}, "#f2a600"),
    ("Romance", {"Romance"}, "#ee7fac"),
    ("Crimen y suspenso", {"Crime", "Thriller", "Mystery", "Film-Noir"}, "#9887ef"),
    ("Comedia", {"Comedy"}, "#0aac23"),
    ("Acción y aventura", {"Action", "Adventure", "War", "Western"}, "#338ced"),
    ("Drama", {"Drama"}, "#f47230"),
]
OTHER = ("Otros", "#8b919c")


def genre_group(genres: str) -> tuple[str, str]:
    gs = set((genres or "").split("|"))
    for label, members, color in GENRE_GROUPS:
        if gs & members:
            return label, color
    return OTHER


def genre_legend(labels_present: set[str]) -> list[tuple[str, str]]:
    items = [(lbl, col) for lbl, _, col in GENRE_GROUPS if lbl in labels_present]
    return items + ([OTHER] if OTHER[0] in labels_present else [])
