# TODO — planned for a future update

Backlog of known follow-ups. Updated 2026-06-06 after live testing in an
Aslain-style modpack (champi.expectedvehiclevalues + champi.settingsgui +
gambiter.guiflash 0.6.3 + poliroid.modslistapi + openwg.gameface + izeberg).

## v6.0.1 — prepared for WoT 2.3.0.1 (committed; awaiting in-game check + GH release)

Bundled in the v6.0.1 commit: garage auto-hide rewrite (layer-gated: hide only for
content screens layer 5 + dialogs layer >= 10; other mods' layer-7 overlays no longer
hide the panel; idempotent show-path), enemy-name-marker removal (only 2 WG classes
patched now: `PersonalEntriesPlugin` + `Avatar.shoot`), refreshed `meta.xml`
description, CHANGELOG `[6.0.1]`, new EN+PL version-changes in
`packaging/PORTAL_LISTING.md`, repackaged for the 2.3.0.1 mods folder.

Remaining before publishing:
1. Smoke-test on the 2.3.0.1 client (battle + garage tabs; the rest of the test
   pack still sits in `mods/2.3.0.0/` — copy it over if testing coexistence).
2. `git tag v6.0.1` + GitHub release with `dist/spotmeter-v6.0.1.{wotmod,zip}`
   (notes ready in PORTAL_LISTING / CHANGELOG) + send Aslain the PL note.

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
