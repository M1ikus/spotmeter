# SpotMeter — WoT minimap mod

Dodaje na minimapie dodatkowy okrąg pokazujący odległość, z jakiej Twój czołg może zostać zauważony przez przeciwnika.

## Co automatycznie / co ręcznie

Granica jest prosta: wszystko co jest w **descriptorze pojazdu** (transmitowanym przez serwer w `strCompactDescr`) bierzemy automatycznie. Reszta jest manualnym toggle.

| Element | Auto / manualne | Skąd |
|---|---|---|
| Hull / turret / gun / engine / radio | ✅ auto | `descr.turret.circularVisionRadius` itd. |
| Coated Optics przeciwnika | ✅ auto | `descr.miscAttrs.circularVisionRadiusFactor` (już z optyką) |
| Stereoscope przeciwnika | ✅ auto | `descr.optionalDevices` (Stereoscope class) |
| Enhancements / dyrektywy w slotach equipment | ❌ manual toggle (Numpad 1) | proste `*1.025` na auto-wykryte sprzęty |
| **Ulepszenia polowe (post-progression) WŁASNE** | ✅ auto | `Vehicle.getDescr` woła `VehicleDescr(..., extData=self)` → `__applyExternalData` woła `installModifications` |
| **Ulepszenia polowe ENEMY (VR)** | ❌ manual toggle (Numpad 0) — **BETA** | per-czołg tabelka w configu (`pickerFieldUpgradeVR`); server transmituje `vehPostProgression` tylko właścicielowi |
| Camo net na **własnym** czołgu | ✅ auto, aktywne po 3s | `descr.optionalDevices` (CamouflageNet class) |
| Tryby siege (CS-63 itp.) | ✅ auto | `CompositeVehicleDescriptor` w silniku |
| Kara za strzał | ✅ auto | hook na `Avatar.shoot` + `miscAttrs.invisibilityFactorAtShot` |
| Skille załogi (BIA+Recon+SitAware bundled) | ❌ manual toggle (Numpad 4) | serwer nie wysyła |
| Combat Rations | ❌ manual toggle (Numpad 7) | serwer nie wysyła aktywnego stanu |

W praktyce: po wybraniu enemy pickerem, jego VR od razu zawiera Coated Optics + Stereoscope (jeśli są na tym czołgu — odczytane z descriptora). Toggle perków / consumables / dyrektyw / field-upgradów nakładasz tylko gdy zakładasz że enemy je faktycznie ma.

> **Weryfikacja własnych field upgrades:** naciśnij **NumpadEnter** (status snapshot) — w chacie pojawi się m.in. linia `myVR: base=410m * factor=1.103` i `myCamo: base(...) + add=0.025`. Jeśli `factor>1.0` lub `add>0.0`, ulepszenia polowe są naliczone w descriptorze.

## Kolory okręgu

- **Czerwony** w ruchu (camo `invMoving`)
- **Zielony** w postoju (camo `invStill`)
- **Ciemnozielony** w postoju 3s+ z aktywną siatką maskującą (camo `invStill + camoNetBonus`)
- **Pomarańczowy** ~3s po strzale (camo `* invisibilityFactorAtShot`)
- Czołgi lekkie / niektóre kołowe — w XML mają `invMoving == invStill`, więc okrąg po prostu nie zmienia rozmiaru. Bez specjalnego case'u.
- Czołgi z trybem siege (CS-63, S-Conqueror, italian heavies) — silnik gry sam podmienia descriptor (`CompositeVehicleDescriptor`) na właściwy tryb, więc mod automatycznie używa odpowiedniego camo dla obecnego trybu.

## Wzór camo (zgodny z `scripts/common/items/utils.py:getInvisibility`)

```
camo = max(0, (base * vehicleFactor * crewBonus
               + invisibilityBaseAdditive + invisibilityAdditiveTerm)
              * invisibilityMultFactor)

spot_distance = enemyViewRange * (1 - camo)
spot_distance ∈ [50 m, 445 m]
```

`base` = `vehicle.typeDescriptor.type.invisibility[moving|still]` (z XML czołgu).

`vehicleFactor`, `invisibilityBaseAdditive`, `invisibilityAdditiveTerm`, `invisibilityMultFactor` — z `vehicle.typeDescriptor.miscAttrs` (zbiorcze modyfikatory wieży / sprzętu / perków).

`crewBonus` — przybliżona poprawka na skill Camouflage załogi (configurable, domyślnie 1.05).

## Skąd `enemyViewRange`?

Trzy źródła w kolejności priorytetu:

1. **Picker aktywny** — bierzemy descriptor wybranego enemy (`strCompactDescr`), liczymy bazowy VR z wieży, dodajemy auto-wykryte (Optics, Stereoscope) i opcjonalnie zaznaczone toggle (Rations, Crew Perks, Directives, Field Upgrades).
2. **`useOwnViewRange: true`** (default, picker nieaktywny) — bierzemy własny VR z `feedback.getVehicleAttrs()['circularVisionRadius']`. Serwer go syncuje (`VEHICLE_ATTRS_TO_SYNC`). Ten VR ma już naliczoną załogę, optykę, lornę itd.
3. **`useOwnViewRange: false`** — używamy `enemyViewRangeFallback` (domyślnie 445 m = max w grze).

## Model picker VR (v5.3+, game-UI matching)

Gra w UI dodaje wszystkie bonusy **addytywnie** wobec baseline `(base_VR × rations)`. Mod robi tak samo:

```
1. base_vr  ← descr.turret.circularVisionRadius
2. JEŚLI Field Upgrades ON i czołg w tabelce:
       base_vr ← min(base_vr * (1 + upgrade%), 445m)
3. baseline ← base_vr * (Rations ? 1.0430 : 1.0)
4. final    ← baseline
   + baseline * (optics_factor * directive_factor - 1)        # auto z descriptora
   + baseline * (stereo_factor * directive_factor - 1)        # auto z descriptora (jeśli ma)
   + baseline * (CrewPerks_factor - 1)                        # toggle, ON default
```

**Mnożniki** (skalibrowane empirycznie wobec UI gry):

| toggle | klawisz | config | default | znaczenie |
|---|---|---|---|---|
| Rations | Numpad 7 | `pickerVRBonusRations` | `1.0430` | **default ON** — racje +4.30% |
| CrewPerks bundled (BIA+Recon+SitAware) | Numpad 4 | `pickerVRBonusCrewPerks` | `1.0953` | **default ON** — łącznie +9.53% |
| Directives na sprzęt | Numpad 1 | `pickerVRBonusDirective` | `1.0250` | **default OFF** — mnożnik na auto-wykryte (optics, stereo) |
| Field Upgrades VR | Numpad 0 | `pickerFieldUpgradeVR` | per-czołg tabelka | **default OFF** — **BETA** |

Plus auto-detekcja z descriptora przeciwnika (zawsze, niezależnie od toggle):
- Coated Optics (basic): ×1.10
- Coated Optics (deluxe / fioletowa): ×1.135
- Coated Optics (bond / improved): ~×1.14 (tank-zależne)
- Stereoscope (basic): ×1.25 (założenie: zawsze aktywna; toggle przez `pickerAssumeStereoscope`)

Verifikacja na czołgu z bazowym VR 340m, 100% załoga:
- BIA alone: +8.6m ✓
- Recon: +9.79m ≈ +9.81 (gra) ✓
- SitAware: +15.33m ≈ +15.34 (gra) ✓
- Rations: +14.6m ✓
- Optyka deluxe: +47.87m (liczona z `(340+rations)*0.135`) ✓

## Field Upgrades VR — BETA (v5.4.1)

Server NIE wysyła `vehPostProgression` przeciwnika (jest to `MY_VEHICLE` scope). Mod używa **ręcznie utrzymywanej tabelki per-czołg** w configu:

```json
"pickerFieldUpgradeVR": {
    "Rhm.-B. WT":   0.02,
    "Obj. 907":     0.03,
    "Jg.Pz. E 100": 0.02
},
"pickerFieldUpgradeCap": 445.0
```

**Mechanika:** po wciśnięciu Numpad 0 (toggle ON), mod szuka czołgu po `shortName` w tabelce. Jeśli znajdzie, mnoży `base_vr` przez `(1 + %)` z capem 445m, **przed** dodaniem rations/perks/directives. Czołgi spoza tabelki = 0% (toggle nie robi nic). EBR 105 nie ma w post-progression żadnego upgradeu na VR, więc go w tabelce nie ma.

**Dopisuj własne wpisy** — sprawdź `shortName` przez Numpad `*` (dump descryptora wybranego enemy do `python.log`), znajdź wpis i dodaj do tabelki w `spotmeter.json`. Np. dla czołgu z +2.5% upgradeu na VR: `"NazwaCzolgu": 0.025`.

> **Dlaczego BETA:** lista czołgów z VR upgrades w post-progression nie jest wyczerpująco udokumentowana publicznie, więc tabelka jest aktualnie bardzo skromna. Jeśli zauważysz zaniżony radius na konkretnym czołgu enemy, to znak że ma upgradeu na VR i trzeba go dopisać.

## Instalacja (release / dla kolegi)

Pobierz `spotmeter-v<wersja>.zip` z [GitHub Releases](https://github.com/M1ikus/spotmeter/releases). W środku:

- `spotmeter-v<wersja>.wotmod` → wrzuć do `<WoT>/mods/2.2.1.3/`
- `spotmeter.json` (opcjonalny) → wrzuć do `<WoT>/mods/configs/`
- `INSTALL.txt` — szczegółowa instrukcja krok po kroku

Gra automatycznie ładuje wszystkie `.wotmod` z `mods/<wersja>/` po starcie. Bez configu mod używa sensownych domyślnych wartości.

## Hotkeys (numpad layout)

```
+-----+-----+-----+-----+
|     |  /  |  *  |  -  |    *=dump descryptor enemy do log
+-----+-----+-----+-----+
|  7  |  8  |  9  |  +  |    7=rations  8=prev    9=overlay-toggle
+-----+-----+-----+-----+
|  4  |  5  |  6  |     |    4=crew-perks  5=clear-picker
+-----+-----+-----+-----+
|  1  |  2  |  3  |Enter|    1=directives  2=next  Enter=full-status
+-----+-----+-----+-----+
|     0     |  .  |          0=field-upgrades   .=reload-config
+-----+-----+-----+-----+
```

| akcja | klawisz | config | default state |
|---|---|---|---|
| następny przeciwnik | Numpad 2 | `pickerNextKey` | — |
| poprzedni przeciwnik | Numpad 8 | `pickerPrevKey` | — |
| wyczyść picker | Numpad 5 | `pickerClearKey` | — |
| toggle Rations | Numpad 7 | `pickerRationsKey` | **ON** |
| toggle Crew Perks (BIA+Recon+SitAware) | Numpad 4 | `pickerCrewPerksKey` | **ON** |
| toggle Directives na sprzęt | Numpad 1 | `pickerDirectivesKey` | OFF |
| toggle Field Upgrades VR (BETA) | Numpad 0 | `pickerFieldUpgradesKey` | OFF |
| toggle overlay tekstu (auto) | Numpad 9 | `overlayToggleKey` | (config) |
| pełen status snapshot | NumpadEnter | `overlayPrintNowKey` | — |
| dump descriptor enemy do logu | Numpad **\*** | `pickerDiagDumpKey` | — |
| reload configu | NumpadPeriod | `reloadKey` | — |

Działa przy **NumLock włączonym i wyłączonym**.

## Konfiguracja (`spotmeter.json`)

| pole | default | opis |
|---|---|---|
| `enabled` | `true` | wyłącza moda bez odinstalowywania |
| `useOwnViewRange` | `true` | używa Twojego VR jako założonego VR przeciwnika (gdy picker nieaktywny) |
| `enemyViewRangeFallback` | `445.0` | VR używany kiedy `useOwnViewRange = false` |
| `crewCamoBonus` | `1.05` | przybliżenie bonusu skilla Camouflage załogi |
| `colorMoving` | `0xFF6347` | kolor okręgu w ruchu (tomato) |
| `colorStill` | `0x32CD32` | kolor okręgu w postoju (lime) |
| `colorAfterShot` | `0xFFA500` | kolor okręgu po strzale (orange) |
| `colorCamoNet` | `0x228B22` | kolor okręgu gdy siatka aktywna (forestGreen) |
| `alpha` | `70` | przezroczystość 0–100 |
| `tickInterval` | `0.2` | jak często aktualizować (s) |
| `movingSpeedThreshold` | `0.5` | prędkość uznawana za ruch (m/s) |
| `applyFirePenalty` | `true` | po strzale aplikuje `* invisibilityFactorAtShot` |
| `fireRevealDuration` | `3.0` | czas trwania kary za strzał (s) |
| `applyCamoNet` | `true` | uwzględnia siatkę maskującą po `camoNetActivateSec` w postoju |
| `camoNetActivateSec` | `3.0` | czas postoju do aktywacji siatki (s) |
| `camoNetFallbackBonus` | `0.05` | bonus jeśli odczyt z descriptora padnie |
| `pickerEnabled` | `true` | włącza picker przeciwnika |
| `pickerVRBonusRations` | `1.0430` | mnożnik gdy toggle Rations ON |
| `pickerVRBonusCrewPerks` | `1.0953` | mnożnik gdy toggle Crew Perks ON (BIA+Recon+SitAware bundled) |
| `pickerVRBonusDirective` | `1.0250` | mnożnik na auto-wykryte sprzęty gdy toggle Directives ON |
| `pickerFieldUpgradeVR` | per-tank dict | **BETA**, mapuje `shortName` → % VR upgrade |
| `pickerFieldUpgradeCap` | `445.0` | cap na `base_vr` po zastosowaniu upgrade'u (m) |
| `pickerAssumeStereoscope` | `true` | jeśli enemy ma lornetkę, zakłada że jest aktywna |
| `pickerStereoscopeFallback` | `1.25` | mnożnik VR jeśli odczyt z descriptora padnie |
| `pickerMarker` | `"● "` | prefix nazwy wybranego przeciwnika |
| `pickerIncludeDeadEnemies` | `false` | czy uwzględniać martwych w cyklu |
| `overlayEnabled` | `true` | włącza overlay tekstu (chat-line nad minimapą) |
| `overlayShowOnTickChange` | `true` | automatycznie pokazuje przy istotnej zmianie radiusa |
| `overlayMinRadiusDelta` | `15.0` | próg zmiany w m do auto-display |
| `pickerNextKey` | `KEY_NUMPAD2` | następny przeciwnik |
| `pickerPrevKey` | `KEY_NUMPAD8` | poprzedni przeciwnik |
| `pickerClearKey` | `KEY_NUMPAD5` | wyczyść picker |
| `pickerRationsKey` | `KEY_NUMPAD7` | toggle Rations |
| `pickerCrewPerksKey` | `KEY_NUMPAD4` | toggle Crew Perks (BIA+Recon+SitAware) |
| `pickerDirectivesKey` | `KEY_NUMPAD1` | toggle Directives |
| `pickerFieldUpgradesKey` | `KEY_NUMPAD0` | toggle Field Upgrades (BETA) |
| `pickerDiagDumpKey` | `KEY_NUMPADSTAR` | dump enemy descriptor do `python.log` |
| `overlayToggleKey` | `KEY_NUMPAD9` | toggle overlay tekstu |
| `overlayPrintNowKey` | `KEY_NUMPADENTER` | pokaż pełen status snapshot |
| `reloadKey` | `KEY_NUMPADPERIOD` | reload configu |
| `logCalcDetails` | `false` | wypisuje camo/radius/state do `python.log` |

Nazwy klawiszy: nazwy z modułu `Keys` (np. `KEY_F8`, `KEY_F7`, `KEY_HOME`, `KEY_INSERT`). Pusty string = bez hotkeya.

## Co serwer faktycznie wysyła do klienta?

Sprawdziłem w zdekompilowanych plikach `scripts/common/constants.py` i `scripts/client/Avatar.py`:

- **View range własny**: tak, `circularVisionRadius` (m) jest jawnie syncowany z serwerem (`VEHICLE_ATTRS_TO_SYNC`). Mamy go w `feedback.getVehicleAttrs()` w trakcie bitwy.
- **Camouflage / invisibility**: NIE jest syncowane jako pojedyncza liczba. Klient liczy go sam z deskryptora pojazdu (`computeBaseInvisibility` + `getInvisibility` w `scripts/common/items/utils.py`). Wszystkie składniki potrzebne do tego są w pełni dostępne klientowi z deskryptora czołgu.
- **`strCompactDescr` przeciwnika**: tak, pełny binarny descriptor każdego pojazdu (`gui/battle_control/arena_info/arena_vos.py`). Po dekodowaniu mamy: hull/turret/gun/engine/radio, zainstalowany sprzęt (binokle, optyka, dyrektywy w slotach), camouflage skin/styl, tier/klasa/rola/max HP.
- **`vehPostProgression` przeciwnika**: NIE — server-side tagged jako `MY_VEHICLE` w `Vehicle.def`. Ulepszenia polowe enemy są niewidoczne dla klienta. Stąd toggle Numpad 0 + ręczna tabelka.
- **Skille załogi przeciwnika** (BIA, Recon, SitAware): NIE — stąd toggle Numpad 4.
- **Aktywne consumables przeciwnika** (Rations): NIE — stąd toggle Numpad 7.

Innymi słowy: mod nie odczytuje żadnej informacji do której nie miałby normalnie dostępu. Przy własnym czołgu liczy ze wszystkiego co dostarcza descriptor + sync. Przy enemy: descriptor + manualne toggle dla rzeczy server-private.

## Aspekt prawny / fair-play

- **Mod jest legalny w świetle Wargaming Fair Play Policy.** WG od dawna toleruje (i zalicza do oficjalnych przykładów) okręgi widoczności na minimapie — patrz np. domyślne ustawienia gry `MINIMAP_VIEW_RANGE` / `MINIMAP_MAX_VIEW_RANGE` / `MINIMAP_MIN_SPOTTING_RANGE` (są to opcje wbudowane). XVM, Aslain's modpack i inne ogólnodostępne packi zawierają od lat funkcję "Spot Range Circle" — działa to dokładnie tak jak ten mod.
- Zakazane są mody, które (a) pokazują pozycje przeciwników, których normalnie nie widzisz, (b) automatyzują celowanie / poruszanie się, (c) odczytują dane serwerowe, do których klient nie ma normalnie dostępu, (d) omijają płatne funkcje gry. Ten mod NIC z tej listy nie robi.
- Linki: [WG EU Fair Play Policy](https://eu.wargaming.net/support/en/products/wot/article/29104/) — kategoria "Allowed mods" obejmuje minimap improvements/markers.

## Hot-reload w bitwie

W bitwie naciśnij `NumpadPeriod` (lub klawisz z `reloadKey`) — config wczytuje się ponownie i okrąg uwzględnia nowe wartości w czasie 1 ticka (0.2 s). Pozwala iterować nad kolorami / VR / `crewCamoBonus` bez zamykania bitwy. Wymaga **NumLock ON**.

## Co technicznie robi mod

1. Loader gry (`scripts/client/gui/mods/__init__.py`) ładuje moduł `mod_spotmeter`.
2. Monkey-patchuje `PersonalEntriesPlugin._invalidateMarkup` z `gui/Scaleform/daapi/view/battle/shared/minimap/plugins.py`.
3. Tworzy **drugi** entry typu `VIEW_RANGE_CIRCLES` (silnik nie limituje liczby; każdy ma własny ID) i steruje nim niezależnie od Twoich istniejących okręgów.
4. Co `tickInterval` sekund:
   - czyta `vehicle.getSpeed()` → moving/still
   - czyta `vehicle.typeDescriptor.miscAttrs` → modyfikatory invisibility
   - czyta `feedback.getVehicleAttrs()['circularVisionRadius']` → własny VR (jeśli `useOwnViewRange`)
   - liczy camo i radius spotu
   - wywołuje na Flashu `as_addDynamicViewRange` / `as_updateDynRange` z (color, alpha, radius)
5. Sprząta entry i callbacki w `_hideMarkup`, `__onPostMortemSwitched`, `stop`.

## Roadmap

### v5.4 — field upgrades BETA ✅

- **Numpad 0 toggle** = ulepszenia polowe na VR (BETA)
- per-czołg tabelka `pickerFieldUpgradeVR` w configu (`shortName` → %)
- pre-fill: Rhm.-B. WT (+2%), Obj. 907 (+3%), Jg.Pz. E 100 (+2%)
- cap 445m
- EBR 105 = brak (nie ma takiego upgradeu)

### v5.3 — empiryczna kalibracja modelu ✅

- Mnożniki dla rations/crew/directive zmierzone wobec UI gry (czołg z bazowym VR 340m)
- Game-UI matching additive model: wszystko addytywne wobec `(base_vr × rations)` baseline
- BIA+Recon+SitAware bundled w jeden toggle (nie da się ich w grze rozdzielić w UI VR)

### v5 — numpad layout, redesigned toggles, overlay text ✅

- Cały picker przeniesiony na klawiaturę numeryczną (działa NumLock ON i OFF)
- 4 toggle'e dla VR enemy: Rations / Crew Perks bundle / Directives / Field Upgrades
- Overlay tekstu nad minimapą (chat-line w battle-message-feed)
- NumpadEnter — pełen status snapshot
- Numpad `*` — dump descryptora enemy do `python.log`
- NumpadPeriod — hot-reload configu

### v4.5 — binoculars in picker + camo net for own tank ✅

- **Stereoscope (lornetka)** w pickerze — gdy wykryta w `descr.optionalDevices`, automatycznie aplikuje czynnik `circularVisionRadiusFactor.getActiveValue(level)`. Worst-case assumption: lorna jest zawsze aktywna. Toggle przez `pickerAssumeStereoscope`.
- **CamouflageNet (siatka)** dla własnego czołgu — silnik gry trackuje `_LAST_MOVEMENT_TIME`. Po `camoNetActivateSec` (default `3.0` s) bez ruchu siatka się aktywuje i bonus `invisibilityBonus` jest dodawany. Kolor okręgu zmienia się na **ciemnozielony**.

### v4 — picker enemy tank ✅

W bitwie wybierasz konkretnego przeciwnika hotkeyami i okrąg dostosowuje się do jego VR. Server wysyła pełny `strCompactDescr` każdego pojazdu od początku bitwy, więc dekodujemy lokalnie.

### v3 — fire penalty + siege modes ✅

- **Kara za strzał** — hook na `PlayerAvatar.shoot()` i `shootDualGun()`. Przez `fireRevealDuration` (3 s) po strzale aplikujemy `camo *= invisibilityFactorAtShot`.
- **Tryby (CS-63, S-Conqueror itp.)** — silnik gry obsługuje to automatycznie przez `CompositeVehicleDescriptor`.
- **EBR / wheeled** — bez specjalnego case'u; XML czołgu ma `invMoving == invStill`.

### Nie planujemy

- **Bonus za roślinność (foliage)** — częściowo obliczany serwerowo, wymaga raycastów do każdego krzaka. Złożoność niewspółmierna do zysku.
- **Pokazywanie czyjegoś camo / VR jako liczby na ekranie** — to "softcheat" w niektórych interpretacjach. Mod liczy tylko własne wartości i pokazuje wynik geometrycznie.

## Dev / build

Wymaga Python 2.7 (do kompilacji `.pyc` zgodnego z silnikiem WoT-a, Anaconda env `py27`) i Python 3.10 (do uruchomienia build skryptu).

### Kompilacja .pyc

```sh
<python2.7> -c "import py_compile; py_compile.compile('src/mod_spotmeter.py', cfile='build/mod_spotmeter.pyc', dfile='mod_spotmeter.py', doraise=True)"
```

Gdzie `<python2.7>` to ścieżka do Pythona 2.7 (np. `python2.7` na systemach gdzie jest w PATH, albo pełna ścieżka do `python.exe` z conda/miniforge env-u o Python 2.7). Parametr `dfile='mod_spotmeter.py'` jest ważny — bez niego ścieżka source (zawierająca lokalną strukturę katalogów) zostaje zaszyta w `.pyc` i jest widoczna po unzipowaniu `.wotmod`.

### Pakowanie .wotmod (release)

```sh
py -3.10 packaging/build_wotmod.py
```

Output do `dist/`:
- `spotmeter-v<wersja>.wotmod` — sam mod (do `mods/<wersja>/`)
- `spotmeter.json` — domyślny config (do `mods/configs/`)
- `INSTALL.txt` — instrukcja
- `spotmeter-v<wersja>.zip` — wszystko w jednym do dystrybucji

Wersja jest czytana z `packaging/meta.xml` — zaktualizuj tam przed kolejnym buildem.

### Hot-test podczas devu

```sh
cp build/mod_spotmeter.pyc "<WoT>/res_mods/2.2.1.3/scripts/client/gui/mods/"
cp src/spotmeter.json "<WoT>/mods/configs/"
```

`res_mods/` ma priorytet nad `mods/<wersja>/*.wotmod` więc lokalna zmiana w `res_mods/` wygrywa nad zainstalowaną wersją release'ową.
