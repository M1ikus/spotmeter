<!--
Release listing texts for SpotMeter, per distribution channel.
Content in the code blocks is the CURRENT (v6.1.0) copy - paste it straight in.

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
- a mods-settings menu (Aslain's aslainMenu / izeberg's ModsSettingsAPI) is
  OPTIONAL too - it only adds the in-garage settings page; the mod runs fully
  without it (JSON config + hotkeys). Recommended for solo installs that want
  in-game configuration.
- requires WoT 2.3.0.1; no special load order
- coexists with other mods: own namespace, replaces no WG UI files, every game
  hook is a wrapper that calls the original, hotkeys are never consumed

# WG Mods portal (wgmods.net) — English

## Version changes  (max 1000 characters)

```
v6.1.0 - for WoT 2.3.0.1.

In-game settings + cleaner defaults:

NEW
- In-game configurator: with a mods-settings menu installed (Aslain's aslainMenu, or izeberg's ModsSettingsAPI - both optional, the mod works without either) SpotMeter gets a settings page: panel visibility, identical-tank grouping, auto-hide, panel hotkey (key combos supported), minimap circle on/off, circle opacity, language, the battle-start loadout, per-class auto-pick presets (class dropdown), and a full rebindable hotkey list. Changes apply live and save to spotmeter.json.
- "Panel only" mode: showMinimapCircle turns the minimap circle off independently of the panel.

CHANGED
- The battle panel starts HIDDEN by default (PageDown shows it). The separate garage panel is gone - its settings live in the configurator now.
- Config moved to AppData (survives modpack reinstalls); an old config is migrated automatically.
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

PANEL & SETTINGS
- In-battle panel: every enemy with its view range; identical tanks grouped (e.g. "Dravec x5"); a target line with the spot-distance; the AUTO state. Click a row or Numpad 2/8 to pick. PageDown shows/hides it; hold TAB/N to peek the team panels.
- Auto-pick (Numpad /) tracks the nearest enemy, with per-class loadout presets.
- In-game configurator: install a mods-settings menu (Aslain's aslainMenu or izeberg's ModsSettingsAPI - free, optional) and SpotMeter adds a settings page in the garage: panel options, the assumed loadout, auto-pick presets, language and a full rebindable hotkey list, applied live. Without a menu the mod auto-creates a commented spotmeter.json you can edit (its exact path is logged to python.log at startup).

LANGUAGE
English and Polish, auto-detected from your game client.

FAIR PLAY
SpotMeter only computes values the client already has and shows the result geometrically. It does NOT reveal hidden enemies, automate aiming or movement, or read server-private data - the same category as the view-range circles already built into the game and shipped in common modpacks.

Hotkeys are on the numpad and work with NumLock on or off; everything is configurable in spotmeter.json.
```

## Installation  (max 1000 characters)

```
1. Download spotmeter-v6.1.0.wotmod.

2. Copy it into:  <WoT>\mods\2.3.0.1\
   Example:  D:\Games\World_of_Tanks_EU\mods\2.3.0.1\
   (create the folder if it does not exist)

3. Launch the game. The minimap spot-distance circle works right away. The battle panel starts hidden - press PageDown in battle to show it.

4. (Optional) Install a mods-settings menu (Aslain's aslainMenu or izeberg's ModsSettingsAPI) to configure everything in the garage, or edit the auto-created config at:
   %APPDATA%\Wargaming.net\WorldOfTanks\mods\spotmeter\spotmeter.json

The game auto-loads every .wotmod in mods\<version>\ at startup.
To uninstall: delete the .wotmod from mods\2.3.0.1\.
Requires WoT 2.3.0.1. No other mods needed - the GUIFlash library is bundled.
```

# Aslain's modpack — Polish

Mod jest w paczce Aslaina, ktora ma wlasny changelog po polsku (bez twardego
limitu znakow - Aslain lubi zwiezle wpisy). Dwie formy do wyboru.

## Zmiany wersji — jedna linia (kompaktowy changelog Aslaina)

```
SpotMeter zaktualizowany do v6.1.0 (WoT 2.3.0.1) — konfigurator w garażu (menu ustawień modów): widoczność panelu, założony loadout, presety auto-dobierania per klasa, pełna klawiszologia. Panel bitewny domyślnie ukryty (PageDown pokazuje), panel garażowy usunięty, config w AppData. (autor: ISEDR_Mikus)
```

## Zmiany wersji — pełne

```
SpotMeter v6.1.0 — pod WoT 2.3.0.1.

Ustawienia w grze + czytelniejsze domyślne:

NOWE
- Konfigurator w garażu: z zainstalowanym menu ustawień modów (aslainMenu Aslaina albo ModsSettingsAPI izeberga — oba opcjonalne, bez nich mod też działa) SpotMeter dostaje stronę ustawień: widoczność panelu, grupowanie identycznych czołgów, auto-ukrywanie, klawisz panelu (z kombinacjami), okrąg na minimapie wł/wył, przezroczystość, język, założony loadout na start bitwy, presety auto-dobierania per klasa (dropdown klas) oraz pełna lista przypisywanych klawiszy. Zmiany działają na żywo i zapisują się do spotmeter.json.
- Tryb „sam panel": showMinimapCircle wyłącza okrąg na minimapie niezależnie od panelu.

ZMIANY
- Panel bitewny domyślnie ukryty (PageDown pokazuje). Osobny panel garażowy usunięty — jego ustawienia są teraz w konfiguratorze.
- Config przeniesiony do AppData (przeżywa reinstalacje paczki); stary config migruje automatycznie.
```
