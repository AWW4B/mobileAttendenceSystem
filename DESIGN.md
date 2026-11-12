# Design system

One visual language for the web portal and the Android app. Tokens are authored once in [`server/portal/static/css/tokens.css`](server/portal/static/css/tokens.css) and mirrored in [`android/.../ui/theme/`](android/app/src/main/java/com/edge/attendance/ui/theme). Change both together.

## Identity

A teacher's register: quiet paper, ink, hairline rules, one verdigris accent. Nothing is decorated; everything that is coloured is saying something.

- **Ground.** Cool neutrals with a trace of green, so the accent belongs to the page. No pure black, no pure white page.
- **One accent, verdigris.** Primary actions, links, selection, and "confirmed / present". It is deep enough to carry white text and is never used for decoration.
- **Two semantic colours, used only for attendance meaning.** Red is *absent*. Amber is *needs a look*. They never act as series colours in charts.
- **Depth through lines, not shadows.** Panels are hairline-bordered surfaces. The only shadow is on overlays (menus, dialogs, toasts, tooltips).
- **Exceptions over totals.** In the register, "present" is quiet text and "absent" is the tinted mark, because absence is what a professor scans for.

## Colour

| Role | Token | Light | Dark | Use |
|---|---|---|---|---|
| Canvas | `--paper` | `#F6F7F5` | `#0F1311` | page background |
| Surface | `--surface` | `#FFFFFF` | `#151A17` | panels, tables, inputs |
| Surface 2 | `--surface-2` | `#EFF1EE` | `#1A201C` | sidebar, table headers, quiet fills |
| Hairline | `--line` / `--line-strong` | `#E1E5DF` / `#C8CEC6` | `#262E29` / `#37433C` | dividers / control borders |
| Ink | `--ink` | `#161A17` | `#E8ECE7` | primary text |
| Ink 2 / 3 | `--ink-2` / `--ink-3` | `#454D45` / `#5F685F` | `#B5BDB4` / `#8F998F` | secondary / muted text |
| Accent | `--accent` | `#1B5E57` | `#72C4B8` | actions, links, present |
| Accent tint | `--accent-tint` | `#E5F0EE` | `#14302C` | selected, present fill |
| Absent | `--absent` on `--absent-tint` | `#A1313A` on `#FAEBEB` | `#F19A96` on `#3B1F20` | absent only |
| Review | `--review` on `--review-tint` | `#84560A` on `#F7EED8` | `#E4B862` on `#33290F` | needs a check |

All 36 text/background pairs pass WCAG AA (4.5:1) in both themes (checked by script, see Verification).

**Chart series** (`--c1 --c2 --c3`, fixed order, never cycled): `#14967E #D9722D #4A83CC` light, `#2FA28F #DD7332 #5E8FDB` dark. Brighter than the accent on purpose; validated for lightness band, chroma, colour-vision separation and 3:1 contrast against each surface. Dark mode is selected, not inverted.

## Type

**Albert Sans** (language) and **JetBrains Mono** (roll numbers, IDs, URLs, measurements). Both are SIL OFL variable fonts, bundled locally (`server/portal/static/fonts`, `android/.../res/font`; licences in [`design/licenses`](design/licenses)). Nothing is loaded from a CDN, which matters for a privacy-first product on a campus network.

| Role | Web | Android (sp) |
|---|---|---|
| Page title | 24/30, 620, -0.014em | `headlineMedium` 26/32, 620 |
| Section title | 16/22, 600 | `titleMedium` 16/24, 600 |
| Body | 14/21, 400 | `bodyLarge` 16/24 · `bodyMedium` 14/20 |
| Small / meta | 13/18 · 12/16 | `bodySmall` 12/16 |
| Button | 14, 540 | `labelLarge` 15/20, 560 |
| Chip | 12, 580 | `labelMedium` 12/16, 560 |
| Mono | 12.5 | `MonoBody` 13/18 |

Fixed scale (no fluid type in the product UI), ratio about 1.15. Body measure stays under 70ch.

## Space, shape, size

- **Space** is a 4px scale: 4 8 12 16 20 24 32 40 56. Tight groups, generous separation, more space above a heading than below.
- **Radius.** 4 (inputs inside dense tables) · 6 (web controls, chips) · 8–10 (panels) · 12 (mobile controls) · 16 (sheets). No pill buttons.
- **Controls.** Web 34px (28px compact, 40px on touch). Mobile buttons 52dp, all touch targets at least 48dp, rows at least 64–72dp.

## Components

Defined once; both platforms follow the same anatomy.

| Component | Web | Android |
|---|---|---|
| Button | `.btn` primary / default / danger / quiet | `PrimaryButton`, `SecondaryButton`, `TonalButton`, `QuietButton` |
| Status chip | `.chip.present / .review / .absent` | `StatusChip(kind)` |
| List row | `.table` row | `SectionRow`, `ReviewRow`, `SettingRow` |
| Group label | `.nav-label`, panel head | `GroupHeader` |
| Hairline | `border` 1px `--line` | `Hairline()` |
| Empty state | `.empty` (icon, title, steps) | `EmptyState` |
| Toast / snackbar | `.toast` with Undo | `SnackbarHost` |
| Dialog | `<dialog class="dlg">` | `AlertDialog` |
| Navigation | sidebar, rail below 1100px, top strip below 720px | Material 3 `NavigationBar` + system Back |

Every interactive component has default, hover, focus-visible, active (scale 0.97–0.98), disabled and, where relevant, loading and error states. Status is never colour alone: every chip and mark carries a word or letter.

## Motion

Crisp and short. Exponential ease-out `cubic-bezier(0.23, 1, 0.32, 1)`, 120ms for feedback, 180ms for state, 240ms for overlays. Only `transform` and `opacity` animate. No orchestrated page loads, nothing animates on a keyboard-initiated or high-frequency action. Overlays open from their trigger or centred (dialogs). `prefers-reduced-motion` and Android's "Remove animations" both collapse motion to an instant cut.

## Iconography

One set, generated from one source: [`design/build_assets.py`](design/build_assets.py) emits the web SVG sprite and the Android vector drawables from the same paths. 24px grid, 1.5 stroke, round caps and joins. Never emoji, never a glyph standing in for an icon.

## Layout

- **Web.** Application shell: sidebar, sticky top bar with breadcrumbs and account menu, content up to 1320px. Breakpoints: 1100px (sidebar becomes an icon rail), 720px (navigation becomes a top strip). Registers pin roll number, name and overall column; on phones only the name stays pinned. Print styles hide chrome so a register prints cleanly.
- **Android.** Tabs (Sections, Uploads, Device) share a bottom navigation bar; the flow (Capture, Review, Submitted) is full screen without it. Edge-to-edge with window insets. The camera screen is always dark.

## Data visualisation

Two form choices: error rates are a line chart on one axis (never dual-axis) with the review band and accept threshold marked, and per-phone timing is a stacked bar with 2px gaps. Legends always present, direct labels on the lines, a hover tooltip on every mark, and a "View as table" alternative under each chart.

## Where things live

| | Web | Android | Shared |
|---|---|---|---|
| Tokens | `server/portal/static/css/tokens.css` | `ui/theme/Color.kt`, `Type.kt`, `Theme.kt` | `DESIGN.md` |
| Components | `server/portal/static/css/portal.css` | `ui/components/Components.kt` | |
| Screens | `server/portal/templates/*.html` | `ui/screens/*.kt`, `ui/AppShell.kt` | |
| Behaviour | `server/portal/static/js/portal.js` | `ui/AttendanceViewModel.kt` | |
| Icons, fonts | `static/fonts`, `templates/_icons.svg` | `res/drawable/ic_*.xml`, `res/font` | `design/build_assets.py` |
| Mobile reference | | `design/mobile-reference/` | |

Regenerate icons and re-copy fonts with `python design/build_assets.py`.

## Verification (what was and was not checked)

Checked in a browser: every web page at desktop (1280), tablet (820) and phone (390) widths; light and dark; sign-in, empty and error states; the correction flow with undo; dialog, Escape and focus return; keyboard focus rings; chart rendering and hover markup; DOM-level accessibility audit (landmarks, names, headings, target sizes); contrast ratios for all token pairs; palette validation for chart colours.

Checked in a browser, as a **design reference only**: all mobile screens (`design/mobile-reference`). This is an approximation of Material 3, not the Android build.

**Not verified:** the Jetpack Compose code has not been compiled or run, because no Android SDK or JDK is installed on the development machine. Expect small fixes on first sync. Emulator checks owed: dark theme, font scale 1.3, predictive Back, and a physical phone for the camera, gestures and performance.
