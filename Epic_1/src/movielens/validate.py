"""Etapa `validate` (US1.3 t1) — gate de calidad que para el pipeline.

Ejecuta los checks de `checks.py` sobre data/interim y escribe:
  reports/quality/checks.json   (detalle por check, lo lee el panel)
  reports/metrics/quality.json  (métricas planas para `dvc metrics show/diff`)

Si algún check bloqueante falla -> exit 1 -> `dvc repro` se detiene y la
etapa `clean` no corre.
"""
from __future__ import annotations

import sys

from .checks import connect, run_checks, table_profile
from .config import CHECKS_REPORT, QUALITY_METRICS, load_params, resolve
from .reporting import apply_overrides, print_results, summarize, write_json, write_report


def run(params: dict) -> int:
    vparams = params["validation"]
    con = connect(resolve(params["data"]["interim_dir"]))
    results = apply_overrides(run_checks(con, vparams), vparams.get("severity_overrides"))
    profile = table_profile(con) if all(r.passed for r in results if r.id.endswith("_schema")) else {}

    report = write_report(CHECKS_REPORT, "validate", results, {"profile": profile, "params": vparams})
    summary = summarize(results)
    write_json(QUALITY_METRICS, {
        "checks_total": summary["n_checks"],
        "checks_passed": summary["n_passed"],
        "blocking_failed": summary["n_blocking_failed"],
        "warnings": summary["n_warnings"],
        **{f"raw_{k}": v for k, v in profile.items()},
    })
    print_results("validate", results, CHECKS_REPORT)
    return 1 if report["status"] == "fail" else 0


def main() -> None:
    sys.exit(run(load_params()))


if __name__ == "__main__":
    main()
