"""Portal tests. MEC receipts are minted directly with the MEC key, so the
portal is tested without the MEC component."""
from __future__ import annotations

import base64

import httpx
import pytest
from fastapi.testclient import TestClient

from common import tokens
from common.keys import load_or_create_admin_token, mec_signing_key, portal_signing_key
from common.settings import MEC_ISSUER, PORTAL_ISSUER
from portal.app import create_app

from conftest import PASSWORD

ROSTER = [("22i-0001", "Ayesha Khan"), ("22i-0002", "Bilal Ahmed"), ("22i-0003", "Sana Malik")]


@pytest.fixture
def portal(settings):
    mec_signing_key(settings)  # the MEC publishes its receipt key on first start
    client = TestClient(create_app(settings))
    store = client.app.state.store
    store.add_teacher("teacher1", "Dr. One", PASSWORD)
    store.add_teacher("teacher2", "Dr. Two", PASSWORD)
    store.add_section("EDGE-A", "Edge Computing A", "teacher1")
    store.add_section("EDGE-B", "Edge Computing B", "teacher2")
    for roll, name in ROSTER:
        store.add_student(roll, name)
        store.enroll("EDGE-A", roll)
    store.add_student("22i-0099", "Other Section")
    store.enroll("EDGE-B", "22i-0099")
    client.settings = settings
    return client


def login(portal, username="teacher1") -> str:
    r = portal.post("/api/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def receipt(portal, *, sid="sess-1", sec="EDGE-A", teacher=1, present=(), tak=1_700_000_000, key=None) -> str:
    token, _ = tokens.issue(key or mec_signing_key(portal.settings), issuer=MEC_ISSUER, typ="receipt",
                            sub=str(teacher), aud=["portal"], ttl_s=3600,
                            extra={"sid": sid, "sec": sec, "psn": list(present), "tak": tak})
    return token


def pseudo(portal, roll):
    return portal.app.state.store.pseudonym_for(roll)


# ---- API -----------------------------------------------------------------
def test_login_and_sections(portal):
    access = login(portal)
    r = portal.get("/api/sections", headers={"Authorization": f"Bearer {access}"})
    assert r.json() == [{"id": "EDGE-A", "title": "Edge Computing A", "student_count": 3}]


def test_login_failures(portal):
    assert portal.post("/api/login", json={"username": "teacher1", "password": "nope"}).status_code == 401
    assert portal.post("/api/login", json={"username": "ghost", "password": "nope"}).status_code == 401


def test_grant_carries_pseudonyms_only(portal, settings):
    access = login(portal)
    r = portal.post("/api/sections/EDGE-A/grant", headers={"Authorization": f"Bearer {access}"})
    body = r.json()
    assert [e["roll_no"] for e in body["roster"]] == [r for r, _ in ROSTER]
    claims = tokens.verify(portal_signing_key(settings).public_key(), body["grant_token"],
                           issuer=PORTAL_ISSUER, typ="grant", aud="mec")
    assert claims["sec"] == "EDGE-A" and len(claims["psn"]) == 3
    assert "22i-0001" not in body["grant_token"] and "Ayesha" not in str(claims)


def test_grant_for_other_teachers_section_is_404(portal):
    access = login(portal)
    r = portal.post("/api/sections/EDGE-B/grant", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 404


def test_receipt_records_present_and_absent(portal):
    rec = receipt(portal, present=[pseudo(portal, "22i-0001"), pseudo(portal, "22i-0003")])
    r = portal.post("/api/attendance/receipts", json={"receipt": rec})
    assert r.json() == {"session_id": "sess-1", "recorded": True, "present": 2, "absent": 1}
    # idempotent: the phone may retry
    r = portal.post("/api/attendance/receipts", json={"receipt": rec})
    assert r.json()["recorded"] is False


def test_receipt_signed_by_wrong_key_rejected(portal):
    forged = receipt(portal, key=portal_signing_key(portal.settings))  # not the MEC key
    assert portal.post("/api/attendance/receipts", json={"receipt": forged}).status_code == 401


def test_receipt_for_other_teachers_section_rejected(portal):
    rec = receipt(portal, sec="EDGE-B", teacher=1)
    assert portal.post("/api/attendance/receipts", json={"receipt": rec}).status_code == 404


def test_receipt_with_outsider_rejected(portal):
    rec = receipt(portal, present=[pseudo(portal, "22i-0099")])
    assert portal.post("/api/attendance/receipts", json={"receipt": rec}).status_code == 400


def test_portal_token_is_not_a_receipt(portal):
    access = login(portal)
    assert portal.post("/api/attendance/receipts", json={"receipt": access}).status_code == 401


def test_admin_pseudonym_lookup(portal, settings):
    assert portal.get("/api/admin/students/22i-0001/pseudonym").status_code == 403
    r = portal.get("/api/admin/students/22i-0001/pseudonym",
                   headers={"X-Admin-Token": load_or_create_admin_token(settings)})
    assert r.json()["pseudonym"] == pseudo(portal, "22i-0001")


# ---- web dashboard -------------------------------------------------------
def web_login(portal, username="teacher1"):
    r = portal.post("/login", data={"username": username, "password": PASSWORD}, follow_redirects=False)
    assert r.status_code == 303 and "portal_session" in r.cookies
    return r


def test_dashboard_requires_login(portal):
    r = portal.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_web_login_failure(portal):
    r = portal.post("/login", data={"username": "teacher1", "password": "wrong"}, follow_redirects=False)
    assert r.status_code == 401 and "Invalid" in r.text


def test_section_page_shows_names_and_marks(portal):
    portal.post("/api/attendance/receipts", json={"receipt": receipt(portal, present=[pseudo(portal, "22i-0001")])})
    web_login(portal)
    page = portal.get("/sections/EDGE-A").text
    assert "Ayesha Khan" in page and "Bilal Ahmed" in page
    assert "100%" in page and "0%" in page
    assert portal.get("/sections/EDGE-B").status_code == 404  # other teacher's section


def test_manual_correction_and_csv(portal):
    portal.post("/api/attendance/receipts", json={"receipt": receipt(portal, present=[pseudo(portal, "22i-0001")])})
    web_login(portal)
    r = portal.post("/sections/EDGE-A/sessions/sess-1/students/22i-0002", data={"status": "present"},
                    follow_redirects=False)
    assert r.status_code == 303
    csv_text = portal.get("/sections/EDGE-A/export.csv").text.splitlines()
    assert csv_text[1].endswith("present") and csv_text[2].endswith("present") and csv_text[3].endswith("absent")


# ---- student login and appeals --------------------------------------------
def appeal_setup(portal):
    """Session sess-1 in EDGE-A: Ayesha present, Bilal and Sana absent; students have passwords."""
    for roll, _ in ROSTER:
        portal.app.state.store.set_student_password(roll, roll)
    sha = "ab" * 32
    portal.post("/api/attendance/receipts", json={"receipt": receipt(portal, present=[pseudo(portal, "22i-0001")])})
    with portal.app.state.store._conn() as c:
        c.execute("UPDATE class_sessions SET evidence_sha256 = ?", (sha,))
    jpeg = b"\xff\xd8\xff" + b"x" * 50
    portal.app.state.fetch_evidence = lambda teacher_id, sid: {
        "sha256": sha, "width": 1000, "height": 500, "jpeg_b64": base64.b64encode(jpeg).decode(),
        "faces": [{"box": [100, 50, 200, 100], "pseudonym": pseudo(portal, "22i-0002"), "score": 0.5},
                  {"box": [500, 50, 100, 100], "pseudonym": None, "score": None}]}
    return jpeg


def student_login(portal, roll="22i-0002", password=None):
    return portal.post("/student/login", data={"username": roll, "password": password or roll},
                       follow_redirects=False)


def test_student_login_appeal_and_teacher_accepts(portal):
    jpeg = appeal_setup(portal)
    assert student_login(portal, password="wrong-password").status_code == 401
    assert student_login(portal).status_code == 303
    page = portal.get("/student").text
    assert "Bilal Ahmed" in page and "Appeal" in page and "evidence" not in page
    r = portal.post("/student/appeals", data={"session_id": "sess-1", "reason": "I sat in the back"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert portal.post("/student/appeals", data={"session_id": "sess-1", "reason": "again"}).status_code == 400
    assert "I sat in the back" in portal.get("/student").text
    portal.cookies.clear()

    web_login(portal)
    assert portal.get("/dashboard").text.count("Appeals") >= 1
    detail = portal.get("/appeals/1").text
    assert "Bilal Ahmed" in detail and "I sat in the back" in detail
    assert "left:10.0%" in detail and "face-box me" in detail and "unmatched" in detail
    assert portal.get("/appeals/1/evidence.jpg").content == jpeg
    assert portal.post("/appeals/1/resolve", data={"decision": "reject"}).status_code == 400
    assert portal.post("/appeals/1/resolve", data={"decision": "accept"}, follow_redirects=False).status_code == 303
    row = portal.app.state.store.matrix("EDGE-A")[("22i-0002", "sess-1")]
    assert row["status"] == "present" and row["source"] == "manual"
    assert portal.post("/appeals/1/resolve", data={"decision": "accept"}).status_code == 409


def test_reject_needs_note_and_keeps_absent(portal):
    appeal_setup(portal)
    student_login(portal)
    portal.post("/student/appeals", data={"session_id": "sess-1", "reason": "r"})
    portal.cookies.clear()
    web_login(portal)
    r = portal.post("/appeals/1/resolve", data={"decision": "reject", "note": "not in photo"}, follow_redirects=False)
    assert r.status_code == 303
    assert portal.app.state.store.matrix("EDGE-A")[("22i-0002", "sess-1")]["status"] == "absent"
    portal.cookies.clear()
    student_login(portal)
    assert "not in photo" in portal.get("/student").text


def test_appeal_resolvable_without_photo(portal):
    appeal_setup(portal)
    student_login(portal)
    portal.post("/student/appeals", data={"session_id": "sess-1", "reason": "r"})
    portal.cookies.clear()
    web_login(portal)

    def down(*_):
        raise httpx.ConnectError("down")
    portal.app.state.fetch_evidence = down
    assert "could not be reached" in portal.get("/appeals/1").text
    assert portal.get("/appeals/1/evidence.jpg").status_code == 404
    portal.app.state.fetch_evidence = lambda *_: {"sha256": "00" * 32}
    assert "does not match" in portal.get("/appeals/1").text
    assert portal.post("/appeals/1/resolve", data={"decision": "accept"}, follow_redirects=False).status_code == 303


def test_present_student_cannot_appeal(portal):
    appeal_setup(portal)
    student_login(portal, "22i-0001")
    assert portal.post("/student/appeals", data={"session_id": "sess-1", "reason": "r"}).status_code == 400


def test_student_and_teacher_cookies_do_not_cross(portal):
    appeal_setup(portal)
    student_login(portal)
    assert portal.get("/dashboard", follow_redirects=False).status_code == 303
    assert portal.get("/appeals", follow_redirects=False).headers["location"] == "/login"
    portal.cookies.clear()
    web_login(portal)
    assert portal.get("/student", follow_redirects=False).headers["location"] == "/student/login"
    assert student_login(portal, "22i-0099").status_code == 401  # no password set


def test_other_teacher_cannot_see_appeal(portal):
    appeal_setup(portal)
    student_login(portal)
    portal.post("/student/appeals", data={"session_id": "sess-1", "reason": "r"})
    portal.cookies.clear()
    web_login(portal, "teacher2")
    assert portal.get("/appeals/1").status_code == 404
    assert portal.get("/appeals/1/evidence.jpg").status_code == 404
    assert portal.post("/appeals/1/resolve", data={"decision": "accept"}).status_code == 404
    assert "Bilal" not in portal.get("/appeals").text


def test_existing_db_gets_new_columns(tmp_path):
    import sqlite3
    from portal.store import PortalStore
    db = tmp_path / "old.db"
    c = sqlite3.connect(db)
    c.executescript("CREATE TABLE students (roll_no TEXT PRIMARY KEY, name TEXT NOT NULL, pseudonym TEXT UNIQUE NOT NULL);"
                    "CREATE TABLE class_sessions (session_id TEXT PRIMARY KEY, section_id TEXT, taken_at INTEGER, received_at INTEGER);")
    c.close()
    store = PortalStore(db)
    store.add_student("r1", "R One")
    assert store.set_student_password("r1", "password-1") and store.verify_student("r1", "password-1")
