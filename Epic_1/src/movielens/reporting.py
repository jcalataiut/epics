"""Formato común de los reportes de calidad (US1.3 t1) que consume el panel (US1.5 t2).

Cada etapa "gate" escribe un JSON con la misma forma: una lista de checks con
severidad. Si algún check *bloqueante* falla, la etapa termina con código 1 y
DVC no ejecuta las etapas siguientes.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BLOCKING = "blocking"
WARNING = "warning"


@dataclass
class CheckResult:
    id: str
    name: str  # descripción legible para el equipo (español)
    table: str
    severity: str  # "blocking" | "warning"
    passed: bool
    n_failed: int = 0  # filas que violan la regla
    expected: str = ""
    observed: str = ""
    sample: list[dict[str, Any]] = field(default_factory=list)  # hasta 5 filas ofensoras
    story: str = "US1.3"
    category: str = ""  # Archivos, Esquema, Valores faltantes, Rango, Duplicados, IDs inexistentes, Fechas

    @property
    def blocks(self) -> bool:
        return self.severity == BLOCKING and not self.passed


def apply_overrides(results: list[CheckResult], overrides: dict[str, str] | None) -> list[CheckResult]:
    for r in results:
        if overrides and r.id in overrides:
            r.severity = overrides[r.id]
    return results


def summarize(results: list[CheckResult]) -> dict[str, Any]:
    n_block = sum(r.blocks for r in results)
    n_warn = sum(r.severity == WARNING and not r.passed for r in results)
    status = "fail" if n_block else ("warn" if n_warn else "pass")
    return {
        "status": status,
        "n_checks": len(results),
        "n_passed": sum(r.passed for r in results),
        "n_blocking_failed": n_block,
        "n_warnings": n_warn,
    }


def write_report(path: Path, stage: str, results: list[CheckResult], extra: dict | None = None) -> dict:
    report = {
        "stage": stage,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **summarize(results),
        "checks": [asdict(r) for r in results],
        **(extra or {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
    return report


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")


def load_report(path: Path) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def print_results(stage: str, results: list[CheckResult], report_path: Path | None = None) -> None:
    """Resumen en consola. Si un control bloqueante falla, explica qué está mal y dónde ver el detalle."""
    icon = {True: "PASA ", False: "FALLA"}
    print(f"\n== {stage}: {len(results)} controles ==")
    for r in results:
        sev = "bloqueante" if r.severity == BLOCKING else "aviso"
        print(f"  {icon[r.passed]}  {sev:10}  {r.id:30} filas={r.n_failed:<10,} {r.name}")
    s = summarize(results)
    failed = [r for r in results if r.blocks]
    if failed:
        print(f"\n>> PIPELINE DETENIDO en '{stage}': {len(failed)} control(es) bloqueante(s) fallaron.")
        for r in failed:
            print(f"   - {r.name} [{r.table}]: {r.observed}. Se esperaba: {r.expected}.")
            for row in r.sample[:3]:
                print(f"       ejemplo: {row}")
        where = f"{report_path.relative_to(report_path.parents[2])}" if report_path else "reports/quality/"
        print(f"   Detalle: {where} · Panel: `make dashboard` → Calidad de datos.")
        print("   Corrige los datos de origen (o la regla en params.yaml) y vuelve a ejecutar `make pipeline`.\n")
    else:
        print(f"\n>> OK: {s['n_passed']} de {s['n_checks']} controles pasan ({s['n_warnings']} aviso(s)).\n")


def _json_default(o: Any):
    # tipos numpy / pandas / fechas
    if hasattr(o, "item"):
        return o.item()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)
