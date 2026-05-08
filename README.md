# WoT Spot Circle Mod

Dodaje na minimapie dodatkowy okrąg pokazujący odległość, z jakiej Twój czołg może zostać zauważony przez przeciwnika.

- **Czerwony** w ruchu (camo `invMoving`)
- **Zielony** w postoju (camo `invStill`)
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

## Instalacja

1. `build/mod_spot_circle.pyc` →  
   `<WoT>/res_mods/2.2.1.2/scripts/client/gui/mods/mod_spot_circle.pyc`
2. `src/wot_spot_mod.json` →  
   `<WoT>/mods/configs/wot_spot_mod.json`

Ten mod był zbudowany pod **WoT 2.2.1.2** (Py 2.7 bytecode, magic `03 F3 0D 0A`). Po patchu gry trzeba zwykle przekompilować i wrzucić do nowej wersji `res_mods/<wersja>/...`.

## Konfiguracja (`wot_spot_mod.json`)

| pole | default | opis |
|---|---|---|
| `enabled` | `true` | wyłącza moda bez odinstalowywania |
| `useOwnViewRange` | `true` | używa Twojego VR jako założonego VR przeciwnika |
| `enemyViewRangeFallback` | `445.0` | VR używany kiedy `useOwnViewRange = false` |
| `crewCamoBonus` | `1.05` | przybliżenie bonusu skilla Camouflage |
| `colorMoving` | `0xFF6347` | kolor okręgu w ruchu |
| `colorStill` | `0x32CD32` | kolor okręgu w postoju |
| `colorAfterShot` | `0xFFA500` | kolor okręgu po strzale (przez `fireRevealDuration`) |
| `alpha` | `70` | przezroczystość 0–100 |
| `tickInterval` | `0.2` | jak często aktualizować (s) |
| `movingSpeedThreshold` | `0.5` | prędkość uznawana za ruch (m/s) |
| `applyFirePenalty` | `true` | po strzale aplikuje `* invisibilityFactorAtShot` |
| `fireRevealDuration` | `3.0` | czas trwania kary za strzał (s) |
| `reloadKey` | `KEY_F8` | hotkey hot-reloadu configu w bitwie |
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

1. Loader gry (`scripts/client/gui/mods/__init__.py`) ładuje moduł `mod_spot_circle`.
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

### v3 — fire penalty + siege modes ✅

- **Kara za strzał (firePenalty)** — hook na `PlayerAvatar.shoot()` i `shootDualGun()`. Przez `fireRevealDuration` (domyślnie 3 s) po strzale aplikujemy `camo *= invisibilityFactorAtShot` z descryptora działa. Okrąg w tym czasie świeci pomarańczowo (`colorAfterShot`).
- **Tryby (CS-63, S-Conqueror, italian heavy, etc.)** — silnik gry obsługuje to automatycznie. `vehicle.typeDescriptor` jest `CompositeVehicleDescriptor`, który dynamicznie deleguje atrybuty do właściwego sub-descriptora (default vs siege) na podstawie aktualnego stanu (`__vehicleMode`). Mod nie wymaga osobnej obsługi — `descr.type.invisibility` zwraca prawidłowe wartości dla bieżącego trybu out of the box.
- **EBR / wheeled** — bez specjalnego case'u; XML czołgu ma `invMoving == invStill`, mod automatycznie pokazuje stały okrąg.

### v4 — picker enemy tank

W bitwie wybieramy konkretnego przeciwnika i dostosowujemy okrąg do jego VR. Server publicznie wysyła pełny `strCompactDescr` każdego przeciwnika (potwierdzone w `gui/battle_control/arena_info/arena_vos.py:277`), więc:

```python
from items.vehicles import VehicleDescr
descr = VehicleDescr(compactDescr=enemy.vehicleType.strCompactDescr)
base_vr = descr.turret.circularVisionRadius
vr_factor = descr.miscAttrs.get('circularVisionRadiusFactor', 1.0)
estimated_vr = base_vr * vr_factor
# +/- 5% bo nie znamy skilli załogi i aktywności lorny
```

Dwa warianty UI:
- **lekki (v4)**: hotkeye `Shift+F1` / `Shift+F2` cyklują przez przeciwników, aktualny wybór w chacie + lekki overlay; bez Flasha.
- **ciężki (v5)**: mały panel w rogu z klikalną listą przeciwników; wymaga Scaleform/SWF.

Co serwer wysyła i czego brakuje (dla picker'a):
| pole | dostępne klientowi | uwagi |
|---|---|---|
| model czołgu, hull/turret/gun/engine | ✅ | z `strCompactDescr` |
| zainstalowany sprzęt (binokle, optyka itd.) | ✅ | z `strCompactDescr` |
| camouflage skin / styl | ✅ | z `strCompactDescr` |
| tier, klasa, rola, max HP | ✅ | z `VehicleTypeInfoVO` |
| skille załogi (Recon, Sit. Awareness, BIA) | ❌ | przybliżamy "100% z popularnymi perkami" |
| aktywne consumable'y (cola, kawa) | ❌ | pomijamy |
| czy lorna jest właśnie aktywna (3s standstill) | ❌ | pokazujemy worst-case (lorna aktywna) |

### v5 — UI/UX

- Pełen settings panel w `Settings → Mods` zamiast pliku JSON. Wymaga osobnego SWF / Pythonowego widoku Scaleform; rozważam też integrację z istniejącym frameworkiem [ModsListAPI](https://wgmods.net/).
- Picker wariantu ciężkiego (z punktu v4).
- Okrąg "ja widzę" obok "ja jestem widzialny" — drugi okrąg z aktualnym VR gracza (jest już w grze jako VIEW_RANGE, ale może być wyłączony przez ustawienia, więc opcjonalnie zdublujemy).
- Per-class presety dla `enemyViewRangeFallback` (scout 420, heavy 380, arta 350).

### Nie planujemy

- **Bonus za roślinność (foliage)** — częściowo obliczany serwerowo, wymaga raycastów do każdego krzaka. Złożoność niewspółmierna do zysku.
- **Pokazywanie czyjegoś camo / VR jako liczby** — to "softcheat" w niektórych interpretacjach. Nasz mod liczy tylko własne wartości i pokazuje wynik geometrycznie.

## Dev / build

Wymaga Python 2.7 (zainstalowany w conda env `py27`).

```sh
cd src
"C:/Users/23120/miniforge3/envs/py27/python.exe" -c "import py_compile; py_compile.compile('mod_spot_circle.py', cfile='../build/mod_spot_circle.pyc', doraise=True)"
cp ../build/mod_spot_circle.pyc "D:/Gry/World_of_Tanks_EU/res_mods/2.2.1.2/scripts/client/gui/mods/"
cp ./wot_spot_mod.json "D:/Gry/World_of_Tanks_EU/mods/configs/"
```
