"""US1.3 t2 — el k-core cumple su contrato."""
from __future__ import annotations

import numpy as np

from movielens.kcore import kcore_mask, matrix_stats, satisfies_kcore


def chain_example():
    """Quitar la película 3 (1 rating) deja al usuario 3 bajo k=2 -> requiere 2 pasadas."""
    users = np.array([1, 1, 2, 2, 3, 3, 4, 4])
    items = np.array([1, 2, 1, 2, 2, 3, 1, 4])
    return users, items


def test_iterativo_converge_y_cumple_k():
    u, i = chain_example()
    res = kcore_mask(u, i, 2, 2)
    assert res.converged and res.iterations >= 2
    assert satisfies_kcore(u[res.mask], i[res.mask], 2, 2)
    assert set(zip(u[res.mask], i[res.mask])) == {(1, 1), (1, 2), (2, 1), (2, 2)}


def test_una_pasada_puede_violar_k():
    """Evidencia de la decisión D-02: el filtro de una pasada no garantiza k."""
    u, i = chain_example()
    res = kcore_mask(u, i, 2, 2, iterative=False)
    assert not satisfies_kcore(u[res.mask], i[res.mask], 2, 2)


def test_k1_conserva_todo():
    u, i = chain_example()
    assert kcore_mask(u, i, 1, 1).mask.all()


def test_k_imposible_deja_vacio():
    u, i = chain_example()
    assert kcore_mask(u, i, 100, 100).n_kept == 0


def test_idempotente():
    rng = np.random.default_rng(0)
    u, i = rng.integers(0, 200, 5000), rng.integers(0, 100, 5000)
    first = kcore_mask(u, i, 10, 10)
    u2, i2 = u[first.mask], i[first.mask]
    assert kcore_mask(u2, i2, 10, 10).mask.all()


def test_matrix_stats():
    s = matrix_stats(np.array([1, 1, 2]), np.array([1, 2, 1]))
    assert s == {"ratings": 3, "users": 2, "movies": 2, "density_pct": 75.0, "sparsity_pct": 25.0}
