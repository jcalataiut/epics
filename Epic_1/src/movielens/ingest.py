"""Etapa `ingest` — integridad de los CSV crudos y conversión a Parquet tipado.

Gate temprano (fail fast) de US1.3 t1: antes de parsear 900 MB se verifica que
cada archivo exista y que su MD5 coincida con `checksums.txt`. Un archivo
truncado (p. ej. una copia a medias) detiene el pipeline aquí.

MovieLens 32M no trae un archivo de usuarios: la tabla `users` se deriva de
ratings (un registro por userId con su actividad) para poder validar sus columnas
y los IDs de tags contra ella.

Salidas:
  data/interim/{ratings,movies,movie_genres,users,tags,links}.parquet
  reports/quality/integrity.json
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from .config import INTEGRITY_REPORT, load_params, resolve
from .reporting import BLOCKING, CheckResult, print_results, summarize, write_report

RAW_FILES = {
    "ratings": "ratings.csv",
    "movies": "movies.csv",
    "tags": "tags.csv",
    "links": "links.csv",
}

SCHEMAS: dict[str, dict[str, pa.DataType]] = {
    "ratings": {"userId": pa.int32(), "movieId": pa.int32(), "rating": pa.float32(), "timestamp": pa.int64()},
    "movies": {"movieId": pa.int32(), "title": pa.string(), "genres": pa.string()},
    "tags": {"userId": pa.int32(), "movieId": pa.int32(), "tag": pa.string(), "timestamp": pa.int64()},
    # imdbId se mantiene como texto para conservar ceros a la izquierda
    "links": {"movieId": pa.int32(), "imdbId": pa.string(), "tmdbId": pa.int64()},
}


def md5sum(path: Path, chunk: int = 8 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def parse_checksums(path: Path) -> dict[str, str]:
    """Formato `md5sum`: '<hash>  <archivo>' por línea."""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2:
            out[parts[1]] = parts[0].lower()
    return out


def check_integrity(raw_dir: Path, verify_checksums: bool = True) -> list[CheckResult]:
    results: list[CheckResult] = []
    expected = parse_checksums(raw_dir / "checksums.txt") if (raw_dir / "checksums.txt").exists() else {}
    for table, fname in RAW_FILES.items():
        path = raw_dir / fname
        exists = path.exists()
        results.append(CheckResult(
            id=f"{table}_file_exists", name=f"Existe {fname}", table=table, severity=BLOCKING, category="Archivos",
            passed=exists, n_failed=0 if exists else 1, expected=f"presente en {raw_dir.name}/",
            observed="ok" if exists else f"no existe: {path}",
        ))
        if exists and verify_checksums:
            exp = expected.get(fname)
            got = md5sum(path)
            ok = exp is not None and got == exp
            results.append(CheckResult(
                id=f"{table}_md5", name=f"MD5 de {fname} coincide con checksums.txt", table=table,
                severity=BLOCKING, category="Archivos", passed=ok, n_failed=0 if ok else 1,
                expected=exp or "(sin entrada en checksums.txt)",
                observed=f"{got} ({path.stat().st_size:,} bytes)",
            ))
    return results


def read_csv(path: Path, schema: dict[str, pa.DataType]) -> pa.Table:
    return pacsv.read_csv(
        path,
        read_options=pacsv.ReadOptions(block_size=64 << 20),
        convert_options=pacsv.ConvertOptions(
            column_types=schema, include_columns=list(schema), strings_can_be_null=False
        ),
    )


def explode_genres(movies: pa.Table) -> pa.Table:
    """movies.genres 'A|B|C' -> tabla larga (movieId, genre) para filtros por género."""
    split = pc.split_pattern(movies["genres"].combine_chunks(), "|")
    ids = pc.take(movies["movieId"].combine_chunks(), pc.list_parent_indices(split))
    return pa.table({"movieId": ids, "genre": pc.list_flatten(split)})


def derive_users(ratings: pa.Table) -> pa.Table:
    """Tabla de usuarios: userId, n_ratings, first_timestamp, last_timestamp (una fila por userId)."""
    agg = ratings.group_by("userId").aggregate([("movieId", "count"), ("timestamp", "min"), ("timestamp", "max")])
    return pa.table({
        "userId": agg["userId"],
        "n_ratings": agg["movieId_count"],
        "first_timestamp": agg["timestamp_min"],
        "last_timestamp": agg["timestamp_max"],
    }).sort_by("userId")


def run(params: dict) -> tuple[int, dict]:
    raw_dir = resolve(params["data"]["raw_dir"])
    out_dir = resolve(params["data"]["interim_dir"])
    vparams = params["validation"]

    results = check_integrity(raw_dir, vparams.get("verify_checksums", True))
    extra: dict = {"raw_dir": str(raw_dir), "rows": {}}
    if summarize(results)["status"] == "fail":
        write_report(INTEGRITY_REPORT, "ingest", results, extra)
        print_results("ingest (integridad)", results, INTEGRITY_REPORT)
        return 1, extra

    out_dir.mkdir(parents=True, exist_ok=True)
    for table, fname in RAW_FILES.items():
        try:
            tbl = read_csv(raw_dir / fname, SCHEMAS[table])
            ok, observed = True, f"{tbl.num_rows:,} filas"
        except (pa.ArrowInvalid, pa.ArrowKeyError) as exc:  # tipo inválido / columna faltante
            tbl, ok, observed = None, False, str(exc).splitlines()[0][:300]
        results.append(CheckResult(
            id=f"{table}_parse", name=f"{fname} se parsea con el esquema esperado", table=table,
            severity=BLOCKING, category="Esquema", passed=ok, n_failed=0 if ok else 1,
            expected=", ".join(f"{c}:{t}" for c, t in SCHEMAS[table].items()), observed=observed,
        ))
        if tbl is None:
            continue
        extra["rows"][table] = tbl.num_rows
        pq.write_table(tbl, out_dir / f"{table}.parquet", compression="zstd")
        if table == "movies":
            pq.write_table(explode_genres(tbl), out_dir / "movie_genres.parquet", compression="zstd")
        if table == "ratings":
            users = derive_users(tbl)
            extra["rows"]["users"] = users.num_rows
            pq.write_table(users, out_dir / "users.parquet", compression="zstd")

    report = write_report(INTEGRITY_REPORT, "ingest", results, extra)
    print_results("ingest (integridad + esquema)", results, INTEGRITY_REPORT)
    return (1 if report["status"] == "fail" else 0), extra


def main() -> None:
    code, _ = run(load_params())
    sys.exit(code)


if __name__ == "__main__":
    main()
