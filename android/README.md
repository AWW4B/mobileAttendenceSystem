# Edge Attendance (Android)

Teacher app. Faces are detected, aligned, embedded and matched **on the
phone**; photos never leave it. Templates for one section are fetched from
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

There is no committed `gradlew` script. Android Studio uses
`gradle/wrapper/gradle-wrapper.properties` directly. To build from a
terminal, run `gradle wrapper` once from this folder.

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
  and crops are zeroed and recycled after use.
- `FLAG_SECURE` blocks screenshots and screen recording. Backup and
  device transfer are disabled.
- Templates are decoded into memory for one session and zeroed at the end.
  Faces that match nobody are dropped.
- Requests are signed by a non-exportable Android Keystore EC key. The MEC
  certificate is pinned.
- Research metrics (timings, face counts, battery) contain no biometric data.
