"""Builds the shared design assets from one source of truth.

  python design/build_assets.py

Outputs (all committed, so nobody needs to run this to use the app):
  server/portal/templates/_icons.svg                   SVG sprite, included inline by the web portal
  design/icons.svg                                     the same sprite for design references
  android/app/src/main/res/drawable/ic_*.xml           Android vector drawables
  server/portal/static/fonts/*.ttf                     Albert Sans + JetBrains Mono (OFL)
  android/app/src/main/res/font/*.ttf                  the same two fonts for the app
  design/licenses/*-OFL.txt                            font licences

Icons live on a 24x24 grid, 1.5 stroke, round caps and joins. Every icon
is a list of primitives; they are flattened to one path so web and Android
draw exactly the same glyph.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_FONTS = ROOT / "Skills/impeccable-main/impeccable-main/ui/component-review/fonts"
WEB_STATIC = ROOT / "server/portal/static"
ANDROID_RES = ROOT / "android/app/src/main/res"


def f(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s or "0"


def line(x1, y1, x2, y2):
    return f"M{f(x1)} {f(y1)}L{f(x2)} {f(y2)}"


def poly(*pts):
    p = list(zip(pts[0::2], pts[1::2]))
    return "M" + "L".join(f"{f(x)} {f(y)}" for x, y in p)


def rect(x, y, w, h, r=0.0):
    if r <= 0:
        return f"M{f(x)} {f(y)}H{f(x + w)}V{f(y + h)}H{f(x)}Z"
    r = min(r, w / 2, h / 2)
    return (f"M{f(x + r)} {f(y)}H{f(x + w - r)}A{f(r)} {f(r)} 0 0 1 {f(x + w)} {f(y + r)}"
            f"V{f(y + h - r)}A{f(r)} {f(r)} 0 0 1 {f(x + w - r)} {f(y + h)}"
            f"H{f(x + r)}A{f(r)} {f(r)} 0 0 1 {f(x)} {f(y + h - r)}"
            f"V{f(y + r)}A{f(r)} {f(r)} 0 0 1 {f(x + r)} {f(y)}Z")


def circle(cx, cy, r):
    return (f"M{f(cx - r)} {f(cy)}A{f(r)} {f(r)} 0 1 0 {f(cx + r)} {f(cy)}"
            f"A{f(r)} {f(r)} 0 1 0 {f(cx - r)} {f(cy)}Z")


def dot(x, y):
    return f"M{f(x)} {f(y)}h.01"


ICONS: dict[str, list[str]] = {
    "mark": [rect(3.5, 3.5, 17, 17, 3.5), line(7.5, 9, 16.5, 9), line(7.5, 12.5, 12, 12.5),
             poly(12.4, 16.4, 14.2, 18.2, 17.6, 14.6)],
    "overview": [rect(4, 4, 6.5, 6.5, 1.5), rect(13.5, 4, 6.5, 6.5, 1.5),
                 rect(4, 13.5, 6.5, 6.5, 1.5), rect(13.5, 13.5, 6.5, 6.5, 1.5)],
    "sections": ["M12 3.5l9 5-9 5-9-5 9-5Z", "M3 12.5l9 5 9-5", "M3 16.5l9 5 9-5"],
    "students": [circle(9, 8.2, 3.2), "M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6", circle(17.2, 9, 2.4),
                 "M17.8 14.3c1.9.5 3.2 2.2 3.2 4.7"],
    "sessions": [rect(3.5, 5, 17, 15.5, 2.5), line(3.5, 10, 20.5, 10), line(8, 3, 8, 7), line(16, 3, 16, 7),
                 poly(9, 15, 11, 17, 15, 13)],
    "device": [rect(6.8, 2.5, 10.4, 19, 2.6), line(10.8, 18.5, 13.2, 18.5)],
    "shield": ["M12 3l7.5 2.7v6c0 4.6-3.2 8-7.5 9.3-4.3-1.3-7.5-4.7-7.5-9.3v-6L12 3Z", poly(9, 12, 11.2, 14.2, 15.4, 10)],
    "chart": ["M4 4v16h16", poly(7.5, 15.5, 11.5, 11, 14.5, 13.5, 19, 7.5)],
    "settings": [line(4, 7, 7.5, 7), line(12.5, 7, 20, 7), circle(10, 7, 2.5), line(4, 17, 11, 17),
                 line(16, 17, 20, 17), circle(13.5, 17, 2.5)],
    "search": [circle(11, 11, 6.5), line(16, 16, 20.5, 20.5)],
    "download": [line(12, 4, 12, 15), poly(7.5, 11, 12, 15.5, 16.5, 11), line(4.5, 19.5, 19.5, 19.5)],
    "upload": [line(12, 16, 12, 5), poly(7.5, 9.5, 12, 5, 16.5, 9.5), line(4.5, 19.5, 19.5, 19.5)],
    "check": [poly(5, 12.5, 10, 17.5, 19, 7)],
    "x": [line(6, 6, 18, 18), line(18, 6, 6, 18)],
    "minus": [line(6, 12, 18, 12)],
    "plus": [line(12, 5.5, 12, 18.5), line(5.5, 12, 18.5, 12)],
    "chevron-right": [poly(9, 5, 16, 12, 9, 19)],
    "chevron-left": [poly(15, 5, 8, 12, 15, 19)],
    "chevron-down": [poly(5, 9, 12, 16, 19, 9)],
    "arrow-left": [line(19, 12, 5, 12), poly(11, 6, 5, 12, 11, 18)],
    "camera": [rect(3.5, 7, 17, 12.5, 2.5), poly(8.5, 7, 9.8, 4.8, 14.2, 4.8, 15.5, 7), circle(12, 13.2, 3.2)],
    "alert": ["M12 4l9 15.5H3L12 4Z", line(12, 10, 12, 13.6), dot(12, 16.6)],
    "info": [circle(12, 12, 8.5), line(12, 11, 12, 16), dot(12, 8)],
    "logout": ["M10 4.5H6A1.5 1.5 0 0 0 4.5 6v12A1.5 1.5 0 0 0 6 19.5h4", poly(15, 8, 19, 12, 15, 16), line(19, 12, 9.5, 12)],
    "lock": [rect(5, 10.5, 14, 9.5, 2.2), "M8 10.5V8a4 4 0 0 1 8 0v2.5"],
    "refresh": ["M4.5 12a7.5 7.5 0 0 1 13-5", poly(17.5, 3.5, 17.5, 7, 14, 7), "M19.5 12a7.5 7.5 0 0 1-13 5",
                poly(6.5, 20.5, 6.5, 17, 10, 17)],
    "more": [dot(6, 12), dot(12, 12), dot(18, 12)],
    "filter": [line(4, 6.5, 20, 6.5), line(7, 12, 17, 12), line(10, 17.5, 14, 17.5)],
    "clock": [circle(12, 12, 8.5), poly(12, 7.5, 12, 12, 15.5, 14)],
    "face": ["M4 8V6a2 2 0 0 1 2-2h2", "M16 4h2a2 2 0 0 1 2 2v2", "M20 16v2a2 2 0 0 1-2 2h-2", "M8 20H6a2 2 0 0 1-2-2v-2",
             line(9, 10, 9, 11), line(15, 10, 15, 11), "M9.5 15c.7.7 1.5 1 2.5 1s1.8-.3 2.5-1"],
    "server": [rect(3.5, 4, 17, 6.5, 2), rect(3.5, 13.5, 17, 6.5, 2), dot(7.5, 7.25), dot(7.5, 16.75)],
    "pencil": ["M4 20l1-4L16.5 4.5a1.8 1.8 0 0 1 2.5 0l.5.5a1.8 1.8 0 0 1 0 2.5L8 19l-4 1Z", line(14.5, 6.5, 17.5, 9.5)],
    "user": [circle(12, 8.5, 3.5), "M4.5 20c0-4 3.4-6.5 7.5-6.5s7.5 2.5 7.5 6.5"],
    "wifi-off": [line(4, 4, 20, 20), "M8.5 16.2a5 5 0 0 1 7 0", dot(12, 19.5), "M5 12.4a10 10 0 0 1 3-2", "M19 12.4a10 10 0 0 0-5.6-3"],
    "cloud-up": ["M7 18.5a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 9.5a4.5 4.5 0 0 1-.5 9", poly(9.5, 14, 12, 11.5, 14.5, 14), line(12, 11.5, 12, 18)],
    "undo": [poly(8.5, 5, 4.5, 9, 8.5, 13), "M4.5 9H14a5.5 5.5 0 0 1 0 11h-3"],
}


def build_sprite(hidden: bool) -> str:
    attrs = 'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"'
    symbols = "\n".join(
        f'  <symbol id="i-{name}" viewBox="0 0 24 24"><path d="{"".join(parts)}" {attrs}/></symbol>'
        for name, parts in ICONS.items()
    )
    root = ('<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0" aria-hidden="true" '
            'style="position:absolute">' if hidden else '<svg xmlns="http://www.w3.org/2000/svg">')
    return root + "\n" + symbols + "\n</svg>\n"


def build_vector(parts: list[str]) -> str:
    return ('<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    android:width="24dp"\n    android:height="24dp"\n'
            '    android:viewportWidth="24"\n    android:viewportHeight="24">\n'
            '    <path\n        android:pathData="' + "".join(parts) + '"\n'
            '        android:strokeColor="#FF000000"\n        android:strokeWidth="1.5"\n'
            '        android:strokeLineCap="round"\n        android:strokeLineJoin="round" />\n'
            '</vector>\n')


def main() -> None:
    (WEB_STATIC / "fonts").mkdir(parents=True, exist_ok=True)
    (ANDROID_RES / "drawable").mkdir(parents=True, exist_ok=True)
    (ANDROID_RES / "font").mkdir(parents=True, exist_ok=True)
    (ROOT / "design/licenses").mkdir(parents=True, exist_ok=True)

    (ROOT / "server/portal/templates/_icons.svg").write_text(build_sprite(True), encoding="utf-8")
    (ROOT / "design/icons.svg").write_text(build_sprite(False), encoding="utf-8")
    for name, parts in ICONS.items():
        (ANDROID_RES / "drawable" / f"ic_{name.replace('-', '_')}.xml").write_text(build_vector(parts), encoding="utf-8")

    for ttf in ("albertsans", "jetbrainsmono"):
        src = SKILL_FONTS / f"{ttf}.ttf"
        shutil.copyfile(src, WEB_STATIC / "fonts" / f"{ttf}.ttf")
        shutil.copyfile(src, ANDROID_RES / "font" / f"{ttf}.ttf")
        shutil.copyfile(SKILL_FONTS / f"{ttf}-OFL.txt", ROOT / "design/licenses" / f"{ttf}-OFL.txt")
    print(f"{len(ICONS)} icons, 2 fonts written")


if __name__ == "__main__":
    main()
