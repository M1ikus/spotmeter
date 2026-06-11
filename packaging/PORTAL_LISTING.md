<!--
Release listing texts for SpotMeter, per distribution channel.
Content in the code blocks is the CURRENT (v6.0.0) copy - paste it straight in.

Channels:
  1. WG Mods portal (wgmods.net) - ENGLISH. Three fields with HARD char limits.
  2. Aslain's modpack - POLISH. Short per-version changelog (no hard limit).

Per release:
  - ALWAYS rewrite the "Version changes" blocks (WG EN + Aslain PL).
  - Update "Mod description" / "Installation" only when features or the target
    WoT version actually change.
  - Keep the WG blocks under their limits (counts noted in the headings).
  - WG portal = English (matches meta.xml <description>); Aslain = Polish.
-->

# Release listing texts — SpotMeter

## Dependencies / wymagania (both channels)

NONE - SpotMeter is fully self-contained in the single .wotmod:
- bundles mod_spotmeter.pyc + a private GUIFlash fork (gui.mods.spotmeter_gf + its SWF)
- does NOT require gambiter.guiflash, XVM, XFW or any shared library
- spotmeter.json config is optional (built-in defaults if absent)
- requires WoT 2.3.0.1; no special load order
- coexists with other mods: own namespace, replaces no WG UI files, every game
  hook is a wrapper that calls the original, hotkeys are never consumed

# WG Mods portal (wgmods.net) — English

## Version changes  (max 1000 characters)

```
v6.0.1 - update for WoT 2.3.0.1.

Maintenance release after live testing in a big modpack:

FIXED
- Garage panel auto-hide: overlays from other mods (mod buttons, notifications, chat) no longer hide the panel. It hides only for real screens (research / depot / profile / loadout) and dialogs, and reliably comes back. Previously the panel could flicker or stay hidden in a modpack.
- Removed the enemy-name marker (the dot prefix on the picked target's nickname) - it never rendered reliably and the battle panel already shows the target. The mod now hooks only two game classes (minimap circle + shot penalty), further reducing the chance of conflicts with other mods.

COMPATIBILITY
- Verified alongside gambiter.guiflash 0.6.3 and CHAMPi mods (expectedvehiclevalues, playerpanelpro, settingsgui) - no conflicts; the bundled UI library coexists with the original one.
```

## Mod description  (max 3000 characters)

```
SpotMeter adds a dynamic circle to your minimap showing the distance from which your tank can currently be spotted - so you always know how close an enemy has to be to see you.

The circle updates live and changes colour with your state:
- red while moving
- green while stationary
- dark green after 3s stationary with a camouflage net active
- orange for ~3s after firing (camo penalty)

WHAT IT READS AUTOMATICALLY
Everything in your own tank's data: base view range, crew, optics, binoculars, camo net, siege modes (CS-63, S-Conqueror, etc.) and the after-shot penalty. By default the circle assumes the enemy sees as far as you do.

ENEMY PICKER
Pick a specific enemy (click a row in the panel, or Numpad 2/8) and the circle switches to that tank's view range. Because the server no longer sends enemy equipment, you set the assumed optics / vents / CVS as quick cyclable levels (Numpad 6 / + / -) and toggle the likely crew perks (Rations, BIA, Recon + Situational Awareness). The estimate matches the in-game view-range formula.

PANELS (v6.0)
- In-battle panel: every enemy with its view range; identical tanks grouped (e.g. "Dravec x5"); a target line with the spot-distance; the AUTO state. Click a row to pick.
- Garage panel: set everything up before battle with a live preview.
- PageDown shows/hides the panels (the choice persists). They also auto-hide while you hold TAB/N or open garage windows.
- Auto-pick (Numpad /) tracks the nearest enemy automatically.

LANGUAGE
English and Polish, auto-detected from your game client.

FAIR PLAY
SpotMeter only computes values the client already has and shows the result geometrically. It does NOT reveal hidden enemies, automate aiming or movement, or read server-private data - the same category as the view-range circles already built into the game and shipped in common modpacks.

Hotkeys are on the numpad and work with NumLock on or off; everything is configurable in spotmeter.json.
```

## Installation  (max 1000 characters)

```
1. Download spotmeter-v6.0.1.wotmod.

2. Copy it into:  <WoT>\mods\2.3.0.1\
   Example:  D:\Games\World_of_Tanks_EU\mods\2.3.0.1\
   (create the folder if it does not exist)

3. (Optional) To change colours, multipliers or keys, copy spotmeter.json into:
   <WoT>\mods\configs\
   Without it the mod uses sensible defaults.

4. Launch the game and enter a battle. An extra circle appears on the minimap and the SpotMeter panel appears on screen - press PageDown to hide/show it.

The game auto-loads every .wotmod in mods\<version>\ at startup.

To uninstall: delete the .wotmod from mods\2.3.0.1\.

Requires WoT 2.3.0.1. No other mods needed - the GUIFlash library is bundled.
```

# Aslain's modpack — Polish

Mod jest w paczce Aslaina, ktora ma wlasny changelog po polsku (bez twardego
limitu znakow - Aslain lubi zwiezle wpisy). Dwie formy do wyboru.

## Zmiany wersji — jedna linia (kompaktowy changelog Aslaina)

```
SpotMeter zaktualizowany do v6.0.1 (WoT 2.3.0.1) — naprawione auto-ukrywanie panelu w garażu obok innych modów, usunięty znacznik przy nicku celu (zbędny przy panelu). (autor: ISEDR_Mikus)
```

## Zmiany wersji — pełne

```
SpotMeter v6.0.1 — pod WoT 2.3.0.1.

Wydanie naprawcze po testach w dużej paczce modów:

POPRAWKI
- Auto-ukrywanie panelu w garażu: nakładki innych modów (przyciski modów, powiadomienia, czat) nie chowają już panelu. Panel chowa się tylko przy prawdziwych ekranach (Badania / magazyn / profil / wyposażenie) i oknach dialogowych, i niezawodnie wraca — wcześniej w paczce modów potrafił migotać albo zostać schowany.
- Usunięty znacznik przy nicku wybranego celu — nigdy nie renderował się poprawnie, a panel bitewny i tak pokazuje cel. Mod hookuje teraz tylko dwie klasy gry (okrąg na minimapie + kara za strzał), więc ryzyko konfliktów z innymi modami jest jeszcze mniejsze.

ZGODNOŚĆ
- Potwierdzone działanie obok gambiter.guiflash 0.6.3 i modów CHAMPi (expectedvehiclevalues, playerpanelpro, settingsgui) — bez konfliktów.
```
