# Product

**Rollbook** is face-recognition attendance for university teachers. A teacher photographs the class on an Android phone. Recognition runs on the phone, a campus server holds encrypted face templates, and a web portal records and presents attendance. Photos never leave the phone.

The name is a working title (a rollbook is the physical register teachers mark). It lives in two places only: `server/portal/templates/base.html` and `android/app/src/main/res/values/strings.xml`.

## Users

University professors and teaching staff: educated, experienced, comfortable with academic vocabulary, time-poor. Two real scenes:

- **The desk.** A professor at a laptop in daylight, reviewing a semester of attendance, correcting a mark, exporting a register, checking who is falling below the threshold. Dense, accurate, calm.
- **The lecture hall.** A professor at the front of a room, one hand on a phone, glancing, with a class waiting. Photograph, confirm who the app is unsure about, submit. Fast, forgiving, unmistakable.

## Surfaces

| Surface | Mode | Where it lives |
|---|---|---|
| Web portal | Operate | `server/portal/` (Jinja + static CSS/JS) |
| Android app | Operate | `android/` (Kotlin, Jetpack Compose, Material 3) |

## Modules

| Module | Web | Mobile | Backend |
|---|---|---|---|
| Sign in | yes | yes | built |
| Sections / overview | yes | yes | built |
| Attendance register, corrections, CSV export | yes | | built |
| Capture, on-device matching, review, submit | | yes | built |
| Upload queue | | yes | built (queue + worker) |
| Device and server settings | | yes | built |
| Sessions (list, detail) | preview | | not built |
| Students and face-template status | preview | | not built |
| Security (devices, activity log) | preview | | not built |
| Evaluation (accuracy, timing, placement) | preview | | not built |
| Settings (thresholds, policy, retention) | preview | | not built |

"Preview" modules render realistic sample data, are labelled "Sample data" in the interface, read and write nothing, and are wired in `server/portal/preview.py` and `preview_data.py`.

## Principles

1. **Exceptions over totals.** Attendance is mostly "present". The interface makes absence and uncertainty the loudest things on screen.
2. **Privacy is visible.** Say plainly what stays on the phone and what is stored, where a teacher would wonder.
3. **Precision and calm.** Hairlines, tabular figures, restrained colour, no decoration that does not carry meaning.
4. **Never trap the user.** Every correction can be undone; Back always steps out; nothing is lost on a dropped connection.
