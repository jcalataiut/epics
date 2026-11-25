"""US1.5 — smoke test del dashboard sobre los datos reales del pipeline.

Abre cada página y aplica filtros. Se salta si todavía no se corrió `make pipeline`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from movielens.config import load_params, resolve

APP = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"
PROCESSED = resolve(load_params()["data"]["processed_dir"])
PAGES = ["views/ratings.py", "views/popularity.py", "views/explorer.py", "views/taste_graph.py",
         "views/quality.py", "views/pipeline.py"]

pytestmark = pytest.mark.skipif(not (PROCESSED / "ratings.parquet").exists(),
                                reason="sin datos procesados: ejecutar `make pipeline`")


def _metric(at, label: str) -> int:
    return int(next(m.value for m in at.metric if m.label == label).replace(".", ""))


def test_dashboard_todas_las_paginas():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=300).run()
    assert not at.exception, [e.message for e in at.exception]
    total = _metric(at, "Ratings")

    # US1.5 t3: filtros de umbral y género recalculan los gráficos
    at.sidebar.slider(key="f_threshold").set_value(100)
    at.sidebar.multiselect(key="f_genres").set_value(["Comedy"])
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert _metric(at, "Ratings") < total

    for page in PAGES:
        at.switch_page(page).run()
        assert not at.exception, (page, [e.message for e in at.exception])
