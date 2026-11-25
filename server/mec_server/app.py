"""MEC / campus site-edge server.

Stores face templates (pseudonymised, transformed, encrypted), hands a
section's templates to an authorised teacher device for on-phone matching,
verifies the signed attendance result and returns a MEC-signed receipt that
the phone forwards to the online portal. The class photo arrives only as
optional appeal evidence and is stored encrypted for a limited time.

Run:  uvicorn mec_server.app:create_app --factory --host 0.0.0.0 --port 8000 \
          --ssl-keyfile data/tls/key.pem --ssl-certfile data/tls/cert.pem
(from the server/ folder, after the portal has run once so its public key exists)
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from common import tokens
from common.admin import require_admin
from common.keys import (
    load_or_create_admin_token,
    load_or_create_secret,
    mec_signing_key,
    portal_public_key,
)
from common.settings import EMBEDDING_DIM, MEC_ISSUER, PORTAL_ISSUER, Settings

from . import signing
from .store import MecStore
from .vault import InvalidVector, TemplateVault, vector_to_b64

PSEUDONYM_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
MAX_SIGNED_BODY = 64 * 1024
MAX_EVIDENCE_BYTES = 2 * 1024 * 1024
MAX_SUBMIT_BODY = 4 * 1024 * 1024   # evidence is base64 inside the signed body
MAX_EVIDENCE_FACES = 200
MAX_EVIDENCE_DIM = 4096
MAX_PHOTO_BYTES = 25 * 1024 * 1024
REPO_ROOT = Path(__file__).resolve().parents[2]


class TemplateIn(BaseModel):
    vector: list[float] = Field(min_length=EMBEDDING_DIM, max_length=EMBEDDING_DIM)


class PhotoIn(BaseModel):
    name: str = Field(max_length=512)
    jpeg_b64: str   # any format OpenCV decodes, despite the name


class EnrollIn(BaseModel):
    photos: list[PhotoIn] = Field(min_length=1)


class ThresholdsIn(BaseModel):
    accept: float
    review: float


class PseudonymsIn(BaseModel):
    pseudonyms: list[str] = Field(max_length=10000)


def _check_pseudonym(p: str) -> None:
    if not PSEUDONYM_RE.match(p):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "malformed pseudonym")


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float("inf")


def parse_evidence(ev, allowed: set[str]) -> tuple[bytes, int, int, list[dict]]:
    """Validate the optional evidence block. Raises ValueError with a reason."""
    if not isinstance(ev, dict):
        raise ValueError("evidence must be an object")
    b64 = ev.get("jpeg_b64")
    if not isinstance(b64, str) or len(b64) > MAX_EVIDENCE_BYTES * 4 // 3 + 8:
        raise ValueError("evidence jpeg missing or too large")
    try:
        jpeg = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("evidence jpeg is not valid base64")
    if len(jpeg) > MAX_EVIDENCE_BYTES or not jpeg.startswith(b"\xff\xd8\xff"):
        raise ValueError("evidence is not a JPEG within the size limit")
    w, h = ev.get("width"), ev.get("height")
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 < v <= MAX_EVIDENCE_DIM for v in (w, h)):
        raise ValueError("evidence width/height invalid")
    faces = ev.get("faces")
    if not isinstance(faces, list) or len(faces) > MAX_EVIDENCE_FACES:
        raise ValueError("evidence faces invalid")
    out = []
    for f in faces:
        box, p, score = (f.get("box"), f.get("pseudonym"), f.get("score")) if isinstance(f, dict) else (None,) * 3
        if not (isinstance(box, list) and len(box) == 4 and all(_num(v) for v in box)):
            raise ValueError("face box must be 4 numbers")
        if p is not None and p not in allowed:
            raise ValueError("evidence names a student not in this section")
        if score is not None and not _num(score):
            raise ValueError("face score must be a number or null")
        out.append({"box": box, "pseudonym": p, "score": score})
    return jpeg, w, h, out


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    auth_key = portal_public_key(settings)
    receipt_key = mec_signing_key(settings)
    admin_token = load_or_create_admin_token(settings)
    vault = TemplateVault(load_or_create_secret(settings.mec_dir / "master.key"), EMBEDDING_DIM)
    store = MecStore(settings.mec_dir / "mec.db")

    app = FastAPI(title="Attendance MEC server", version="0.2.0")
    app.state.store = store
    app.state.vault = vault

    def store_template(pseudonym: str, values) -> int:
        try:
            vec = vault.normalize(values)
        except InvalidVector as e:
            raise HTTPException(400, str(e))
        version = store.transform_version()
        nonce, ct = vault.seal(pseudonym, version, vault.transform(version).apply(vec))
        store.put_template(pseudonym, version, nonce, ct)
        return version

    def thresholds() -> dict:
        saved = store.thresholds()
        if saved:
            return saved
        contract = REPO_ROOT / "models" / "model_contract.json"
        m = json.loads(contract.read_text(encoding="utf-8"))["matching"]
        return {"accept": m["accept_threshold"], "review": m["review_band"][0]}

    face_lock = threading.Lock()   # the OpenCV detector is stateful
    engine: list = []

    def face_engine() -> tuple:
        """(face_pipeline, detector, embedder), loaded on first enrollment."""
        if not engine:
            try:
                if str(REPO_ROOT / "enrollment") not in sys.path:
                    sys.path.append(str(REPO_ROOT / "enrollment"))
                import face_pipeline as fp
                models = settings.models_dir or fp.MODELS_DIR
                engine.extend((fp, fp.YuNetDetector(models / "face_detection_yunet_2023mar.onnx"),
                               fp.OnnxEmbedder(models / fp.CONTRACT["embedder"]["file"])))
            except (ImportError, FileNotFoundError) as e:
                raise HTTPException(503, f"photo enrollment is not available: {e}")
        return tuple(engine)

    def reject(actor: str, action: str, code: int, msg: str, **detail) -> HTTPException:
        store.audit(actor, f"rejected:{action}", reason=msg, **detail)
        return HTTPException(code, msg)

    async def signed_payload(request: Request, x_signature: str | None, action: str,
                             limit: int = MAX_SIGNED_BODY) -> tuple[dict, Any]:
        """Read the raw body, verify the device signature and timestamp."""
        raw = await request.body()
        if len(raw) > limit:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "body too large")
        try:
            payload = json.loads(raw)
            device_id = str(payload["device_id"])
            ts = int(payload["timestamp"])
        except (ValueError, KeyError, TypeError):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "body must be JSON with device_id and timestamp")
        device = store.get_device(device_id)
        if device is None or device["revoked"]:
            raise reject(device_id, action, 401, "unknown or revoked device")
        try:
            signing.verify(device["public_key_pem"], raw, x_signature)
        except signing.BadSignature as e:
            raise reject(device_id, action, 401, str(e))
        if abs(time.time() - ts) > settings.request_clock_skew_s:
            raise reject(device_id, action, 401, "timestamp outside allowed window")
        return payload, device

    # ---- public ----------------------------------------------------------
    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "mec", "embedding_dim": EMBEDDING_DIM}

    @app.post("/devices")
    async def register_device(request: Request, authorization: str | None = Header(default=None),
                              x_signature: str | None = Header(default=None)) -> dict:
        """Register a teacher's phone key. Body {public_key_pem, label?, timestamp},
        signed with the key being registered (proof of possession)."""
        claims = tokens.verify(auth_key, tokens.bearer(authorization), issuer=PORTAL_ISSUER,
                               typ="access", aud="mec")
        raw = await request.body()
        try:
            payload = json.loads(raw)
            pem = str(payload["public_key_pem"])
            ts = int(payload["timestamp"])
            label = payload.get("label")
        except (ValueError, KeyError, TypeError):
            raise HTTPException(400, "body must be JSON with public_key_pem and timestamp")
        try:
            signing.verify(pem, raw, x_signature)
        except signing.BadSignature as e:
            raise reject(f"teacher:{claims['sub']}", "register_device", 400, str(e))
        if abs(time.time() - ts) > settings.request_clock_skew_s:
            raise HTTPException(401, "timestamp outside allowed window")
        device_id = uuid.uuid4().hex
        store.add_device(device_id, claims["sub"], pem, str(label)[:64] if label else None)
        store.audit(f"teacher:{claims['sub']}", "device_registered", device_id=device_id)
        return {"device_id": device_id}

    @app.delete("/devices/{device_id}")
    def revoke_device(device_id: str, authorization: str | None = Header(default=None)) -> dict:
        claims = tokens.verify(auth_key, tokens.bearer(authorization), issuer=PORTAL_ISSUER,
                               typ="access", aud="mec")
        if not store.revoke_device(device_id, claims["sub"]):
            raise HTTPException(404, "device not found")
        store.audit(f"teacher:{claims['sub']}", "device_revoked", device_id=device_id)
        return {"revoked": device_id}

    @app.post("/sessions")
    async def open_session(request: Request, authorization: str | None = Header(default=None),
                           x_signature: str | None = Header(default=None)) -> dict:
        """Open a capture session. Needs a one-time grant from the auth service
        plus a request signed by the teacher's registered device. Returns the
        section's templates and transform for on-phone matching."""
        grant = tokens.verify(auth_key, tokens.bearer(authorization), issuer=PORTAL_ISSUER,
                              typ="grant", aud="mec")
        payload, device = await signed_payload(request, x_signature, "open_session")
        if device["teacher_sub"] != grant["sub"]:
            raise reject(device["device_id"], "open_session", 403, "device does not belong to this teacher")
        if not store.consume_grant(grant["jti"], int(grant["exp"])):
            raise reject(device["device_id"], "open_session", 409, "grant already used")

        allowed = [p for p in grant.get("psn", []) if PSEUDONYM_RE.match(p)]
        version = store.transform_version()
        templates, not_enrolled = [], set(allowed)
        for row in store.get_templates(allowed):
            if row["transform_version"] != version:
                continue  # mid-rotation; treat as not enrolled
            vec = vault.open(row["pseudonym"], version, row["nonce"], row["ciphertext"])
            templates.append({"pseudonym": row["pseudonym"], "vector": vector_to_b64(vec)})
            not_enrolled.discard(row["pseudonym"])

        session_id = uuid.uuid4().hex
        nonce = secrets.token_urlsafe(24)
        expires_at = int(time.time()) + settings.session_ttl_s
        store.create_session(session_id=session_id, teacher_sub=grant["sub"], section_id=grant["sec"],
                             device_id=device["device_id"], nonce=nonce, allowed=allowed,
                             expires_at=expires_at)
        store.audit(device["device_id"], "session_opened", session_id=session_id,
                    section_id=grant["sec"], templates_released=len(templates))
        return {
            "session_id": session_id,
            "nonce": nonce,
            "expires_at": expires_at,
            "embedding_dim": EMBEDDING_DIM,
            "transform": vault.transform(version).to_wire(),
            "templates": templates,
            "not_enrolled": sorted(not_enrolled),
            "thresholds": thresholds(),
        }

    @app.post("/sessions/{session_id}/attendance")
    async def submit_attendance(session_id: str, request: Request,
                                x_signature: str | None = Header(default=None)) -> dict:
        """Body: {device_id, session_id, nonce, timestamp, present: [pseudonym...], metrics?: {...},
        evidence?: {jpeg_b64, width, height, faces: [{box, pseudonym, score}]}}"""
        payload, device = await signed_payload(request, x_signature, "submit_attendance", MAX_SUBMIT_BODY)
        dev = device["device_id"]
        session = store.get_session(session_id)
        if session is None or payload.get("session_id") != session_id:
            raise reject(dev, "submit_attendance", 404, "session not found", session_id=session_id)
        if session["device_id"] != dev:
            raise reject(dev, "submit_attendance", 403, "session belongs to another device")
        if not hmac.compare_digest(str(payload.get("nonce", "")), session["nonce"]):
            raise reject(dev, "submit_attendance", 401, "bad nonce", session_id=session_id)
        if time.time() > session["expires_at"]:
            raise reject(dev, "submit_attendance", 410, "session expired", session_id=session_id)

        present = payload.get("present")
        if not isinstance(present, list) or not all(isinstance(p, str) for p in present):
            raise HTTPException(400, "present must be a list of pseudonyms")
        if len(set(present)) != len(present):
            raise HTTPException(400, "duplicate pseudonyms in present")
        allowed = set(json.loads(session["allowed"]))
        unknown = [p for p in present if p not in allowed]
        if unknown:
            raise reject(dev, "submit_attendance", 400, "present contains students not in this section",
                         session_id=session_id, count=len(unknown))

        metrics = payload.get("metrics")
        if metrics is not None:
            if not isinstance(metrics, dict) or len(json.dumps(metrics)) > settings.max_metrics_bytes:
                raise HTTPException(400, "metrics must be a small JSON object")

        evidence, extra = None, {}
        if payload.get("evidence") is not None:
            try:
                jpeg, w, h, faces = parse_evidence(payload["evidence"], allowed)
            except ValueError as e:
                raise reject(dev, "submit_attendance", 400, str(e), session_id=session_id)
            sha = hashlib.sha256(jpeg).hexdigest()
            nonce_e, ct = vault.seal_evidence(session_id, jpeg)
            evidence = (sha, w, h, json.dumps(faces), nonce_e, ct, int(time.time()) + settings.evidence_retention_s)
            extra["evidence_sha256"] = sha

        # Receipt for the online portal: MEC-signed, pseudonyms only. The phone
        # forwards it (now, or later if offline); the portal maps pseudonyms to
        # names and marks everyone else in the roster absent.
        receipt, _ = tokens.issue(
            receipt_key, issuer=MEC_ISSUER, typ="receipt", sub=session["teacher_sub"], aud=["portal"],
            ttl_s=settings.receipt_ttl_s,
            extra={"sid": session_id, "sec": session["section_id"], "psn": sorted(present),
                   "tak": int(time.time()), **extra},
        )
        if not store.submit(session_id, present, metrics, receipt, evidence):
            raise reject(dev, "submit_attendance", 409, "attendance already submitted", session_id=session_id)
        store.audit(dev, "attendance_submitted", session_id=session_id, present=len(present),
                    section_size=len(allowed), evidence=evidence is not None)
        return {"session_id": session_id, "recorded": len(present), "receipt": receipt}

    @app.get("/sessions/{session_id}/attendance")
    def get_attendance(session_id: str, authorization: str | None = Header(default=None)) -> dict:
        claims = tokens.verify(auth_key, tokens.bearer(authorization), issuer=PORTAL_ISSUER,
                               typ="access", aud="mec")
        session = store.get_session(session_id)
        if session is None or session["teacher_sub"] != claims["sub"]:
            raise HTTPException(404, "session not found")
        return {
            "session_id": session_id,
            "section_id": session["section_id"],
            "submitted_at": session["submitted_at"],
            "present": store.present_for(session_id),
            "receipt": session["receipt"],  # re-fetch if the phone lost it before forwarding
        }

    @app.get("/sessions/{session_id}/evidence")
    def get_evidence(session_id: str, authorization: str | None = Header(default=None)) -> dict:
        claims = tokens.verify(auth_key, tokens.bearer(authorization), issuer=PORTAL_ISSUER,
                               typ="access", aud="mec")
        session = store.get_session(session_id)
        row = store.get_evidence(session_id) if session and session["teacher_sub"] == claims["sub"] else None
        if row is None:
            raise HTTPException(404, "no evidence for this session")
        store.audit(f"teacher:{claims['sub']}", "evidence_read", session_id=session_id)
        jpeg = vault.open_evidence(session_id, row["nonce"], row["ciphertext"])
        return {"sha256": row["sha256"], "width": row["width"], "height": row["height"],
                "faces": json.loads(row["faces_json"]), "jpeg_b64": base64.b64encode(jpeg).decode(),
                "expires_at": row["expires_at"]}

    # ---- admin (enrollment tooling only) ------------------------------
    @app.put("/admin/templates/{pseudonym}")
    def put_template(pseudonym: str, body: TemplateIn, x_admin_token: str | None = Header(default=None)) -> dict:
        require_admin(admin_token, x_admin_token)
        _check_pseudonym(pseudonym)
        version = store_template(pseudonym, body.vector)
        store.audit("admin", "template_put", pseudonym=pseudonym)
        return {"pseudonym": pseudonym, "transform_version": version}

    @app.post("/admin/enroll/{pseudonym}")
    def enroll_photos(pseudonym: str, body: EnrollIn, x_admin_token: str | None = Header(default=None)) -> dict:
        """Build a template from photos, in memory. Photos are never written; file names are never logged."""
        require_admin(admin_token, x_admin_token)
        _check_pseudonym(pseudonym)
        embeddings, problems = [], []
        with face_lock:
            fp, detector, embedder = face_engine()
            for photo in body.photos:
                embedding, problem = None, "larger than 25 MB"
                if len(photo.jpeg_b64) <= MAX_PHOTO_BYTES * 4 // 3 + 8:
                    try:
                        data = base64.b64decode(photo.jpeg_b64, validate=True)
                    except (binascii.Error, ValueError):
                        problem = "not valid base64"
                    else:
                        if len(data) <= MAX_PHOTO_BYTES:
                            embedding, problem = fp.embed_photo(data, detector, embedder)
                if problem:
                    problems.append(f"{photo.name}: {problem}")
                if embedding is not None:
                    embeddings.append(embedding)
        if not embeddings:
            store.audit("admin", "rejected:enroll", pseudonym=pseudonym, reason="no usable face")
            raise HTTPException(422, {"message": "no usable face in any photo", "problems": problems})
        tpl = fp.build_template(embeddings)
        version = store_template(pseudonym, tpl.vector)
        store.audit("admin", "template_enrolled", pseudonym=pseudonym, photos_used=tpl.used)
        return {"pseudonym": pseudonym, "transform_version": version, "used": tpl.used,
                "min_agreement": tpl.min_agreement, "problems": problems}

    @app.post("/admin/templates/status")
    def template_status(body: PseudonymsIn, x_admin_token: str | None = Header(default=None)) -> dict:
        """{pseudonym: updated_at} for those that have a template. No vectors leave."""
        require_admin(admin_token, x_admin_token)
        return {r["pseudonym"]: r["updated_at"] for r in store.get_templates(body.pseudonyms)}

    @app.get("/admin/devices")
    def list_devices(teacher: str, x_admin_token: str | None = Header(default=None)) -> list[dict]:
        require_admin(admin_token, x_admin_token)
        return store.devices_for(teacher)

    @app.delete("/admin/devices/{device_id}")
    def admin_revoke_device(device_id: str, teacher: str,
                            x_admin_token: str | None = Header(default=None)) -> dict:
        require_admin(admin_token, x_admin_token)
        if not store.revoke_device(device_id, teacher):
            raise HTTPException(404, "device not found")
        store.audit(f"teacher:{teacher}", "device_revoked", device_id=device_id)
        return {"revoked": device_id}

    @app.get("/admin/sessions")
    def list_sessions(teacher: str, x_admin_token: str | None = Header(default=None)) -> list[dict]:
        require_admin(admin_token, x_admin_token)
        return store.submitted_sessions(teacher)

    @app.get("/admin/settings")
    def get_settings(x_admin_token: str | None = Header(default=None)) -> dict:
        require_admin(admin_token, x_admin_token)
        return thresholds()

    @app.put("/admin/settings")
    def put_settings(body: ThresholdsIn, x_admin_token: str | None = Header(default=None)) -> dict:
        require_admin(admin_token, x_admin_token)
        if not 0 < body.review <= body.accept < 1:   # also false for NaN
            raise HTTPException(400, "thresholds must satisfy 0 < review <= accept < 1")
        store.set_thresholds(body.accept, body.review)
        store.audit("admin", "thresholds_changed", accept=body.accept, review=body.review)
        return thresholds()

    @app.delete("/admin/templates/{pseudonym}")
    def delete_template(pseudonym: str, x_admin_token: str | None = Header(default=None)) -> dict:
        require_admin(admin_token, x_admin_token)
        _check_pseudonym(pseudonym)
        if not store.delete_template(pseudonym):
            raise HTTPException(404, "no template for that pseudonym")
        store.audit("admin", "template_deleted", pseudonym=pseudonym)
        return {"deleted": pseudonym}

    @app.post("/admin/transform/rotate")
    def rotate_transform(x_admin_token: str | None = Header(default=None)) -> dict:
        """Revoke all current templates by re-issuing them under a new transform."""
        require_admin(admin_token, x_admin_token)
        old_v = store.transform_version()
        new_v = old_v + 1
        new_t = vault.transform(new_v)
        rows = []
        for r in store.all_templates():
            stored_t = vault.transform(r["transform_version"])
            raw = stored_t.invert(vault.open(r["pseudonym"], r["transform_version"], r["nonce"], r["ciphertext"]))
            nonce, ct = vault.seal(r["pseudonym"], new_v, new_t.apply(raw))
            rows.append((r["pseudonym"], nonce, ct))
        store.rotate(new_v, rows)
        store.audit("admin", "transform_rotated", from_version=old_v, to_version=new_v, templates=len(rows))
        return {"transform_version": new_v, "templates_reissued": len(rows)}

    @app.get("/admin/audit")
    def audit(limit: int = 50, x_admin_token: str | None = Header(default=None)) -> list[dict]:
        require_admin(admin_token, x_admin_token)
        return store.audit_tail(max(1, min(limit, 500)))

    return app
