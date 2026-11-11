"""Download the two ONNX models into models/ and print their SHA-256.

  python fetch_models.py

Sources:
  * YuNet face detector (MIT), OpenCV Zoo
  * MobileFaceNet w600k_mbf.onnx from the InsightFace buffalo_sc pack
    (non-commercial research licence; fine for a university project)

Record the printed hashes in models/README.md so the phone and laptop are
provably using the same files.
"""
from __future__ import annotations

import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

MODELS = Path(__file__).resolve().parents[1] / "models"
YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
             "face_detection_yunet_2023mar.onnx")
BUFFALO_SC_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip"


def _get(url: str) -> bytes:
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def _save(name: str, data: bytes) -> None:
    path = MODELS / name
    path.write_bytes(data)
    print(f"  {name}: {len(data) / 1e6:.1f} MB  sha256={hashlib.sha256(data).hexdigest()}")


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    if not (MODELS / "face_detection_yunet_2023mar.onnx").exists():
        _save("face_detection_yunet_2023mar.onnx", _get(YUNET_URL))
    if not (MODELS / "w600k_mbf.onnx").exists():
        with zipfile.ZipFile(io.BytesIO(_get(BUFFALO_SC_URL))) as z:
            member = next(n for n in z.namelist() if n.endswith("w600k_mbf.onnx"))
            _save("w600k_mbf.onnx", z.read(member))
    print("Done.")


if __name__ == "__main__":
    main()
