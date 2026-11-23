# Edge Attendance (Android)

Teacher app. Faces are detected, aligned, embedded and matched **on the
phone**. The class photo is stored encrypted on the campus server for 30 days
as evidence for appeals. Recognition runs on this phone. Templates for one section are fetched from
the campus MEC per session, held in memory only, and wiped afterwards.

## Build

1. Install Android Studio (stable) and open this `android/` folder.
2. From the repo root, fetch the face model (the app build copies it in):
   ```bash
   .venv/Scripts/python enrollment/fetch_models.py
   ```
3. Generate the laptop's TLS certificate (the app pins it):
   ```bash
   cd server && ../.venv/Scripts/python scripts/gen_dev_cert.py <laptop-wifi-ip>
   ```
4. Let Gradle sync, plug in your phone (USB debugging on), press Run.

From a terminal (JDK 17 to 21; set `sdk.dir` in the git-ignored
`local.properties`):

```bash
./gradlew assembleDebug testDebugUnitTest
```

The APK lands in `app/build/outputs/apk/debug/`. If `models/w600k_mbf.onnx` is
missing the build still succeeds (with a warning) but the app cannot embed faces.

## Device requirements

The Device tab checks these and flags failures on the home screen. A failing
phone is not blocked; the teacher may still try.

| | Minimum | Recommended |
|---|---|---|
| Android | 8.0 (API 26) | 10+ (API 29) |
| CPU | 64-bit | 6+ cores |
| RAM | 3 GB | 4 GB+ |
| Rear camera | 8 MP | 12 MP+ with continuous autofocus |

Faces must be at least 60 px wide for the detector. At 12 MP and about 70 degrees
field of view a face is roughly 60 px wide at 8 m, so for rooms deeper than
about 8 m take two photos (front and back half) or use 2x zoom. The app always
captures at the camera's highest still resolution.

## Using it

1. Server settings on the login screen: `https://<laptop-ip>:8001` (portal)
   and `https://<laptop-ip>:8000` (MEC). Phone and laptop must be on the same Wi-Fi.
2. Sign in, pick a section, photograph the class (several photos for a big
   room), review, submit.
3. The MEC verifies the signed submission and returns a receipt. The app
   forwards it to the portal, or queues it if the portal is unreachable.

## Code map

| Package | What |
|---|---|
| `data/` | portal + MEC clients, Keystore device key, pinned TLS, receipt queue/worker |
| `face/` | ML Kit detection, similarity alignment, ONNX MobileFaceNet, transform + one-to-one matching |
| `ui/` | Compose screens, CameraX in-memory capture, ViewModel |

## Privacy measures in the app

- In-memory capture only, never saved to storage or the gallery. Bitmaps
  and crops are zeroed and recycled after use. The one kept class photo (most
  faces) stays in memory until submit or discard, then is sent with the signed
  submission as appeal evidence.
- `FLAG_SECURE` blocks screenshots and screen recording. Backup and
  device transfer are disabled.
- Templates are decoded into memory for one session and zeroed at the end.
  Faces that match nobody are dropped.
- Requests are signed by a non-exportable Android Keystore EC key. The MEC
  certificate is pinned.
- Research metrics (timings, face counts, battery) contain no biometric data.
