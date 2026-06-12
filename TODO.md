# TODO — planned for a future update

Backlog of known follow-ups. Updated 2026-06-06 after live testing in an
Aslain-style modpack (champi.expectedvehiclevalues + champi.settingsgui +
gambiter.guiflash 0.6.3 + poliroid.modslistapi + openwg.gameface + izeberg).

## Released

- **v6.0.2** (WoT 2.3.0.1) — **released 2026-06-11**: tag `v6.0.2` @ `4c7de8d`
  + GH release. Config auto-create on first run; auto-restore honours
  `battlePanelEnabled`/`garagePanelEnabled` ("panel off by default" works, PgDn
  still summons); GUIFlash fork hardened against Python↔AS3 registry desync
  (per-instance `_pushedAliases` guard on update/delete + stale `_dispose` no
  longer orphans a newer view) — kills the AS3 #1009 spam from OldSkool's log.
  Pending follow-through: send to Aslain + update the wgmods.net listing.
- **v6.0.1** (WoT 2.3.0.1) — **published 2026-06-11** to wgmods.net + sent to
  Aslain (by the author, outside git). Content = commit `8dbb2ca`: garage
  auto-hide rewrite + enemy-name-marker removal + 2.3.0.1 repackage. Git tag
  `v6.0.1` pinned to that commit; GH release carries artifacts rebuilt from it.

## v6.1.0 — IMPLEMENTED (pending in-game testing; not released)

Scope agreed with Aslain (2026-06-12). Goal: kill the "panel is in my way and I
don't know how to turn it off" complaints. **Code is in (2026-06-12), built +
installed locally (mods/2.3.0.1, alongside aslainMenu 1.1.2 + modslist 1.7.8 +
gameface 1.1.5). Remaining: in-game test matrix (no API / izeberg / aslainMenu),
README + PORTAL_LISTING (EN+PL) updates, release.** Plan below as implemented:

### 1. Panels default OFF
Flip `battlePanelEnabled` / `garagePanelEnabled` defaults to `false` (code
`DEFAULT_CONFIG` + shipped `spotmeter.json`). PgDn still summons; the minimap
circle stays default ON. Existing users keep their seeded config (true/true)
— only fresh installs start hidden. v6.0.2's enabled-flags work makes this
behave correctly.

### 2. ModsSettingsAPI integration (garage configurator)
Soft dependency — without any API installed everything keeps working (JSON +
numpad). Import pattern per Aslain (his fork first, izeberg fallback):
```python
g_modsSettingsApi = None; msa_templates = None
try:
    from gui.aslainMenu import g_modsSettingsApi, templates as msa_templates
except ImportError: pass
if g_modsSettingsApi is None:
    try:
        from gui.modsSettingsApi import g_modsSettingsApi, templates as msa_templates
    except ImportError: pass
```
- Linkage `'spotmeter'`, `settingsVersion: 1`, labels via our `_t()` (PL/EN).
- Register: `setModTemplate(linkage, template, onModSettingsChanged)` — seed
  template values from `_CFG`; returned saved settings (MSA's copy) override
  the exposed subset; mirror every change back into our JSON (`_write_config`)
  so the file stays the single human-readable truth.
- Controls v1 (tight): master `enabled` (soft-disable: hide circle+panels,
  ignore keys, live), checkboxes `battlePanelEnabled` / `garagePanelEnabled` /
  `autoHidePanelOnWindow` / `battlePanelGroupSameTanks` / **`showMinimapCircle`
  (NEW key — the long-deferred panel-only opt-out, guards the circle entry)**,
  hotkey `panelToggleKey` (value = list of BigWorld key codes — needs mapping
  to/from our `'KEY_PGDN'` string; press-detect via `checkKeyset` when MSA
  present, plain key compare otherwise), dropdown `language` (auto/en/pl ->
  index), slider `alpha` (circle opacity).
- Apply live in `onModSettingsChanged` (filter by linkage): update `_CFG`,
  `_write_config()`, show/hide panels per flags + context, add/remove circle,
  rebind hotkey, re-create panels on language change.
- Fork-only extras guarded with `hasattr` (izeberg-compatible per Aslain):
  `templates.createControlsGroup` to indent panel sub-options (fallback: flat
  list). Skip image/live-change extras in v1.
- Test matrix: no API at all / izeberg 1.7.x (already in our test pack) /
  aslainMenu 1.1.2 (1.1.3 imminent — Aslain says 1.1.2 is OK to test against).
  Need the aslainMenu .wotmod from Aslain or his repo releases.

### 3. Config in AppData (Aslain's recommendation)
New primary path: `%APPDATA%/Wargaming.net/WorldOfTanks/mods/spotmeter/spotmeter.json`
(CHAMPi-style; survives modpack clean-installs that wipe the game dir).
- Read order: AppData -> `./mods/configs/spotmeter.json` (legacy) ->
  `./res_mods/configs/` (legacy) -> defaults.
- Migration: AppData missing + legacy found -> load legacy, write AppData copy.
- All writes (incl. v6.0.2 first-run seed) target AppData; `os.environ['APPDATA']`
  missing -> fall back to `./mods/configs`.
- Update the garage-panel footer string + README/INSTALL (they say "edit
  mods/configs/spotmeter.json").

### 4. Docs
README section "Konfigurator w garażu", PORTAL_LISTING + INSTALL (soft-dep
note: works standalone; integrates with ModsSettingsAPI / Aslain's menu when
present), CHANGELOG `[6.1.0]`.

Reference sources downloaded to `research/msa/` (izeberg api/templates/example
+ aslainMenu fork example/templates/README).

## Optional / low priority

### Isolate the GUIFlash fork's AS3 namespace
Our SWF's AS3 classes are still `net.gambiter.*` (same as upstream). **Coexistence
empirically confirmed OK (2026-06-06):** gambiter.guiflash 0.6.3 and our fork both
initialised and both rendered their views in the same session — zero AS3 errors,
because the two SWFs are byte-identical (no version skew). So this is now *optional
hygiene*, NOT a needed fix. Only becomes relevant if gambiter ever ships a
*different* `GUIFlash.swf` while ours stays pinned AND WoT loads both into a shared
ApplicationDomain.

**NOT a simple edit — and risky.** `spotmeter_guiflash.swf` is a byte-identical
PASS-THROUGH COPY of gambiter's `GUIFlash.swf` (swf/build.py, `pass_through=True`),
not built from source here. Renaming the AS3 package means re-emitting the SWF's
ABC, and our only Flash tool (FFDec) ALREADY produced AVM2-verifier-failing bytecode
when we tried to patch this exact SWF (the click-listener attempt **crashed WoT** —
that's literally why it's a verbatim copy now). Safe path = clean Adobe/Apache Flex
compile of CH4MPi's full GUIFlash source (github.com/CH4MPi/GUIFlash) with packages
renamed, then heavy in-game testing. High effort + real crash risk for a doubly-
hypothetical payoff. **Do NOT attempt unless gambiter actually diverges AND
coexistence visibly breaks.**

### Calibrate the camo / spot-distance estimate
Values run slightly HIGH (we over-estimate the range from which we get spotted).
User prefers over- to under-estimate, so left as-is. Revisit `_compute_camo` /
`_compute_spot_radius` + the crew/equipment camo factors.

### Opt-out flag: showMinimapCircle (panel-only mode)
A config flag (default true) to disable our minimap spot-distance circle while
keeping the panels — a real "panel only" mode for XVM users / Aslain when our circle
would overlap XVM's own view-range circles. Safe + small (guard the circle-entry
creation behind the flag, ~15 lines, no SWF/AS3 risk). Considered for v6.0.1,
deferred (user: keep documented). The companion `enemyNameMarker` flag is moot now
(the name marker was removed in v6.0.1).

### Test specifically with XVM
The 2026-06-06 modpack test did NOT include XVM itself (only champi/gambiter/
poliroid/gameface/izeberg - including champi.playerpanelpro, an XVM-ears
equivalent, which coexisted cleanly). XVM-specific interaction still untested:
our minimap circle (native `VIEW_RANGE_CIRCLES`) may visually overlap XVM's own
circles. Non-crashing by analysis; optional opt-out flag `showMinimapCircle` if
it ever matters. (The other XVM concern - the enemy-name marker - is GONE: the
`PlayerFullNameFormatter` patch was removed in v6.0.1.)

## Bigger / future projects

### Native AS3 IView panels — drop GUIFlash
**Realisation 2026-06-06:** native AS3 IView SWFs DO work on WoT 2.x — proof: the
gambiter `GUIFlash.swf` we already ship is one, and Aslain ships native-AS3 mods.
Our old "native rejected by WG's IView contract" belief was almost certainly a
TOOLCHAIN problem, not a platform limit: we built our custom SWFs with **FFDec**
(a decompiler), whose AS3 recompile emits AVM2-verifier-failing bytecode
(documented crash in swf/build.py). We NEVER tried a real compiler.

Proper native path = **Apache Flex SDK / `mxmlc`** (free) or Adobe Animate ->
clean verifier-passing SWF, + a correct IView (skeleton `AbstractView.as` already
in `swf/src`) + in-game testing. Payoff: removes the GUIFlash dependency and its
client-update fragility (our most brittle layer; Aslain's reason for going native).
Big opt-in rewrite of the panel layer — good v6.1/v7 candidate. Do NOT rewrite the
working v6.0.x pre-emptively. (Aslain's native AS3 mod = reference.)
