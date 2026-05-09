# SpotMeter — WoT minimap mod

Dodaje na minimapie dodatkowy okrąg pokazujący odległość, z jakiej Twój czołg może zostać zauważony przez przeciwnika.

## Co automatycznie / co ręcznie

Granica jest prosta: wszystko co jest w **descriptorze pojazdu** (transmitowanym przez serwer w `strCompactDescr`) bierzemy automatycznie. Reszta jest manualnym toggle.

| Element | Auto / manualne | Skąd |
|---|---|---|
| Hull / turret / gun / engine / radio | ✅ auto | `descr.turret.circularVisionRadius` itd. |
| Coated Optics przeciwnika | ✅ auto | `descr.miscAttrs.circularVisionRadiusFactor` (już z optyką) |
| Stereoscope przeciwnika | ✅ auto + toggle Numpad 7 | `descr.optionalDevices` (Stereoscope class) |
| Enhancements / dyrektywy w slotach equipment | ✅ auto | `descr.miscAttrs` jest rebuildowany po `installEnhancements` |
| **Ulepszenia polowe (post-progression) WŁASNE** | ✅ auto | `Vehicle.getDescr` woła `VehicleDescr(..., extData=self)` → `__applyExternalData` woła `installModifications` |
| **Ulepszenia polowe ENEMY** | ❌ manual toggle (proxy via BIA/Recon/Vents) | `Vehicle.def` ma `vehPostProgression` jako `MY_VEHICLE` — server transmituje tylko właścicielowi |
| Camo net na **własnym** czołgu | ✅ auto, aktywne po 3s | `descr.optionalDevices` (CamouflageNet class) |
| Tryby siege (CS-63 itp.) | ✅ auto | `CompositeVehicleDescriptor` w silniku |
| Kara za strzał | ✅ auto | hook na `Avatar.shoot` + `miscAttrs.invisibilityFactorAtShot` |
| Skille załogi (BIA/Recon/SitAware) | ❌ manual toggle | serwer nie wysyła |
| Consumablesy (rations/vents) | ❌ manual toggle | serwer nie wysyła aktywnego stanu |

W praktyce: po wybraniu enemy pickerem, jego VR od razu zawiera Coated Optics + Stereoscope + dyrektywy w slotach (jeśli są na tym czołgu). Toggle perków / consumables nakładasz tylko gdy zakładasz że enemy je faktycznie ma. Ulepszenia polowe (field upgrades, post-progression) enemy są niewidoczne dla klienta — pokrywasz je przez stack BIA + Recon + SitAware + Vents (typowo +5–10% łącznie).

> **Weryfikacja własnych field upgrades:** naciśnij **NumpadEnter** (status snapshot) — w chacie pojawi się m.in. linia `myVR: base=410m * factor=1.103` i `myCamo: base(...) + add=0.025`. Jeśli `factor>1.0` lub `add>0.0`, ulepszenia polowe są naliczone w descriptorze.



- **Czerwony** w ruchu (camo `invMoving`)
- **Zielony** w postoju (camo `invStill`)
- **Ciemnozielony** w postoju 3s+ z aktywną siatką maskującą (camo `invStill + camoNetBonus`)
- **Pomarańczowy** ~3s po strzale (camo `* invisibilityFactorAtShot`)
- Czołgi lekkie / niektóre kołowe — w XML mają `invMoving == invStill`, więc okrąg po prostu nie zmienia rozmiaru. Bez specjalnego case'u.
- Czołgi z trybem siege (CS-63, S-Conqueror, italian heavies) — silnik gry sam podmienia descriptor (`CompositeVehicleDescriptor`) na właściwy tryb, więc mod automatycznie używa odpowiedniego camo dla obecnego trybu.

## Wzór (zgodny z `scripts/common/items/utils.py:getInvisibility`)

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

- **Domyślnie (`useOwnViewRange: true`)** — bierzemy własny VR z `feedback.getVehicleAttrs()['circularVisionRadius']`. Serwer go syncuje (potwierdzone w `constants.py`: `VEHICLE_ATTRS_TO_SYNC = frozenset(['circularVisionRadius', ...])`). Ten VR ma już naliczoną załogę, optykę, lornę itd.
- **`useOwnViewRange: false`** — używamy `enemyViewRangeFallback` (domyślnie 445 m = max w grze).

## Instalacja (release / dla kolegi)

Pobierz `spotmeter-v<wersja>.zip` z [GitHub Releases](https://github.com/M1ikus/spotmeter/releases). W środku:

- `spotmeter-v<wersja>.wotmod` → wrzuć do `<WoT>/mods/2.2.1.2/`
- `spotmeter.json` (opcjonalny) → wrzuć do `<WoT>/mods/configs/`
- `INSTALL.txt` — szczegółowa instrukcja krok po kroku

Gra automatycznie ładuje wszystkie `.wotmod` z `mods/<wersja>/` po starcie. Bez configu mod używa sensownych domyślnych wartości.

## Instalacja (dev / własny build)

1. `build/mod_spotmeter.pyc` →  
   `<WoT>/res_mods/2.2.1.2/scripts/client/gui/mods/mod_spotmeter.pyc`
2. `src/spotmeter.json` →  
   `<WoT>/mods/configs/spotmeter.json`

Ten mod był zbudowany pod **WoT 2.2.1.2** (Py 2.7 bytecode, magic `03 F3 0D 0A`). Po patchu gry trzeba zwykle przekompilować i wrzucić do nowej wersji `res_mods/<wersja>/...`.

> **Migracja z `wot_spot_mod`:** loader nadal akceptuje stare ścieżki configu (`wot_spot_mod.json` itp.) jako fallback, ale plik moda przy nowej nazwie to `mod_spotmeter.pyc` — usuń stary `mod_spot_circle.pyc` żeby nie ładowały się obie kopie naraz.

## Konfiguracja (`spotmeter.json`)

| pole | default | opis |
|---|---|---|
| `enabled` | `true` | wyłącza moda bez odinstalowywania |
| `useOwnViewRange` | `true` | używa Twojego VR jako założonego VR przeciwnika |
| `enemyViewRangeFallback` | `445.0` | VR używany kiedy `useOwnViewRange = false` |
| `crewCamoBonus` | `1.05` | przybliżenie bonusu skilla Camouflage |
| `colorMoving` | `0xFF6347` | kolor okręgu w ruchu |
| `colorStill` | `0x32CD32` | kolor okręgu w postoju |
| `colorAfterShot` | `0xFFA500` | kolor okręgu po strzale (przez `fireRevealDuration`) |
| `colorCamoNet` | `0x228B22` | kolor okręgu gdy siatka aktywna (postój 3s+) |
| `alpha` | `70` | przezroczystość 0–100 |
| `tickInterval` | `0.2` | jak często aktualizować (s) |
| `movingSpeedThreshold` | `0.5` | prędkość uznawana za ruch (m/s) |
| `applyFirePenalty` | `true` | po strzale aplikuje `* invisibilityFactorAtShot` |
| `fireRevealDuration` | `3.0` | czas trwania kary za strzał (s) |
| `applyCamoNet` | `true` | uwzględnia siatkę maskującą po `camoNetActivateSec` w postoju |
| `camoNetActivateSec` | `3.0` | czas postoju do aktywacji siatki (s) |
| `camoNetFallbackBonus` | `0.05` | bonus jeśli odczyt z descriptora padnie |
| `pickerAssumeStereoscope` | `true` | jeśli enemy ma lornetkę, zakłada że jest aktywna |
| `pickerStereoscopeFallback` | `1.25` | mnożnik VR jeśli odczyt z descriptora padnie |
| `overlayEnabled` | `true` | włącza overlay tekstu (chat-line nad minimapą) |
| `overlayShowOnTickChange` | `true` | automatycznie pokazuje przy istotnej zmianie radiusa |
| `overlayMinRadiusDelta` | `15.0` | próg zmiany w m do auto-display |
| `pickerEnabled` | `true` | włącza picker przeciwnika (PgUp/PgDn) |
| `pickerNextKey` | `KEY_NUMPAD2` | następny przeciwnik |
| `pickerPrevKey` | `KEY_NUMPAD8` | poprzedni przeciwnik |
| `pickerClearKey` | `KEY_NUMPAD0` | wyczyść picker |
| `pickerRationsKey` | `KEY_NUMPAD1` | toggle Combat Rations |
| `pickerVentsKey` | `KEY_NUMPAD3` | toggle Improved Ventilation |
| `pickerBIAKey` | `KEY_NUMPAD4` | toggle Brothers in Arms |
| `pickerReconKey` | `KEY_NUMPAD5` | toggle Recon (commander) |
| `pickerSitAwareKey` | `KEY_NUMPAD6` | toggle Sit. Awareness (radio) |
| `pickerStereoKey` | `KEY_NUMPAD7` | toggle założenia o lornetce |
| `overlayToggleKey` | `KEY_NUMPAD9` | toggle overlay tekstu |
| `overlayPrintNowKey` | `KEY_NUMPADENTER` | pokaż aktualny spot teraz |
| `reloadKey` | `KEY_NUMPADPERIOD` | reload configu |
| `pickerVRBonusRations` | `1.10` | mnożnik gdy Rations ON |
| `pickerVRBonusVents` | `1.05` | mnożnik gdy Vents ON |
| `pickerVRBonusBIA` | `1.05` | mnożnik gdy BIA ON |
| `pickerVRBonusRecon` | `1.02` | mnożnik gdy Recon ON |
| `pickerVRBonusSitAware` | `1.03` | mnożnik gdy SitAware ON |
| `pickerMarker` | `"● "` | prefix nazwy wybranego przeciwnika |
| `pickerIncludeDeadEnemies` | `false` | czy uwzględniać martwych w cyklu |
| `logCalcDetails` | `false` | wypisuje camo/radius/state do `python.log` |

Nazwy klawiszy: nazwy z modułu `Keys` (np. `KEY_F8`, `KEY_F7`, `KEY_HOME`, `KEY_INSERT`). Pusty string = bez hotkeya.

## Co serwer faktycznie wysyła do klienta?

Tak, sprawdziłem w zdekompilowanych plikach `scripts/common/constants.py` i `scripts/client/Avatar.py`:

- **View range**: tak, `circularVisionRadius` (m) jest jawnie syncowany z serwerem (`VEHICLE_ATTRS_TO_SYNC`). Mamy go w `feedback.getVehicleAttrs()` w trakcie bitwy.
- **Camouflage / invisibility**: NIE jest syncowane jako pojedyncza liczba. Klient liczy go sam z deskryptora pojazdu (`computeBaseInvisibility` + `getInvisibility` w `scripts/common/items/utils.py`). Wszystkie składniki potrzebne do tego (`type.invisibility`, `miscAttrs.invisibilityFactor`, `miscAttrs.invisibilityBaseAdditive`, `miscAttrs.invisibilityAdditiveTerm`, `miscAttrs.invisibilityMultFactor`) są w pełni dostępne klientowi z deskryptora czołgu — to nic niejawnego.

Innymi słowy: mod nie odczytuje żadnej informacji do której nie miałby normalnie dostępu. Liczy tylko z Twojego czołgu i ze stałych z gry.

## Aspekt prawny / fair-play

- **Mod jest legalny w świetle Wargaming Fair Play Policy.** WG od dawna toleruje (i zalicza do oficjalnych przykładów) okręgi widoczności na minimapie — patrz np. domyślne ustawienia gry `MINIMAP_VIEW_RANGE` / `MINIMAP_MAX_VIEW_RANGE` / `MINIMAP_MIN_SPOTTING_RANGE` (są to opcje wbudowane). XVM, Aslain's modpack i inne ogólnodostępne packi zawierają od lat funkcję "Spot Range Circle" — działa to dokładnie tak jak ten mod.
- Zakazane są mody, które (a) pokazują pozycje przeciwników, których normalnie nie widzisz (np. tracery wyłączone, wallhack), (b) automatyzują celowanie / poruszanie się, (c) odczytują dane serwerowe, do których klient nie ma normalnie dostępu, (d) omijają płatne funkcje gry. Ten mod NIC z tej listy nie robi — pokazuje wyłącznie metryki dotyczące Twojego własnego czołgu (camo + VR), które w pełni pochodzą z deskryptora Twojego pojazdu.
- Dla pewności: w Public Test / Sandbox czasem pojawiają się tymczasowe restrykcje moddingowe (zwłaszcza w turniejach). Na zwykłym serwerze losowych bitew okręgi widoczności są w porządku.

Linki referencyjne (w razie wątpliwości warto sprawdzić aktualną wersję):  
- [WG EU Fair Play Policy](https://eu.wargaming.net/support/en/products/wot/article/29104/) — kategoria "Allowed mods" obejmuje minimap improvements/markers.

## Hot-reload w bitwie

W bitwie naciśnij `F8` (lub klawisz z `reloadKey`) — config wczytuje się ponownie i okrąg uwzględnia nowe wartości w czasie 1 ticka (0.2 s). Pozwala iterować nad kolorami / VR / `crewCamoBonus` bez zamykania bitwy.

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

### v5 — numpad layout, per-perk toggles, overlay text ✅

- **Numpad-based hotkeys**: cały picker przeniesiony na klawiaturę numeryczną (8/2/0 dla pickera, 4/5/6 dla perków załogi, 1/3 dla rations/vents, 7 dla lornetki, 9 dla overlay, NumpadEnter dla print-now, NumpadPeriod dla reload).
- **Perki rozdzielone na osobne toggle**: każdy modyfikator (Rations, Vents, BIA, Recon, Sit. Awareness) ma swój klawisz i konfigurowalny mnożnik. Przed v5 było tylko zbiorcze "+perks". Teraz można precyzyjnie odzwierciedlić znany stan przeciwnika (np. tylko Rations jeśli wiemy że jest light z colą ale bez perków).
- **Overlay tekstu nad minimapą**: chat-line w battle-message-feed (obszar nad minimapą) z formatu `[SpotMod] Spot: 287 m (postoj, vs VR 445 m) | target: RhmPzW VR=587m [+rations +bia]`. Domyślnie pokazuje się przy istotnych zmianach radiusa (>15m delta) lub stanu (still↔moving↔afterShot). NumpadEnter wymusza print teraz, Numpad9 włącza/wyłącza auto-display.

Implementacja overlay'a używa `MessengerEntry.g_instance.gui.addClientMessage(text, isCurrentPlayer=True)` — to wbudowany kanał komunikatów klient-only (nie wysyłany na serwer). Wiadomości pojawiają się w tym samym miejscu co system messages od gry.

### v4.5 — binoculars in picker + camo net for own tank ✅

Conditional optional devices uwzględnione zgodnie z `scripts/common/items/artefacts.py`:

- **Stereoscope (lornetka)** w pickerze — gdy wykryta w `descr.optionalDevices`, automatycznie aplikuje czynnik `circularVisionRadiusFactor.getActiveValue(level)` (typowo `1.25` dla tier I, więcej dla improved/bond). Worst-case assumption: lorna jest zawsze aktywna (3s standstill check pomijamy bo nie wiemy kiedy enemy zaczął stać). Toggle przez `pickerAssumeStereoscope`.
- **CamouflageNet (siatka)** dla własnego czołgu — silnik gry trackuje `_LAST_MOVEMENT_TIME`. Po `camoNetActivateSec` (default `3.0` s) bez ruchu siatka się aktywuje i bonus `invisibilityBonus` jest dodawany do `additive` w wzorze. Zgodnie z grą: strzał nie resetuje timera ruchu, tylko sam ruch resetuje. Kolor okręgu zmienia się na **ciemnozielony** w tym stanie.

Kod sczytuje wartości z descriptora przez `device.defineActiveValueForSpecFactor(descr, 'invisibilityBonus', level)` / `device.circularVisionRadiusFactor.getActiveValue(level)` — czyli używamy DOKŁADNIE tych wartości, których używa gra. Fallback constants (`camoNetFallbackBonus=0.05`, `pickerStereoscopeFallback=1.25`) tylko jeśli odczyt descriptora padnie z jakiegoś powodu.

### v3 — fire penalty + siege modes ✅

- **Kara za strzał (firePenalty)** — hook na `PlayerAvatar.shoot()` i `shootDualGun()`. Przez `fireRevealDuration` (domyślnie 3 s) po strzale aplikujemy `camo *= invisibilityFactorAtShot` z descryptora działa. Okrąg w tym czasie świeci pomarańczowo (`colorAfterShot`).
- **Tryby (CS-63, S-Conqueror, italian heavy, etc.)** — silnik gry obsługuje to automatycznie. `vehicle.typeDescriptor` jest `CompositeVehicleDescriptor`, który dynamicznie deleguje atrybuty do właściwego sub-descriptora (default vs siege) na podstawie aktualnego stanu (`__vehicleMode`). Mod nie wymaga osobnej obsługi — `descr.type.invisibility` zwraca prawidłowe wartości dla bieżącego trybu out of the box.
- **EBR / wheeled** — bez specjalnego case'u; XML czołgu ma `invMoving == invStill`, mod automatycznie pokazuje stały okrąg.

### v4 — picker enemy tank ✅

W bitwie wybierasz konkretnego przeciwnika hotkeyami i okrąg dostosowuje się do jego VR. Server wysyła pełny `strCompactDescr` każdego pojazdu od początku bitwy (potwierdzone w `gui/battle_control/arena_info/arena_vos.py:277`), więc dekodujemy lokalnie:

```python
from items.vehicles import VehicleDescr
descr = VehicleDescr(compactDescr=enemy.vehicleType.strCompactDescr)
base_vr = descr.turret.circularVisionRadius
vr_factor = descr.miscAttrs.get('circularVisionRadiusFactor', 1.0)  # optyka itd.
estimated_vr = base_vr * vr_factor
# opcjonalnie * pickerVRBonusRations (default 1.10) jeśli zakładamy racje bojowe
# opcjonalnie * pickerVRBonusPerks (default 1.10) jeśli zakładamy BIA + Recon + SitAware
```

#### Hotkeys (numpad layout, configurable)

```
+-----+-----+-----+-----+
|     |  /  |  *  |  -  |    /=dir-camo-net (own)  *=dir-stereo  -=dir-vents
+-----+-----+-----+-----+
|  7  |  8  |  9  |  +  |    7=stereo   8=prev    9=overlay-toggle  +=dir-optics
+-----+-----+-----+-----+
|  4  |  5  |  6  |     |    4=BIA      5=Recon   6=SitAware
+-----+-----+-----+-----+
|  1  |  2  |  3  |Enter|    1=rations  2=next    3=vents   Enter=print-now
+-----+-----+-----+-----+
|     0     |  .  |          0=clear-picker   .=reload-config
+-----+-----+-----+-----+
```

**Picker — wybór przeciwnika**
| akcja | klawisz | config |
|---|---|---|
| następny przeciwnik | Numpad 2 | `pickerNextKey` |
| poprzedni przeciwnik | Numpad 8 | `pickerPrevKey` |
| wyczyść picker | Numpad 0 | `pickerClearKey` |
| toggle założenia o lornetce | Numpad 7 | `pickerStereoKey` |

**Załoga (perki)**
| akcja | klawisz | config |
|---|---|---|
| toggle Brothers in Arms (BIA) | Numpad 4 | `pickerBIAKey` |
| toggle Recon (commander) | Numpad 5 | `pickerReconKey` |
| toggle Sit. Awareness (radio) | Numpad 6 | `pickerSitAwareKey` |

**Equipment / consumables**
| akcja | klawisz | config |
|---|---|---|
| toggle racji bojowych | Numpad 1 | `pickerRationsKey` |
| toggle ulepszonej wentylacji | Numpad 3 | `pickerVentsKey` |

**Overlay / diag / reload**
| akcja | klawisz | config |
|---|---|---|
| toggle overlay tekstu (auto) | Numpad 9 | `overlayToggleKey` |
| pełen status snapshot | NumpadEnter | `overlayPrintNowKey` |
| dump descriptor enemy do logu | Numpad **\*** | `pickerDiagDumpKey` |
| reload configu | NumpadPeriod | `reloadKey` |

#### Założenia w obliczeniach
Domyślnie zakładamy że przeciwnik **NIE MA** consumablesów ani VR-perks (bo serwer tego nie wysyła). Każdy modyfikator ma własny toggle z osobnym multiplikatorem (multiplikatywne, mnożone razem przy stackowaniu):

| toggle | klawisz | mnożnik (config) | default |
|---|---|---|---|
| Recon (commander perk) | Numpad 5 | `pickerVRBonusRecon` | `1.02` |
| Situational Awareness (radio perk) | Numpad 6 | `pickerVRBonusSitAware` | `1.03` |
| Combat Rations / cola / coffee | Numpad 1 | `pickerVRBonusRations` | `1.01` |
| Improved Ventilation | Numpad 3 | `pickerVRBonusVents` | `1.005` |
| Brothers in Arms | Numpad 4 | `pickerVRBonusBIA` | `1.005` |

#### Skąd te liczby się biorą

Z `VehicleDescrCrew.py:_process_perk` i `perks.xml`:
- **Recon** (`commander_eagleEye`): `factor_per_level = 0.0002` → +2% przy 100% skilla
- **SitAware** (`radioman_finder`): `factor_per_level = 0.0003` → +3% przy 100% skilla
- **Końcowe**: `VR_factor = cvrA × (1 + cvrB)`, gdzie `cvrB = Recon + SitAware`

Brotherhood, Vents i Rations **NIE** mnożą VR bezpośrednio — boostują tylko *efektywny poziom skilli załogi* (`crewLevelIncrease`):
- BIA: `+5` poziomów (`brotherhood.crewLevelIncrease = 0.05` przy max)
- Vents (basic): `+5` poziomów (`miscAttrs/crewLevelIncrease += 5`)
- Rations: `+10` poziomów (`crewLevelIncrease = 10`)

Te +20 poziomów łącznie skaluje Recon (`120 × 0.0002 = 0.024` zamiast `100 × 0.0002 = 0.02`) i SitAware (`120 × 0.0003 = 0.036` zamiast `0.030`). Cały stack BIA + Vents + Rations dorzuca do cvrB tylko `0.0085` (+0.85% do VR).

**Tryhard stack realny:** `1.02 × 1.03 × 1.005 × 1.005 × 1.01 ≈ 1.07` (+7% do VR z manualnych toggle).
**Plus** auto-detekcja Coated Optics (×1.10) i Stereoscope (×1.25) z descriptora — czyli totalny tryhard (full perki + lornetka aktywna): `1.07 × 1.10 × 1.25 ≈ 1.47` (+47% do VR).

> **v5.2.3 fix:** Wcześniejsze defaulty `BIA=1.05, Vents=1.05, Rations=1.10` traktowały te toggle jak bezpośrednie multiplikatory VR. To było ZA WYSOKO ~20 punktów procentowych przy stacku. Sprawdziłem mechanikę w grze i obniżyłem do realistycznych wartości.

> **v5.2 cleanup:** w wersjach v5.0–v5.1 były dodatkowe toggle dla dyrektyw enemy (`pickerOpticsDirective`, `pickerVentsDirective`, `pickerStereoDirective`) oraz dla dyrektywy siatki własnego czołgu (`ownCamoNetDirective`, "Naturalne maskowanie"). **Wszystkie usunięte:**
> - Dyrektywy w slotach equipment (optics / vents / stereoscope) są już naliczone w `descr.miscAttrs.circularVisionRadiusFactor` przy budowie descriptora — manualny mnożnik podwójnie liczył.
> - "Naturalne maskowanie" sprawdziłem w `battle_boosters.xml` — taka dyrektywa po prostu nie istnieje w WoT 2.x. Wymyślona z głowy w v3 na podstawie starych źródeł WoT 1.x. Wycofana.
> 
> Wszystkie pozostałe toggle (BIA, Recon, SitAware, rations, vents) są ściśle dla **VR przeciwnika** (w pickerze) — nasz własny camo bierze się z descriptora bez interakcji.

Podczas bitwy widać aktywne flagi w logu (`python.log` → `SpotMeter: picker -> RhmPzW VR=587m [+rations +bia +recon] | stereo=on`).

#### Wizualny marker
Hook na `PlayerFullNameFormatter.format` wstrzykuje konfigurowalny prefix (`pickerMarker`, default `'● '`) przed nazwę gracza dla wybranego czołgu. **Caveat:** classic players panel (top-right) nie udostępnia API do natychmiastowej zmiany wyświetlanej nazwy — marker pojawia się przy najbliższym naturalnym redraw'ie wiersza (zmiana HP, śmierć, otwarcie pełnego panelu Tab). Kliknij Tab dla pełnej listy ze świeżą formatą.

Główny feedback: **zmiana rozmiaru okręgu na minimapie** — od razu po cyklu okrąg dostosowuje się do nowego VR-u.

#### Co serwer wysyła i czego brakuje
| pole | dostępne klientowi | uwagi |
|---|---|---|
| model czołgu, hull/turret/gun/engine | ✅ | z `strCompactDescr` |
| zainstalowany sprzęt (binokle, optyka itd.) | ✅ | z `strCompactDescr` |
| camouflage skin / styl | ✅ | z `strCompactDescr` |
| tier, klasa, rola, max HP | ✅ | z `VehicleTypeInfoVO` |
| skille załogi (Recon, Sit. Awareness, BIA) | ❌ | toggle `pickerVRBonusPerks` |
| aktywne consumable'y (cola, kawa) | ❌ | toggle `pickerVRBonusRations` |
| czy lorna jest właśnie aktywna (3s standstill) | ❌ | nie modelujemy w v4 |

### v5 — UI/UX

- **Pełen settings panel** w `Settings → Mods` zamiast pliku JSON. Wymaga osobnego SWF / Pythonowego widoku Scaleform; rozważam też integrację z istniejącym frameworkiem [ModsListAPI](https://wgmods.net/).
- **Natychmiastowy marker w panelu**: classic players panel nie ma Python-side hooka do nazw, więc trzeba: (a) załadować osobny SWF nakładający marker poza panelem, albo (b) hookować bardziej wewnętrzną AS3 gateway. Do rozważenia.
- **Okrąg "ja widzę" obok "ja jestem widzialny"** — drugi okrąg z aktualnym VR gracza (jest już w grze jako VIEW_RANGE, ale może być wyłączony przez ustawienia, więc opcjonalnie zdublujemy).
- **Per-class presety** dla `enemyViewRangeFallback` (scout 420, heavy 380, arta 350).
- **Lornetka w trybie aktywnym** (3s standstill detection dla pickera) — wymaga utrzymywania `last_speed_change` per enemy, ale działa tylko dla spotted enemies.

### Nie planujemy

- **Bonus za roślinność (foliage)** — częściowo obliczany serwerowo, wymaga raycastów do każdego krzaka. Złożoność niewspółmierna do zysku.
- **Pokazywanie czyjegoś camo / VR jako liczby** — to "softcheat" w niektórych interpretacjach. Nasz mod liczy tylko własne wartości i pokazuje wynik geometrycznie.

## Dev / build

Wymaga Python 2.7 (do kompilacji `.pyc` zgodnego z silnikiem WoT-a) i Python 3.x (do uruchomienia build skryptu).

### Kompilacja .pyc

```sh
"C:/Users/23120/miniforge3/envs/py27/python.exe" -c "import py_compile; py_compile.compile('src/mod_spotmeter.py', cfile='build/mod_spotmeter.pyc', doraise=True)"
```

### Pakowanie .wotmod (release)

```sh
py -3 packaging/build_wotmod.py
```

Output do `dist/`:
- `spotmeter-v<wersja>.wotmod` — sam mod (do `mods/<wersja>/`)
- `spotmeter.json` — domyślny config (do `mods/configs/`)
- `INSTALL.txt` — instrukcja
- `spotmeter-v<wersja>.zip` — wszystko w jednym do dystrybucji

Wersja jest czytana z `packaging/meta.xml` — zaktualizuj tam przed kolejnym buildem.

### Hot-test podczas devu

```sh
cp build/mod_spotmeter.pyc "D:/Gry/World_of_Tanks_EU/res_mods/2.2.1.2/scripts/client/gui/mods/"
cp src/spotmeter.json "D:/Gry/World_of_Tanks_EU/mods/configs/"
```

`res_mods/` ma priorytet nad `mods/<wersja>/*.wotmod` więc lokalna zmiana w `res_mods/` wygrywa nad zainstalowaną wersją release'ową.
