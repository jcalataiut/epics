"""Criterios de aceptación de US1.3, de punta a punta sobre CSV sintéticos con problemas conocidos.

AC1  un control falla (faltantes, escala, repetidos, IDs) -> el pipeline se detiene antes de limpiar
AC2  el mensaje dice qué control falló, en qué tabla, cuántas filas y ejemplos
AC3  usuarios y películas bajo data.min_ratings se eliminan; los datos limpios se guardan (DVC)
AC4  cada ejecución deja un informe corto: problemas por control y ratings eliminados
Además: CSV truncado o con tipos inválidos se detiene en `ingest`.
"""
from __future__ import annotations

import json

import pandas as pd

from movielens import clean, ingest, profile, validate

from .conftest import synthetic_tables, write_raw


def test_ac3_ac4_camino_feliz(workspace):
    p, tmp = workspace["params"], workspace["tmp"]
    write_raw(tmp / "raw", synthetic_tables())

    assert ingest.run(p)[0] == 0
    assert validate.run(p) == 0
    assert clean.run(p) == 0
    assert profile.run(p) == 0

    out = pd.read_parquet(tmp / "processed" / "ratings.parquet")
    k = p["data"]["min_ratings"]
    assert out.groupby("userId").size().min() >= k
    assert out.groupby("movieId").size().min() >= k
    assert set(pd.read_parquet(tmp / "processed" / "movies.parquet")["movieId"]) == set(out["movieId"])

    metrics = json.loads(workspace["paths"]["CLEAN_METRICS"].read_text())
    assert metrics["after"]["ratings"] == len(out) and metrics["converged"]
    assert metrics["removed"]["ratings"] == metrics["before"]["ratings"] - len(out)
    assert json.loads(workspace["paths"]["CHECKS_REPORT"].read_text())["status"] == "pass"

    # AC4: informe corto con los problemas por control y los ratings eliminados
    report = workspace["paths"]["CLEAN_REPORT"].read_text()
    assert "Sin valores faltantes en ratings.rating" in report and "Eliminados" in report
    assert f"{metrics['removed']['ratings']:,}".replace(",", ".") in report


def test_ac1_nota_invalida_detiene_el_pipeline(workspace):
    p, tmp = workspace["params"], workspace["tmp"]
    t = synthetic_tables()
    t["ratings"].loc[3, "rating"] = 7.0
    write_raw(tmp / "raw", t)

    assert ingest.run(p)[0] == 0          # el archivo está íntegro…
    assert validate.run(p) == 1           # …pero su contenido viola una regla bloqueante
    report = json.loads(workspace["paths"]["CHECKS_REPORT"].read_text())
    assert report["status"] == "fail"
    assert [c["id"] for c in report["checks"] if not c["passed"]] == ["ratings_rating_range"]

    assert clean.run(p) == 1              # defensa en profundidad: clean no corre sin validación
    assert not (tmp / "processed" / "ratings.parquet").exists()


def test_ac3_csv_truncado_falla_en_ingest(workspace):
    p, tmp = workspace["params"], workspace["tmp"]
    write_raw(tmp / "raw", synthetic_tables())
    ratings = tmp / "raw" / "ratings.csv"
    ratings.write_bytes(ratings.read_bytes()[:-40])  # simula una copia a medias

    code, _ = ingest.run(p)
    assert code == 1
    report = json.loads(workspace["paths"]["INTEGRITY_REPORT"].read_text())
    assert [c["id"] for c in report["checks"] if not c["passed"]] == ["ratings_md5"]
    assert not (tmp / "interim" / "ratings.parquet").exists()


def test_tipo_invalido_en_csv_falla_en_ingest(workspace):
    p, tmp = workspace["params"], workspace["tmp"]
    t = synthetic_tables()
    t["ratings"]["rating"] = t["ratings"]["rating"].astype(object)
    t["ratings"].loc[0, "rating"] = "cinco"
    write_raw(tmp / "raw", t)
    code, _ = ingest.run(p)
    assert code == 1
    report = json.loads(workspace["paths"]["INTEGRITY_REPORT"].read_text())
    assert [c["id"] for c in report["checks"] if not c["passed"]] == ["ratings_parse"]


def test_ac1_ac2_valor_faltante_detiene_con_mensaje_claro(workspace, capsys):
    p, tmp = workspace["params"], workspace["tmp"]
    t = synthetic_tables()
    t["ratings"]["rating"] = t["ratings"]["rating"].astype(object)
    t["ratings"].loc[2, "rating"] = None          # celda vacía en el CSV
    write_raw(tmp / "raw", t)

    assert ingest.run(p)[0] == 0
    assert validate.run(p) == 1
    out = capsys.readouterr().out
    assert "PIPELINE DETENIDO en 'validate'" in out
    assert "Sin valores faltantes en ratings.rating [ratings]: 1 filas" in out
    assert "ejemplo:" in out and "reports/quality/checks.json" in out
    assert clean.run(p) == 1
