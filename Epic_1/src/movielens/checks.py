"""US1.3 t1 — Controles básicos de calidad sobre la capa `interim` (inicio del pipeline).

Cada control es una consulta SQL que devuelve las *filas que violan la regla*:
0 filas => pasa. Así cualquier persona del equipo puede leer (y discutir con el PO)
qué significa exactamente cada regla.

Checklist de US1.3 t1 → controles (todos bloqueantes: detienen el pipeline):
  - Valores faltantes en cada columna de users, movies y ratings → `<tabla>_<columna>_missing`
  - Notas fuera de escala                                         → `ratings_rating_range`, `ratings_rating_step`
  - Ratings repetidos usuario–película                            → `ratings_unique_pair` (+ IDs únicos)
  - IDs de usuario y película que no existen en la otra tabla     → `*_orphan_*`
Aviso (se reporta, no detiene): fechas fuera de rango.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .config import duckdb_connect
from .reporting import BLOCKING, WARNING, CheckResult

TABLES = ("ratings", "movies", "users", "tags", "links")

EXPECTED_SCHEMA = {
    "ratings": {"userId": "INTEGER", "movieId": "INTEGER", "rating": "FLOAT", "timestamp": "BIGINT"},
    "movies": {"movieId": "INTEGER", "title": "VARCHAR", "genres": "VARCHAR"},
    "users": {"userId": "INTEGER", "n_ratings": "BIGINT", "first_timestamp": "BIGINT", "last_timestamp": "BIGINT"},
}

# Columnas que no pueden tener valores faltantes (NULL o texto vacío)
REQUIRED_COLUMNS = {table: list(cols) for table, cols in EXPECTED_SCHEMA.items()}


@dataclass(frozen=True)
class SqlCheck:
    id: str
    name: str
    table: str
    severity: str
    sql: str  # devuelve filas ofensoras; puede usar $parametros
    expected: str
    category: str = ""


def missing_value_checks() -> list[SqlCheck]:
    out = []
    for table, cols in REQUIRED_COLUMNS.items():
        for col in cols:
            text = EXPECTED_SCHEMA[table][col] == "VARCHAR"
            cond = f'"{col}" IS NULL' + (f" OR trim(\"{col}\") = ''" if text else "")
            out.append(SqlCheck(
                f"{table}_{col}_missing", f"Sin valores faltantes en {table}.{col}", table, BLOCKING,
                f"SELECT * FROM {table} WHERE {cond}",
                "0 filas vacías" if text else "0 filas con NULL", "Valores faltantes",
            ))
    return out


def sql_checks(p: dict) -> list[SqlCheck]:
    rmin, rmax, step = p["rating_min"], p["rating_max"], p["rating_step"]
    return missing_value_checks() + [
        SqlCheck(
            "ratings_rating_range", f"Notas dentro de la escala [{rmin}, {rmax}]", "ratings", BLOCKING,
            "SELECT * FROM ratings WHERE rating < $rmin OR rating > $rmax",
            f"{rmin} ≤ rating ≤ {rmax}", "Rango",
        ),
        SqlCheck(
            "ratings_rating_step", f"Notas en pasos de {step}", "ratings", BLOCKING,
            "SELECT * FROM ratings WHERE abs(rating / $step - round(rating / $step)) > 1e-6",
            f"rating múltiplo de {step}", "Rango",
        ),
        SqlCheck(
            "ratings_unique_pair", "Sin ratings repetidos (userId, movieId)", "ratings", BLOCKING,
            "SELECT userId, movieId, count(*) AS n FROM ratings GROUP BY ALL HAVING count(*) > 1",
            "1 rating por usuario y película", "Duplicados",
        ),
        SqlCheck(
            "movies_unique_id", "movieId único en movies", "movies", BLOCKING,
            "SELECT movieId, count(*) AS n FROM movies GROUP BY ALL HAVING count(*) > 1",
            "movieId sin repetir", "Duplicados",
        ),
        SqlCheck(
            "users_unique_id", "userId único en users", "users", BLOCKING,
            "SELECT userId, count(*) AS n FROM users GROUP BY ALL HAVING count(*) > 1",
            "userId sin repetir", "Duplicados",
        ),
        SqlCheck(
            "ratings_orphan_movie", "Películas de ratings existen en movies", "ratings", BLOCKING,
            "SELECT r.* FROM ratings r ANTI JOIN movies m USING (movieId)",
            "todo ratings.movieId existe en movies", "IDs inexistentes",
        ),
        SqlCheck(
            "ratings_orphan_user", "Usuarios de ratings existen en users", "ratings", BLOCKING,
            "SELECT r.* FROM ratings r ANTI JOIN users u USING (userId)",
            "todo ratings.userId existe en users", "IDs inexistentes",
        ),
        SqlCheck(
            "tags_orphan_movie", "Películas de tags existen en movies", "tags", BLOCKING,
            "SELECT t.* FROM tags t ANTI JOIN movies m USING (movieId)",
            "todo tags.movieId existe en movies", "IDs inexistentes",
        ),
        SqlCheck(
            "tags_orphan_user", "Usuarios de tags existen en users", "tags", BLOCKING,
            "SELECT t.* FROM tags t ANTI JOIN users u USING (userId)",
            "todo tags.userId existe en users", "IDs inexistentes",
        ),
        SqlCheck(
            "links_orphan_movie", "Películas de links existen en movies", "links", BLOCKING,
            "SELECT l.* FROM links l ANTI JOIN movies m USING (movieId)",
            "todo links.movieId existe en movies", "IDs inexistentes",
        ),
        SqlCheck(
            "ratings_timestamp_range", "Fechas de rating plausibles", "ratings", WARNING,
            "SELECT * FROM ratings WHERE timestamp < $ts_min OR timestamp > $ts_max",
            f"entre {p['min_date']} y hoy", "Fechas",
        ),
    ]


def connect(interim_dir: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb_connect()
    for table in TABLES:
        path = Path(interim_dir) / f"{table}.parquet"
        con.execute(f"CREATE VIEW {table} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    return con


def schema_checks(con: duckdb.DuckDBPyConnection) -> list[CheckResult]:
    results = []
    for table, expected in EXPECTED_SCHEMA.items():
        actual = {name: dtype for name, dtype, *_ in con.execute(f"DESCRIBE {table}").fetchall()}
        diff = {c: actual.get(c, "(falta)") for c, t in expected.items() if actual.get(c) != t}
        results.append(CheckResult(
            id=f"{table}_schema", name=f"Esquema de {table} (columnas y tipos)", table=table,
            severity=BLOCKING, passed=not diff, n_failed=len(diff), category="Esquema",
            expected=", ".join(f"{c}:{t}" for c, t in expected.items()),
            observed="ok" if not diff else ", ".join(f"{c}:{t}" for c, t in diff.items()),
        ))
    return results


def _sql_params(p: dict) -> dict:
    ts_min = int(datetime.fromisoformat(str(p["min_date"])).replace(tzinfo=timezone.utc).timestamp())
    return {
        "rmin": float(p["rating_min"]), "rmax": float(p["rating_max"]), "step": float(p["rating_step"]),
        "ts_min": ts_min, "ts_max": int(datetime.now(timezone.utc).timestamp()),
    }


def run_sql_check(con: duckdb.DuckDBPyConnection, check: SqlCheck, params: dict) -> CheckResult:
    used = {k: v for k, v in params.items() if f"${k}" in check.sql}
    n_failed = con.execute(f"SELECT count(*) FROM ({check.sql})", used).fetchone()[0]
    sample = []
    if n_failed:
        df = con.execute(f"SELECT * FROM ({check.sql}) LIMIT 5", used).df()
        sample = df.astype(object).where(df.notna(), None).to_dict("records")
    return CheckResult(
        id=check.id, name=check.name, table=check.table, severity=check.severity,
        passed=n_failed == 0, n_failed=int(n_failed), expected=check.expected,
        observed="0 filas" if not n_failed else f"{n_failed:,} filas".replace(",", "."), sample=sample,
        category=check.category,
    )


def run_checks(con: duckdb.DuckDBPyConnection, vparams: dict) -> list[CheckResult]:
    results = schema_checks(con)
    if any(not r.passed for r in results):
        return results  # sin el esquema correcto las demás reglas no tienen sentido
    params = _sql_params(vparams)
    return results + [run_sql_check(con, c, params) for c in sql_checks(vparams)]


def table_profile(con: duckdb.DuckDBPyConnection) -> dict:
    """Conteos base que el panel de calidad muestra junto a los checks."""
    n, users, movies = con.execute(
        "SELECT count(*), count(DISTINCT userId), count(DISTINCT movieId) FROM ratings"
    ).fetchone()
    catalog = con.execute("SELECT count(*) FROM movies").fetchone()[0]
    tags = con.execute("SELECT count(*) FROM tags").fetchone()[0]
    return {
        "ratings": int(n), "users": int(users), "movies_rated": int(movies), "movies_catalog": int(catalog),
        "tags": int(tags),
        "density_pct": round(100 * n / (users * movies), 4) if users and movies else 0.0,
    }
