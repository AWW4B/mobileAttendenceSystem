from __future__ import annotations

import numpy as np
import pytest
from cryptography.exceptions import InvalidTag

from mec_server.vault import InvalidVector, TemplateVault

DIM = 512


@pytest.fixture
def vault():
    return TemplateVault(b"k" * 32, DIM)


def test_transform_is_orthogonal_and_invertible(vault):
    rng = np.random.default_rng(1)
    a, b = (vault.normalize(rng.normal(size=DIM)) for _ in range(2))
    t = vault.transform(1)
    assert np.isclose(float(t.apply(a) @ t.apply(b)), float(a @ b), atol=1e-6)
    assert np.allclose(t.invert(t.apply(a)), a, atol=1e-7)


def test_transform_is_deterministic_per_version(vault):
    assert np.array_equal(vault.transform(3).permutation, vault.transform(3).permutation)
    assert not np.array_equal(vault.transform(3).permutation, vault.transform(4).permutation)


def test_ciphertext_bound_to_pseudonym(vault):
    v = vault.normalize(np.ones(DIM))
    nonce, ct = vault.seal("student-aaaa", 1, v)
    assert np.allclose(vault.open("student-aaaa", 1, nonce, ct), v)
    with pytest.raises(InvalidTag):
        vault.open("student-bbbb", 1, nonce, ct)  # row swapped to another student
    with pytest.raises(InvalidTag):
        vault.open("student-aaaa", 2, nonce, ct)


@pytest.mark.parametrize("bad", [np.zeros(DIM), np.ones(DIM - 1), np.full(DIM, np.nan)])
def test_invalid_vectors_rejected(vault, bad):
    with pytest.raises(InvalidVector):
        vault.normalize(bad)
