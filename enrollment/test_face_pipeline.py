from __future__ import annotations

import numpy as np
import pytest

from face_pipeline import (
    REFERENCE_LANDMARKS,
    Face,
    align,
    build_template,
    largest_face,
    preprocess,
)


def test_align_maps_landmarks_onto_reference():
    # Draw dots at landmark positions in a big image (scaled 3x + offset),
    # align, and check the dots land on the reference layout.
    src = REFERENCE_LANDMARKS * 3 + np.array([100, 50], dtype=np.float32)
    img = np.zeros((600, 600, 3), dtype=np.uint8)
    for x, y in src.astype(int):
        img[y - 3:y + 4, x - 3:x + 4] = 255
    out = align(img, src)
    assert out.shape == (112, 112, 3)
    for x, y in REFERENCE_LANDMARKS.round().astype(int):
        assert out[y, x].max() > 100


def test_similarity_matrix_recovers_known_transform():
    from face_pipeline import similarity_matrix
    angle, scale, t = 0.3, 1.7, np.array([12.0, -5.0])
    rot = scale * np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    src = REFERENCE_LANDMARKS.astype(np.float64)
    dst = src @ rot.T + t
    m = similarity_matrix(src, dst)
    assert np.allclose(m[:, :2], rot) and np.allclose(m[:, 2], t)


def test_preprocess_layout():
    aligned = np.zeros((112, 112, 3), dtype=np.uint8)
    aligned[..., 2] = 255  # pure red in BGR
    x = preprocess(aligned)
    assert x.shape == (1, 3, 112, 112) and x.dtype == np.float32
    assert np.allclose(x[0, 0], 1.0) and np.allclose(x[0, 2], -1.0)  # RGB order, (x-127.5)/127.5


def test_build_template_averages_and_flags_outliers():
    rng = np.random.default_rng(0)
    base = rng.normal(size=512)
    same = [base + rng.normal(scale=0.1, size=512) for _ in range(3)]
    tpl = build_template(same)
    assert tpl.used == 3 and np.isclose(np.linalg.norm(tpl.vector), 1.0) and tpl.min_agreement > 0.9
    assert build_template(same + [rng.normal(size=512)]).min_agreement < 0.5


def test_build_template_requires_input():
    with pytest.raises(ValueError):
        build_template([])


def test_largest_face_ignores_tiny_faces():
    lm = np.zeros((5, 2), dtype=np.float32)
    small = Face((0, 0, 30, 30), lm, 0.9)
    big = Face((0, 0, 120, 140), lm, 0.9)
    assert largest_face([small, big]) is big
    assert largest_face([small]) is None
