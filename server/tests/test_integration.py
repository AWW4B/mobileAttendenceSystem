"""End-to-end: portal + MEC together, with the phone simulated.

login (portal) -> device registration (MEC) -> enrollment (admin) -> grant
(portal) -> session (MEC) -> on-phone match -> signed submit (MEC) ->
receipt -> portal records present/absent -> teacher dashboard.
"""
from __future__ import annotations

import time

import numpy as np
from fastapi.testclient import TestClient

from common.keys import load_or_create_admin_token
from mec_server.app import create_app as create_mec
from mec_server.vault import vector_from_b64
from portal.app import create_app as create_portal

from conftest import PASSWORD, new_device, random_embedding

STUDENTS = [("22i-0001", "Ayesha Khan"), ("22i-0002", "Bilal Ahmed"), ("22i-0003", "Sana Malik")]


def test_end_to_end_attendance(settings):
    portal = TestClient(create_portal(settings))
    mec = TestClient(create_mec(settings))
    admin = {"X-Admin-Token": load_or_create_admin_token(settings)}

    # --- admin setup on the portal
    store = portal.app.state.store
    store.add_teacher("teacher1", "Dr. One", PASSWORD)
    store.add_section("EDGE-A", "Edge Computing A", "teacher1")
    for roll, name in STUDENTS:
        store.add_student(roll, name)
        store.enroll("EDGE-A", roll)

    # --- enrollment: what enrollment/enroll.py does with real photos
    faces = {roll: random_embedding(i) for i, (roll, _) in enumerate(STUDENTS)}
    for roll, emb in faces.items():
        pseudonym = portal.get(f"/api/admin/students/{roll}/pseudonym", headers=admin).json()["pseudonym"]
        assert mec.put(f"/admin/templates/{pseudonym}", headers=admin, json={"vector": emb.tolist()}).status_code == 200

    # --- phone: login + register
    access = portal.post("/api/login", json={"username": "teacher1", "password": PASSWORD}).json()["access_token"]
    phone = new_device()
    body, sig = phone.sign({"public_key_pem": phone.public_pem, "label": "phone", "timestamp": int(time.time())})
    phone.device_id = mec.post("/devices", content=body,
                               headers={"Authorization": f"Bearer {access}", "X-Signature": sig}).json()["device_id"]

    # --- phone: grant from portal, session from MEC
    grant = portal.post("/api/sections/EDGE-A/grant", headers={"Authorization": f"Bearer {access}"}).json()
    names = {r["pseudonym"]: r["name"] for r in grant["roster"]}
    body, sig = phone.sign({"device_id": phone.device_id, "timestamp": int(time.time())})
    session = mec.post("/sessions", content=body,
                       headers={"Authorization": f"Bearer {grant['grant_token']}", "X-Signature": sig}).json()
    assert len(session["templates"]) == 3

    # --- phone: class photo has Ayesha and Sana (with noise), plus a stranger
    rng = np.random.default_rng(42)
    live = [faces["22i-0001"] + rng.normal(scale=0.01, size=512),
            faces["22i-0003"] + rng.normal(scale=0.01, size=512),
            random_embedding(99)]
    t = session["transform"]
    perm, signs = np.array(t["permutation"]), np.array(t["signs"], dtype=np.float32)
    templates = {tp["pseudonym"]: vector_from_b64(tp["vector"]) for tp in session["templates"]}
    present = []
    for q in live:
        q = q / np.linalg.norm(q)
        tq = signs * q[perm]
        best = max(templates, key=lambda p: float(templates[p] @ tq))
        if float(templates[best] @ tq) >= 0.40:
            present.append(best)
    assert sorted(names[p] for p in present) == ["Ayesha Khan", "Sana Malik"]

    # --- phone: signed submit to MEC -> receipt -> portal
    body, sig = phone.sign({"device_id": phone.device_id, "session_id": session["session_id"],
                            "nonce": session["nonce"], "timestamp": int(time.time()), "present": present,
                            "metrics": {"faces": 3, "match_ms": 1}})
    r = mec.post(f"/sessions/{session['session_id']}/attendance", content=body, headers={"X-Signature": sig})
    assert r.status_code == 200, r.text
    r = portal.post("/api/attendance/receipts", json={"receipt": r.json()["receipt"]})
    assert r.json() == {"session_id": session["session_id"], "recorded": True, "present": 2, "absent": 1}

    # --- teacher dashboard shows it by name
    portal.post("/login", data={"username": "teacher1", "password": PASSWORD})
    page = portal.get("/sections/EDGE-A").text
    assert "Ayesha Khan" in page and "Bilal Ahmed" in page and "2/3" in page
    csv_rows = portal.get("/sections/EDGE-A/export.csv").text.splitlines()
    assert [row.split(",")[-1] for row in csv_rows[1:]] == ["present", "absent", "present"]

    # --- separation of data: no names in the MEC, no vectors in the portal
    mec_db = b"".join(p.read_bytes() for p in settings.mec_dir.glob("mec.db*"))
    portal_db = b"".join(p.read_bytes() for p in settings.portal_dir.glob("portal.db*"))
    for roll, name in STUDENTS:
        assert roll.encode() not in mec_db and name.encode() not in mec_db
        assert faces[roll].astype("<f4").tobytes()[:64] not in portal_db
