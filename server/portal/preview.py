"""Web UI routes for portal modules that have no backend yet.

These pages render sample data from preview_data.py so the whole product can
be designed, reviewed and demoed. They read nothing from the database, write
nothing, and are marked "Sample data" in the interface. They sit behind the
same login as the real dashboard.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from . import preview_data as data


def build_router(teacher_from_cookie, store, templates) -> APIRouter:
    router = APIRouter(include_in_schema=False)

    def page(request: Request, name: str, **ctx):
        teacher_id = teacher_from_cookie(request)
        if teacher_id is None:
            return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse(request, name, {"teacher": store.get_teacher(teacher_id), **ctx})

    @router.get("/sessions")
    def sessions(request: Request):
        return page(request, "sessions.html", sessions=data.sessions())

    @router.get("/sessions/{session_id}")
    def session_detail(request: Request, session_id: str):
        s = data.session(session_id)
        if s is None:
            raise HTTPException(404, "session not found")
        return page(request, "session_detail.html", s=s, results=data.session_results(s))

    @router.get("/students")
    def students(request: Request):
        rows = data.students()
        counts = {k: sum(1 for r in rows if r["state"] == k) for k in ("enrolled", "missing", "redo")}
        return page(request, "students.html", students=rows, counts=counts)

    @router.get("/security")
    def security(request: Request):
        return page(request, "security.html", devices=data.DEVICES, activity=data.ACTIVITY)

    @router.get("/evaluation")
    def evaluation(request: Request):
        return page(request, "evaluation.html", **data.evaluation(), accept=data.ACCEPT)

    @router.get("/settings")
    def settings(request: Request):
        return page(request, "settings.html")

    return router
