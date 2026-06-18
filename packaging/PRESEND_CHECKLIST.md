# SpotMeter — pre-send checklist

**Always run this before sending the mod to Aslain or uploading to wgmods.**
Aslain explicitly asked us to verify every build first (he's been burned by a
modder beta-testing on him). We play solo without other mods, so verification is
**offline**: the automated gate below proves the build is structurally sound and
self-consistent; the manual items cover what only a running client can show.

A send is allowed only when **both** sections are green.

---

## 1. Automated gate — `python packaging/preflight.py`

One command. Exit 0 = all hard checks pass. It performs:

- **py2.7 compile** of `mod_spotmeter.py` + the 3 `spotmeter_gf` files (the
  authoritative Python-2 syntax check — catches any accidental py3 syntax, and
  writes fresh bytecode to `build/` so the artifact is never stale).
- **ast.parse** of the main module + **json.load** of `spotmeter.json`.
- **dead-symbol scan** (tokenised, so comments don't false-positive): no live
  reference to any garage-panel / lobby window-watch symbol removed in v6.1.0.
- **config parity**: `DEFAULT_CONFIG` keys == `spotmeter.json` keys.
- **i18n parity**: `_STRINGS['en']` and `['pl']` have identical keys, and every
  `_t('...')` literal is defined.
- **version consistency**: `MOD_VERSION` == `meta.xml` == built filename; the
  version appears in README / CHANGELOG / PORTAL_LISTING / INSTALL.
- **portal limits**: the three WG blocks are ≤ 1000 / 3000 / 1000 chars.
- **`_MSA_SETTINGS_VERSION`** is reported (must be bumped on ANY template change,
  or the configurator silently keeps the old layout).
- **build + package**: runs `build_wotmod.py`, then asserts the `.wotmod` is
  all-`ZIP_STORED`, CRC-clean, has `meta.xml` first, contains the exact 6-file
  payload under `res/`, and includes every intermediate directory entry.
- **git** working tree clean (warning only).

Fix every `[FAIL]` before continuing. Warnings are judgement calls.

---

## 2. Manual / in-game (one quick battle + a garage visit)

The author runs these in a clean WoT 2.3.0.1 with **only** SpotMeter installed.

- [ ] **Loads**: `python.log` has `SpotMeter: initialised (version=6.1.0, ...)`
      and **no** traceback at startup.
- [ ] **Minimap circle** appears in battle and recolours: red moving → green
      still → dark-green after 3s still with net → orange ~3s after firing.
- [ ] **Battle panel starts HIDDEN** (default). **PageDown** shows it; PageDown
      again hides it.
- [ ] **PgDn hide persists by design**: once hidden with PageDown, the panel
      stays hidden into the next battle and after a garage→battle round-trip —
      it only comes back when the user presses PageDown again. (This is intended;
      do **not** treat the panel staying hidden as a bug.)
- [ ] **Picker** works: click a row / Numpad 2/8 selects an enemy and the circle
      switches to that tank's view range; Numpad 5 clears back to own/auto.
- [ ] **Auto-pick** (Numpad /) tracks the nearest enemy and applies the per-class
      preset.
- [ ] **Never writes to chat**: the mod posts **nothing** to game chat, ever —
      no picker/toggle confirmations, no status block, no hints. NumpadEnter
      logs the status block to `python.log`; NumpadStar logs the descriptor +
      VR breakdown there too. (Numpad9 / live mode no longer exists.)
- [ ] **No log spam** during a battle (no per-tick lines unless `logCalcDetails`
      is on; on-demand NumpadEnter / NumpadStar entries only when pressed).
- [ ] **Configurator** (only if a mods-settings menu is installed for the test):
      SpotMeter page appears in the garage; changing panel/loadout/hotkey options
      applies live and writes `spotmeter.json`; the class dropdown switches the
      auto-pick preset being edited; hotkey buttons show compact names
      (`NUM2`, not a clipped `NUMPAD`). Without any menu installed, the mod must
      still load and run normally.
- [ ] **No-menu path**: with **no** mods-settings menu installed, the startup
      `python.log` line names the exact config path; the mod loads and runs
      normally (no chat hint — chat is never used).
- [ ] **Config location**: confirm `spotmeter.json` is created/updated under
      `%APPDATA%\Wargaming.net\WorldOfTanks\mods\spotmeter\`; an existing old
      config is migrated, not ignored.

---

## 3. Release steps (after both sections are green)

1. Move the `CHANGELOG.md` `[6.1.0]` entry from *Unreleased* to a dated release.
2. Commit (working tree clean → re-run preflight to confirm).
3. `git tag v6.1.0` and push the tag.
4. Build the final artifact from the tagged tree; create the GitHub release and
   attach `dist/spotmeter-v6.1.0.wotmod`.
5. Paste the PORTAL_LISTING blocks: EN (version changes / description /
   installation) to wgmods; PL (one-line or full) to Aslain.
6. Send Aslain the `.wotmod` **plus** a one-line "preflight + in-game checklist
   passed" note, and (once) the `research/msa/hotkey_display_name.patch` for his
   ModsSettingsAPI fork.
