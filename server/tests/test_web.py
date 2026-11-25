"""The teacher web pages against a real MEC: students, enrollment, sessions,
security, evaluation, settings and the live view. The portal's MEC calls go to
an in-process MEC through app.state.mec."""
from __future__ import annotations

import base64
import re
import struct
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from common.keys import load_or_create_admin_token, portal_signing_key
from mec_server.app import create_app as create_mec
from portal.app import create_app as create_portal
from portal.pages import match_roll

from conftest import PASSWORD, new_device, random_embedding

REPO = Path(__file__).resolve().parents[2]
HOPPER = Path(r"X:\Programs\Python\Lib\site-packages\matplotlib\mpl-data\sample_data\grace_hopper.jpg")
HAVE_MODELS = all((REPO / "models" / f).exists() for f in ("face_detection_yunet_2023mar.onnx", "w600k_mbf.onnx"))
needs_face = pytest.mark.skipif(not (HAVE_MODELS and HOPPER.exists()), reason="face models or sample photo absent")


class World:
    def __init__(self, settings):
        self.settings = settings
        self.portal = TestClient(create_portal(settings))
        self.mec = TestClient(create_mec(settings))
        self.admin = {"X-Admin-Token": load_or_create_admin_token(settings)}
        self.portal.app.state.mec = lambda method, path, timeout=None, **kw: self.mec.request(
            method, path, headers=self.admin, **kw)
        self.store = self.portal.app.state.store
        self.store.add_teacher("teacher1", "Dr. One", PASSWORD)
        self.store.add_teacher("teacher2", "Dr. Two", PASSWORD)
        self.login()

    def login(self, user="teacher1"):
        self.portal.cookies.clear()
        self.portal.post("/login", data={"username": user, "password": PASSWORD})

    def post(self, path, **kw):
        return self.portal.post(path, follow_redirects=False, **kw)

    def setup_class(self):
        assert self.post("/students/sections", data={"id": "EDGE-A", "title": "Edge A"}).status_code == 303
        for roll, name in [("22i-0001", "Ayesha Khan"), ("22i-0002", "Bilal Ahmed")]:
            r = self.post("/students", data={"roll_no": roll, "name": name, "section_id": "EDGE-A"})
            assert r.status_code == 303, r.text

    def pseudo(self, roll):
        return self.store.pseudonym_for(roll)

    def templates(self):
        return {r["pseudonym"] for r in self.mec.app.state.store.all_templates()}

    def phone(self):
        access = self.portal.post("/api/login", json={"username": "teacher1", "password": PASSWORD}).json()[
            "access_token"]
        device = new_device()
        body, sig = device.sign({"public_key_pem": device.public_pem, "label": "Pixel", "timestamp": int(time.time())})
        device.device_id = self.mec.post("/devices", content=body, headers={
            "Authorization": f"Bearer {access}", "X-Signature": sig}).json()["device_id"]
        return device, access

    def attend(self, device, access, present_rolls, before_receipt=None, metrics=None):
        grant = self.portal.post("/api/sections/EDGE-A/grant",
                                 headers={"Authorization": f"Bearer {access}"}).json()["grant_token"]
        body, sig = device.sign({"device_id": device.device_id, "timestamp": int(time.time())})
        session = self.mec.post("/sessions", content=body, headers={
            "Authorization": f"Bearer {grant}", "X-Signature": sig}).json()
        body, sig = device.sign({
            "device_id": device.device_id, "session_id": session["session_id"], "nonce": session["nonce"],
            "timestamp": int(time.time()), "present": [self.pseudo(r) for r in present_rolls],
            "metrics": metrics or {"photos": 1, "faces": 2, "detect_ms": 120, "embed_ms": 80, "match_ms": 2,
                                   "device": "=cmd()", "sdk": 34}})
        r = self.mec.post(f"/sessions/{session['session_id']}/attendance", content=body, headers={"X-Signature": sig})
        assert r.status_code == 200, r.text
        if before_receipt:
            before_receipt()
        r2 = self.portal.post("/api/attendance/receipts", json={"receipt": r.json()["receipt"]})
        assert r2.status_code == 200, r2.text
        return session


@pytest.fixture
def world(settings) -> World:
    return World(settings)


def test_match_roll():
    rolls = ["22i-0001", "22i-0002", "a1", "a1-2"]
    assert match_roll("22I-0001_2.jpg", rolls) == "22i-0001"
    assert match_roll("class/22i-0002/IMG.png", rolls) == "22i-0002"
    assert match_roll("a1-2.jpg", rolls) == "a1-2"
    assert match_roll("22i-00012.jpg", rolls) is None
    assert match_roll("holiday.jpg", rolls) is None


def test_every_page_renders_empty_and_without_mec(world):
    pages = ["/dashboard", "/appeals", "/sessions", "/students", "/evaluation", "/security", "/settings"]
    for path in pages:
        r = world.portal.get(path)
        assert r.status_code == 200 and "Sample data" not in r.text and "Preview" not in r.text, path

    def down(*a, **kw):
        raise OSError("down")
    world.setup_class()
    world.portal.app.state.mec = down
    for path in ["/students", "/evaluation", "/security", "/settings"]:
        r = world.portal.get(path)
        assert r.status_code == 200 and "could not be reached" in r.text, path
    r = world.post("/students/22i-0001/delete")
    assert r.status_code == 502 and world.pseudo("22i-0001")   # nothing lost
    world.portal.cookies.clear()
    for path in pages:
        assert world.portal.get(path, follow_redirects=False).status_code == 303
    assert world.portal.get("/live/latest").status_code == 401
    assert world.post("/students/photos", files={"photos": ("a.jpg", b"x")}).headers["location"] == "/login"


def test_student_management_and_ownership(world):
    world.setup_class()
    assert world.post("/students/sections", data={"id": "bad id", "title": "x"}).status_code == 400
    assert world.post("/students", data={"roll_no": "a/b", "name": "X", "section_id": "EDGE-A"}).status_code == 400
    assert world.post("/students/22i-0001/password", data={"password": "short"}).status_code == 400
    assert world.post("/students/22i-0001/password", data={"password": "long-enough"}).status_code == 303
    assert world.store.verify_student("22i-0001", "long-enough")
    # only section: removal would orphan the student
    assert world.post("/students/22i-0001/remove", data={"section_id": "EDGE-A"}).status_code == 400

    world.login("teacher2")
    for path, data in [("password", {"password": "long-enough"}), ("delete", {}), ("template/delete", {}),
                       ("remove", {"section_id": "EDGE-A"})]:
        assert world.post(f"/students/22i-0001/{path}", data=data).status_code == 404, path
    assert world.post("/students/22i-0001/photos", files={"photos": ("a.jpg", b"x")}).status_code == 404
    assert world.post("/students", data={"roll_no": "x1", "name": "X", "section_id": "EDGE-A"}).status_code == 400
    assert world.post("/students/sections", data={"id": "EDGE-A", "title": "mine"}).status_code == 400
    world.post("/students/sections", data={"id": "EDGE-B", "title": "Edge B"})
    add = {"roll_no": "22i-0001", "name": "Wrong Name", "section_id": "EDGE-B"}
    assert world.post("/students", data=add).status_code == 400
    assert world.post("/students", data={**add, "name": "ayesha khan"}).status_code == 303
    assert world.post("/students/22i-0001/delete").status_code == 409   # shared with teacher1
    assert world.post("/students/22i-0001/remove", data={"section_id": "EDGE-B"}).status_code == 303

    world.login()
    assert world.mec.put(f"/admin/templates/{world.pseudo('22i-0001')}", headers=world.admin,
                         json={"vector": random_embedding(1).tolist()}).status_code == 200
    assert "On file" in world.portal.get("/students").text
    assert world.post("/students/22i-0001/delete").status_code == 303
    assert world.pseudo("22i-0001") is None and not world.templates()


def test_sessions_live_evaluation_security(world):
    world.setup_class()
    assert world.portal.get("/live/latest").json()["session_id"] is None
    device, access = world.phone()
    # a student removed between capture and a late receipt must not lose the session
    world.post("/students/sections", data={"id": "EDGE-C", "title": "C"})
    world.post("/students", data={"roll_no": "22i-0002", "name": "Bilal Ahmed", "section_id": "EDGE-C"})
    sid = world.attend(device, access, ["22i-0001", "22i-0002"], before_receipt=lambda: world.post(
        "/students/22i-0002/remove", data={"section_id": "EDGE-A"}))["session_id"]

    assert world.portal.get("/live/latest").json() == {"session_id": sid, "section": "Edge A"}
    assert f'data-latest="{sid}"' in world.portal.get("/dashboard").text
    assert sid in world.portal.get("/sessions").text
    page = world.portal.get(f"/sessions/{sid}").text
    assert "Ayesha Khan" in page and "Recognition" in page and "No class photo" in page
    assert "22i-0001,Ayesha Khan,present,recognition" in world.portal.get(f"/sessions/{sid}/export.csv").text
    world.post(f"/sections/EDGE-A/sessions/{sid}/students/22i-0001", data={"status": "absent"})
    assert world.store.teacher_sessions(1, sid)[0]["corrections"] == 1

    page = world.portal.get("/evaluation").text
    assert "120" in page and "Sessions measured" in page
    csv_text = world.portal.get("/evaluation/export.csv").text
    assert sid in csv_text and "'=cmd()" in csv_text

    page = world.portal.get("/security").text
    assert "Pixel" in page and "Attendance submitted" in page

    world.login("teacher2")
    assert world.portal.get(f"/sessions/{sid}").status_code == 404
    assert world.portal.get(f"/sessions/{sid}/export.csv").status_code == 404
    assert world.portal.get("/live/latest").json()["session_id"] is None
    assert "Pixel" not in world.portal.get("/security").text
    world.post(f"/security/devices/{device.device_id}/revoke")
    assert not world.mec.app.state.store.get_device(device.device_id)["revoked"]

    world.login()
    assert world.post(f"/security/devices/{device.device_id}/revoke").status_code == 303
    assert world.mec.app.state.store.get_device(device.device_id)["revoked"]
    assert "Revoked" in world.portal.get("/security").text


def test_thresholds_saved_and_sent_to_phone(world):
    world.setup_class()
    device, access = world.phone()
    assert world.attend(device, access, [])["thresholds"] == {"accept": 0.4, "review": 0.3}
    for bad in [("0.3", "0.4"), ("1", "0.3"), ("0.4", "0"), ("nan", "0.3"), ("x", "0.3")]:
        r = world.post("/settings", data={"accept": bad[0], "review": bad[1]})
        assert r.status_code == 400, bad
    assert world.mec.put("/admin/settings", headers=world.admin, json={"accept": 0.2, "review": 0.5}).status_code == 400
    assert world.mec.put("/admin/settings", json={"accept": 0.5, "review": 0.2}).status_code == 403
    assert world.post("/settings", data={"accept": "0.55", "review": "0.35"}).status_code == 303
    assert world.attend(device, access, [])["thresholds"] == {"accept": 0.55, "review": 0.35}


def test_admin_reads_need_token(world):
    for path in ["/admin/devices?teacher=1", "/admin/sessions?teacher=1", "/admin/settings"]:
        assert world.mec.get(path).status_code == 403
    assert world.mec.post("/admin/templates/status", json={"pseudonyms": []}).status_code == 403
    assert world.mec.post("/admin/enroll/abcdefgh1234", json={"photos": [{"name": "a", "jpeg_b64": ""}]}
                          ).status_code == 403


def test_missing_models_is_503(settings, tmp_path):
    portal_signing_key(settings)
    mec = TestClient(create_mec(replace(settings, models_dir=tmp_path)))
    r = mec.post("/admin/enroll/abcdefgh1234", headers={"X-Admin-Token": load_or_create_admin_token(settings)},
                 json={"photos": [{"name": "a.jpg", "jpeg_b64": "AAAA"}]})
    assert r.status_code == 503 and "not available" in r.json()["detail"]


# ---- real faces ------------------------------------------------------------
def photo_variants() -> dict[str, bytes]:
    import cv2
    image = cv2.imread(str(HOPPER))
    h, w = image.shape[:2]
    big = cv2.resize(image, (int(w * 4000 / h), 4000))
    tight = image[int(h * 0.12):int(h * 0.62), int(w * 0.28):int(w * 0.72)]   # face fills the frame
    enc = lambda im: cv2.imencode(".jpg", im)[1].tobytes()
    return {"full": enc(image), "tight": enc(tight), "big": enc(big)}


@needs_face
def test_preprocessing_handles_crops_large_and_rotated_photos():
    import cv2
    import sys
    sys.path.append(str(REPO / "enrollment"))
    import face_pipeline as fp
    detector = fp.YuNetDetector(fp.MODELS_DIR / "face_detection_yunet_2023mar.onnx")
    embedder = fp.OnnxEmbedder(fp.MODELS_DIR / "w600k_mbf.onnx")
    vectors = {}
    for name, data in photo_variants().items():
        vectors[name], problem = fp.embed_photo(data, detector, embedder)
        assert vectors[name] is not None, (name, problem)
    assert min(float(vectors["full"] @ v) for v in vectors.values()) > 0.7
    # a sideways photo with an EXIF "rotate 90 CW" tag must come out upright
    upright = cv2.imread(str(HOPPER))
    sideways = cv2.imencode(".jpg", cv2.rotate(upright, cv2.ROTATE_90_COUNTERCLOCKWISE))[1].tobytes()
    tiff = b"II*\x00" + struct.pack("<IHHHIHHI", 8, 1, 0x0112, 3, 1, 6, 0, 0)
    app1 = b"\xff\xe1" + struct.pack(">H", len(tiff) + 8) + b"Exif\x00\x00" + tiff
    decoded = fp.decode_image(sideways[:2] + app1 + sideways[2:])
    assert decoded.shape == upright.shape and np.abs(decoded.astype(int) - upright).mean() < 8
    assert max(fp.decode_image(photo_variants()["big"]).shape[:2]) == fp.MAX_LONG_EDGE
    assert fp.decode_image(b"not an image") is None and fp.decode_image(b"") is None


@needs_face
def test_web_photo_enrollment(world):
    world.setup_class()
    photos = photo_variants()
    blank = base64.b64decode(  # 1x1 PNG
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    r = world.portal.post("/students/22i-0001/photos", files=[
        ("photos", (f"{n}.jpg", data)) for n, data in photos.items()] + [("photos", ("blank.png", blank))])
    assert r.status_code == 200 and "Enrolled from 3 photo(s)." in r.text and "blank.png: no usable face" in r.text
    assert world.templates() == {world.pseudo("22i-0001")}
    before = world.mec.app.state.store.all_templates()[0]["ciphertext"]

    r = world.portal.post("/students/22i-0001/photos", files={"photos": ("blank.png", blank)})
    assert "No usable face" in r.text
    assert world.mec.app.state.store.all_templates()[0]["ciphertext"] == before
    r = world.mec.post(f"/admin/enroll/{world.pseudo('22i-0001')}", headers=world.admin, json={
        "photos": [{"name": "b.png", "jpeg_b64": base64.b64encode(blank).decode()}]})
    assert r.status_code == 422

    r = world.portal.post("/students/photos", files=[
        ("photos", ("22i-0002_1.jpg", photos["full"])), ("photos", ("set/22i-0001/x.jpg", photos["tight"])),
        ("photos", ("stranger.jpg", photos["full"]))])
    assert r.status_code == 200 and "stranger.jpg" in r.text and len(world.templates()) == 2
    assert len(re.findall(r"Enrolled from 1 photo", r.text)) == 2
    # the portal stores no photos and no vectors
    portal_files = b"".join(p.read_bytes() for p in world.settings.portal_dir.rglob("*") if p.is_file())
    assert photos["full"][-200:] not in portal_files
    assert world.post("/students/22i-0002/template/delete").status_code == 303
    assert world.templates() == {world.pseudo("22i-0001")}
