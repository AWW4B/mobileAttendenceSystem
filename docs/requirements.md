# Model selection rules and device requirements

## Rules for choosing a face model

A model may run on the phone only if it passes every rule:

1. **Same file on both sides.** Enrollment (laptop) and the phone run the identical embedder file and preprocessing in [models/model_contract.json](../models/model_contract.json). A model that cannot run on both is rejected.
2. **Fits the edge budget on the minimum device** (below): embedder file <= 20 MB, <= 150 ms per face, whole class photo (40 faces) processed in <= 8 s, peak extra RAM <= 300 MB.
3. **Accuracy is judged in the low-compute class**, on IJB-C TAR at FAR = 1e-4 and LFW, from the paper or model card, and then on our own class photos (FAR/FRR at the contract thresholds).
4. **Runs offline** through ONNX Runtime (embedder) or a bundled ML Kit model (detector). No cloud inference.
5. **Licence fits the use.** Current options are research / non-commercial only; a product release needs a commercially licensed model.
6. **A swap is a migration, not a config change:** re-enroll every student, rotate the MEC transform (`POST /admin/transform/rotate`), and re-calibrate `accept_threshold` and `review_band` on real class photos.

## Current choice

| Stage | Model | Why |
|---|---|---|
| Detection (phone) | ML Kit face detection, bundled, landmark mode ALL | Offline, fast, Google-maintained, gives the five landmarks alignment needs |
| Detection (enrollment) | YuNet 2023mar (OpenCV Zoo, MIT) | Tiny, accurate, same five landmarks |
| Embedding (both) | MobileFaceNet `w600k_mbf.onnx` (InsightFace buffalo_sc), 512-d | Proven mobile embedder, ~13 MB, ONNX available, already wired end to end |
| Matching | Cosine, one-to-one greedy, accept >= 0.40, review 0.30–0.40 | One face per student, one student per face |

**Upgrade path:** EdgeFace-XS (Idiap, IEEE T-BIOM 2024): 1.77 M parameters, 154 MFLOPs, LFW 99.73 %, IJB-C 94.85 %; top model under 2 M parameters in the IJCB 2023 Efficient Face Recognition Competition. It needs an ONNX export and the migration in rule 6, and it is CC BY-NC (non-commercial) too. Not swapped in this prototype because it cannot be validated on a phone overnight.

## Minimum Android device

The app checks Android version, CPU, RAM and camera on the home screen (`DeviceCheck.kt`). Failing items are shown but do not block use.

| Item | Minimum (fail below) | Recommended (warn below) |
|---|---|---|
| Android version | 8.0 (API 26) | 10 (API 29) |
| CPU | 64-bit ARM (arm64-v8a) | 6+ cores |
| RAM | 3 GB | 4 GB |
| Storage | 150 MB free | — |
| Network | Campus Wi-Fi to the MEC at capture time | — |

## Camera requirements

| Item | Minimum | Recommended |
|---|---|---|
| Rear camera resolution | 8 MP (3264 x 2448) | 12 MP (4000 x 3000) or more |
| Focus | Autofocus | Continuous autofocus |
| Capture | Highest still resolution, quality mode (the app sets this) | — |

The detector needs faces at least **60 px wide**. A face is about 16 cm wide, so with a 12 MP camera and a ~70° field of view a face is about 60 px wide at 8 m. Rules for the teacher:

- Rooms deeper than about 8 m (12 MP) or 6 m (8 MP): take two photos (left half, right half) or use 2x zoom from the front.
- Shoot from the front at head height, room lights on, no strong window behind the class.
- Students face the camera; the review step catches the rest.
