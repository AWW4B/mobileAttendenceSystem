# mobileAttendenceSystem

Privacy-preserving, edge-based face attendance.
A teacher photographs the class. **Face recognition runs on the Android
phone**, a **campus MEC (laptop)** stores encrypted face templates, the
**online portal** records attendance, and **no image ever leaves the phone**.

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

## Setup (Windows, from the repo root)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r server/requirements.txt -r enrollment/requirements.txt
```

Run all tests:

```bash
cd server && ../.venv/Scripts/python -m pytest -q
```

## Run it

All server commands run from `server/`. Keys, databases and certificates go
to `server/data/`, which is git-ignored.

**1. Portal data.** Use demo data, or add your own:

```bash
../.venv/Scripts/python -m portal.cli demo
```

```bash
../.venv/Scripts/python -m portal.cli add-teacher teacher1 "Dr. Example"
../.venv/Scripts/python -m portal.cli add-section EDGE-A "Edge Computing A" teacher1
../.venv/Scripts/python -m portal.cli import-csv students.csv EDGE-A
```

`students.csv` has the columns `roll_no,name`.

**2. TLS certificate** for the laptop's Wi-Fi IP (find it with `ipconfig`):

```bash
../.venv/Scripts/python scripts/gen_dev_cert.py 192.168.1.20
```

**3. Start the portal and the MEC** (two terminals):

```bash
../.venv/Scripts/python -m uvicorn portal.app:create_app --factory --host 0.0.0.0 --port 8001 --ssl-keyfile data/tls/key.pem --ssl-certfile data/tls/cert.pem
```

```bash
../.venv/Scripts/python -m uvicorn mec_server.app:create_app --factory --host 0.0.0.0 --port 8000 --ssl-keyfile data/tls/key.pem --ssl-certfile data/tls/cert.pem
```

The teacher dashboard is at `https://<laptop-ip>:8001/`. In this prototype
the portal also runs on the laptop. In the design it is a separate online
service, and it shares no database with the MEC.

**4. Enroll faces.** Download the models, then upload embeddings from
`photos/<roll_no>/*.jpg`:

```bash
cd ../enrollment
../.venv/Scripts/python fetch_models.py
../.venv/Scripts/python enroll.py --photos photos --portal https://192.168.1.20:8001 --mec https://192.168.1.20:8000 --ca ../server/data/tls/cert.pem
```

Use `--dry-run` to check photo quality first. Delete the photos afterwards.

**5. Phone.** Open `android/` in Android Studio and run it on your phone.
See [android/README.md](android/README.md).

## Design and frontend

The web portal and the Android app share one design language. See [DESIGN.md](DESIGN.md) for the system and [PRODUCT.md](PRODUCT.md) for the modules.

- Web: server-rendered Jinja templates with a static stylesheet and a small script (`server/portal/templates`, `server/portal/static`). Modules whose backend is not built yet (Sessions, Students, Security, Evaluation, Settings) render clearly labelled **sample data** from `server/portal/preview_data.py`.
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
