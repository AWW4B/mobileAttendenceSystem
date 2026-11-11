"""Face pipeline shared in spirit with the Android app.

detect (YuNet) -> align (5-point similarity to 112x112) -> embed (MobileFaceNet ONNX)
-> L2-normalise. See models/model_contract.json; the phone must do the same.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_ROOT / "models"
CONTRACT = json.loads((MODELS_DIR / "model_contract.json").read_text(encoding="utf-8"))

REFERENCE_LANDMARKS = np.array(CONTRACT["alignment"]["reference_landmarks"], dtype=np.float32)
ALIGNED_SIZE = tuple(CONTRACT["alignment"]["output_size"])
EMBEDDING_DIM = CONTRACT["embedder"]["output_dim"]


@dataclass(frozen=True)
class Face:
    box: tuple[float, float, float, float]   # x, y, w, h
    landmarks: np.ndarray                     # (5, 2) in contract order
    score: float

    @property
    def area(self) -> float:
        return self.box[2] * self.box[3]


class Detector(Protocol):
    def detect(self, image_bgr: np.ndarray) -> list[Face]: ...


class Embedder(Protocol):
    def embed(self, aligned_bgr: np.ndarray) -> np.ndarray: ...


class YuNetDetector:
    """OpenCV YuNet. Output rows: x, y, w, h, then 5 landmarks
    (subject's right eye, left eye, nose tip, right mouth corner, left mouth
    corner), then score. The subject's right eye is on the image left, which
    is exactly the contract order."""

    def __init__(self, model_path: Path, min_score: float = CONTRACT["detector"]["min_score"]):
        if not model_path.exists():
            raise FileNotFoundError(f"{model_path} missing; run enrollment/fetch_models.py")
        self._det = cv2.FaceDetectorYN.create(str(model_path), "", (320, 320), min_score, 0.3, 5000)

    def detect(self, image_bgr: np.ndarray) -> list[Face]:
        h, w = image_bgr.shape[:2]
        self._det.setInputSize((w, h))
        _, rows = self._det.detect(image_bgr)
        if rows is None:
            return []
        return [
            Face(box=tuple(float(v) for v in r[0:4]),
                 landmarks=np.asarray(r[4:14], dtype=np.float32).reshape(5, 2),
                 score=float(r[14]))
            for r in rows
        ]


def similarity_matrix(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Closed-form least-squares similarity (rotation + uniform scale +
    translation, no reflection) mapping src points onto dst points.
    The Android app implements the identical formula (Aligner.kt)."""
    src = np.asarray(src, dtype=np.float64)
    dst = np.asarray(dst, dtype=np.float64)
    ms, md = src.mean(axis=0), dst.mean(axis=0)
    sc, dc = src - ms, dst - md
    denom = float((sc ** 2).sum())
    if denom < 1e-9:
        raise ValueError("degenerate landmarks")
    a = float((sc[:, 0] * dc[:, 0] + sc[:, 1] * dc[:, 1]).sum()) / denom
    b = float((sc[:, 0] * dc[:, 1] - sc[:, 1] * dc[:, 0]).sum()) / denom
    tx = md[0] - (a * ms[0] - b * ms[1])
    ty = md[1] - (b * ms[0] + a * ms[1])
    return np.array([[a, -b, tx], [b, a, ty]], dtype=np.float64)


def align(image_bgr: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
    """Warp a face to the 112x112 ArcFace layout using a similarity transform."""
    matrix = similarity_matrix(landmarks, REFERENCE_LANDMARKS)
    return cv2.warpAffine(image_bgr, matrix, ALIGNED_SIZE, flags=cv2.INTER_LINEAR, borderValue=0.0)


def preprocess(aligned_bgr: np.ndarray) -> np.ndarray:
    """BGR uint8 112x112 -> float32 [1,3,112,112] RGB, (x-127.5)/127.5."""
    rgb = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    rgb = (rgb - 127.5) / 127.5
    return np.transpose(rgb, (2, 0, 1))[None, ...]


def l2_normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    if n < 1e-6:
        raise ValueError("embedding has zero norm")
    return v / n


class OnnxEmbedder:
    def __init__(self, model_path: Path):
        import onnxruntime as ort

        if not model_path.exists():
            raise FileNotFoundError(f"{model_path} missing; run enrollment/fetch_models.py")
        self._sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self._input = self._sess.get_inputs()[0].name

    def embed(self, aligned_bgr: np.ndarray) -> np.ndarray:
        out = self._sess.run(None, {self._input: preprocess(aligned_bgr)})[0]
        vec = l2_normalize(out)
        if vec.shape[0] != EMBEDDING_DIM:
            raise ValueError(f"model produced {vec.shape[0]} dims, contract says {EMBEDDING_DIM}")
        return vec


def largest_face(faces: list[Face], min_px: int = CONTRACT["detector"]["min_face_px"]) -> Face | None:
    ok = [f for f in faces if min(f.box[2], f.box[3]) >= min_px]
    return max(ok, key=lambda f: f.area) if ok else None


@dataclass
class Template:
    vector: np.ndarray
    used: int
    min_agreement: float  # lowest cosine between a single photo and the mean


def build_template(embeddings: list[np.ndarray]) -> Template:
    """Average per-photo embeddings into one template and report consistency.
    A low min_agreement usually means one photo is of the wrong person or
    very poor quality."""
    if not embeddings:
        raise ValueError("no usable embeddings")
    stack = np.stack([l2_normalize(e) for e in embeddings])
    mean = l2_normalize(stack.mean(axis=0))
    return Template(vector=mean, used=len(embeddings), min_agreement=float((stack @ mean).min()))
