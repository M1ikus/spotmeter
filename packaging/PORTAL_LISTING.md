<!--
Release listing texts for SpotMeter, per distribution channel.
Content in the code blocks is the CURRENT (v7.0.0) copy - paste it straight in.

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

REQUIRES net.openwg.gameface (free, MIT; already shipped in common modpacks):
- the in-battle panel is a Gameface (HTML/CSS/JS) overlay rendered through
  net.openwg.gameface. Without it the minimap circle + numpad hotkeys still work,
  but the panel does not appear.
- v7.0.0 ships NO SWF - the old bundled GUIFlash fork is gone, so SpotMeter can
  never duplicate the net.gambiter.* classes or disturb another GUIFlash mod's
  saved window positions.
- spotmeter.json config is optional (built-in defaults if absent), stored in AppData.
- a mods-settings menu (Aslain's aslainMenu / izeberg's ModsSettingsAPI) is
  OPTIONAL - it only adds the in-garage settings page; the mod runs on JSON config
  + hotkeys without it.
- requires WoT 2.3.1.0; no special load order.
- coexists cleanly: own namespace, replaces no WG UI files, every game hook wraps
  the original, hotkeys are never consumed.

# WG Mods portal (wgmods.net) — English

## Version changes  (max 1000 characters)

```
v7.0.0 - for WoT 2.3.1.0.

Major update: the in-battle panel is rebuilt on Gameface (modern HTML/CSS/JS).

CHANGED
- The panel is now a Gameface overlay instead of a Scaleform/GUIFlash SWF. SpotMeter ships NO SWF anymore, so it can never collide with another GUIFlash mod's saved window positions. The minimap circle and the whole spot-distance engine are unchanged.

NEW
- Requires net.openwg.gameface (free, in common modpacks). Without it the circle + hotkeys still work.
- Modern look: transparent panel, white text, green for the enabled options.
- Drag the panel by its header (position saved).
- Collapse arrow: shrink it to just the picked vehicle + spot distance (state remembered).

Cleaner log: benign status lines are INFO now (no more warning-looking noise).
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

IN-BATTLE PANEL (v7 - Gameface)
A modern HTML overlay: every enemy with its view range, identical tanks grouped (e.g. "Dravec x5"), a target line with the spot-distance, and the AUTO state. Click a row to pick a target; click the loadout cells to change the assumed optics/perks. Drag it by the header (position saved); a collapse arrow shrinks it to just the picked vehicle + spot distance. PageDown shows/hides it.
- Auto-pick (Numpad /) tracks the nearest enemy, with per-class loadout presets.
- Optional in-garage configurator via a mods-settings menu (aslainMenu / ModsSettingsAPI). Without a menu, edit the auto-created spotmeter.json (path logged at startup).

REQUIRES
net.openwg.gameface (free, MIT; already in common modpacks) for the panel. The minimap circle and the hotkeys work even without it.

LANGUAGE
English and Polish, auto-detected from your game client.

FAIR PLAY
SpotMeter only computes values the client already has and shows the result geometrically. It does NOT reveal hidden enemies, automate aiming or movement, or read server-private data - the same category as the view-range circles already built into the game.

Hotkeys are on the numpad and work with NumLock on or off; everything is configurable in spotmeter.json.
```

## Installation  (max 1000 characters)

```
1. Install net.openwg.gameface (free; already in most modpacks, or from the OpenWG project). SpotMeter's panel needs it.

2. Download spotmeter-v7.0.0.wotmod.

3. Copy it into:  <WoT>\mods\2.3.1.0\
   Example:  D:\Games\World_of_Tanks_EU\mods\2.3.1.0\
   (create the folder if it does not exist)

4. Launch the game. On first launch it briefly restarts once to register the panel (net.openwg.gameface rebuilds its resource map) - this is normal. The minimap circle works right away; in battle, PageDown shows/hides the panel and you drag it by the header.

5. (Optional) Install a mods-settings menu (aslainMenu / ModsSettingsAPI) to configure in the garage, or edit:
   %APPDATA%\Wargaming.net\WorldOfTanks\mods\spotmeter\spotmeter.json

To uninstall: delete the .wotmod from mods\2.3.1.0\. Requires WoT 2.3.1.0 + net.openwg.gameface.
```

# Aslain's modpack — Polish

Mod jest w paczce Aslaina, ktora ma wlasny changelog po polsku (bez twardego
limitu znakow - Aslain lubi zwiezle wpisy). Dwie formy do wyboru.

## Zmiany wersji — jedna linia (kompaktowy changelog Aslaina)

```
SpotMeter v7.0.0 (WoT 2.3.1.0) — panel bitewny przepisany na Gameface (nowoczesny HTML/CSS/JS) zamiast GUIFlash/SWF: mod nie wysyła już żadnego SWF-a, więc nie może kolidować z zapisanymi pozycjami okien innych modów GUIFlash. Nowości: przezroczysty styl, przeciąganie za nagłówek (zapis pozycji), strzałka zwijania. WYMAGA net.openwg.gameface. Czystszy log (statusy przez INFO). (autor: ISEDR_Mikus)
```

## Zmiany wersji — pełne

```
SpotMeter v7.0.0 — pod WoT 2.3.1.0.

Duża zmiana: panel bitewny przepisany na Gameface (nowoczesny HTML/CSS/JS).

ZMIANY
- Panel to teraz overlay Gameface zamiast SWF-a (GUIFlash/Scaleform). SpotMeter NIE wysyła już żadnego SWF-a — nie może kolidować z zapisanymi pozycjami okien innych modów GUIFlash (to był ten problem, który zgłaszał Aslain z modem RaJCeLa). Okrąg na minimapie i cały silnik spot-distance bez zmian.

NOWE
- WYMAGA net.openwg.gameface (darmowa, MIT; jest w typowych paczkach). Bez niej okrąg + klawisze działają, panelu nie ma.
- Nowoczesny wygląd: przezroczyste tło, biały tekst, zielone włączone opcje.
- Przeciąganie panelu za nagłówek (pozycja zapisywana).
- Strzałka zwijania: panel kurczy się do samego wybranego pojazdu + spot distance (stan zapamiętany).

POPRAWKI
- Czystszy log: benign statusy idą teraz przez INFO (koniec warningów wyglądających jak błędy). „module loaded" leci przez INFO.
```
