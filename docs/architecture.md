# Architecture & privacy design

Teacher-led, one-to-many face attendance. **Recognition runs on the phone;
the campus MEC (site-edge laptop) stores templates and, for 30 days, the class
photo as encrypted appeal evidence. The portal never holds a photo.**

> Terminology: by the course taxonomy (Lecture 3/4), a laptop on campus
> Wi-Fi is a *cloudlet / site edge*. True ETSI MEC sits in the cellular
> RAN. This project uses the laptop as a MEC stand-in.

## Tiers

```
 ┌──────────── Online portal (:8001) ──────────┐
 │ teachers, students (name, roll no),         │
 │ sections, student ↔ pseudonym,              │   NO face data
 │ attendance records + teacher dashboard,     │
 │ student appeals (no photos stored)          │
 └─────────────────────────────────────────────┘
   │ access token (1 h)  │ one-time grant (15 min)   ▲ MEC-signed receipt
   │                     │ section + pseudonyms only │ (pseudonyms only, store-and-forward)
   ▼                     ▼                           │
 ┌────────────── Teacher phone (device edge) ──┐       ┌──────── MEC laptop (site edge, :8000) ──┐
 │ capture → detect → align → embed → match    │ TLS + │ templates by pseudonym only,            │
 │ photo + crops in RAM, wiped after upload    │ pinned│ transformed + AES-GCM encrypted         │
 │ templates in RAM for the session only       │◄─────►│ sessions, nonces, attendance, audit log │
 │ unmatched faces discarded                   │ cert  │ class photo, encrypted, 30 days (appeals)│
 │                                             │       │ NO names, NO roll numbers               │
 │ Keystore EC key signs every request         │       └──────────────────────────────────────────┘
 └─────────────────────────────────────────────┘
```

## Flows

**Enrollment (admin, on the laptop):** student photos → `enrollment/enroll.py`
→ same detector/aligner/embedder as the phone → averaged 512-d vector → looked
up by roll number to get the pseudonym → `PUT /admin/templates/{pseudonym}`.
Photos are then deleted.

**Taking attendance:**

1. Teacher logs in to the portal → access token.
2. First run: the app creates an EC P-256 key in Android Keystore and calls
   `POST /devices` on the MEC (signed with that key = proof of possession).
3. Teacher picks a section → `POST /sections/{id}/grant` → one-time grant
   (pseudonyms only) + roster with names (kept in app memory for display).
4. App calls `POST /sessions` on the MEC with the grant, signed by the device.
   MEC returns the section's templates, the transform parameters, and a nonce.
5. Teacher captures class photo(s). On the phone: detect all faces, align,
   embed, apply the transform, cosine-match one-to-one against the templates.
6. Teacher reviews (accepted / needs-review / unmatched), confirms.
7. App calls `POST /sessions/{id}/attendance` with the nonce and the list of
   present pseudonyms, signed. Optional `metrics` carry research timings.
   Optional `evidence` carries the class photo (JPEG, long edge up to 1600 px)
   and the face boxes with matched pseudonyms. The MEC validates it, stores the
   JPEG AES-GCM encrypted for 30 days and adds `evidence_sha256` to the receipt.
   The MEC verifies everything and returns a **receipt**: a JWT signed with
   the MEC's own Ed25519 key holding teacher, section, session, present
   pseudonyms and the evidence hash.
8. App forwards the receipt to the portal (`POST /api/attendance/receipts`).
   The portal checks the MEC signature, maps pseudonyms to students, marks
   the rest of the roster absent. If the portal is unreachable, the app
   queues the receipt (WorkManager) and retries; receipts are idempotent.
9. App wipes templates and image buffers after the upload. The teacher reviews or corrects
   attendance and exports CSV on the portal dashboard.

**Appeals:** a student signs in at `/student/login`, sees their sessions and,
for a session marked absent, files an appeal with a reason. The section's
teacher opens it on `/appeals/{id}`. The portal fetches the class photo from the
MEC as that teacher, checks its hash against the receipt, and shows it with
labelled face boxes. Accepting marks the student present; rejecting needs a
note. Without a photo, or with the MEC unreachable, the teacher can still
decide. Students never see the photo.

Why receipts: the portal never trusts the phone's claim directly, only the
MEC's verified result, and the MEC never needs a connection to the portal.
That suits a campus edge whose internet link may be intermittent.

## API summary

| Service | Endpoint | Auth | Purpose |
|---|---|---|---|
| portal | `POST /api/login` | password | access token |
| portal | `GET /api/sections` | access | teacher's sections |
| portal | `POST /api/sections/{id}/grant` | access | one-time grant + roster |
| portal | `POST /api/attendance/receipts` | MEC signature | record attendance |
| portal | `GET /api/admin/students/{roll}/pseudonym` | admin token | enrollment lookup |
| portal | `/login`, `/dashboard`, `/sections/{id}` | cookie | teacher web dashboard, corrections, CSV |
| portal | `/appeals`, `/appeals/{id}`, `/appeals/{id}/evidence.jpg`, `POST /appeals/{id}/resolve` | teacher cookie | review and resolve appeals |
| portal | `/student/login`, `/student`, `POST /student/appeals` | student cookie | student sign-in, status, appeal |
| mec | `POST /devices` | access + self-signature | register phone key |
| mec | `DELETE /devices/{id}` | access | revoke lost phone |
| mec | `POST /sessions` | grant + device signature | templates, transform, nonce |
| mec | `POST /sessions/{id}/attendance` | device signature + nonce | submit present list, get receipt |
| mec | `GET /sessions/{id}/attendance` | access | read back result + receipt |
| mec | `GET /sessions/{id}/evidence` | access (session owner) | class photo + face boxes, audited |
| mec | `PUT/DELETE /admin/templates/{p}` | admin token | enroll / remove template |
| mec | `POST /admin/transform/rotate` | admin token | revoke all templates |
| mec | `GET /admin/audit` | admin token | audit trail |

Signed requests: body is JSON with `device_id` and `timestamp` (±120 s);
header `X-Signature` = base64 DER of SHA256withECDSA over the **exact body
bytes**.

## Privacy controls

| Asset | Control |
|---|---|
| Photos on the phone | Never written to disk or gallery; `FLAG_SECURE`; buffers zeroed after upload; backup disabled (app side) |
| Photos on the MEC | Sent only as signed appeal evidence; AES-256-GCM with session-bound AAD; deleted after 30 days; only the owning teacher can read them (each read is audited); students never see them; the portal fetches them per request and does not store them |
| Bystander / unmatched faces | Embeddings discarded immediately; they appear only as unlabelled boxes in the stored photo |
| Templates at rest | Pseudonym-keyed; cancelable transform; AES-256-GCM with pseudonym-bound AAD; master key outside the DB |
| Templates in transit | TLS with certificate pinning; released only for one section, to a registered device, with a single-use grant |
| Templates on phone | RAM only, cleared at session end |
| Identity linkage | Names/roll numbers only in the portal DB; MEC only sees pseudonyms; the portal never holds vectors (verified by tests that scan both DB files) |
| Forged attendance | Portal accepts attendance only as MEC-signed receipts bound to teacher + section |
| Replay / forgery | One-time grants, per-session nonce, single submission, device signatures, timestamp window |
| Leak response | `POST /admin/transform/rotate` makes leaked templates useless without re-enrolling anyone |
| Accountability | Audit log of releases, submissions and rejections |
| Consent & deletion | Enroll only with consent; deleting a student removes their template |

## Threat model

| Threat | Mitigation |
|---|---|
| Lost / stolen teacher phone | Nothing cached; revoke device via `DELETE /devices/{id}`; tokens expire |
| MEC database copied | Encrypted + transformed + pseudonymous; photos encrypted under the master key; rotate transform |
| Insider browsing the DB | No names in MEC; audit log |
| Campus Wi-Fi MITM | TLS + pinned self-signed cert |
| Forged / modified app | Keystore signatures (Play Integrity is a planned addition) |
| Holding up a printed photo | Teacher review step; liveness = future work |
| Template inversion | Transform + no plaintext export path |

## Known limitations (state these in the report)

- Permutation + sign-flip is a lightweight cancelable transform. A full
  random orthogonal projection or homomorphic matching is stronger.
- The phone receives a section's templates during a session; a compromised
  phone could copy them. Moving matching to the MEC (query vectors instead
  of templates) is the alternative design, and comparing the two is the
  research question.
- Self-signed cert + dev admin token are for the prototype only.
- InsightFace model weights are non-commercial research use only.

## Research hooks

- `metrics` field on submission: detection/embedding/matching ms, faces
  found, battery, network RTT. Stored per session for analysis.
- Matching location (phone vs MEC), template caching, and transform
  strength are the experimental variables.
