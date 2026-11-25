"""Teacher pages backed by the campus server: students and face enrollment,
devices and activity, measurements, and match thresholds.

Everything face-related goes through the MEC admin API (app.state.mec). Photos
pass through this process in memory on their way there and are never stored.
"""
from __future__ import annotations

import base64
import csv
import io
import math
import re

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartParser

MAX_PHOTO_BYTES = 25 * 1024 * 1024   # same cap as the MEC
# Starlette spools larger parts to temp files; photos must not touch this disk.
# shortcut: a whole upload is held in RAM; upload in per-student batches if that ever hurts.
MultiPartParser.spool_max_size = MAX_PHOTO_BYTES + 1

SECTION_RE = re.compile(r"[A-Za-z0-9_-]{1,32}")
ROLL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}")
MEC_DOWN = "The campus server (MEC) could not be reached. Check that it is running, then reload."

NOTICES = {"section": "Section created.", "student": "Student added.", "password": "Password set.",
           "removed": "Student removed from the section.", "deleted": "Student deleted.",
           "template": "Face template removed."}

# Keys of the phone's metrics() (AttendanceViewModel.kt).
METRIC_KEYS = [("photos", "Photos"), ("faces", "Faces"), ("templates", "Templates"), ("detect_ms", "Detect ms"),
               ("embed_ms", "Embed ms"), ("match_ms", "Match ms"), ("open_session_rtt_ms", "Open session ms"),
               ("battery_start", "Battery start %"), ("battery_end", "Battery end %")]


class MecError(Exception):
    pass


def csv_response(rows: list[list], filename: str) -> Response:
    buf = io.StringIO()
    # A leading = + - @ would run as a formula in a spreadsheet.
    csv.writer(buf).writerows(
        [["'" + v if isinstance(v, str) and v[:1] in tuple("=+-@\t\r") else v for v in row] for row in rows])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def match_roll(path: str, rolls: list[str]) -> str | None:
    """Roll number from the nearest parent folder, else from the start of the file name."""
    *folders, name = re.split(r"[/\\]", path.lower())
    by_lower = {r.lower(): r for r in rolls}
    for folder in reversed(folders):
        if folder in by_lower:
            return by_lower[folder]
    for low in sorted(by_lower, key=len, reverse=True):
        if name.startswith(low) and not name[len(low):len(low) + 1].isalnum():
            return by_lower[low]
    return None


def _number(x) -> float | None:
    """Metrics come from the phone: keep only finite numbers."""
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and -1e12 < x < 1e12 else None


def build_router(teacher_from_cookie, store, templates) -> APIRouter:
    router = APIRouter(include_in_schema=False)

    def to_login() -> RedirectResponse:
        return RedirectResponse("/login", status_code=303)

    def page(request: Request, teacher_id: int, name: str, status: int = 200, **ctx):
        return templates.TemplateResponse(request, name, {"teacher": store.get_teacher(teacher_id), **ctx},
                                          status_code=status)

    def mec(request: Request, method: str, path: str, ok: tuple = (200,), **kw) -> httpx.Response:
        try:
            r = request.app.state.mec(method, path, **kw)
        except (httpx.HTTPError, OSError):
            raise MecError(MEC_DOWN)
        if r.status_code not in ok:
            raise MecError(f"The campus server refused the request (HTTP {r.status_code}).")
        return r

    async def form_of(request: Request):
        """(teacher_id, form). Signed-out requests are refused before the body is read."""
        teacher_id = teacher_from_cookie(request)
        if teacher_id is None:
            return None, None
        return teacher_id, await request.form(max_files=10000)

    # ---- students ---------------------------------------------------------
    def students_page(request: Request, teacher_id: int, status: int = 200, error: str | None = None,
                      results: list | None = None):
        students = store.teacher_students(teacher_id)
        enrolled, mec_problem = {}, None
        try:
            if students:
                enrolled = mec(request, "POST", "/admin/templates/status",
                               json={"pseudonyms": [s["pseudonym"] for s in students]}).json()
        except MecError as e:
            mec_problem = str(e)
        for s in students:
            s["enrolled_at"] = enrolled.get(s["pseudonym"])
        return page(request, teacher_id, "students.html", status, students=students,
                    sections=store.sections_for(teacher_id), mec_problem=mec_problem, error=error,
                    results=results, notice=NOTICES.get(request.query_params.get("ok", "")),
                    enrolled_count=sum(1 for s in students if s["enrolled_at"]))

    def done(key: str) -> RedirectResponse:
        return RedirectResponse(f"/students?ok={key}", status_code=303)

    def my_student(teacher_id: int, roll_no: str) -> dict:
        for s in store.teacher_students(teacher_id):
            if s["roll_no"] == roll_no:
                return s
        raise HTTPException(404, "student not found in your sections")

    @router.get("/students")
    def students(request: Request):
        teacher_id = teacher_from_cookie(request)
        return to_login() if teacher_id is None else students_page(request, teacher_id)

    @router.post("/students/sections")
    async def create_section(request: Request):
        teacher_id, form = await form_of(request)
        if teacher_id is None:
            return to_login()
        sid, title = str(form.get("id", "")).strip(), str(form.get("title", "")).strip()

        def apply():
            if not SECTION_RE.fullmatch(sid) or not 0 < len(title) <= 80:
                error = "Section code: up to 32 letters, digits, - or _. Title: 1 to 80 characters."
            elif not store.create_section(sid, title, teacher_id):
                error = f"Section code {sid} is already taken."
            else:
                return done("section")
            return students_page(request, teacher_id, 400, error)

        return await run_in_threadpool(apply)

    @router.post("/students")
    async def add_student(request: Request):
        teacher_id, form = await form_of(request)
        if teacher_id is None:
            return to_login()
        roll, name, sid, password = (str(form.get(k, "")) for k in ("roll_no", "name", "section_id", "password"))
        roll, name = roll.strip(), name.strip()

        def check_and_add() -> str | None:
            if store.section(sid, teacher_id) is None:
                return "Choose one of your sections."
            if not ROLL_RE.fullmatch(roll) or not 0 < len(name) <= 100:
                return "Roll number: up to 32 letters, digits, . - or _. Name: 1 to 100 characters."
            if password and not 8 <= len(password) <= 256:
                return "Password must be 8 to 256 characters, or left empty."
            existing = store.get_student(roll)
            if existing is None:
                store.add_student(roll, name)
                if password:
                    store.set_student_password(roll, password)
            elif existing["name"].casefold() != name.casefold():
                return f"{roll} already exists under a different name. Enter the name exactly as registered."
            elif password:
                return f"{roll} already exists. Leave the password empty, then use Set password."
            store.enroll(sid, roll)
            return None

        def apply():
            error = check_and_add()
            return students_page(request, teacher_id, 400, error) if error else done("student")

        return await run_in_threadpool(apply)

    @router.post("/students/{roll_no}/password")
    async def set_password(request: Request, roll_no: str):
        teacher_id, form = await form_of(request)
        if teacher_id is None:
            return to_login()
        password = str(form.get("password", ""))

        def apply():
            my_student(teacher_id, roll_no)
            if not 8 <= len(password) <= 256:
                return students_page(request, teacher_id, 400, "Password must be 8 to 256 characters.")
            store.set_student_password(roll_no, password)
            return done("password")

        return await run_in_threadpool(apply)

    @router.post("/students/{roll_no}/remove")
    async def remove_from_section(request: Request, roll_no: str):
        teacher_id, form = await form_of(request)
        if teacher_id is None:
            return to_login()
        sid = str(form.get("section_id", ""))

        def apply():
            student = my_student(teacher_id, roll_no)
            if sid not in student["sections"]:
                raise HTTPException(404, "student is not in that section")
            if len(student["sections"]) == 1 and not store.in_other_teachers_section(roll_no, teacher_id):
                return students_page(request, teacher_id, 400,
                                     f"{sid} is the only section of {roll_no}. Use Delete student instead.")
            store.remove_from_section(sid, roll_no)
            return done("removed")

        return await run_in_threadpool(apply)

    @router.post("/students/{roll_no}/template/delete")
    def delete_template(request: Request, roll_no: str):
        teacher_id = teacher_from_cookie(request)
        if teacher_id is None:
            return to_login()
        student = my_student(teacher_id, roll_no)
        try:
            mec(request, "DELETE", f"/admin/templates/{student['pseudonym']}", ok=(200, 404))
        except MecError as e:
            return students_page(request, teacher_id, 502, str(e))
        return done("template")

    @router.post("/students/{roll_no}/delete")
    def delete_student(request: Request, roll_no: str):
        teacher_id = teacher_from_cookie(request)
        if teacher_id is None:
            return to_login()
        student = my_student(teacher_id, roll_no)
        if store.in_other_teachers_section(roll_no, teacher_id):
            return students_page(request, teacher_id, 409,
                                 f"{roll_no} is also in another teacher's section. Remove them from yours instead.")
        try:   # template first: never leave a face template with no owner
            mec(request, "DELETE", f"/admin/templates/{student['pseudonym']}", ok=(200, 404))
        except MecError as e:
            return students_page(request, teacher_id, 502, f"Nothing was deleted. {e}")
        store.remove_student(roll_no)
        return done("deleted")

    # ---- photo enrollment -------------------------------------------------
    def enroll_one(request: Request, student: dict, files: list[UploadFile]) -> dict:
        result = {"roll_no": student["roll_no"], "name": student["name"], "ok": False, "problems": []}
        photos = []
        for f in files:
            data = f.file.read(MAX_PHOTO_BYTES + 1)
            if len(data) > MAX_PHOTO_BYTES:
                result["problems"].append(f"{f.filename}: larger than 25 MB")
            else:
                photos.append({"name": f.filename[-512:], "jpeg_b64": base64.b64encode(data).decode()})
        if not photos:
            return {**result, "message": "No photo could be sent."}
        try:
            r = mec(request, "POST", f"/admin/enroll/{student['pseudonym']}", ok=(200, 422, 503),
                    json={"photos": photos}, timeout=600)
        except MecError as e:
            return {**result, "message": str(e)}
        body = r.json()
        if r.status_code == 503:
            return {**result, "message": str(body.get("detail"))}
        if r.status_code == 422:
            detail = body.get("detail")
            result["problems"] += detail.get("problems", []) if isinstance(detail, dict) else []
            return {**result, "message": "No usable face. Any earlier template is unchanged."}
        result["problems"] += body["problems"]
        message = f"Enrolled from {body['used']} photo(s)."
        if body["min_agreement"] < 0.5:
            message += f" Low agreement ({body['min_agreement']:.2f}): check these photos show one person."
        return {**result, "ok": True, "message": message}

    async def upload(request: Request, roll_no: str | None):
        teacher_id, form = await form_of(request)
        if teacher_id is None:
            return to_login()

        def process():
            files = [f for f in form.getlist("photos") if isinstance(f, UploadFile) and f.filename]
            # Folder picks bring along OS clutter.
            files = [f for f in files if not re.split(r"[/\\]", f.filename)[-1].startswith(".")
                     and not f.filename.lower().endswith(("thumbs.db", "desktop.ini"))]
            students = {s["roll_no"]: s for s in store.teacher_students(teacher_id)}
            if roll_no is not None and roll_no not in students:
                raise HTTPException(404, "student not found in your sections")
            if not files:
                return students_page(request, teacher_id, 400, "Choose at least one photo.")
            groups, unmatched = {}, []
            for f in files:
                roll = roll_no or match_roll(f.filename, list(students))
                if roll is None:
                    unmatched.append(f.filename)
                else:
                    groups.setdefault(roll, []).append(f)
            results = [enroll_one(request, students[r], g) for r, g in sorted(groups.items())]
            if unmatched:
                results.append({"roll_no": "", "name": "Not matched to a student", "ok": False,
                                "message": "Start each file name with the roll number, or use one folder per roll number.",
                                "problems": unmatched})
            return students_page(request, teacher_id, results=results)

        try:
            return await run_in_threadpool(process)
        finally:
            await form.close()

    @router.post("/students/photos")
    async def bulk_photos(request: Request):
        return await upload(request, None)

    @router.post("/students/{roll_no}/photos")
    async def student_photos(request: Request, roll_no: str):
        return await upload(request, roll_no)

    # ---- security ---------------------------------------------------------
    def security_page(request: Request, teacher_id: int, status: int = 200, error: str | None = None):
        devices, activity, problem = [], [], None
        try:
            devices = mec(request, "GET", "/admin/devices", params={"teacher": str(teacher_id)}).json()
            audit = mec(request, "GET", "/admin/audit", params={"limit": 500}).json()
        except MecError as e:
            problem = str(e)
        else:
            labels = {d["device_id"]: d["label"] or "Unnamed phone" for d in devices}
            students = {s["pseudonym"]: s["roll_no"] for s in store.teacher_students(teacher_id)}
            for e in audit:
                actor, detail = e["actor"], dict(e["detail"])
                pseudonym = detail.pop("pseudonym", None)
                # Only this teacher's events; admin events only about their students or the whole server.
                if actor == "admin":
                    if pseudonym is not None and pseudonym not in students:
                        continue
                elif actor != f"teacher:{teacher_id}" and actor not in labels:
                    continue
                if pseudonym is not None:
                    detail["student"] = students.get(pseudonym, "unknown")
                if "device_id" in detail:
                    detail["device"] = labels.get(detail.pop("device_id"), "unknown")
                action = e["action"]
                activity.append({
                    "ts": e["ts"], "rejected": action.startswith("rejected:"),
                    "event": action.removeprefix("rejected:").replace("_", " ").capitalize(),
                    "who": labels.get(actor, "Administrator" if actor == "admin" else "You"),
                    "detail": ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in detail.items())})
        return page(request, teacher_id, "security.html", status, devices=devices, activity=activity,
                    mec_problem=problem, error=error)

    @router.get("/security")
    def security(request: Request):
        teacher_id = teacher_from_cookie(request)
        return to_login() if teacher_id is None else security_page(request, teacher_id)

    @router.post("/security/devices/{device_id}/revoke")
    def revoke(request: Request, device_id: str):
        teacher_id = teacher_from_cookie(request)
        if teacher_id is None:
            return to_login()
        if not re.fullmatch(r"[0-9a-f]{32}", device_id):
            raise HTTPException(404, "device not found")
        try:
            mec(request, "DELETE", f"/admin/devices/{device_id}", params={"teacher": str(teacher_id)})
        except MecError as e:
            return security_page(request, teacher_id, 502, f"The device was not revoked. {e}")
        return RedirectResponse("/security", status_code=303)

    # ---- evaluation -------------------------------------------------------
    def measurements(request: Request, teacher_id: int) -> list[dict]:
        """One row per submitted session: the phone's metrics plus the portal's error indicators."""
        known = {s["session_id"]: s for s in store.teacher_sessions(teacher_id)}
        rows = []
        for m in mec(request, "GET", "/admin/sessions", params={"teacher": str(teacher_id)}).json():
            metrics = m["metrics"] or {}
            s = known.get(m["session_id"])
            rows.append({
                "session_id": m["session_id"], "section_id": m["section_id"], "at": m["submitted_at"],
                "device": str(metrics.get("device") or m["device_label"] or ""),
                "sdk": _number(metrics.get("sdk")),
                "values": {k: _number(metrics.get(k)) for k, _ in METRIC_KEYS},
                "received": s is not None,
                "corrections": s["corrections"] if s else None,
                "accepted_appeals": s["accepted_appeals"] if s else None})
        return rows

    @router.get("/evaluation")
    def evaluation(request: Request):
        teacher_id = teacher_from_cookie(request)
        if teacher_id is None:
            return to_login()
        try:
            rows, problem = measurements(request, teacher_id), None
        except MecError as e:
            rows, problem = [], str(e)
        averages = {}
        for key, _ in METRIC_KEYS:
            # battery -1 means the phone could not read it
            found = [r["values"][key] for r in rows if r["values"][key] is not None and r["values"][key] >= 0]
            averages[key] = sum(found) / len(found) if found else None
        return page(request, teacher_id, "evaluation.html", rows=rows, keys=METRIC_KEYS, averages=averages,
                    corrections=sum(r["corrections"] or 0 for r in rows),
                    appeals=sum(r["accepted_appeals"] or 0 for r in rows), mec_problem=problem)

    @router.get("/evaluation/export.csv")
    def evaluation_csv(request: Request):
        teacher_id = teacher_from_cookie(request)
        if teacher_id is None:
            return to_login()
        try:
            rows = measurements(request, teacher_id)
        except MecError as e:
            raise HTTPException(502, str(e))
        out = [["session_id", "section_id", "submitted_at", "device", "sdk"] + [k for k, _ in METRIC_KEYS]
               + ["manual_corrections", "accepted_appeals"]]
        out += [[r["session_id"], r["section_id"], r["at"], r["device"], r["sdk"]]
                + [r["values"][k] for k, _ in METRIC_KEYS] + [r["corrections"], r["accepted_appeals"]] for r in rows]
        return csv_response(out, "measurements.csv")

    # ---- settings ---------------------------------------------------------
    def settings_page(request: Request, teacher_id: int, status: int = 200, error: str | None = None,
                      entered: dict | None = None):
        values, problem = None, None
        try:
            values = mec(request, "GET", "/admin/settings").json()
        except MecError as e:
            problem = str(e)
        return page(request, teacher_id, "settings.html", status, values=entered or values, mec_problem=problem,
                    error=error, saved=request.query_params.get("ok") == "saved")

    @router.get("/settings")
    def settings(request: Request):
        teacher_id = teacher_from_cookie(request)
        return to_login() if teacher_id is None else settings_page(request, teacher_id)

    @router.post("/settings")
    async def save_settings(request: Request):
        teacher_id, form = await form_of(request)
        if teacher_id is None:
            return to_login()
        entered = {k: str(form.get(k, "")).strip()[:16] for k in ("accept", "review")}

        def save():
            try:
                accept, review = float(entered["accept"]), float(entered["review"])
            except ValueError:
                accept = review = math.nan
            if not 0 < review <= accept < 1:
                return settings_page(request, teacher_id, 400, "Use 0 < review ≤ accept < 1.", entered)
            try:
                mec(request, "PUT", "/admin/settings", json={"accept": accept, "review": review})
            except MecError as e:
                return settings_page(request, teacher_id, 502, f"Not saved. {e}", entered)
            return RedirectResponse("/settings?ok=saved", status_code=303)

        return await run_in_threadpool(save)

    return router
