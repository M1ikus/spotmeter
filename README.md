# WoT mods (M1ikus)

Monorepo dla moich modów do **World of Tanks 2.2.1.2** (Python 2.7 bytecode, magic `03 F3 0D 0A`).

## Mody

| Mod | Status | Opis |
|---|---|---|
| [spotmeter](mods/spotmeter/) | aktywny (v5.4.1) | Dynamiczny okrąg na minimapie pokazujący odległość, z jakiej Twój czołg może zostać zauważony. Picker przeciwnika z toggle'ami consumablesów / perków / dyrektyw / field upgrades. |

## Layout

```
.
├── README.md                   ← ten plik (overview monorepo)
├── tools/
│   └── build_wotmod.py         ← parametryzowany builder; arg = nazwa moda
├── mods/
│   └── <modname>/
│       ├── README.md           ← dokumentacja konkretnego moda
│       ├── meta.xml            ← id, version, name, description (do .wotmod)
│       ├── INSTALL.txt         ← instrukcja dla użytkownika (opcjonalna)
│       ├── src/
│       │   ├── mod_<modname>.py    ← główny moduł (źródło)
│       │   └── <modname>.json      ← domyślny config (opcjonalny)
│       ├── build/
│       │   └── mod_<modname>.pyc   ← skompilowany moduł (Py 2.7)
│       └── dist/                   ← artefakty release'a (gitignored)
│           ├── <modname>-v<ver>.wotmod
│           ├── <modname>-v<ver>.zip
│           ├── <modname>.json
│           └── INSTALL.txt
├── docs/                       ← wspólne notatki o modowaniu WoT-a
└── research/                   ← gitignored (decompiled WG IP)
```

## Konwencja nowego moda

1. `mkdir mods/<modname>/{src,build}` — folder po nazwie krótkiej (lowercase, bez spacji)
2. `mods/<modname>/src/mod_<modname>.py` — główny moduł (musi nazywać się `mod_<modname>`, bo loader gry skanuje `scripts/client/gui/mods/mod_*.py[co]`)
3. `mods/<modname>/src/<modname>.json` — opcjonalny config (jeśli mod ma)
4. `mods/<modname>/meta.xml` — `<id>`, `<version>`, `<name>`, `<description>`
5. `mods/<modname>/INSTALL.txt` — opcjonalna instrukcja (build podstawia `{{VERSION}}`)
6. `mods/<modname>/README.md` — dokumentacja moda

Build: `py -3.10 tools/build_wotmod.py <modname>` produkuje `mods/<modname>/dist/<modname>-v<ver>.wotmod` + `.zip` bundle.

## Dev workflow (per-mod)

### 1. Kompilacja .pyc (wymaga Python 2.7 — Anaconda env `py27`)

```sh
"C:/Users/23120/miniforge3/envs/py27/python.exe" -c "import py_compile; py_compile.compile('mods/<modname>/src/mod_<modname>.py', cfile='mods/<modname>/build/mod_<modname>.pyc', doraise=True)"
```

WoT 2.2.1.2 wymaga Pythona 2.7 (magic `03 F3 0D 0A`). Bytecode skompilowany pod inną wersję się nie załaduje.

### 2. Build .wotmod

```sh
py -3.10 tools/build_wotmod.py <modname>
```

Output do `mods/<modname>/dist/`:
- `<modname>-v<ver>.wotmod` — sam mod (do `<WoT>/mods/2.2.1.2/`)
- `<modname>.json` — domyślny config (do `<WoT>/mods/configs/`)
- `INSTALL.txt` — instrukcja
- `<modname>-v<ver>.zip` — bundle dla release'a

### 3. Hot-test podczas devu (bez budowania .wotmod)

```sh
cp mods/<modname>/build/mod_<modname>.pyc "D:/Gry/World_of_Tanks_EU/res_mods/2.2.1.2/scripts/client/gui/mods/"
cp mods/<modname>/src/<modname>.json "D:/Gry/World_of_Tanks_EU/mods/configs/"
```

`res_mods/<wersja>/` ma priorytet nad `mods/<wersja>/*.wotmod`, więc lokalna zmiana wygrywa nad zainstalowaną wersją release'ową.

### 4. Release

```sh
git commit -am "v<ver>: ..."
git tag v<ver>          # opcjonalnie
git push origin main
gh release create v<ver> mods/<modname>/dist/<modname>-v<ver>.{wotmod,zip} mods/<modname>/dist/{<modname>.json,INSTALL.txt} \
    --title "v<ver> — <opis>" --notes "..."
```

> **Uwaga:** GitHub repo nazywa się aktualnie `M1ikus/spotmeter`. Po dodaniu drugiego moda warto rozważyć przemianowanie repo na `wot-mods` (GH automatycznie redirectuje stare URL-e).

## Wymagania pakietów (Wargaming IP)

Folder `research/` (zignorowany w gicie) zawiera zdekompilowane skrypty WoT-a do referencji — nie redystrybuujemy ich. Każdy dev musi sobie sam zdekompilować z lokalnej instalacji (np. przez `uncompyle6`).

## Aspekt prawny / fair-play

Wszystkie mody w tym repo trzymają się Wargaming Fair Play Policy:
- ✅ minimap improvements / markery (np. circle widoczności)
- ❌ wallhacki, auto-aim, bypass płatnych funkcji, czytanie danych nie-syncowanych do klienta

Każdy mod ma w swoim README sekcję "Aspekt prawny" potwierdzającą że nie robi nic z czarnej listy.

## Licencja

Patrz [LICENSE](LICENSE).
