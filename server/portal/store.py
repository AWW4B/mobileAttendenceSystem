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
    pseudonym  TEXT UNIQUE NOT NULL,
    pw_salt    BLOB,                         -- student login; NULL = cannot sign in
    pw_hash    BLOB
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
    received_at  INTEGER NOT NULL,
    evidence_sha256  TEXT                    -- from the MEC receipt; NULL = no class photo kept
);
CREATE TABLE IF NOT EXISTS attendance (
    session_id  TEXT NOT NULL REFERENCES class_sessions(session_id) ON DELETE CASCADE,
    roll_no     TEXT NOT NULL REFERENCES students(roll_no) ON DELETE CASCADE,
    status      TEXT NOT NULL CHECK (status IN ('present', 'absent')),
    source      TEXT NOT NULL CHECK (source IN ('face', 'manual')),
    PRIMARY KEY (session_id, roll_no)
);
CREATE TABLE IF NOT EXISTS appeals (
    id            INTEGER PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES class_sessions(session_id) ON DELETE CASCADE,
    roll_no       TEXT NOT NULL REFERENCES students(roll_no) ON DELETE CASCADE,
    reason        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'accepted', 'rejected')),
    teacher_note  TEXT,
    created_at    INTEGER NOT NULL,
    resolved_at   INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_appeal ON appeals(session_id, roll_no) WHERE status = 'open';
"""

# Columns added after the first release: ALTER TABLE on databases created before them.
MIGRATIONS = [("students", "pw_salt", "BLOB"), ("students", "pw_hash", "BLOB"),
              ("class_sessions", "evidence_sha256", "TEXT")]

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
        with self._conn() as c:
            for table, col, decl in MIGRATIONS:
                if col not in {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

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

    def set_student_password(self, roll_no: str, password: str) -> bool:
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        salt = secrets.token_bytes(16)
        with self._conn() as c:
            return c.execute("UPDATE students SET pw_salt = ?, pw_hash = ? WHERE roll_no = ?",
                             (salt, _hash_pw(password, salt), roll_no)).rowcount > 0

    def verify_student(self, roll_no: str, password: str) -> sqlite3.Row | None:
        with self._conn() as c:
            row = c.execute("SELECT roll_no, name, pw_salt, pw_hash FROM students WHERE roll_no = ?",
                            (roll_no,)).fetchone()
        if row is None or row["pw_hash"] is None:
            hmac.compare_digest(_hash_pw(password, _DUMMY_SALT), _DUMMY_HASH)
            return None
        return row if hmac.compare_digest(_hash_pw(password, row["pw_salt"]), row["pw_hash"]) else None

    def get_student(self, roll_no: str) -> sqlite3.Row | None:
        with self._conn() as c:
            return c.execute("SELECT roll_no, name FROM students WHERE roll_no = ?", (roll_no,)).fetchone()

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
                       present_pseudonyms: set[str], evidence_sha256: str | None = None) -> tuple[bool, int, int]:
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
            c.execute("INSERT INTO class_sessions(session_id, section_id, taken_at, received_at, evidence_sha256)"
                      " VALUES (?,?,?,?,?)", (session_id, section_id, taken_at, int(time.time()), evidence_sha256))
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

    # ---- appeals --------------------------------------------------------
    def student_sessions(self, roll_no: str) -> list[sqlite3.Row]:
        """Every session of the student's sections with their status and latest appeal."""
        with self._conn() as c:
            return c.execute(
                """SELECT sec.title AS section, cs.session_id, cs.taken_at, a.status,
                          ap.status AS appeal_status, ap.reason, ap.teacher_note
                   FROM section_students ss
                   JOIN sections sec ON sec.id = ss.section_id
                   JOIN class_sessions cs ON cs.section_id = sec.id
                   JOIN attendance a ON a.session_id = cs.session_id AND a.roll_no = ss.roll_no
                   LEFT JOIN appeals ap ON ap.id = (SELECT MAX(id) FROM appeals
                                                    WHERE session_id = cs.session_id AND roll_no = ss.roll_no)
                   WHERE ss.roll_no = ? ORDER BY sec.title, cs.taken_at DESC""",
                (roll_no,),
            ).fetchall()

    def create_appeal(self, session_id: str, roll_no: str, reason: str) -> bool:
        """Only for a session where the student is marked absent; one open appeal at a time."""
        with self._conn() as c:
            row = c.execute("SELECT status FROM attendance WHERE session_id = ? AND roll_no = ?",
                            (session_id, roll_no)).fetchone()
            if row is None or row["status"] != "absent":
                return False
            try:
                c.execute("INSERT INTO appeals(session_id, roll_no, reason, created_at) VALUES (?,?,?,?)",
                          (session_id, roll_no, reason, int(time.time())))
            except sqlite3.IntegrityError:
                return False
        return True

    def open_appeal_count(self, teacher_id: int) -> int:
        with self._conn() as c:
            return c.execute(
                """SELECT COUNT(*) FROM appeals ap JOIN class_sessions cs ON cs.session_id = ap.session_id
                   JOIN sections sec ON sec.id = cs.section_id
                   WHERE ap.status = 'open' AND sec.teacher_id = ?""", (teacher_id,)).fetchone()[0]

    _APPEAL_SELECT = """SELECT ap.*, st.name, st.pseudonym, cs.section_id, cs.taken_at, cs.evidence_sha256,
                                sec.title AS section_title
                         FROM appeals ap JOIN students st ON st.roll_no = ap.roll_no
                         JOIN class_sessions cs ON cs.session_id = ap.session_id
                         JOIN sections sec ON sec.id = cs.section_id WHERE sec.teacher_id = ?"""

    def appeals_for(self, teacher_id: int) -> list[sqlite3.Row]:
        with self._conn() as c:
            return c.execute(self._APPEAL_SELECT + " ORDER BY ap.status != 'open', ap.created_at DESC",
                             (teacher_id,)).fetchall()

    def appeal(self, appeal_id: int, teacher_id: int) -> sqlite3.Row | None:
        with self._conn() as c:
            return c.execute(self._APPEAL_SELECT + " AND ap.id = ?", (teacher_id, appeal_id)).fetchone()

    def resolve_appeal(self, appeal_id: int, accept: bool, note: str) -> bool:
        """Accepting also marks the student present. False if the appeal was not open."""
        with self._conn() as c:
            row = c.execute("SELECT session_id, roll_no FROM appeals WHERE id = ? AND status = 'open'",
                            (appeal_id,)).fetchone()
            if row is None:
                return False
            c.execute("UPDATE appeals SET status = ?, teacher_note = ?, resolved_at = ? WHERE id = ?",
                      ("accepted" if accept else "rejected", note or None, int(time.time()), appeal_id))
        if accept:
            self.set_status(row["session_id"], row["roll_no"], "present")
        return True
