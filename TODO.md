# TODO — planned for a future update

Backlog of known follow-ups. None block v6.0.0 (already released) — collected here
so the next update has a clear checklist.

## 1. Isolate the GUIFlash fork's AS3 namespace  (priority — mod coexistence)

The fork is renamed on the Python/WoT layer (`gui.mods.spotmeter_gf`, `g_smGuiFlash`,
view alias `SpotMeterGuiFlashView`, file `spotmeter_guiflash.swf`) — verified clean.
BUT the SWF's AS3 document class is still **`net.gambiter.FlashUI`**, the same as
upstream gambiter.guiflash. If a user also has `gambiter.guiflash_0.6.x.wotmod`
installed (other mods still ship/use it), both SWFs declare the same AS3 class.

- **Risk:** conflict ONLY if WoT loads view SWFs into a *shared* ApplicationDomain
  (first-loaded class wins → 0.6.3 vs our 0.6.4 version skew → one panel may break).
  Per-view *isolated* domain → no problem.
- **Test first** — Aslain has the environment: `gambiter.guiflash_0.6.3` + a mod that
  uses it + ours; enter battle & garage, confirm BOTH UIs render, watch `python.log`
  for AS3/Flash errors. (We can't test locally — no mods on this machine.)
- **Fix if confirmed:** change `'package': 'net.gambiter'` → `'net.spotmeter'` in
  `swf/build.py` (~L73) + rebuild the stub SWF + repackage the `.wotmod`. `flash.py`
  does NOT reference the AS3 class name (verified by grep) → no `.pyc` change. Ship as
  v6.0.1.
- **Caution:** SWF / view-layer edits are risky (the `SUB_VIEW` change once hung the
  client) — after rebuild, verify the renamed SWF still loads as a valid IView.

---

## Other known follow-ups (pre-existing, lower priority)

### 2. Calibrate the camo / spot-distance estimate
Values run slightly HIGH (we over-estimate the range from which we get spotted). User
prefers over- to under-estimate, so left as-is for now. Revisit `_compute_camo` /
`_compute_spot_radius` + the crew/equipment camo factors.

### 3. Test alongside XVM / Aslain modpack
Confirmed non-crashing by code analysis (all hooks are wrappers that call the original;
keys never consumed; panel is an independent overlay). Open *cosmetic* interactions:
our minimap circle (native `VIEW_RANGE_CIRCLES`) may visually overlap XVM's own circles;
the enemy-name marker may not render inside XVM's player panels. Optional mitigation
(deferred): opt-out flags `showMinimapCircle` / `enemyNameMarker`.

### 4. Refresh meta.xml `<description>`
Still describes only the minimap circle + picker; doesn't mention the v6.0 panels /
auto-pick / PL-EN. Cosmetic (shown in the in-game mod list). Update on the next build.
