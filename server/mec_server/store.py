"""MEC database. Holds no images, names or roll numbers: pseudonyms only."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from common.db import connect, init_schema

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS templates (
    pseudonym          TEXT PRIMARY KEY,
    transform_version  INTEGER NOT NULL,
    nonce              BLOB NOT NULL,
    ciphertext         BLOB NOT NULL,
    updated_at         INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS devices (
    device_id       TEXT PRIMARY KEY,
    teacher_sub     TEXT NOT NULL,
    public_key_pem  TEXT NOT NULL,
    label           TEXT,
    registered_at   INTEGER NOT NULL,
    revoked         INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS used_grants (
    jti         TEXT PRIMARY KEY,
    expires_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    teacher_sub   TEXT NOT NULL,
    section_id    TEXT NOT NULL,
    device_id     TEXT NOT NULL REFERENCES devices(device_id),
    nonce         TEXT NOT NULL,
    allowed       TEXT NOT NULL,          -- JSON list of pseudonyms from the grant
    created_at    INTEGER NOT NULL,
    expires_at    INTEGER NOT NULL,
    submitted_at  INTEGER,
    metrics       TEXT,                   -- JSON, research measurements from the phone
    receipt       TEXT                    -- MEC-signed receipt for the portal
);
CREATE TABLE IF NOT EXISTS attendance (
    session_id  TEXT NOT NULL REFERENCES sessions(session_id),
    pseudonym   TEXT NOT NULL,
    PRIMARY KEY (session_id, pseudonym)
);
CREATE TABLE IF NOT EXISTS audit (
    id      INTEGER PRIMARY KEY,
    ts      INTEGER NOT NULL,
    actor   TEXT NOT NULL,
    action  TEXT NOT NULL,
    detail  TEXT NOT NULL
);
"""


class MecStore:
    def __init__(self, path: Path):
        self.path = path
        init_schema(path, SCHEMA)
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('transform_version', '1')")

    def _conn(self) -> sqlite3.Connection:
        return connect(self.path)

    # ---- meta ------------------------------------------------------------
    def transform_version(self) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT value FROM meta WHERE key='transform_version'").fetchone()[0])

    # ---- audit -----------------------------------------------------------
    def audit(self, actor: str, action: str, **detail) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO audit(ts, actor, action, detail) VALUES (?,?,?,?)",
                (int(time.time()), actor, action, json.dumps(detail, sort_keys=True)),
            )

    def audit_tail(self, limit: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]

    # ---- templates -------------------------------------------------------
    def put_template(self, pseudonym: str, version: int, nonce: bytes, ct: bytes) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO templates(pseudonym, transform_version, nonce, ciphertext, updated_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(pseudonym) DO UPDATE SET transform_version=excluded.transform_version,
                     nonce=excluded.nonce, ciphertext=excluded.ciphertext, updated_at=excluded.updated_at""",
                (pseudonym, version, nonce, ct, int(time.time())),
            )

    def delete_template(self, pseudonym: str) -> bool:
        with self._conn() as c:
            return c.execute("DELETE FROM templates WHERE pseudonym = ?", (pseudonym,)).rowcount > 0

    def get_templates(self, pseudonyms: list[str]) -> list[sqlite3.Row]:
        if not pseudonyms:
            return []
        marks = ",".join("?" * len(pseudonyms))
        with self._conn() as c:
            return c.execute(f"SELECT * FROM templates WHERE pseudonym IN ({marks})", pseudonyms).fetchall()

    def all_templates(self) -> list[sqlite3.Row]:
        with self._conn() as c:
            return c.execute("SELECT * FROM templates").fetchall()

    def rotate(self, new_version: int, rows: list[tuple[str, bytes, bytes]]) -> None:
        """Atomically replace every template and bump the transform version."""
        now = int(time.time())
        with self._conn() as c:
            for pseudonym, nonce, ct in rows:
                c.execute(
                    "UPDATE templates SET transform_version=?, nonce=?, ciphertext=?, updated_at=? WHERE pseudonym=?",
                    (new_version, nonce, ct, now, pseudonym),
                )
            c.execute("UPDATE meta SET value=? WHERE key='transform_version'", (str(new_version),))

    # ---- devices ---------------------------------------------------------
    def add_device(self, device_id: str, teacher_sub: str, public_key_pem: str, label: str | None) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO devices(device_id, teacher_sub, public_key_pem, label, registered_at) VALUES (?,?,?,?,?)",
                (device_id, teacher_sub, public_key_pem, label, int(time.time())),
            )

    def get_device(self, device_id: str) -> sqlite3.Row | None:
        with self._conn() as c:
            return c.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()

    def revoke_device(self, device_id: str, teacher_sub: str) -> bool:
        with self._conn() as c:
            return c.execute(
                "UPDATE devices SET revoked=1 WHERE device_id=? AND teacher_sub=?", (device_id, teacher_sub)
            ).rowcount > 0

    # ---- grants & sessions ----------------------------------------------
    def consume_grant(self, jti: str, expires_at: int) -> bool:
        """Mark a grant as used. False if it was already used (replay)."""
        with self._conn() as c:
            c.execute("DELETE FROM used_grants WHERE expires_at < ?", (int(time.time()),))
            try:
                c.execute("INSERT INTO used_grants(jti, expires_at) VALUES (?,?)", (jti, expires_at))
            except sqlite3.IntegrityError:
                return False
        return True

    def create_session(self, *, session_id: str, teacher_sub: str, section_id: str, device_id: str,
                       nonce: str, allowed: list[str], expires_at: int) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO sessions(session_id, teacher_sub, section_id, device_id, nonce, allowed,
                                        created_at, expires_at) VALUES (?,?,?,?,?,?,?,?)""",
                (session_id, teacher_sub, section_id, device_id, nonce, json.dumps(allowed),
                 int(time.time()), expires_at),
            )

    def get_session(self, session_id: str) -> sqlite3.Row | None:
        with self._conn() as c:
            return c.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()

    def submit(self, session_id: str, present: list[str], metrics: dict | None, receipt: str) -> bool:
        """Record attendance once. False if the session was already submitted."""
        with self._conn() as c:
            cur = c.execute(
                """UPDATE sessions SET submitted_at=?, metrics=?, receipt=?
                   WHERE session_id=? AND submitted_at IS NULL""",
                (int(time.time()), json.dumps(metrics) if metrics else None, receipt, session_id),
            )
            if cur.rowcount == 0:
                return False
            c.executemany(
                "INSERT INTO attendance(session_id, pseudonym) VALUES (?,?)",
                [(session_id, p) for p in present],
            )
        return True

    def present_for(self, session_id: str) -> list[str]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT pseudonym FROM attendance WHERE session_id = ? ORDER BY pseudonym", (session_id,)
            ).fetchall()
        return [r["pseudonym"] for r in rows]
