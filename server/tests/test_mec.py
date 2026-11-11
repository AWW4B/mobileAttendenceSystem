"""MEC tests. Portal tokens (access, grant) are minted directly with the
portal key, so the MEC is tested without the portal component."""
from __future__ import annotations

import secrets
import time
from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from common import tokens
from common.keys import load_or_create_admin_token, mec_signing_key, portal_signing_key
from common.settings import MEC_ISSUER, PORTAL_ISSUER, Settings
from mec_server.app import create_app
from mec_server.vault import vector_from_b64

from conftest import Device, new_device, random_embedding


class Mec:
    def __init__(self, settings: Settings, mec_settings: Settings | None = None):
        self.settings = settings
        self.portal_key = portal_signing_key(settings)
        self.client = TestClient(create_app(mec_settings or settings))
        self.admin = {"X-Admin-Token": load_or_create_admin_token(settings)}
        # section EDGE-A: three students; EDGE-B: one other
        self.students = {f"s{i}": {"pseudonym": secrets.token_urlsafe(16), "embedding": random_embedding(i)}
                         for i in range(3)}
        self.outsider = secrets.token_urlsafe(16)

    def access(self, teacher="1") -> str:
        return tokens.issue(self.portal_key, issuer=PORTAL_ISSUER, typ="access", sub=teacher,
                            aud=["portal", "mec"], ttl_s=600)[0]

    def grant(self, teacher="1", section="EDGE-A", psn=None) -> str:
        psn = psn if psn is not None else [s["pseudonym"] for s in self.students.values()]
        return tokens.issue(self.portal_key, issuer=PORTAL_ISSUER, typ="grant", sub=teacher, aud=["mec"],
                            ttl_s=600, extra={"sec": section, "psn": psn})[0]

    def register(self, device: Device, teacher="1") -> Device:
        body, sig = device.sign({"public_key_pem": device.public_pem, "label": "phone",
                                 "timestamp": int(time.time())})
        r = self.client.post("/devices", content=body,
                             headers={"Authorization": f"Bearer {self.access(teacher)}", "X-Signature": sig})
        assert r.status_code == 200, r.text
        device.device_id = r.json()["device_id"]
        return device

    def enroll(self, *keys):
        for k in keys:
            s = self.students[k]
            r = self.client.put(f"/admin/templates/{s['pseudonym']}", headers=self.admin,
                                json={"vector": s["embedding"].tolist()})
            assert r.status_code == 200, r.text

    def open(self, grant: str, device: Device, ts: int | None = None):
        body, sig = device.sign({"device_id": device.device_id, "timestamp": ts or int(time.time())})
        return self.client.post("/sessions", content=body,
                                headers={"Authorization": f"Bearer {grant}", "X-Signature": sig})

    def submit(self, session: dict, device: Device, present: list[str], **overrides):
        payload = {"device_id": device.device_id, "session_id": session["session_id"],
                   "nonce": session["nonce"], "timestamp": int(time.time()), "present": present}
        payload.update(overrides)
        body, sig = device.sign(payload)
        return self.client.post(f"/sessions/{session['session_id']}/attendance", content=body,
                                headers={"X-Signature": sig})

    def p(self, key) -> str:
        return self.students[key]["pseudonym"]


@pytest.fixture
def mec(settings) -> Mec:
    return Mec(settings)


def phone_match(session: dict, embedding: np.ndarray) -> tuple[str, float]:
    """What the phone does: transform the live embedding, best cosine."""
    t = session["transform"]
    q = np.array(t["signs"], dtype=np.float32) * embedding[np.array(t["permutation"])]
    scores = {tpl["pseudonym"]: float(vector_from_b64(tpl["vector"]) @ q) for tpl in session["templates"]}
    best = max(scores, key=scores.get)
    return best, scores[best]


def test_session_flow_and_receipt(mec):
    device = mec.register(new_device())
    mec.enroll("s0", "s1")  # s2 not enrolled yet
    r = mec.open(mec.grant(), device)
    assert r.status_code == 200, r.text
    session = r.json()
    assert len(session["templates"]) == 2 and session["not_enrolled"] == [mec.p("s2")]

    stored = {t["pseudonym"]: vector_from_b64(t["vector"]) for t in session["templates"]}
    assert float(stored[mec.p("s0")] @ mec.students["s0"]["embedding"]) < 0.5  # transformed
    best, score = phone_match(session, mec.students["s0"]["embedding"])
    assert best == mec.p("s0") and score > 0.999

    r = mec.submit(session, device, [mec.p("s0")], metrics={"match_ms": 12.5, "faces": 1})
    assert r.status_code == 200, r.text
    claims = tokens.verify(mec_signing_key(mec.settings).public_key(), r.json()["receipt"],
                           issuer=MEC_ISSUER, typ="receipt", aud="portal")
    assert claims["sid"] == session["session_id"] and claims["sec"] == "EDGE-A"
    assert claims["psn"] == [mec.p("s0")] and claims["sub"] == "1"

    r = mec.client.get(f"/sessions/{session['session_id']}/attendance",
                       headers={"Authorization": f"Bearer {mec.access()}"})
    assert r.json()["present"] == [mec.p("s0")] and r.json()["receipt"]


def test_grant_cannot_be_replayed(mec):
    device = mec.register(new_device())
    grant = mec.grant()
    assert mec.open(grant, device).status_code == 200
    assert mec.open(grant, device).status_code == 409


def test_attendance_cannot_be_submitted_twice(mec):
    device = mec.register(new_device())
    session = mec.open(mec.grant(), device).json()
    assert mec.submit(session, device, []).status_code == 200
    assert mec.submit(session, device, []).status_code == 409


def test_tampered_body_is_rejected(mec):
    device = mec.register(new_device())
    session = mec.open(mec.grant(), device).json()
    _, sig = device.sign({"device_id": device.device_id, "session_id": session["session_id"],
                          "nonce": session["nonce"], "timestamp": int(time.time()), "present": []})
    forged, _ = new_device().sign({"device_id": device.device_id, "session_id": session["session_id"],
                                   "nonce": session["nonce"], "timestamp": int(time.time()),
                                   "present": [mec.p("s1")]})
    r = mec.client.post(f"/sessions/{session['session_id']}/attendance", content=forged,
                        headers={"X-Signature": sig})
    assert r.status_code == 401


def test_wrong_device_key_is_rejected(mec):
    device = mec.register(new_device())
    impostor = new_device()
    impostor.device_id = device.device_id
    assert mec.open(mec.grant(), impostor).status_code == 401


def test_bad_nonce_is_rejected(mec):
    device = mec.register(new_device())
    session = mec.open(mec.grant(), device).json()
    assert mec.submit(session, device, [], nonce="guess").status_code == 401


def test_stale_timestamp_is_rejected(mec):
    device = mec.register(new_device())
    assert mec.open(mec.grant(), device, ts=int(time.time()) - 3600).status_code == 401


def test_cannot_mark_students_outside_the_grant(mec):
    device = mec.register(new_device())
    session = mec.open(mec.grant(), device).json()
    assert mec.submit(session, device, [mec.outsider]).status_code == 400


def test_other_teachers_device_cannot_use_grant(mec):
    other = mec.register(new_device(), teacher="2")
    assert mec.open(mec.grant(teacher="1"), other).status_code == 403


def test_teacher_cannot_read_other_teachers_session(mec):
    device = mec.register(new_device())
    session = mec.open(mec.grant(), device).json()
    r = mec.client.get(f"/sessions/{session['session_id']}/attendance",
                       headers={"Authorization": f"Bearer {mec.access('2')}"})
    assert r.status_code == 404


def test_revoked_device_is_rejected(mec):
    device = mec.register(new_device())
    r = mec.client.delete(f"/devices/{device.device_id}", headers={"Authorization": f"Bearer {mec.access()}"})
    assert r.status_code == 200
    assert mec.open(mec.grant(), device).status_code == 401


def test_expired_session_is_rejected(settings):
    mec = Mec(settings, replace(settings, session_ttl_s=-1))
    device = mec.register(new_device())
    session = mec.open(mec.grant(), device).json()
    assert mec.submit(session, device, []).status_code == 410


def test_access_token_is_not_a_grant(mec):
    device = mec.register(new_device())
    assert mec.open(mec.access(), device).status_code == 401


def test_token_from_wrong_issuer_rejected(mec):
    device = mec.register(new_device())
    fake = tokens.issue(mec_signing_key(mec.settings), issuer=PORTAL_ISSUER, typ="grant", sub="1", aud=["mec"],
                        ttl_s=600, extra={"sec": "EDGE-A", "psn": [mec.p("s0")]})[0]
    assert mec.open(fake, device).status_code == 401


def test_admin_endpoints_need_token(mec):
    assert mec.client.put(f"/admin/templates/{mec.p('s0')}", json={"vector": [0.1] * 512}).status_code == 403
    assert mec.client.post("/admin/transform/rotate").status_code == 403
    assert mec.client.get("/admin/audit").status_code == 403


def test_rotation_revokes_old_templates_but_matching_still_works(mec):
    device = mec.register(new_device())
    mec.enroll("s0", "s1", "s2")
    before = mec.open(mec.grant(), device).json()
    r = mec.client.post("/admin/transform/rotate", headers=mec.admin)
    assert r.json() == {"transform_version": 2, "templates_reissued": 3}
    after = mec.open(mec.grant(), device).json()

    assert after["transform"]["version"] == 2
    pick = lambda s: next(vector_from_b64(t["vector"]) for t in s["templates"] if t["pseudonym"] == mec.p("s0"))
    assert abs(float(pick(before) @ pick(after))) < 0.5   # leaked v1 template useless under v2
    best, score = phone_match(after, mec.students["s0"]["embedding"])
    assert best == mec.p("s0") and score > 0.999           # accuracy unchanged


def test_mec_database_contains_no_plain_embeddings(mec):
    device = mec.register(new_device())
    mec.enroll("s0", "s1", "s2")
    session = mec.open(mec.grant(), device).json()
    mec.submit(session, device, [mec.p("s0")])
    db_bytes = b"".join(p.read_bytes() for p in mec.settings.mec_dir.glob("mec.db*"))
    for s in mec.students.values():
        assert s["embedding"].astype("<f4").tobytes()[:64] not in db_bytes


def test_deleting_template_removes_student_from_sessions(mec):
    device = mec.register(new_device())
    mec.enroll("s0")
    assert mec.client.delete(f"/admin/templates/{mec.p('s0')}", headers=mec.admin).status_code == 200
    assert mec.open(mec.grant(), device).json()["templates"] == []


def test_audit_log_records_rejections(mec):
    device = mec.register(new_device())
    mec.open(mec.grant(), device, ts=1)
    actions = [e["action"] for e in mec.client.get("/admin/audit", headers=mec.admin).json()]
    assert "rejected:open_session" in actions and "device_registered" in actions
