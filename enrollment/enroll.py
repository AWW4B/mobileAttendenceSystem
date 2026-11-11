"""Enroll students' faces into the MEC from photos you provide.

Photo layout (folder per roll number, 1-5 clear, front-facing photos each):

    photos/
      22i-0018/  a.jpg  b.jpg
      22i-0042/  front.png

The student must already exist in the portal
(`python -m portal.cli add-student` or `import-csv`).

Only the 512-number embedding is sent to the MEC, over HTTPS, keyed by
the student's pseudonym. Photos are not uploaded or copied anywhere.
Delete the photo folder once enrollment succeeds.

  python enroll.py --photos photos --portal https://192.168.1.20:8001 \
                   --mec https://192.168.1.20:8000 --ca ../server/data/tls/cert.pem
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import httpx

from face_pipeline import (
    MODELS_DIR,
    OnnxEmbedder,
    YuNetDetector,
    align,
    build_template,
    largest_face,
)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_ADMIN_TOKEN = Path(__file__).resolve().parents[1] / "server" / "data" / "shared" / "admin_token.txt"
LOW_AGREEMENT = 0.5


def embed_student(folder: Path, detector, embedder) -> tuple[list, list[str]]:
    embeddings, problems = [], []
    for img_path in sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT):
        image = cv2.imread(str(img_path))
        if image is None:
            problems.append(f"{img_path.name}: unreadable")
            continue
        faces = detector.detect(image)
        face = largest_face(faces)
        if face is None:
            problems.append(f"{img_path.name}: no usable face")
            continue
        if len(faces) > 1:
            problems.append(f"{img_path.name}: {len(faces)} faces, used the largest")
        embeddings.append(embedder.embed(align(image, face.landmarks)))
        del image  # keep pixel data short-lived
    return embeddings, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photos", type=Path, required=True)
    ap.add_argument("--portal", required=True, help="portal base URL")
    ap.add_argument("--mec", required=True, help="MEC server base URL")
    ap.add_argument("--ca", type=Path, help="self-signed cert to trust (server/data/tls/cert.pem)")
    ap.add_argument("--admin-token-file", type=Path, default=DEFAULT_ADMIN_TOKEN)
    ap.add_argument("--detector", type=Path, default=MODELS_DIR / "face_detection_yunet_2023mar.onnx")
    ap.add_argument("--embedder", type=Path, default=MODELS_DIR / "w600k_mbf.onnx")
    ap.add_argument("--dry-run", action="store_true", help="compute templates, upload nothing")
    args = ap.parse_args(argv)

    detector = YuNetDetector(args.detector)
    embedder = OnnxEmbedder(args.embedder)
    token = args.admin_token_file.read_text(encoding="utf-8").strip()
    verify: bool | str = str(args.ca) if args.ca else True
    headers = {"X-Admin-Token": token}

    students = sorted(d for d in args.photos.iterdir() if d.is_dir())
    if not students:
        print(f"No student folders in {args.photos}", file=sys.stderr)
        return 1

    ok = failed = 0
    with httpx.Client(verify=verify, timeout=15, headers=headers) as http:
        for folder in students:
            roll = folder.name
            embeddings, problems = embed_student(folder, detector, embedder)
            for p in problems:
                print(f"  [{roll}] {p}")
            if not embeddings:
                print(f"FAIL {roll}: no usable photos")
                failed += 1
                continue
            tpl = build_template(embeddings)
            warn = f"  (low agreement {tpl.min_agreement:.2f}: check photos)" if tpl.min_agreement < LOW_AGREEMENT else ""
            if args.dry_run:
                print(f"DRY  {roll}: {tpl.used} photo(s){warn}")
                ok += 1
                continue
            r = http.get(f"{args.portal}/api/admin/students/{roll}/pseudonym")
            if r.status_code == 404:
                print(f"FAIL {roll}: not registered in the portal")
                failed += 1
                continue
            r.raise_for_status()
            pseudonym = r.json()["pseudonym"]
            r = http.put(f"{args.mec}/admin/templates/{pseudonym}", json={"vector": tpl.vector.tolist()})
            r.raise_for_status()
            print(f"OK   {roll}: {tpl.used} photo(s){warn}")
            ok += 1

    print(f"\nEnrolled {ok}, failed {failed}.")
    if ok and not args.dry_run:
        print("Templates are stored on the MEC. You can now delete the photo folder.")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
