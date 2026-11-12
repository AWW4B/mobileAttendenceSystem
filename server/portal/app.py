"""Online attendance portal (dummy platform).

JSON API for the mobile app under /api, teacher web dashboard under /.

Run (from server/):
  uvicorn portal.app:create_app --factory --host 0.0.0.0 --port 8001
"""
from __future__ import annotations

import csv
import datetime as dt
import io
from pathlib import Path

from fastapi import FastAPI, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from common import tokens
from common.admin import require_admin
from common.keys import load_or_create_admin_token, mec_public_key, portal_signing_key
from common.settings import MEC_ISSUER, PORTAL_ISSUER, Settings

from .preview import build_router as build_preview_router
from .store import PortalStore

COOKIE = "portal_session"


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    name: str


class SectionOut(BaseModel):
    id: str
    title: str
    student_count: int


class RosterEntry(BaseModel):
    pseudonym: str
    roll_no: str
    name: str


class GrantOut(BaseModel):
    grant_token: str
    expires_in: int
    section_id: str
    roster: list[RosterEntry]


class ReceiptIn(BaseModel):
    receipt: str = Field(min_length=20, max_length=16384)


def _fmt_time(ts: int | None) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%d %b %Y, %H:%M") if ts else "—"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    signing_key = portal_signing_key(settings)
    public_key = signing_key.public_key()
    admin_token = load_or_create_admin_token(settings)
    store = PortalStore(settings.portal_dir / "portal.db")
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    templates.env.filters["when"] = _fmt_time

    app = FastAPI(title="Attendance portal", version="0.2.0")
    app.state.store = store
    app.state.settings = settings
    # Web UI assets (css, js, fonts). Presentation only.
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

    def issue_access(teacher_id: int) -> str:
        token, _ = tokens.issue(signing_key, issuer=PORTAL_ISSUER, typ="access", sub=str(teacher_id),
                                aud=["portal", "mec"], ttl_s=settings.access_token_ttl_s)
        return token

    def teacher_from_bearer(authorization: str | None) -> int:
        claims = tokens.verify(public_key, tokens.bearer(authorization), issuer=PORTAL_ISSUER,
                               typ="access", aud="portal")
        return int(claims["sub"])

    def teacher_from_cookie(request: Request) -> int | None:
        token = request.cookies.get(COOKIE)
        if not token:
            return None
        try:
            claims = tokens.verify(public_key, token, issuer=PORTAL_ISSUER, typ="access", aud="portal")
        except HTTPException:
            return None
        return int(claims["sub"])

    # =====================================================================
    # JSON API (mobile app, enrollment tooling)
    # =====================================================================
    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "service": "portal"}

    @app.post("/api/login", response_model=LoginOut)
    def api_login(body: LoginIn) -> LoginOut:
        row = store.verify_teacher(body.username, body.password)
        if row is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid username or password")
        return LoginOut(access_token=issue_access(row["id"]), expires_in=settings.access_token_ttl_s,
                        name=row["name"])

    @app.get("/api/sections", response_model=list[SectionOut])
    def api_sections(authorization: str | None = Header(default=None)) -> list[SectionOut]:
        teacher_id = teacher_from_bearer(authorization)
        return [SectionOut(id=r["id"], title=r["title"], student_count=r["student_count"])
                for r in store.sections_for(teacher_id)]

    @app.post("/api/sections/{section_id}/grant", response_model=GrantOut)
    def api_grant(section_id: str, authorization: str | None = Header(default=None)) -> GrantOut:
        """One-time grant to open a capture session on the MEC.

        The grant carries pseudonyms only. The roster with names goes back to
        the teacher's app for display; the MEC never receives names."""
        teacher_id = teacher_from_bearer(authorization)
        roster = store.roster(section_id, teacher_id)
        if roster is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "section not found")
        token, _ = tokens.issue(
            signing_key, issuer=PORTAL_ISSUER, typ="grant", sub=str(teacher_id), aud=["mec"],
            ttl_s=settings.grant_ttl_s,
            extra={"sec": section_id, "psn": [r["pseudonym"] for r in roster]},
        )
        return GrantOut(grant_token=token, expires_in=settings.grant_ttl_s, section_id=section_id,
                        roster=[RosterEntry(**dict(r)) for r in roster])

    @app.post("/api/attendance/receipts")
    def api_receipt(body: ReceiptIn) -> dict:
        """Record attendance from a MEC-signed receipt.

        The receipt is self-authenticating (signed by the MEC, bound to the
        teacher and section), so the phone can forward it later if it was
        offline. Submitting the same receipt twice is harmless."""
        try:
            mec_key = mec_public_key(settings)
        except RuntimeError:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "MEC receipt key not configured")
        claims = tokens.verify(mec_key, body.receipt, issuer=MEC_ISSUER, typ="receipt", aud="portal")
        teacher_id, section_id = int(claims["sub"]), str(claims["sec"])
        roster = store.roster(section_id, teacher_id)
        if roster is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "section not found for this teacher")
        present = set(claims.get("psn", []))
        if not present <= {r["pseudonym"] for r in roster}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "receipt lists students outside the section")
        new, p, a = store.record_session(str(claims["sid"]), section_id, int(claims["tak"]), present)
        return {"session_id": claims["sid"], "recorded": new, "present": p, "absent": a}

    @app.get("/api/admin/students/{roll_no}/pseudonym")
    def api_admin_pseudonym(roll_no: str, x_admin_token: str | None = Header(default=None)) -> dict:
        require_admin(admin_token, x_admin_token)
        pseudonym = store.pseudonym_for(roll_no)
        if pseudonym is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown roll number")
        return {"roll_no": roll_no, "pseudonym": pseudonym}

    # =====================================================================
    # Web dashboard (teachers)
    # =====================================================================
    def to_login() -> RedirectResponse:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/", include_in_schema=False)
    def root(request: Request) -> RedirectResponse:
        return RedirectResponse("/dashboard" if teacher_from_cookie(request) else "/login", status_code=303)

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "login.html", {"error": None})

    @app.post("/login", include_in_schema=False)
    def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
        row = store.verify_teacher(username, password)
        if row is None:
            return templates.TemplateResponse(request, "login.html", {"error": "Invalid username or password."},
                                              status_code=401)
        resp = RedirectResponse("/dashboard", status_code=303)
        resp.set_cookie(COOKIE, issue_access(row["id"]), max_age=settings.access_token_ttl_s,
                        httponly=True, samesite="strict", secure=request.url.scheme == "https")
        return resp

    @app.post("/logout", include_in_schema=False)
    def logout() -> RedirectResponse:
        resp = to_login()
        resp.delete_cookie(COOKIE)
        return resp

    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def dashboard(request: Request):
        teacher_id = teacher_from_cookie(request)
        if teacher_id is None:
            return to_login()
        return templates.TemplateResponse(request, "dashboard.html", {
            "teacher": store.get_teacher(teacher_id), "sections": store.sections_for(teacher_id)})

    def section_view(request: Request, section_id: str):
        teacher_id = teacher_from_cookie(request)
        if teacher_id is None:
            return None, None, to_login()
        roster = store.roster(section_id, teacher_id)
        if roster is None:
            raise HTTPException(404, "section not found")
        return teacher_id, roster, None

    @app.get("/sections/{section_id}", response_class=HTMLResponse, include_in_schema=False)
    def section_page(request: Request, section_id: str):
        teacher_id, roster, redirect = section_view(request, section_id)
        if redirect:
            return redirect
        sessions = store.sessions(section_id)
        matrix = store.matrix(section_id)
        stats = {}
        for s in roster:
            marks = [matrix.get((s["roll_no"], cs["session_id"])) for cs in sessions]
            held = [m for m in marks if m is not None]
            present = sum(1 for m in held if m["status"] == "present")
            stats[s["roll_no"]] = round(100 * present / len(held)) if held else None
        return templates.TemplateResponse(request, "section.html", {
            "teacher": store.get_teacher(teacher_id), "section": store.section(section_id, teacher_id),
            "roster": roster, "sessions": sessions, "matrix": matrix, "stats": stats})

    @app.post("/sections/{section_id}/sessions/{session_id}/students/{roll_no}",
              include_in_schema=False)
    def toggle(request: Request, section_id: str, session_id: str, roll_no: str,
               status_value: str = Form(..., alias="status")):
        _, _, redirect = section_view(request, section_id)
        if redirect:
            return redirect
        if status_value not in ("present", "absent") or store.session_section(session_id) != section_id:
            raise HTTPException(400, "bad request")
        store.set_status(session_id, roll_no, status_value)
        return RedirectResponse(f"/sections/{section_id}", status_code=303)

    @app.get("/sections/{section_id}/export.csv", include_in_schema=False)
    def export_csv(request: Request, section_id: str):
        _, roster, redirect = section_view(request, section_id)
        if redirect:
            return redirect
        sessions = store.sessions(section_id)
        matrix = store.matrix(section_id)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["roll_no", "name"] + [_fmt_time(s["taken_at"]) for s in sessions])
        for s in roster:
            w.writerow([s["roll_no"], s["name"]] + [
                (matrix[(s["roll_no"], cs["session_id"])]["status"]
                 if (s["roll_no"], cs["session_id"]) in matrix else "") for cs in sessions])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{section_id}-attendance.csv"'})

    # Web UI for modules with no backend yet (sample data; see preview.py).
    app.include_router(build_preview_router(teacher_from_cookie, store, templates))

    return app
