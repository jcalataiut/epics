"""US1.3 t2 — Filtro k-core sobre la matriz usuario × película.

k-core (k_user, k_item): el mayor subconjunto de ratings en que cada usuario
tiene ≥ k_user ratings y cada película ≥ k_item ratings. Quitar películas
puede dejar usuarios bajo el umbral (y viceversa), por eso se itera hasta que
nada cambie. Con `iterative=False` se aplica una sola pasada (sólo como
referencia; ver D-02 en docs/DECISIONS.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class KCoreResult:
    mask: np.ndarray  # bool por rating: True = se conserva
    iterations: int
    converged: bool
    history: list[dict] = field(default_factory=list)  # filas/usuarios/películas por iteración

    @property
    def n_kept(self) -> int:
        return int(self.mask.sum())


def _codes(ids: np.ndarray) -> tuple[np.ndarray, int]:
    uniq, inv = np.unique(ids, return_inverse=True)
    return inv.astype(np.int64, copy=False), len(uniq)


def kcore_mask(
    users: np.ndarray,
    items: np.ndarray,
    k_user: int,
    k_item: int,
    iterative: bool = True,
    max_iter: int = 50,
) -> KCoreResult:
    u, n_u = _codes(np.asarray(users))
    i, n_i = _codes(np.asarray(items))
    mask = np.ones(len(u), dtype=bool)
    history: list[dict] = []
    iterations, converged = 0, False

    while iterations < max_iter:
        uc = np.bincount(u[mask], minlength=n_u)
        ic = np.bincount(i[mask], minlength=n_i)
        new_mask = mask & (uc[u] >= k_user) & (ic[i] >= k_item)
        iterations += 1
        history.append({
            "iteration": iterations,
            "ratings": int(new_mask.sum()),
            "users": int(np.count_nonzero(np.bincount(u[new_mask], minlength=n_u))),
            "items": int(np.count_nonzero(np.bincount(i[new_mask], minlength=n_i))),
        })
        if new_mask.sum() == mask.sum():
            converged = True
            break
        mask = new_mask
        if not iterative:
            converged = bool(_satisfies(u[mask], i[mask], k_user, k_item))
            break
    return KCoreResult(mask=mask, iterations=iterations, converged=converged, history=history)


def _satisfies(u: np.ndarray, i: np.ndarray, k_user: int, k_item: int) -> bool:
    if len(u) == 0:
        return True
    return bool(np.bincount(u)[np.unique(u)].min() >= k_user and np.bincount(i)[np.unique(i)].min() >= k_item)


def satisfies_kcore(users: np.ndarray, items: np.ndarray, k_user: int, k_item: int) -> bool:
    """Post-condición (contrato de datos): todo usuario/película restante cumple k."""
    u, _ = _codes(np.asarray(users))
    i, _ = _codes(np.asarray(items))
    return _satisfies(u, i, k_user, k_item)


def matrix_stats(users: np.ndarray, items: np.ndarray) -> dict:
    n = int(len(users))
    n_u = int(len(np.unique(users))) if n else 0
    n_i = int(len(np.unique(items))) if n else 0
    density = n / (n_u * n_i) if n_u and n_i else 0.0
    return {
        "ratings": n, "users": n_u, "movies": n_i,
        "density_pct": round(100 * density, 4),
        "sparsity_pct": round(100 * (1 - density), 4),
    }
