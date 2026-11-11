"""Admin CLI for the portal (run from server/).

  python -m portal.cli init
  python -m portal.cli add-teacher <username> "<name>"          (prompts for password)
  python -m portal.cli add-student <roll_no> "<name>"
  python -m portal.cli add-section <id> "<title>" <teacher_username>
  python -m portal.cli enroll <section_id> <roll_no> [<roll_no> ...]
  python -m portal.cli import-csv <file.csv> <section_id>        (columns: roll_no,name)
  python -m portal.cli list <section_id> <teacher_username>
  python -m portal.cli demo                                      (teacher "demo", password "demo-password")
"""
from __future__ import annotations

import argparse
import csv
import getpass
import sys

from common.keys import load_or_create_admin_token, portal_signing_key
from common.settings import Settings

from .store import PortalStore

DEMO_STUDENTS = [("22i-0001", "Ayesha Khan"), ("22i-0002", "Bilal Ahmed"), ("22i-0003", "Sana Malik"),
                 ("22i-0004", "Usman Tariq"), ("22i-0005", "Hira Siddiqui")]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="portal.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("demo")
    t = sub.add_parser("add-teacher"); t.add_argument("username"); t.add_argument("name")
    t.add_argument("--password", help="omit to be prompted (recommended)")
    s = sub.add_parser("add-student"); s.add_argument("roll_no"); s.add_argument("name")
    sec = sub.add_parser("add-section"); sec.add_argument("id"); sec.add_argument("title"); sec.add_argument("teacher")
    e = sub.add_parser("enroll"); e.add_argument("section_id"); e.add_argument("roll_nos", nargs="+")
    c = sub.add_parser("import-csv"); c.add_argument("file"); c.add_argument("section_id")
    ls = sub.add_parser("list"); ls.add_argument("section_id"); ls.add_argument("teacher")
    args = p.parse_args(argv)

    settings = Settings.from_env()
    portal_signing_key(settings)
    load_or_create_admin_token(settings)
    store = PortalStore(settings.portal_dir / "portal.db")

    if args.cmd == "init":
        print(f"Initialised. Data dir: {settings.data_dir}")
    elif args.cmd == "demo":
        if store.teacher_id("demo") is None:
            store.add_teacher("demo", "Demo Teacher", "demo-password")
            store.add_section("EDGE-A", "Edge Computing (demo)", "demo")
        for roll, name in DEMO_STUDENTS:
            if store.pseudonym_for(roll) is None:
                store.add_student(roll, name)
            store.enroll("EDGE-A", roll)
        print("Demo data ready: login demo / demo-password, section EDGE-A with 5 students.")
        print("Enroll their faces with enrollment/enroll.py using folders named by roll number.")
    elif args.cmd == "add-teacher":
        pw = args.password or getpass.getpass("Password (min 8 chars): ")
        store.add_teacher(args.username, args.name, pw)
        print(f"Teacher {args.username} added.")
    elif args.cmd == "add-student":
        store.add_student(args.roll_no, args.name)
        print(f"Student {args.roll_no} added.")
    elif args.cmd == "add-section":
        store.add_section(args.id, args.title, args.teacher)
        print(f"Section {args.id} added.")
    elif args.cmd == "enroll":
        for r in args.roll_nos:
            store.enroll(args.section_id, r)
        print(f"Enrolled {len(args.roll_nos)} student(s) in {args.section_id}.")
    elif args.cmd == "import-csv":
        n = 0
        with open(args.file, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                roll, name = row["roll_no"].strip(), row["name"].strip()
                if store.pseudonym_for(roll) is None:
                    store.add_student(roll, name)
                store.enroll(args.section_id, roll)
                n += 1
        print(f"Imported {n} student(s) into {args.section_id}.")
    elif args.cmd == "list":
        tid = store.teacher_id(args.teacher)
        rows = store.roster(args.section_id, tid) if tid else None
        if rows is None:
            print("Section not found for that teacher.", file=sys.stderr)
            return 1
        for r in rows:
            print(f"{r['roll_no']}\t{r['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
