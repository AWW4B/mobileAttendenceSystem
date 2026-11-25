# mobileAttendenceSystem

Privacy-preserving, edge-based face attendance.
A teacher photographs the class. **Face recognition runs on the Android
phone**, a **campus MEC (laptop)** stores encrypted face templates, the
**online portal** records attendance. The class photo is kept encrypted on the
MEC for 30 days as evidence for student appeals, and never stored on the portal.

See [docs/architecture.md](docs/architecture.md) for the design, privacy
controls and threat model.

## Components and branches

| Folder | Component | Developed on |
|---|---|---|
| `server/common/` | shared keys, tokens, settings | `main` |
| `server/portal/` | online attendance portal: API + teacher web dashboard | `feature/portal` |
| `server/mec_server/`, `enrollment/` | campus MEC + face enrollment | `feature/mec` |
| `android/` | mobile edge app (Kotlin, Compose) | `feature/mobile` |
| `models/` | model contract shared by phone and laptop | `main` |
| `design/` | icon + font build, mobile design reference, font licences | frontend redesign |
| `server/tests/test_integration.py` | end-to-end test across portal + MEC | `main` |

## Set up a server on any Windows PC

Needs [Git](https://git-scm.com) and [Python](https://www.python.org/downloads/) 3.10 or newer.

```powershell
git clone https://github.com/AWW4B/mobileAttendenceSystem
```

```powershell
cd mobileAttendenceSystem
```

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

`setup.ps1` creates the Python environment, installs the packages, downloads the
two face models, creates your teacher account and opens the firewall (when run
as administrator; otherwise it prints the command). Add `-Demo` for a demo
teacher (`demo` / `demo-password`) with five students.

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

The portal opens at `https://localhost:8001` (accept the self-signed certificate
warning). On the phone, open **Server settings** on the sign-in screen and enter
the portal address, campus server address and **server code** that `start.ps1`
prints. The phone and PC must be on the same network.

**The app (APK).** One APK works with any server through the server code. To
build it, install Android Studio (for the Android SDK) and a JDK 17 to 21, then:

```powershell
powershell -ExecutionPolicy Bypass -File .\build-apk.ps1
```

Run all tests:

```powershell
cd server; ..\.venv\Scripts\python -m pytest -q
```

## Using it

**1. In the portal,** open **Students**: create a section, add students, and
upload any number of photos per student (or in bulk, with filenames starting
with the roll number, e.g. `22i-0001_2.jpg`). Photos are turned into a template
and discarded.

**2. On the phone,** sign in, pick the section, photograph, review, submit. An
open portal tab shows the new session within a few seconds.

Students sign in at `/student/login` (roll number + password, set on the
Students page) to appeal an absence. Teachers resolve appeals under **Appeals**
with the class photo. Match thresholds are under **Settings**.

**Different networks:** install Tailscale on the PC and phone, run
`.\start.ps1 -Ip <PC Tailscale address>`, and enter the printed addresses and
server code in the app.

`enrollment/enroll.py` remains for command-line enrollment from
`photos/<roll_no>/` folders.

## Design and frontend

The web portal and the Android app share one design language. See [DESIGN.md](DESIGN.md) for the system and [PRODUCT.md](PRODUCT.md) for the modules.

- Web: server-rendered Jinja templates with a static stylesheet and a small script (`server/portal/templates`, `server/portal/static`).
- Android: Jetpack Compose, Material 3 themed with the same tokens (`android/.../ui/theme`, `ui/components`, `ui/screens`).
- Mobile design reference, viewable without Android tooling. From the repo root:

```bash
python -m http.server 8012
```

Then open `http://127.0.0.1:8012/design/mobile-reference/index.html` (clickable flow) or add `?all=1` to see every screen.

- Regenerate icons and copy fonts: `python design/build_assets.py`.

## Models

`enrollment/fetch_models.py` downloads YuNet (OpenCV Zoo, MIT) and
MobileFaceNet `w600k_mbf.onnx` (InsightFace `buffalo_sc`, non-commercial
research licence). The phone and the laptop run the **same** embedder file
and follow [models/model_contract.json](models/model_contract.json).
