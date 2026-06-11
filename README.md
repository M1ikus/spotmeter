# SpotMeter — WoT minimap mod

Dodaje na minimapie dodatkowy okrąg pokazujący odległość, z jakiej Twój czołg może zostać zauważony przez przeciwnika. Od **v6.0** dochodzą dwa przeciągalne panele GUIFlash: **panel bitewny** (lista przeciwników + picker celu) i **panel garażowy** (pre-konfiguracja przed bitwą), plus **auto-dobieranie** celu i pełne **PL/EN** UI. Panele pokazujesz/ukrywasz klawiszem **PageDown**.

> Build pod **WoT 2.3.0.1** · wersja moda **6.0.2**.

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

## Panel SpotMeter (v6.0)

Dwa przeciągalne panele renderowane przez wbudowany fork GUIFlash (`spotmeter_gf` — własny namespace, **nie wymaga** i nie koliduje z `gambiter.guiflash`). Jeden klawisz **PageDown** pokazuje/ukrywa panel — kontekstowo (w bitwie panel bitewny, w garażu garażowy).

### Panel bitewny
Stale widoczna lista przeciwników. Każdy wiersz: `[klasa] Nazwa xN  T<tier>  VR=XXXm`. Identyczne czołgi są grupowane w jeden wiersz (`battlePanelGroupSameTanks`, np. `Dravec x5`) — jeden przystanek w cyklu Numpad 2/8, bo ten sam model = ten sam VR = ten sam okrąg.
- **Linia „Cel:"** — pokazuje odległość spotu (`spot=XXXm`) dla wybranego przeciwnika. Gdy nic nie wybrane i auto OFF — pokazuje **Twój własny** czołg.
- **Linia AUTO** — stan auto-dobierania (ON/OFF).
- **Toggle / poziomy** — bieżący stan rations / BIA / recon / optyki / wentylacji / CVS.
- Wybór celu: **Numpad 2/8** lub klik na wierszu.
- **Auto-hide**: panel chowa się gdy trzymasz **TAB/N** (tablica wyników) i wraca po puszczeniu; chowa się też gdy otwierasz okna WG (jeśli `autoHidePanelOnWindow`). Stopka pod listą podpowiada `Naciśnij PgDn żeby ukryć panel`.

### Panel garażowy
Konfiguracja **przed** bitwą. Te same Numpady przełączają opcje na żywo i panel od razu to odzwierciedla. Widać stan AUTO. Auto-chowa się przy wejściu w zakładki (Badania / wyposażenie / amunicja / materiały eksploatacyjne).

### Auto-dobieranie (NumpadSlash) — „najświeższa akcja wygrywa"
- Włączenie AUTO → stosuje **preset per-klasa** (`autoPresets`) wg klasy aktualnie namierzonego czołgu. Lekkie: optyka+CVS na slocie + rations/BIA/recon ON; reszta (MT/HT/TD/SPG): optyka+CVS OFF + rations/BIA/recon ON. Preset stosuje się raz przy włączeniu auto (off→on by zaaplikować ponownie).
- Ręczny wybór (Numpad 2/8) **nadpisuje** auto; włączenie auto **nadpisuje** ręczny wybór (symetrycznie).
- Numpad 5 czyści ręczny wybór (przy auto ON wraca do auto).

### Język (i18n)
`language: "auto"` czyta język klienta WoT — `pl` → polski, cokolwiek innego → angielski. Wymuś przez `"pl"` / `"en"`.

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

1. **Picker aktywny** — bierzemy descriptor wybranego enemy (`strCompactDescr`), liczymy bazowy VR z wieży, dodajemy Stereoscope (auto z descriptora jeśli wykryta), ręcznie ustawiony poziom optyki / wentylacji / CVS oraz zaznaczone toggle (Rations, BIA, Recon+SitAware, Directives, Field Upgrades).
2. **`useOwnViewRange: true`** (default, picker nieaktywny) — bierzemy własny VR z `feedback.getVehicleAttrs()['circularVisionRadius']`. Serwer go syncuje (`VEHICLE_ATTRS_TO_SYNC`). Ten VR ma już naliczoną załogę, optykę, lornę itd.
3. **`useOwnViewRange: false`** — używamy `enemyViewRangeFallback` (domyślnie 445 m = max w grze).

## Model picker VR (v5.6 — dwustopniowy)

```
1. base_vr  ← descr.turret.circularVisionRadius
2. JEŚLI Field Upgrades ON i czołg w tabelce:
       base_vr ← min(base_vr * (1 + upgrade%), 445m)
3. Stage 1 — wzmacniacz załogi (liczony OD base_vr):
       crew_amplified ← base_vr * (1 + (Rations? 0.0430) + (BIA? 0.0253))
       (Rations i BIA liczone OD base_vr, nie od siebie; × ventsFactor gdy wentylacja > 0)
4. Stage 2 — bonusy addytywne (liczone OD crew_amplified):
       final ← crew_amplified
             + crew_amplified * (optics_factor * directive_factor - 1)   # poziom optyki
             + crew_amplified * (stereo_factor * directive_factor - 1)   # auto z descriptora (jeśli ma)
             + crew_amplified * (ReconSitAware_factor - 1)               # toggle
```

| toggle / poziom | klawisz | config | default |
|---|---|---|---|
| Rations | Numpad 7 | `pickerVRBonusRations` `1.0430` | **ON** (+4.30%) |
| BIA | Numpad 3 | `pickerVRBonusBIA` `1.0253` | **ON** (+2.53%) |
| Recon + SitAware (bundle) | Numpad 4 | `pickerVRBonusReconSitAware` `1.0739` | **ON** (+7.39%) |
| Optyka — poziom 0–4 | Numpad 6 | `pickerOpticsFactors` | `4` (Ulepszona) |
| Wentylacja — poziom 0–4 | Numpad + | `pickerVentsFactors` | `0` (OFF) |
| CVS — poziom 0–2 | Numpad − | `pickerCvsFactors` | `0` (OFF) |
| Directives na sprzęt | Numpad 1 | `pickerVRBonusDirective` `1.0250` | OFF |
| Field Upgrades VR (BETA) | Numpad 0 | `pickerFieldUpgradeVR` | OFF |

**Poziomy** (serwer w WoT 2.x nie wysyła `optionalDevices` przeciwnika, więc optyka / wentylacja / CVS są ręcznie cyklowane):
- **Optyka** `[1.0, 1.10, 1.115, 1.125, 1.135]` = 0 OFF / 1 zwykła / 2 na slocie / 3 Z nagród (czerwona) / 4 Ulepszona (fioletowa)
- **Wentylacja** `[1.0, 1.05, 1.0625, 1.075, 1.085]` — mnoży addytywne bonusy załogi (rations / BIA / recon)
- **CVS** `[1.0, 0.900, 0.875]` = 0 OFF / 1 zwykły / 2 na slocie. CVS przeciwnika obniża **NASZE** camo w ruchu (mocniej nas widzi), więc mnożniki < 1.0.

Plus **Stereoscope** ×1.25 z descriptora, jeśli wykryta (założenie: zawsze aktywna; `pickerAssumeStereoscope` / `pickerStereoscopeFallback`).

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

- `spotmeter-v<wersja>.wotmod` → wrzuć do `<WoT>/mods/2.3.0.1/`
- `spotmeter.json` (opcjonalny) → wrzuć do `<WoT>/mods/configs/`
- `INSTALL.txt` — szczegółowa instrukcja krok po kroku

Gra automatycznie ładuje wszystkie `.wotmod` z `mods/<wersja>/` po starcie. Bez configu mod używa sensownych domyślnych wartości.

## Hotkeys (numpad layout)

```
+-----+-----+-----+-----+
|     |  /  |  *  |  -  |   /=auto-pick  *=dump enemy  -=CVS poziom
+-----+-----+-----+-----+
|  7  |  8  |  9  |  +  |   7=rations  8=prev  9=live-mode  +=wentylacja poziom
+-----+-----+-----+-----+
|  4  |  5  |  6  |     |   4=recon+sitaware  5=clear  6=optyka poziom
+-----+-----+-----+-----+
|  1  |  2  |  3  |Enter|   1=directives  2=next  3=BIA  Enter=snapshot
+-----+-----+-----+-----+
|     0     |  .  |         0=field-upgrades(BETA)  .=reload-config
+-----+-----+-----+-----+

   PageDown = pokaż/ukryj panel (bitwa + garaż)
```

| akcja | klawisz | config | default |
|---|---|---|---|
| następny przeciwnik | Numpad 2 | `pickerNextKey` | — |
| poprzedni przeciwnik | Numpad 8 | `pickerPrevKey` | — |
| wyczyść picker | Numpad 5 | `pickerClearKey` | — |
| toggle Rations | Numpad 7 | `pickerRationsKey` | **ON** |
| toggle BIA | Numpad 3 | `pickerBIAKey` | **ON** |
| toggle Recon + SitAware | Numpad 4 | `pickerReconSitAwareKey` | **ON** |
| cykl poziomu **optyki** (0–4) | Numpad 6 | `pickerOpticsKey` | 4 |
| cykl poziomu **wentylacji** (0–4) | Numpad + | `pickerVentsKey` | 0 |
| cykl poziomu **CVS** (0–2) | Numpad − | `pickerCvsKey` | 0 |
| toggle Directives | Numpad 1 | `pickerDirectivesKey` | OFF |
| toggle Field Upgrades (BETA) | Numpad 0 | `pickerFieldUpgradesKey` | OFF |
| **auto-dobieranie celu** | Numpad / | `autoPickToggleKey` | OFF |
| toggle live-mode overlay | Numpad 9 | `overlayToggleKey` | OFF |
| status snapshot | NumpadEnter | `overlayPrintNowKey` | — |
| dump descriptor enemy do logu | Numpad **\*** | `pickerDiagDumpKey` | — |
| reload configu | NumpadPeriod | `reloadKey` | — |
| **pokaż/ukryj panel** (bitwa + garaż) | **PageDown** | `panelToggleKey` | — |

Działa przy **NumLock włączonym i wyłączonym**. **PageDown** jest poza numpadem — `KEY_PGDN` został zwolniony z aliasu Numpad3/BIA (Numpad3 dalej robi BIA), więc służy jako kontekstowy pokaż/ukryj panelu.

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
| `pickerVRBonusBIA` | `1.0253` | mnożnik gdy toggle BIA ON (stage 1) |
| `pickerVRBonusReconSitAware` | `1.0739` | mnożnik gdy toggle Recon+SitAware ON (stage 2) |
| `pickerVRBonusDirective` | `1.0250` | mnożnik na auto-wykryte sprzęty gdy toggle Directives ON |
| `pickerFieldUpgradeVR` | per-tank dict | **BETA**, mapuje `shortName` → % VR upgrade |
| `pickerFieldUpgradeCap` | `445.0` | cap na `base_vr` po zastosowaniu upgrade'u (m) |
| `pickerAssumeStereoscope` | `true` | jeśli enemy ma lornetkę, zakłada że jest aktywna |
| `pickerStereoscopeFallback` | `1.25` | mnożnik VR jeśli odczyt z descriptora padnie |
| `pickerIncludeDeadEnemies` | `false` | czy uwzględniać martwych w cyklu |
| `overlayEnabled` | `true` | włącza overlay tekstu (chat-line nad minimapą) |
| `overlayShowOnTickChange` | `true` | automatycznie pokazuje przy istotnej zmianie radiusa |
| `overlayMinRadiusDelta` | `15.0` | próg zmiany w m do auto-display |
| `pickerNextKey` | `KEY_NUMPAD2` | następny przeciwnik |
| `pickerPrevKey` | `KEY_NUMPAD8` | poprzedni przeciwnik |
| `pickerClearKey` | `KEY_NUMPAD5` | wyczyść picker |
| `pickerRationsKey` | `KEY_NUMPAD7` | toggle Rations |
| `pickerBIAKey` | `KEY_NUMPAD3` | toggle BIA |
| `pickerReconSitAwareKey` | `KEY_NUMPAD4` | toggle Recon + SitAware |
| `pickerDirectivesKey` | `KEY_NUMPAD1` | toggle Directives |
| `pickerFieldUpgradesKey` | `KEY_NUMPAD0` | toggle Field Upgrades (BETA) |
| `pickerDiagDumpKey` | `KEY_NUMPADSTAR` | dump enemy descriptor do `python.log` |
| `overlayToggleKey` | `KEY_NUMPAD9` | toggle overlay tekstu |
| `overlayPrintNowKey` | `KEY_NUMPADENTER` | pokaż pełen status snapshot |
| `reloadKey` | `KEY_NUMPADPERIOD` | reload configu |
| `logCalcDetails` | `false` | wypisuje camo/radius/state do `python.log` |

Nazwy klawiszy: nazwy z modułu `Keys` (np. `KEY_F8`, `KEY_F7`, `KEY_HOME`, `KEY_INSERT`). Pusty string = bez hotkeya.

### Konfiguracja v6.0 — panele, auto-dobieranie, język

| pole | default | opis |
|---|---|---|
| `language` | `"auto"` | `auto` = język klienta WoT (`pl`→PL, reszta→EN); wymuś `"pl"` / `"en"` |
| `panelToggleKey` | `KEY_PGDN` | pokaż/ukryj panel (bitwa + garaż), kontekstowy |
| `battlePanelEnabled` | `true` | widoczność panelu bitewnego na starcie |
| `battlePanelX/Y/W/H` | `10 / 400 / 320 / 380` | pozycja i rozmiar panelu bitewnego (przeciągalny, zapisuje się) |
| `battlePanelGroupSameTanks` | `true` | grupuje identyczne czołgi w jeden wiersz (`Nazwa xN`) |
| `autoHidePanelOnWindow` | `true` | chowa panel gdy otwarte okno WG; wraca po zamknięciu |
| `battleHidePanelKeys` | `["KEY_TAB","KEY_N"]` | trzymanie któregoś chowa panel w bitwie |
| `garagePanelEnabled` | `true` | widoczność panelu garażowego |
| `garagePanelX/Y/W/H` | `1500 / 320 / 380 / 320` | pozycja i rozmiar panelu garażowego |
| `autoPickEnabled` | `false` | auto-dobieranie najbliższego przeciwnika |
| `autoPickToggleKey` | `KEY_NUMPADSLASH` | klawisz auto-dobierania |
| `autoPickRangeMeters` | `445.0` | maks. zasięg auto-dobierania |
| `autoPickCacheTimeoutSec` | `5.0` | jak długo trzymać ostatnią pozycję gdy spotter mrugnie |
| `autoPresetsEnabled` | `true` | stosuje preset per-klasa przy włączeniu AUTO |
| `autoPresets` | per-klasa | rations/BIA/recon/directives/fieldUpgrades + optics/vents/cvs wg klasy |
| `defaultToggles` | rations/BIA/recon ON | które toggle są ON na starcie bitwy |
| `defaultLevels` | optics 4, vents 0, cvs 0 | startowe poziomy optyki / wentylacji / CVS |
| `pickerOpticsKey` | `KEY_NUMPAD6` | cykl poziomu optyki (0–4) |
| `pickerVentsKey` | `KEY_ADD` | cykl poziomu wentylacji (0–4) |
| `pickerCvsKey` | `KEY_NUMPADMINUS` | cykl poziomu CVS (0–2) |
| `pickerOpticsFactors` | `[1.0, 1.10, 1.115, 1.125, 1.135]` | mnożniki VR per poziom optyki |
| `pickerVentsFactors` | `[1.0, 1.05, 1.0625, 1.075, 1.085]` | mnożniki bonusów załogi per poziom wentylacji |
| `pickerCvsFactors` | `[1.0, 0.900, 0.875]` | mnożniki NASZEGO camo w ruchu gdy enemy ma CVS |

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
6. **Panele v6.0** renderuje przez forka GUIFlash (`gui.mods.spotmeter_gf` — własny namespace + SWF) jako niezależny overlay; **nie modyfikuje plików UI Wargamingu**. Patchuje dodatkowo `Avatar.shoot/shootDualGun` (kara za strzał) — **patche wrapperem wołającym oryginał** + try/except, więc komponują się z innymi modami (np. XVM) i nie crashują. (W v6.0.1 usunięto patch `PlayerFullNameFormatter` — marker przy nicku nigdy się porządnie nie renderował i był zbędny przy panelu; o jeden monkey-patch mniej = mniejsza powierzchnia konfliktu.)

## Roadmap

### v6.0 — panele GUIFlash + auto-dobieranie ✅

- **Panel bitewny** — stała lista przeciwników z VR, grupowanie identycznych czołgów, linia „Cel" ze spot-distance, stan AUTO; wybór Numpad 2/8 lub klik na wierszu
- **Panel garażowy** — pre-konfiguracja toggli/poziomów przed bitwą, podgląd na żywo, stan AUTO; auto-hide przy zakładkach
- **PageDown** — kontekstowy pokaż/ukryj panelu (bitwa + garaż)
- **Auto-dobieranie** (Numpad /) — najbliższy przeciwnik jako cel; model „najświeższa akcja wygrywa"; presety per-klasa
- **Optyka / Wentylacja / CVS jako cyklowane poziomy** (Numpad 6 / + / −) — serwer 2.x nie wysyła `optionalDevices` przeciwnika
- **BIA wydzielone** na Numpad 3 (Recon+SitAware zostaje na Numpad 4)
- **Auto-hide panelu** — TAB/N w bitwie + okna WG w garażu
- **i18n** — angielski + polski, auto-detekcja z języka klienta
- Fork GUIFlash (`spotmeter_gf`) — własny namespace, koegzystuje z `gambiter.guiflash`

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
cp build/mod_spotmeter.pyc "<WoT>/res_mods/2.3.0.0/scripts/client/gui/mods/"
cp src/spotmeter.json "<WoT>/mods/configs/"
```

`res_mods/` ma priorytet nad `mods/<wersja>/*.wotmod` więc lokalna zmiana w `res_mods/` wygrywa nad zainstalowaną wersją release'ową.
