"""Sample data for portal modules whose backend does not exist yet.

Everything here is invented for design review and is labelled "Sample data" in
the UI. Nothing in this file is read from, or written to, any database. When a
module gets a real backend, replace its function here with a store query and
delete the "Sample data" note from its template.
"""
from __future__ import annotations

import random

NAMES = [
    "Ayesha Khan", "Bilal Ahmed", "Sana Malik", "Usman Tariq", "Hira Siddiqui", "Hamza Qureshi",
    "Maryam Siddiqui", "Zainab Farooq", "Talha Mehmood", "Rabia Anwar", "Daniyal Chaudhry", "Hira Batool",
    "Ibrahim Sheikh", "Noor ul Ain", "Saad Rizvi", "Fatima Zahra", "Areeba Imran", "Mustafa Jamil",
    "Laiba Nadeem", "Haider Abbas", "Kinza Raza", "Shahzaib Butt", "Mahnoor Iqbal", "Omer Farid",
]

SECTIONS = {
    "EDGE-A": "Edge Computing & Intelligent Systems",
    "DAA-B": "Design and Analysis of Algorithms",
}

# id, date, time, section, device, photos, faces, matched, present, total, corrections, status
_SESSIONS = [
    ("s-2042", "12 Nov 2026", "11:20", "DAA-B", "Samsung Galaxy A34", 3, 50, 45, 44, 54, 0, "Awaiting upload"),
    ("s-2041", "12 Nov 2026", "09:02", "EDGE-A", "Google Pixel 8", 3, 47, 43, 41, 48, 2, "Recorded"),
    ("s-2040", "10 Nov 2026", "10:33", "EDGE-A", "Google Pixel 8", 2, 46, 41, 40, 48, 1, "Recorded"),
    ("s-2039", "10 Nov 2026", "14:05", "DAA-B", "Samsung Galaxy A34", 4, 51, 46, 44, 54, 3, "Recorded"),
    ("s-2038", "07 Nov 2026", "09:04", "EDGE-A", "Google Pixel 8", 3, 45, 42, 42, 48, 0, "Recorded"),
    ("s-2037", "05 Nov 2026", "14:11", "DAA-B", "Samsung Galaxy A34", 3, 49, 44, 43, 54, 0, "Recorded"),
    ("s-2036", "03 Nov 2026", "09:00", "EDGE-A", "Google Pixel 8", 2, 44, 38, 37, 48, 4, "Recorded"),
    ("s-2035", "31 Oct 2026", "14:09", "DAA-B", "Samsung Galaxy A34", 1, 36, 31, 31, 54, 5, "Recorded"),
]
_KEYS = ("id", "date", "time", "section", "device", "photos", "faces", "matched", "present", "total", "corrections", "status")


def sessions() -> list[dict]:
    out = []
    for row in _SESSIONS:
        d = dict(zip(_KEYS, row))
        d["title"] = SECTIONS[d["section"]]
        out.append(d)
    return out


def session(session_id: str) -> dict | None:
    return next((s for s in sessions() if s["id"] == session_id), None)


def session_results(s: dict) -> list[dict]:
    """Per-student results for one sample session: deterministic from its id."""
    rnd = random.Random(s["id"])
    absent_n = len(NAMES) * (s["total"] - s["present"]) // s["total"]
    absent = set(rnd.sample(range(len(NAMES)), absent_n))
    corrected = set(rnd.sample([i for i in range(len(NAMES)) if i not in absent], min(s["corrections"], 3)))
    rows = []
    for i, name in enumerate(NAMES):
        roll = f"22i-{(i * 7 + 18) % 90 + 10:04d}"
        if i in absent:
            rows.append({"roll": roll, "name": name, "result": "absent", "score": None, "source": "face"})
        elif i in corrected:
            rows.append({"roll": roll, "name": name, "result": "present", "score": round(rnd.uniform(0.31, 0.39), 2), "source": "manual"})
        else:
            rows.append({"roll": roll, "name": name, "result": "present", "score": round(rnd.uniform(0.44, 0.79), 2), "source": "face"})
    return sorted(rows, key=lambda r: r["roll"])


def students() -> list[dict]:
    rnd = random.Random(11)
    missing, redo = {3, 9, 15}, {6}
    rows = []
    for i, name in enumerate(NAMES):
        section = "EDGE-A" if i % 3 != 2 else "DAA-B"
        state = "missing" if i in missing else "redo" if i in redo else "enrolled"
        rows.append({
            "roll": f"22i-{(i * 7 + 18) % 90 + 10:04d}", "name": name, "section": section, "state": state,
            "enrolled": None if state == "missing" else f"{rnd.randint(2, 28):02d} Sep 2026",
            "pct": rnd.choice([100, 96, 92, 88, 84, 81, 77, 72, 68, 61]),
        })
    return sorted(rows, key=lambda r: r["roll"])


DEVICES = [
    {"id": "d-91", "label": "Google Pixel 8", "registered": "03 Sep 2026", "last": "12 Nov 2026, 09:02", "active": True},
    {"id": "d-96", "label": "Samsung Galaxy A34", "registered": "21 Oct 2026", "last": "12 Nov 2026, 11:20", "active": True},
    {"id": "d-62", "label": "Pixel 6a (retired)", "registered": "14 Feb 2026", "last": "19 Jun 2026, 10:41", "active": False},
]

ACTIVITY = [
    ("12 Nov 2026, 11:21", "Attendance submitted", "DAA-B: 44 present of 54", "accepted"),
    ("12 Nov 2026, 11:19", "Session opened", "DAA-B: 54 templates released to Samsung Galaxy A34", "accepted"),
    ("12 Nov 2026, 09:03", "Attendance submitted", "EDGE-A: 41 present of 48", "accepted"),
    ("12 Nov 2026, 09:01", "Session opened", "EDGE-A: 48 templates released to Google Pixel 8", "accepted"),
    ("10 Nov 2026, 14:02", "Request rejected", "The phone's clock differed from the server's by more than two minutes", "rejected"),
    ("21 Oct 2026, 13:48", "Device registered", "Samsung Galaxy A34", "accepted"),
    ("19 Jun 2026, 11:05", "Device revoked", "Pixel 6a (retired)", "accepted"),
]

# ---- Evaluation (research) -------------------------------------------------
THRESHOLDS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
FAR = [9.8, 6.4, 3.9, 2.1, 0.9, 0.4, 0.2, 0.1, 0.05, 0.02, 0.0]
FRR = [0.4, 0.7, 1.1, 1.9, 3.4, 5.6, 8.2, 11.3, 13.9, 15.2, 15.8]
ACCEPT, REVIEW_LOW = 0.40, 0.30

# device, detect ms, embed ms, match ms (per photo, ~14 faces)
LATENCY = [("Google Pixel 8", 118, 142, 4), ("Samsung Galaxy A34", 196, 331, 6), ("Redmi Note 12", 241, 402, 7)]

PLACEMENT = [
    # name, p50 ms, uploaded per session, battery mAh, who sees what
    ("On the phone (current)", 186, "0 B of images", 14, "Templates are sent to the phone for one session"),
    ("Campus server", 241, "~7 KB of vectors", 9, "Query vectors leave the phone; templates stay on the server"),
    ("Cloud", 412, "~7 KB of vectors", 8, "Query vectors leave campus"),
]


def evaluation() -> dict:
    """SVG geometry for the two charts, computed here so the template stays declarative."""
    # Chart 1: error rate against match threshold
    W, H, L, R, T, B = 640, 296, 46, 56, 18, 42
    pw, ph, ymax = W - L - R, H - T - B, 16.0
    x = lambda t: L + (t - 0.20) / 0.50 * pw
    y = lambda v: T + ph - v / ymax * ph
    pts = lambda series: " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in zip(THRESHOLDS, series))
    step = pw / (len(THRESHOLDS) - 1)
    cols = []
    for i, t in enumerate(THRESHOLDS):
        cols.append({
            "x": round(x(t) - step / 2, 1), "w": round(step, 1),
            "tip": f"<b>Threshold {t:.2f}</b><br>False rejects <span class='mono'>{FRR[i]:.1f}%</span><br>False accepts <span class='mono'>{FAR[i]:.1f}%</span>",
            "cx": round(x(t), 1), "far_y": round(y(FAR[i]), 1), "frr_y": round(y(FRR[i]), 1),
        })
    err = {
        "W": W, "H": H, "L": L, "T": T, "pw": pw, "ph": ph, "bottom": T + ph,
        "frr": pts(FRR), "far": pts(FAR), "cols": cols,
        "xticks": [{"x": round(x(t), 1), "label": f"{t:.2f}"} for t in (0.20, 0.30, 0.40, 0.50, 0.60, 0.70)],
        "yticks": [{"y": round(y(v), 1), "label": f"{v}%"} for v in (0, 4, 8, 12, 16)],
        "accept_x": round(x(ACCEPT), 1),
        "band_x": round(x(REVIEW_LOW), 1), "band_w": round(x(ACCEPT) - x(REVIEW_LOW), 1),
        "frr_label": (round(x(0.425), 1), round(y(10.8), 1)),
        "far_label": (round(x(0.215), 1), round(y(9.0) - 12, 1)),
    }

    # Chart 2: latency per photo, stacked detect | embed | match with 2px gaps
    W2, L2, R2, rowh, top = 640, 142, 88, 46, 14
    plot = W2 - L2 - R2
    scale = plot / 800
    rows = []
    for i, (device, d, e, m) in enumerate(LATENCY):
        yy, cursor, segs = top + i * rowh, L2, []
        for n, (label, val) in enumerate((("Detect", d), ("Embed", e), ("Match", m)), 1):
            w = max(val * scale - 2, 2)
            segs.append({"n": n, "x": round(cursor, 1), "w": round(w, 1), "tip": f"<b>{device}</b><br>{label} <span class='mono'>{val} ms</span>"})
            cursor += val * scale
        rows.append({"device": device, "y": yy, "segs": segs, "total": d + e + m, "end": round(cursor + 8, 1)})
    lat = {
        "W": W2, "H": top + len(rows) * rowh + 28, "L": L2, "rows": rows, "gridh": top + len(rows) * rowh - 14,
        "ticks": [{"x": round(L2 + v * scale, 1), "label": str(v)} for v in (0, 200, 400, 600, 800)],
        "axis_y": top + len(rows) * rowh - 8,
    }
    return {"err": err, "lat": lat, "far": FAR, "frr": FRR, "thresholds": THRESHOLDS,
            "latency_rows": LATENCY, "placement": PLACEMENT}
