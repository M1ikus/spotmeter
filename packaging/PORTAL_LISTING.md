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

# WG Mods portal (wgmods.net) — English

## Version changes  (max 1000 characters)

```
v6.0.0 - built for WoT 2.3.0.0.

A major update on top of the minimap spot-distance circle:

NEW
- In-battle picker panel: lists every enemy with its view range; identical tanks group into one row. Shows the spot-distance of the picked target (or your own tank). Pick by clicking a row or with Numpad 2/8. Draggable.
- Garage panel: pre-configure perk/equipment levels before battle, with a live preview.
- PageDown: show/hide the panel (battle + garage); stays hidden until pressed again.
- Auto-pick (Numpad /): auto-targets the nearest enemy, with per-class presets.
- Optics / Vents / CVS as manual cyclable levels (Numpad 6 / + / -).
- Auto-hide while holding TAB/N or when garage windows are open.
- English + Polish interface, auto-detected from the client.

FIXED
- Panel no longer reappears by itself after being hidden with PageDown.
- Garage performance cleanup.
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
1. Download spotmeter-v6.0.0.wotmod.

2. Copy it into:  <WoT>\mods\2.3.0.0\
   Example:  D:\Games\World_of_Tanks_EU\mods\2.3.0.0\
   (create the folder if it does not exist)

3. (Optional) To change colours, multipliers or keys, copy spotmeter.json into:
   <WoT>\mods\configs\
   Without it the mod uses sensible defaults.

4. Launch the game and enter a battle. An extra circle appears on the minimap and the SpotMeter panel appears on screen - press PageDown to hide/show it.

The game auto-loads every .wotmod in mods\<version>\ at startup.

To uninstall: delete the .wotmod from mods\2.3.0.0\.

Requires WoT 2.3.0.0. No other mods needed - the GUIFlash library is bundled.
```

# Aslain's modpack — Polish

Mod jest w paczce Aslaina, ktora ma wlasny changelog po polsku (bez twardego
limitu znakow - Aslain lubi zwiezle wpisy). Dwie formy do wyboru.

## Zmiany wersji — jedna linia (kompaktowy changelog Aslaina)

```
SpotMeter zaktualizowany do v6.0.0 (WoT 2.3.0.0) — panele w bitwie i garażu, auto-dobieranie celu, klawisz PageDown, interfejs PL/EN. (autor: ISEDR_Mikus)
```

## Zmiany wersji — pełne

```
SpotMeter v6.0.0 — pod WoT 2.3.0.0.

Duża aktualizacja — oprócz okręgu na minimapie pokazującego dystans wykrycia doszły panele i automatyka:

NOWE
- Panel w bitwie: lista przeciwników z zasięgiem widzenia (VR); identyczne czołgi grupowane w jeden wiersz. Pokazuje dystans spotu wybranego celu (albo Twojego czołgu, gdy nic nie wybrane). Wybór klikiem albo Numpad 2/8. Przeciągalny.
- Panel w garażu: konfiguracja perków/sprzętu przed bitwą, z podglądem na żywo.
- PageDown: pokaż/ukryj panel (bitwa + garaż); zostaje ukryty aż do ponownego wciśnięcia.
- Auto-dobieranie (Numpad /): automatycznie celuje w najbliższego przeciwnika, presety per klasa.
- Optyka / Wentylacja / CVS jako ręczne, cyklowane poziomy (Numpad 6 / + / −).
- Auto-ukrywanie przy trzymaniu TAB/N oraz po otwarciu okien w garażu.
- Interfejs po polsku i angielsku (wykrywany automatycznie z języka klienta).

POPRAWKI
- Panel nie włącza się już sam po ukryciu przez PageDown.
- Optymalizacja wydajności w garażu.
```
