"""Portal database: identities, sections and attendance records. NO face data.

The only link between a student and their face template is a random
pseudonym. The MEC knows pseudonym -> template; the portal knows
pseudonym -> name/roll number. Neither alone links a face to a person.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from pathlib import Path

from common.db import connect, init_schema

SCHEMA = """
CREATE TABLE IF NOT EXISTS teachers (
    id        INTEGER PRIMARY KEY,
    username  TEXT UNIQUE NOT NULL,
    name      TEXT NOT NULL,
    pw_salt   BLOB NOT NULL,
    pw_hash   BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS students (
    roll_no    TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    pseudonym  TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS sections (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    teacher_id  INTEGER NOT NULL REFERENCES teachers(id)
);
CREATE TABLE IF NOT EXISTS section_students (
    section_id  TEXT NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    roll_no     TEXT NOT NULL REFERENCES students(roll_no) ON DELETE CASCADE,
    PRIMARY KEY (section_id, roll_no)
);
-- One row per class session, created from a MEC-signed receipt.
CREATE TABLE IF NOT EXISTS class_sessions (
    session_id   TEXT PRIMARY KEY,           -- MEC session id
    section_id   TEXT NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    taken_at     INTEGER NOT NULL,           -- when the MEC verified it
    received_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS attendance (
    session_id  TEXT NOT NULL REFERENCES class_sessions(session_id) ON DELETE CASCADE,
    roll_no     TEXT NOT NULL REFERENCES students(roll_no) ON DELETE CASCADE,
    status      TEXT NOT NULL CHECK (status IN ('present', 'absent')),
    source      TEXT NOT NULL CHECK (source IN ('face', 'manual')),
    PRIMARY KEY (session_id, roll_no)
);
"""

# scrypt parameters (~16 MiB memory, fine for a laptop server)
_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def _hash_pw(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)


# Spend the same time on unknown usernames as on wrong passwords.
_DUMMY_SALT = secrets.token_bytes(16)
_DUMMY_HASH = _hash_pw("dummy-password", _DUMMY_SALT)


class PortalStore:
    def __init__(self, path: Path):
        self.path = path
        init_schema(path, SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return connect(self.path)

    # ---- teachers -------------------------------------------------------
    def add_teacher(self, username: str, name: str, password: str) -> int:
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        salt = secrets.token_bytes(16)
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO teachers(username, name, pw_salt, pw_hash) VALUES (?,?,?,?)",
                (username, name, salt, _hash_pw(password, salt)),
            )
            return int(cur.lastrowid)

    def verify_teacher(self, username: str, password: str) -> sqlite3.Row | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM teachers WHERE username = ?", (username,)).fetchone()
        if row is None:
            hmac.compare_digest(_hash_pw(password, _DUMMY_SALT), _DUMMY_HASH)
            return None
        if hmac.compare_digest(_hash_pw(password, row["pw_salt"]), row["pw_hash"]):
            return row
        return None

    def get_teacher(self, teacher_id: int) -> sqlite3.Row | None:
        with self._conn() as c:
            return c.execute("SELECT id, username, name FROM teachers WHERE id = ?", (teacher_id,)).fetchone()

    def teacher_id(self, username: str) -> int | None:
        with self._conn() as c:
            row = c.execute("SELECT id FROM teachers WHERE username = ?", (username,)).fetchone()
        return int(row["id"]) if row else None

    # ---- students -------------------------------------------------------
    def add_student(self, roll_no: str, name: str) -> str:
        pseudonym = secrets.token_urlsafe(16)
        with self._conn() as c:
            c.execute("INSERT INTO students(roll_no, name, pseudonym) VALUES (?,?,?)",
                      (roll_no, name, pseudonym))
        return pseudonym

    def pseudonym_for(self, roll_no: str) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT pseudonym FROM students WHERE roll_no = ?", (roll_no,)).fetchone()
        return row["pseudonym"] if row else None

    def remove_student(self, roll_no: str) -> str | None:
        """Delete a student. Returns the pseudonym so the caller can delete the MEC template."""
        pseudonym = self.pseudonym_for(roll_no)
        with self._conn() as c:
            c.execute("DELETE FROM students WHERE roll_no = ?", (roll_no,))
        return pseudonym

    # ---- sections -------------------------------------------------------
    def add_section(self, section_id: str, title: str, teacher_username: str) -> None:
        tid = self.teacher_id(teacher_username)
        if tid is None:
            raise ValueError(f"unknown teacher {teacher_username!r}")
        with self._conn() as c:
            c.execute("INSERT INTO sections(id, title, teacher_id) VALUES (?,?,?)", (section_id, title, tid))

    def enroll(self, section_id: str, roll_no: str) -> None:
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO section_students(section_id, roll_no) VALUES (?,?)",
                      (section_id, roll_no))

    def section(self, section_id: str, teacher_id: int) -> sqlite3.Row | None:
        with self._conn() as c:
            return c.execute("SELECT * FROM sections WHERE id = ? AND teacher_id = ?",
                             (section_id, teacher_id)).fetchone()

    def sections_for(self, teacher_id: int) -> list[sqlite3.Row]:
        with self._conn() as c:
            return c.execute(
                """SELECT s.id, s.title,
                          (SELECT COUNT(*) FROM section_students ss WHERE ss.section_id = s.id) AS student_count,
                          (SELECT COUNT(*) FROM class_sessions cs WHERE cs.section_id = s.id) AS session_count,
                          (SELECT MAX(taken_at) FROM class_sessions cs WHERE cs.section_id = s.id) AS last_taken_at
                   FROM sections s WHERE s.teacher_id = ? ORDER BY s.id""",
                (teacher_id,),
            ).fetchall()

    def roster(self, section_id: str, teacher_id: int) -> list[sqlite3.Row] | None:
        """Roster for a section owned by this teacher, or None if not theirs."""
        if self.section(section_id, teacher_id) is None:
            return None
        with self._conn() as c:
            return c.execute(
                """SELECT st.roll_no, st.name, st.pseudonym
                   FROM section_students ss JOIN students st ON st.roll_no = ss.roll_no
                   WHERE ss.section_id = ? ORDER BY st.roll_no""",
                (section_id,),
            ).fetchall()

    # ---- attendance -----------------------------------------------------
    def record_session(self, session_id: str, section_id: str, taken_at: int,
                       present_pseudonyms: set[str]) -> tuple[bool, int, int]:
        """Store a verified session: present for listed pseudonyms, absent for
        the rest of the roster. Idempotent on session_id.
        Returns (newly_recorded, present_count, absent_count)."""
        with self._conn() as c:
            if c.execute("SELECT 1 FROM class_sessions WHERE session_id = ?", (session_id,)).fetchone():
                return False, 0, 0
            roster = c.execute(
                """SELECT st.roll_no, st.pseudonym FROM section_students ss
                   JOIN students st ON st.roll_no = ss.roll_no WHERE ss.section_id = ?""",
                (section_id,),
            ).fetchall()
            c.execute("INSERT INTO class_sessions(session_id, section_id, taken_at, received_at) VALUES (?,?,?,?)",
                      (session_id, section_id, taken_at, int(time.time())))
            rows = [(session_id, r["roll_no"], "present" if r["pseudonym"] in present_pseudonyms else "absent",
                     "face") for r in roster]
            c.executemany("INSERT INTO attendance(session_id, roll_no, status, source) VALUES (?,?,?,?)", rows)
        present = sum(1 for r in rows if r[2] == "present")
        return True, present, len(rows) - present

    def sessions(self, section_id: str) -> list[sqlite3.Row]:
        with self._conn() as c:
            return c.execute(
                """SELECT cs.session_id, cs.taken_at,
                          SUM(a.status = 'present') AS present, COUNT(a.roll_no) AS total
                   FROM class_sessions cs LEFT JOIN attendance a ON a.session_id = cs.session_id
                   WHERE cs.section_id = ? GROUP BY cs.session_id ORDER BY cs.taken_at""",
                (section_id,),
            ).fetchall()

    def matrix(self, section_id: str) -> dict[tuple[str, str], sqlite3.Row]:
        """(roll_no, session_id) -> attendance row for a section."""
        with self._conn() as c:
            rows = c.execute(
                """SELECT a.* FROM attendance a JOIN class_sessions cs ON cs.session_id = a.session_id
                   WHERE cs.section_id = ?""",
                (section_id,),
            ).fetchall()
        return {(r["roll_no"], r["session_id"]): r for r in rows}

    def set_status(self, session_id: str, roll_no: str, status: str) -> bool:
        """Teacher correction from the dashboard."""
        with self._conn() as c:
            return c.execute(
                "UPDATE attendance SET status = ?, source = 'manual' WHERE session_id = ? AND roll_no = ?",
                (status, session_id, roll_no),
            ).rowcount > 0

    def session_section(self, session_id: str) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT section_id FROM class_sessions WHERE session_id = ?", (session_id,)).fetchone()
        return row["section_id"] if row else None
