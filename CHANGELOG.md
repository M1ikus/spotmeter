# Changelog

All notable changes to **SpotMeter**. Dates are ISO (YYYY-MM-DD). Full per-commit
history is in the git tags (`v5.1.0` … `v6.0.0`).

## [6.0.0] — 2026-06-06

Built for **WoT 2.3.0.0**. Major release: adds on-screen panels, automatic target
selection and a full English/Polish UI on top of the v5.6 minimap-circle + picker core.

### Added
- **In-battle picker panel** — always-visible overlay listing every enemy tank with
  its view range (`VR=XXXm`). Identical tanks collapse into one row (`Dravec x5`).
  A *target* line shows the spot-distance of the picked tank, or your own tank when
  nothing is picked. Pick by clicking a row or with Numpad 2/8. Draggable; position
  is saved.
- **Garage pre-config panel** — set toggles and levels before battle with a live
  preview, and see the AUTO state at a glance.
- **PageDown** — context-aware show/hide for the panel (battle + garage). The hidden
  state persists across battles and garage tabs until you press PageDown again.
- **Auto-pick** (Numpad /) — continuously targets the nearest visible enemy.
  *Most-recent-action-wins*: a manual pick (Numpad 2/8) overrides auto, and turning
  auto on overrides a manual pick. Applies a per-class preset when enabled.
- **Optics / Vents / CVS as cyclable levels** (Numpad 6 / + / −) — set manually now
  that the 2.x server no longer transmits enemy equipment. CVS has three levels
  (off / standard / on-slot); optics and vents five each.
- **Auto-hide** — the panel hides while TAB/N is held in battle and while a WG window
  is open in the garage (research, equipment, ammo, consumables), then restores.
- **English + Polish UI** — language auto-detected from the WoT client (`pl` → Polish,
  otherwise English); override with `language` in the config.

### Changed
- Ships a private **GUIFlash fork** (`spotmeter_gf`) inside the `.wotmod` — no external
  `gambiter.guiflash` required; coexists with one if it is also installed.
- Enemy view range is now driven by the manual optics/vents/CVS levels instead of
  reading equipment from the vehicle descriptor (the 2.x server stopped sending it
  for enemies).
- Packaged for **WoT 2.3.0.0**.

### Fixed
- Panel no longer reappears on its own after being hidden with PageDown (minimap
  refreshes used to revive it).
- Garage performance: the window-watch skips tooltip churn and no longer writes
  per-event diagnostic logs that could cause stutter.

### Notes
- The minimap spot-distance circle (the original feature) is unchanged.
- Spot-distance may read slightly high — it intentionally over- rather than
  under-estimates; calibration is a known follow-up.

## Earlier versions

Condensed; see the git tags for the full history.

- **5.6.x** — two-stage VR model (BIA split from the crew-perks bundle onto Numpad 3),
  multi-line status block replacing chat spam, opt-in live mode, per-tank
  field-upgrade table (BETA), WoT 2.2.x compatibility.
- **5.3 – 5.5** — picker VR model calibrated empirically against the in-game UI.
- **5.x** — numpad picker layout (works with NumLock on or off), enemy picker, fire
  penalty, siege-mode handling, camo-net for your own tank.
- **early** — the core dynamic minimap spot-distance circle.
