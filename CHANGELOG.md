# Changelog

All notable changes to **SpotMeter**. Dates are ISO (YYYY-MM-DD). Full per-commit
history is in the git tags (`v5.1.0` … `v7.0.0`).

## [7.0.0] — 2026-07-15

Major release: the in-battle panel is rebuilt on **Gameface** (modern HTML/CSS/JS),
retiring GUIFlash/Scaleform entirely. Built for **WoT 2.3.1.0**.

### Changed (headline: GUIFlash → Gameface)
- **The in-battle panel is now a Gameface overlay** (HTML/CSS/JS) hosted in a Wulf
  window, rendered through the `net.openwg.gameface` library instead of a
  Scaleform SWF. This permanently removes the `net.gambiter.*` AS3 class-collision
  class of bug (the v6.1.0 hybrid resolver only mitigated it): SpotMeter no longer
  ships any SWF, so nothing can collide with another GUIFlash mod's saved window
  positions. The whole spot-distance engine — minimap circle, view-range calc,
  picker, identical-tank grouping, hotkeys, config — is unchanged; only the panel's
  render layer was replaced.

### Added
- **New dependency: `net.openwg.gameface`** (free, MIT; already shipped in common
  modpacks). Required for the panel; without it the minimap circle and the numpad
  hotkeys still work.
- **Modern panel look** — transparent "glass" style, white text with green for the
  enabled loadout options, a subtle outline. Real CSS instead of GUIFlash `<font>`
  markup.
- **Drag the panel by its header**; the position is saved (survives battles and
  restarts).
- **Collapse arrow** — shrinks the panel to just the target line (picked vehicle +
  spot distance); the collapsed/expanded state is remembered.
- Clickable enemy rows (pick a target), loadout cells (toggle/cycle each), and the
  Auto-pick line, all through the Gameface model-command bridge.

### Removed
- The GUIFlash panel, the bundled `spotmeter_gf` fork, and its byte-identical
  `spotmeter_guiflash.swf`. No more shared `net.gambiter.*` classes ship at all.

### Fixed
- **Log noise** (reported by Aslain): benign status/lifecycle lines and the
  on-demand diagnostic dumps were logged at WARNING and looked like errors — they
  are now INFO. A normal session logs **zero WARNING/ERROR lines** from SpotMeter,
  and `module loaded` comes through INFO.

### Packaging / tooling
- `build_wotmod.py` ships the Gameface payload (`spotmeter_gfpanel.pyc` +
  `SpotMeterPanel.html` + the `res_map` JSON) — no SWF, no fork.
- `preflight.py` audits the new payload and validates the res_map ↔ layout-key ↔
  HTML consistency; the GUIFlash-resolver check is retired.
- Built for **WoT 2.3.1.0**.

## [6.1.0] — 2026-07-08

Garage configurator + quieter defaults. Scope agreed with Aslain.

### Fixed (GUIFlash coexistence — important)
- **SpotMeter no longer breaks other GUIFlash mods' saved window positions.**
  Our bundled panel library shipped a SWF that was a byte-identical copy of
  `gambiter.guiflash` and therefore declared the same AS3 classes
  (`net.gambiter.*`). With a real `gambiter.guiflash` also installed (any
  modpack), the duplicate class definitions collided in Scaleform and stopped
  another mod (e.g. RaJCeL's in-battle statistics) from saving its dragged
  position (reported/confirmed by Aslain). Fix: SpotMeter now **prefers a
  shared `gui.mods.gambiter` when present** — one definition of the classes, no
  collision, our components live on its shared canvas — and only falls back to
  the bundled fork when gambiter is absent (then nothing else defines those
  classes either). Our GUIFlash event handlers were also made fully
  exception-isolated so they can never break another mod's handler in the
  shared event chain.

### Added
- **In-game configurator** — when a mods-settings API is installed (Aslain's
  `aslainMenu`, fallback to izeberg's `ModsSettingsAPI` — both optional, the
  mod keeps working without either), SpotMeter registers a settings page:
  panel visibility (battle / garage), grouping of identical tanks, auto-hide,
  panel show/hide hotkey (supports key combos), minimap circle on/off, circle
  opacity, language (auto / EN / PL), plus the master mod toggle. Changes
  apply live and are mirrored into `spotmeter.json`.
- `showMinimapCircle` config switch — "panel only" mode without the minimap
  circle (e.g. alongside XVM's own circles).
- `panelToggleKeyset` — multi-key combo support for the panel toggle.
- **Auto-pick presets in the configurator** — the per-class loadouts applied
  when auto-pick turns on are editable as sub-options of the auto-pick
  checkbox. On Aslain's menu a **class dropdown** (light / medium / heavy /
  TD / SPG / default) switches which class the editor shows, re-rendering
  in place; pending edits per class are kept until Apply. On the plain
  izeberg menu a static two-section layout (light tanks / other classes)
  is used instead.
- **Full key mapping in the configurator** — every hotkey (picker, toggles,
  level cycling, diagnostics, reload) is rebindable; changes apply without
  a restart.

### Changed
- **The garage panel is gone** — everything it offered (panel visibility,
  loadout defaults, hotkey reference) lives in the configurator now, where it
  belongs. The SpotMeter panel is battle-only; PageDown toggles it in battle.
  With the panel went the whole lobby window/route watcher (the most fragile
  code in the mod) and the `garagePanel*` config keys (stale entries in old
  configs are ignored).
- **The battle panel starts hidden by default** (fresh installs only — an
  existing config keeps its values). PageDown still summons it; enable
  permanently in the configurator or the JSON. Response to modpack feedback:
  "the panel is in my way and I don't know how to turn it off".
- **Config lives in AppData now** — primary path
  `%APPDATA%/Wargaming.net/WorldOfTanks/mods/spotmeter/spotmeter.json`
  (survives modpack clean-installs). A legacy game-dir config is migrated
  automatically on first load; game-dir paths remain as read fallbacks.

### Changed (no chat output)
- **The mod never writes to game chat.** All former chat output is gone:
  picker/toggle/auto-pick/level confirmations (the battle panel already shows
  that state), the diagnostic-dump confirmations, and the live-mode block. On-
  demand diagnostics now go to `python.log` instead — **NumpadEnter** logs a
  one-shot status block (spot distance for all four states + picker/toggle/own-
  tank context), **NumpadStar** logs the enemy descriptor + VR breakdown.
- **Live mode removed** (the old Numpad9 auto-refreshing chat block) along with
  its config keys `overlayToggleKey` / `liveModeIntervalSec`. `overlayEnabled`
  now gates the on-demand NumpadEnter logging. The configurator's hotkey list
  drops the live-mode key accordingly (`_MSA_SETTINGS_VERSION` → 6).
- When no mods-settings menu is installed, the startup `python.log` line names
  the exact config path; the listing recommends a (free, optional) menu for
  solo installs that want in-game configuration.

### Hardening
- All client patches are now individually fault-isolated: the `Avatar.shootDualGun`
  wrapper guards the original call against signature drift (mirroring `shoot`),
  and each install step in `init()` (plugin / shoot / hangar lifecycle / reload
  hotkey) is wrapped so one failing hook can't abort the rest of startup.
- The ModsSettingsAPI read-back clamps every numeric setting to its valid range
  and tolerates non-list hotkey values, so a hand-edited or stale settings store
  can't feed bad data into the mod.
- **New offline pre-send gate** — `packaging/preflight.py` (one command) plus
  `packaging/PRESEND_CHECKLIST.md` automate the structural/consistency checks
  (py2.7 compile, config + i18n parity, dead-symbol scan, version consistency,
  portal char limits, `.wotmod` ZIP_STORED/payload audit) so every build is
  verified before it ships.

## [6.0.2] — 2026-06-11

Config quality-of-life after modpack tester feedback ("there's no config file
to edit"). Still targets **WoT 2.3.0.1** — no other changes.

### Added
- The mod now creates `mods/configs/spotmeter.json` with the defaults on first
  run when no config exists — so there is always a file to edit (modpack
  installs ship only the `.wotmod`). To start with the panel hidden, set
  `battlePanelEnabled` / `garagePanelEnabled` to `false` — PageDown still
  summons it on demand.

### Fixed
- The panel auto-restore now honours `battlePanelEnabled` / `garagePanelEnabled`
  — a "panel off by default" config is no longer force-summoned by window
  open/close events.
- No more AS3 `Error #1009` entries in `python.log` when the panel is hidden or
  refreshed alongside many other mods (reported by a modpack tester). The
  Python↔Flash component registries could desync across view load races —
  update/delete calls are now mirrored per view instance, and a stale view
  teardown no longer detaches a freshly loaded one.

## [6.0.1] — 2026-06-11

Built for **WoT 2.3.0.1** (client update needed no code changes — repackaged for
the new mods folder). Maintenance release after live testing in an Aslain-style
modpack.

### Fixed
- Garage panel auto-hide no longer reacts to other mods' overlays (mod-list
  button, notifications, chat, other GUIFlash views) — in a modpack the panel
  used to flicker and could stick hidden. It now hides only for real content
  screens (research / depot / profile / loadout) and modal dialogs, restores
  reliably, and still respects a manual PageDown hide.

### Removed
- The enemy-name marker (the `●`/`○` prefix on the picked target's nickname) —
  it never rendered reliably and the battle panel already shows the target.
  The mod now patches only two game classes (minimap circle + fire penalty),
  shrinking the conflict surface with other mods. The `pickerMarker` /
  `autoPickMarker` config keys are gone (leftover entries are ignored).

### Compatibility
- Verified alongside `gambiter.guiflash 0.6.3` + CHAMPi `expectedvehiclevalues`
  / `playerpanelpro` / `settingsgui` + poliroid `modslistapi` + `openwg.gameface`
  + izeberg `modssettingsapi` — no conflicts; the bundled GUIFlash fork coexists
  with the upstream library.

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
