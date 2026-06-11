# -*- coding: utf-8 -*-
# SpotMeter — World of Tanks minimap mod.
# Adds an extra dynamic circle to the player's minimap showing the distance
# from which the tank can be spotted, plus an in-battle picker for sizing
# the circle to a specific enemy's view range.
# Works alongside the game's existing view-range circles (does not replace them).
#
# Loader entry: scripts/client/gui/mods/mod_spotmeter.pyc
# Game version: World of Tanks 2.2.1.3 (Python 2.7 bytecode)
import json
import logging
import os
import weakref

import BigWorld
from constants import VISIBILITY
from gui.Scaleform.daapi.view.battle.shared.minimap import plugins as _mm_plugins
from gui.Scaleform.daapi.view.battle.shared.minimap import settings as _mm_settings
from gui.battle_control import matrix_factory

_logger = logging.getLogger('SpotMeter')

# WARNING-level so the line shows up in python.log even if the user's logging
# level is filtering INFO out. This proves the mod was at least imported by
# the loader; if you don't see this line, the .wotmod isn't being picked up.
MOD_VERSION = '6.0.1'
# Short "major.minor" form shown in panel titles ("6.0.0" -> "6.0"); the
# full MOD_VERSION still drives logs / version reporting / meta.xml. Bumping
# the patch (6.0.1) keeps the panel at "6.0"; a minor bump (6.1.0) -> "6.1".
MOD_VERSION_SHORT = '.'.join(MOD_VERSION.split('.')[:2])
MOD_AUTHOR = 'ISEDR_Mikus'  # small credit line shown in the panels
_logger.warning('SpotMeter: module loaded (version=%s)', MOD_VERSION)


# ---------------------------------------------------------------------------
# i18n: UI strings in English (default) + Polish, auto-picked from the WoT
# client language via helpers.getClientLanguage(): a 'pl' client gets Polish,
# anything else English. Override with "language": "pl"/"en"/"auto" in config.
# ---------------------------------------------------------------------------
_LANG = None


def _detect_lang():
    forced = (_CFG.get('language') or 'auto').lower()
    if forced in ('pl', 'en'):
        return forced
    try:
        from helpers import getClientLanguage
        return 'pl' if (getClientLanguage() or '').lower() == 'pl' else 'en'
    except Exception:
        return 'en'


def _t(key):
    """UI string for `key` in the detected language (English fallback)."""
    global _LANG
    if _LANG is None:
        _LANG = _detect_lang()
    return (_STRINGS.get(_LANG, _STRINGS['en']).get(key)
            or _STRINGS['en'].get(key)
            or key)


_STRINGS = {
    'en': {
        'garage_title_suffix': '- garage, settings',
        'garage_loadout_header': 'Loadout (session):',
        'garage_battle_panel': 'Battle panel:',
        'garage_footer': 'To change defaults: edit mods/configs/spotmeter.json + restart WoT',
        'garage_hotkeys': (
            '<font size="11" color="#88AABB"><b>Keyboard shortcuts:</b></font><br>'
            '<font size="10" color="#CCCCCC">'
            '  <b>N 2 / N 8</b> &#8212; next / previous enemy<br>'
            '  <b>N 5</b>       &#8212; clear pick (back to auto)<br>'
            '  <b>N /</b>       &#8212; auto-pick (nearest visible)<br>'
            '  <b>N 7 / N 3 / N 4</b> &#8212; rations / BIA / recon+SitA<br>'
            '  <b>N 6</b>       &#8212; cycle optics level (OFF/basic/slot/bonds/deluxe)<br>'
            '  <b>N +</b>       &#8212; cycle ventilation level<br>'
            '  <b>N -</b>       &#8212; cycle enemy CVS (lowers our moving camo)<br>'
            '  <b>N 1 / N 0</b>    &#8212; directives / field upgrades<br>'
            '  <b>N *</b>       &#8212; dump enemy descriptor to python.log<br>'
            '  <b>N Enter</b>   &#8212; snapshot spot-distance to chat<br>'
            '  <b>N .</b>       &#8212; hot-reload spotmeter.json<br>'
            '  <b>PageDown</b>  &#8212; show/hide panel (battle + garage)'
            '</font>'),
        'chat_live_on': 'live mode: ON (refresh every %.1fs - Numpad9 to turn off)',
        'tl_rations': 'rations', 'tl_BIA': 'BIA', 'tl_reconSitAware': 'recon+SitA',
        'tl_directives': 'directives', 'tl_fieldUpgrades': 'field upg.',
        'tl_optics': 'optics', 'tl_vents': 'vents', 'tl_cvs': 'CVS', 'tl_auto': 'auto',
        'lv_0': 'OFF', 'lv_1': 'basic', 'lv_2': 'slot', 'lv_3': 'bonds', 'lv_4': 'deluxe',
        'battle_target': 'Target:', 'battle_target_hint': '(Numpad 2/8 or click the list)',
        'battle_auto_hint': 'click / Numpad /',
        'battle_hide_hint': 'Press PgDn to hide panel',
        'battle_target_own': 'own',
    },
    'pl': {
        'garage_title_suffix': '- garaz, ustawienia',
        'garage_loadout_header': 'Ulepszacze (sesja):',
        'garage_battle_panel': 'Panel w bitwie:',
        'garage_footer': 'Zmiany defaultow: edytuj mods/configs/spotmeter.json + restart WoT',
        'garage_hotkeys': (
            '<font size="11" color="#88AABB"><b>Skroty klawiszowe:</b></font><br>'
            '<font size="10" color="#CCCCCC">'
            '  <b>N 2 / N 8</b> &#8212; nastepny / poprzedni przeciwnik<br>'
            '  <b>N 5</b>       &#8212; wyczysc wybor (powrot do auto)<br>'
            '  <b>N /</b>       &#8212; auto-pick (najblizszy widoczny)<br>'
            '  <b>N 7 / N 3 / N 4</b> &#8212; racje / BIA / Zwiad+Rozezn.<br>'
            '  <b>N 6</b>       &#8212; cykl poziomow optyki (WYL/zwykla/na slocie/Z nagrod/Ulepszone)<br>'
            '  <b>N +</b>       &#8212; cykl poziomow wentylacji<br>'
            '  <b>N -</b>       &#8212; cykl CVS przeciwnika (zmniejsza nasze camo w ruchu)<br>'
            '  <b>N 1 / N 0</b>    &#8212; dyrektywy / ulepszenia polowe<br>'
            '  <b>N *</b>       &#8212; zrzut deskryptora wroga do python.log<br>'
            '  <b>N Enter</b>   &#8212; zrzut dystansu spot do czatu<br>'
            '  <b>N .</b>       &#8212; przeladuj spotmeter.json<br>'
            '  <b>PageDown</b>  &#8212; pokaz/ukryj panel (bitwa + garaz)'
            '</font>'),
        'chat_live_on': 'live mode: ON (refresh co %.1fs - Numpad9 zeby wylaczyc)',
        'tl_rations': 'racje', 'tl_BIA': 'BIA', 'tl_reconSitAware': 'Zwiad+Rozezn.',
        'tl_directives': 'dyrektywy', 'tl_fieldUpgrades': 'ulepsz.pol',
        'tl_optics': 'optyka', 'tl_vents': 'wentyl.', 'tl_cvs': 'CVS', 'tl_auto': 'auto',
        'lv_0': 'WYL', 'lv_1': 'zwykla', 'lv_2': 'na slocie', 'lv_3': 'Z nagrod', 'lv_4': 'Ulepszone',
        'battle_target': 'Cel:', 'battle_target_hint': '(Numpad 2/8 lub klik na liscie)',
        'battle_auto_hint': 'klik / Numpad /',
        'battle_hide_hint': 'Nacisnij PgDn zeby ukryc panel',
        'battle_target_own': 'wlasny',
    },
}

_S_NAME = _mm_settings.ENTRY_SYMBOL_NAME
_C_NAME = _mm_settings.CONTAINER_NAME
_AS3 = _mm_settings.VIEW_RANGE_CIRCLES_AS3_DESCR

# Tried in order. The legacy 'wot_spot_mod.json' names are kept so users with
# a config from before the rename keep working without manual migration.
_CONFIG_CANDIDATES = (
    './mods/configs/spotmeter.json',
    './res_mods/configs/spotmeter.json',
    './mods/spotmeter.json',
    './mods/configs/wot_spot_mod.json',
    './res_mods/configs/wot_spot_mod.json',
    './mods/wot_spot_mod.json',
)

DEFAULT_CONFIG = {
    'enabled': True,
    'useOwnViewRange': True,
    # UI language: 'auto' reads the WoT client language (pl -> Polish, any
    # other -> English); force with 'pl' or 'en'.
    'language': 'auto',
    'enemyViewRangeFallback': 445.0,
    'crewCamoBonus': 1.05,
    'colorMoving': 0xFF6347,
    'colorStill': 0x32CD32,
    'colorAfterShot': 0xFFA500,
    'colorCamoNet': 0x228B22,
    'alpha': 70,
    'tickInterval': 0.2,
    'movingSpeedThreshold': 0.5,
    'applyFirePenalty': True,
    'fireRevealDuration': 3.0,
    'applyCamoNet': True,
    'camoNetActivateSec': 3.0,
    'camoNetFallbackBonus': 0.05,
    'logCalcDetails': False,
    'reloadKey': 'KEY_NUMPADPERIOD',
    # v4/v5 picker - numpad layout
    'pickerEnabled': True,
    'pickerNextKey': 'KEY_NUMPAD2',
    'pickerPrevKey': 'KEY_NUMPAD8',
    'pickerClearKey': 'KEY_NUMPAD5',
    # Toggle keys. v5.6 split BIA out of the perks bundle because BIA is
    # mathematically a "crew amplifier" (acts on base_vr, like Rations),
    # while Recon and SitAware are skills that scale with the amplified
    # crew level (act on crew_amplified = base_vr * (1+rations+BIA)).
    'pickerRationsKey':         'KEY_NUMPAD7',  # default ON  - Combat Rations (crew amp from base_vr)
    'pickerBIAKey':             'KEY_NUMPAD3',  # default ON  - Brothers in Arms (crew amp from base_vr)
    'pickerReconSitAwareKey':   'KEY_NUMPAD4',  # default ON  - Recon + SitAware (skills from amplified)
    'pickerOpticsKey':          'KEY_NUMPAD6',     # cycles opticsLevel 0..4
    'pickerVentsKey':           'KEY_ADD',         # cycles ventsLevel 0..4 (WoT calls numpad+ "KEY_ADD")
    'pickerCvsKey':             'KEY_NUMPADMINUS', # cycles cvsLevel 0..2 (CVS reduces OUR moving camo)
    'pickerDirectivesKey':      'KEY_NUMPAD1',  # default OFF - boost auto-detected equipment by 1.025
    'pickerFieldUpgradesKey':   'KEY_NUMPAD0',  # default OFF - VR-related field upgrades (per-tank)
    # Panel visibility toggle (PageDown). Context-aware: garage panel in
    # the garage, battle panel in battle. Deliberately NOT a numpad key -
    # the whole numpad + nav cluster is taken (see _key_aliases below), so
    # KEY_PGDN is freed from the Numpad3/BIA alias and reused here.
    'panelToggleKey':           'KEY_PGDN',
    # Picker VR multipliers. Two-stage model:
    #   crew_amplified = base_vr * (1 + (rations? 0.0430 : 0) + (BIA? 0.0253 : 0))
    #   final = crew_amplified
    #         + crew_amplified * (optics_factor * directive_factor - 1)   # auto from descriptor
    #         + crew_amplified * (stereo_factor * directive_factor - 1)   # auto from descriptor
    #         + crew_amplified * (reconSitAware_factor - 1)               # 1 + 0.0288 + 0.0451
    # Empirical calibration on user's 340m base VR tank.
    'pickerVRBonusRations':         1.0430,  # +4.30% from base_vr
    'pickerVRBonusBIA':             1.0253,  # +2.53% from base_vr
    'pickerVRBonusReconSitAware':   1.0739,  # +7.39% from amplified (= 1 + 0.0288 Recon + 0.0451 SitAware)
    'pickerVRBonusDirective':       1.0250,
    # Field upgrades on VR are tank-specific (BETA). Server doesn't
    # transmit vehPostProgression for enemies, so this is a manual
    # lookup. Cap at 445 m (VISIBILITY.MAX_RADIUS) is applied to the
    # post-upgrade base VR before further bonuses. Tanks not in the
    # map get 0 - safer default than guessing. User can extend via
    # config JSON. Empirical values from user's hangar:
    'pickerFieldUpgradeVR': {
        'Rhm.-B. WT':   0.02,
        'Obj. 907':     0.03,
        'Jg.Pz. E 100': 0.02,
    },
    'pickerFieldUpgradeCap': 445.0,
    'pickerAssumeStereoscope': True,
    'pickerStereoscopeFallback': 1.25,
    # WoT 2.x server doesn't transmit enemy optionalDevices, so optics
    # and vents never show up in the decoded descriptor. We model them
    # as 5-level cyclable presets via Numpad 6 / Numpad +.
    #
    # opticsLevel: 0=OFF, 1=Coated Optics basic (+10%), 2=basic in
    #              optics slot (+11.5%), 3=Bonds/red (+12.5%),
    #              4=Deluxe/purple (+13.5%). Factor = VR multiplier.
    # ventsLevel:  0=OFF, 1=Improved Ventilation basic (+5% crew),
    #              2=basic in vents slot (+6.25%), 3=Bonds/red (+7.5%),
    #              4=Deluxe/purple (+8.5%). Factor multiplies the
    #              additive crew bonuses (rations / BIA / recon).
    # cvsLevel:    0=OFF, 1=zwykly, 2=na slocie. CVS has no Bonds/Deluxe
    #              grade, so only two real levels (unlike optics/vents).
    #              When the picked ENEMY has CVS, OUR moving camo is
    #              multiplied by the factor (<1.0) - making us more
    #              visible while we move toward that target.
    #
    # Tune these in spotmeter.json if WG patches the exact percentages.
    'pickerOpticsFactors': [1.0, 1.10, 1.115, 1.125, 1.135],
    'pickerVentsFactors':  [1.0, 1.05, 1.0625, 1.075, 1.085],
    # CVS calibration from user (CVS only exists as zwykly + na slocie):
    #   L1 (zwykly):   -10%   = factor 0.900
    #   L2 (na slocie):-12.5% = factor 0.875
    'pickerCvsFactors':    [1.0, 0.900, 0.875],
    'pickerIncludeDeadEnemies': False,
    'pickerDiagDumpKey': 'KEY_NUMPADSTAR',
    # v5.5 overlay - rewritten as a multi-line "status block" that shows
    # spot distance for all 4 states at once (still/moving/net/afterShot).
    # Auto-spam on tick changes is GONE. Two ways to see the block:
    #   1) NumpadEnter (overlayPrintNowKey) - one-shot snapshot
    #   2) live mode (overlayToggleKey, default OFF) - re-posts every
    #      liveModeIntervalSec seconds while enabled. The chat will show
    #      a refreshing block; older blocks scroll out.
    # User-action chat lines (toggle confirmations, picker change, diag
    # dump) remain as short one-line responses since they're triggered
    # by user input, not background events.
    'overlayEnabled': True,
    'overlayToggleKey': 'KEY_NUMPAD9',  # toggles live mode
    'overlayPrintNowKey': 'KEY_NUMPADENTER',  # one-shot snapshot
    'liveModeIntervalSec': 3.0,  # only used when live mode is enabled
    # v6.0 auto-pick: continuously track the closest visible enemy as VR
    # target. Default OFF. Manual pick (Numpad 2/8) always overrides auto;
    # clearing manual (Numpad 5) restores auto when enabled. Position cache
    # keeps a last-known fix for autoPickCacheTimeoutSec so the target
    # doesn't flicker when the spotter blinks. When no candidate is within
    # range the spot circle falls back to own VR (same path as no manual pick).
    'autoPickEnabled': False,
    'autoPickRangeMeters': 445.0,
    'autoPickCacheTimeoutSec': 5.0,
    'autoPickToggleKey': 'KEY_NUMPADSLASH',  # numpad /
    # Per-class auto presets. ONLY active while auto-pick is ON. Applied
    # ONCE when you ENABLE auto (toggle off+on to re-apply), based on the
    # class of the tank auto picks at that moment - it does NOT re-apply as
    # auto retargets. Numpad presses override live. Keyed by WoT class tag;
    # 'default' is the fallback for any class without its own entry (here
    # MT/HT/TD/SPG). Levels 0..4 (0=OFF 1=basic 2=slot 3=bonds 4=deluxe).
    'autoPresetsEnabled': True,
    'autoPresets': {
        'lightTank': {'rations': True, 'BIA': True, 'reconSitAware': True,
                      'directives': False, 'fieldUpgrades': False,
                      'optics': 2, 'vents': 0, 'cvs': 2},
        'default':   {'rations': True, 'BIA': True, 'reconSitAware': True,
                      'directives': False, 'fieldUpgrades': False,
                      'optics': 0, 'vents': 0, 'cvs': 0},
    },
    # v6.0 schema versioning. v1 = pre-v6 flat config (no version field).
    # v2 adds defaultToggles section. _migrate_config() auto-bumps in memory
    # when an old file is loaded; the file on disk is NOT rewritten until
    # the user saves via the in-garage menu (preserves their formatting /
    # comments / unknown keys).
    'configVersion': 2,
    # v6.0 defaultToggles: which picker bonuses start ON at battle start.
    # Applied to _PICKER_TOGGLES exactly once at init(); hot-reload does
    # NOT re-apply, so user-action hotkeys during a session (Numpad
    # 1/3/4/7/0) keep their effect across reloads. Restart WoT to pick up
    # new defaults, or use the v6 menu's "Reset toggles to defaults".
    'defaultToggles': {
        'rations':       True,
        'BIA':           True,
        'reconSitAware': True,
        'directives':    False,
        'fieldUpgrades': False,
    },
    'defaultLevels': {
        'optics': 4,  # 0=OFF 1=basic 2=basicInSlot 3=Bonds 4=Deluxe
        'vents':  0,
        'cvs':    0,
    },
    # v6.0 in-garage menu button. Floating Scaleform overlay on the hangar
    # view; drag with mouse to reposition. Coords are absolute pixels from
    # the screen top-left and persist via Save action in the menu (or
    # automatic save on drag-release, see Phase 3.3). Defaults aim at the
    # bottom-of-hangar area near the customization brush icon at 1920x1080;
    # at other resolutions, _clamp_button_pos() rebases to visible bounds
    # on each Hangar populate.
    # v6.0.0 MVP1 ship: garage UI deferred (the new WG IGui View
    # framework gate). In-battle panel ships via a byte-identical copy
    # of GambitER / CH4MPi's GUIFlash 0.6.4 (MIT), bundled under our
    # private gui.mods.spotmeter_gf namespace + 'SpotMeterGuiFlashView'
    # alias. Display-only - any FFDec recompile attempting to add click
    # events crashes WoT during AVM2 verify, so clicks are NOT wired:
    # interaction stays on Numpad keys (2/8 cycle target, 5 clear,
    # 1/3/4/7/0 toggle perks, NumpadSlash auto-pick).
    'menuButtonEnabled': False,
    'menuButtonX': 720,
    'menuButtonY': 850,
    'menuButtonW': 90,  # button width  (px) - matches stock hangar button height roughly
    'menuButtonH': 28,  # button height (px)
    'battlePanelEnabled': True,
    'battlePanelX': 10,
    'battlePanelY': 400,
    'battlePanelW': 320,
    'battlePanelH': 380,
    # Collapse identical enemy tanks into one panel row + one cycle stop
    # (same model = same view range = same circle). Numpad 2/8 then steps
    # types, not individuals. False = list every enemy separately.
    'battlePanelGroupSameTanks': True,
    # Auto-hide the panel when any WG window opens (research/depot/dialogs in
    # the garage, TAB-style overlays in battle); restore it when the last one
    # closes. False = panel always stays on top.
    'autoHidePanelOnWindow': True,
    # In battle, hide the panel while one of these keys is held (TAB / N show
    # the team-stats overlays); released -> panel returns. WoT Keys names.
    'battleHidePanelKeys': ['KEY_TAB', 'KEY_N'],
    # v6.0.0 garage settings readout panel. Same GUIFlash plumbing as
    # the in-battle panel - draggable, position persists, components
    # tagged lobby=True so they only render in the garage. Display-only
    # (no click events available on WoT 2.x in our setup); user edits
    # spotmeter.json to change defaults and the panel reflects the
    # current in-session state of toggles plus a Numpad hotkey
    # reference card. Default position is top-right area of the
    # garage at 1920x1080.
    'garagePanelEnabled': True,
    'garagePanelX': 1500,
    'garagePanelY': 320,
    'garagePanelW': 380,
    'garagePanelH': 340,
}

def _fresh_cfg():
    """Return a fresh _CFG initialised from DEFAULT_CONFIG. Nested dicts
    (defaultToggles, pickerFieldUpgradeVR) get their own copies so user
    edits via _CFG never bleed back into the module-level DEFAULT_CONFIG.
    """
    out = {}
    for k, v in DEFAULT_CONFIG.iteritems():
        out[k] = dict(v) if isinstance(v, dict) else v
    return out


_CFG = _fresh_cfg()
_CFG_PATH = None  # absolute path the active config was loaded from (None if running on defaults)
_PATCHED = False
_AVATAR_PATCHED = False
_HANGAR_PATCHED = False
_HOTKEYS_INSTALLED = False  # v5.6.4: guards _install_reload_hotkey against double-registration
_STATE = weakref.WeakKeyDictionary()
_LAST_SHOT_TIME = 0.0
_LAST_MOVEMENT_TIME = 0.0
_LAST_SPOT_RADIUS = None  # last spot-circle radius from _tick (m); shown on the panel target line
_PICKED_VID = None
# v5.6.4 perf fix: cache the expensive VehicleDescr decode per vid. The
# entries hold (base_vr, optics_factor, stereo_factor, has_stereo_fallback,
# short_name) - all constant for a given enemy in a given battle. Cleared
# when the minimap plugin stops (battle end / scenario load).
_PICKER_DESCR_CACHE = {}
_PICKER_TOGGLES = {
    'rations':       True,   # default ON:  assume enemy has Combat Rations active
    'BIA':           True,   # default ON:  assume enemy has Brothers in Arms
    'reconSitAware': True,   # default ON:  assume enemy has Recon + Sit. Awareness
    'directives':    False,  # default OFF: assume no directives on equipment slots
    'fieldUpgrades': False,  # default OFF: assume no VR field upgrades
}
# v6.0.0: multi-level states. Different from _PICKER_TOGGLES because each
# has more than 2 states. opticsLevel + ventsLevel are 0..4 indexes into
# the matching pickerOpticsFactors / pickerVentsFactors lists in _CFG.
# Numpad 6 cycles opticsLevel, Numpad + cycles ventsLevel.
_PICKER_LEVELS = {
    'optics': 4,  # default Deluxe (purple) Coated Optics
    'vents':  0,  # default OFF - vents are less universal than optics
    'cvs':    0,  # default OFF - CVS is rare on most enemies
}
_LIVE_MODE_ENABLED = False  # default OFF - user enables via Numpad9 if they want auto-refreshing block
_LIVE_MODE_CALLBACK_ID = None  # BigWorld.callback handle for the periodic poster
_AUTO_PICKED_VID = None  # vid auto-selected as nearest visible enemy; None when no candidate
_ENEMY_POS_CACHE = {}  # vid -> (x, z, timestamp) last-known 2D positions for auto-pick
# v6.0.0 per-battle reset. _DEFAULT_AUTO_PICK_ENABLED captures the user's
# preferred auto-pick state at WoT startup (from JSON). _CFG['autoPickEnabled']
# is the live state that gets toggled by clicks/hotkeys; we reset it to the
# default at each battle start so a mid-battle toggle doesn't leak forward.
# _BATTLE_RESET_DONE guards against multiple invalidateMarkup-driven resets
# within a single battle (respawns, scenario reloads). Cleared on stop.
_DEFAULT_AUTO_PICK_ENABLED = False
_BATTLE_RESET_DONE = False
_LOADER_DIAG_INSTALLED = False


def _read_config():
    """Load config from the first available candidate path. Resets _CFG
    to fresh defaults first, so a hot-reload where the user removed a
    key restores that key's default (rather than keeping the previously
    loaded value). Runs schema migration (v1 -> v2) in memory; the JSON
    file on disk is NOT rewritten - user formatting / comments are
    preserved until they explicitly save via the v6 menu.
    """
    global _CFG, _CFG_PATH
    _CFG = _fresh_cfg()
    for path in _CONFIG_CANDIDATES:
        try:
            with open(path, 'rb') as fh:
                payload = json.load(fh)
            if isinstance(payload, dict):
                _migrate_config(payload)
                for k, v in payload.iteritems():
                    if k in DEFAULT_CONFIG:
                        _CFG[k] = v
                _CFG_PATH = path
                _logger.info('SpotMeter: config loaded from %s', path)
                return
        except IOError:
            continue
        except (ValueError, KeyError) as exc:
            _logger.warning('SpotMeter: bad config at %s: %s', path, exc)
            return
    _CFG_PATH = None
    _logger.info('SpotMeter: no config file found, using defaults')


def _migrate_config(payload):
    """Mutate `payload` in place to current schema version.

    v1 (no configVersion field) -> v2: adds defaultToggles section with
    pre-v6 hardcoded values so existing players see zero behavior change.
    Returns True if anything was changed. Caller is responsible for
    persisting the migrated payload if desired - we do NOT auto-write to
    avoid clobbering user-edited formatting or comments.
    """
    try:
        version = int(payload.get('configVersion', 1))
    except (TypeError, ValueError):
        version = 1
    migrated = False
    if version < 2:
        if 'defaultToggles' not in payload:
            # Pre-v6 hardcoded defaults from _PICKER_TOGGLES init.
            payload['defaultToggles'] = {
                'rations':       True,
                'BIA':           True,
                'reconSitAware': True,
                'optics':        True,
                'directives':    False,
                'fieldUpgrades': False,
            }
        payload['configVersion'] = 2
        migrated = True
        _logger.info('SpotMeter: migrated config v1 -> v2 in memory')
    # v2 -> v2.1: optics + vents promoted from binary toggle to a 5-level
    # cyclable state (OFF/basic/slot/bonds/deluxe). Patch legacy configs
    # in-memory so existing JSON files keep working without manual edits.
    defaults = payload.get('defaultToggles')
    if isinstance(defaults, dict) and 'optics' in defaults:
        # Old binary `optics` toggle leaked through — strip it; the new
        # level controls live under defaultLevels instead.
        del defaults['optics']
        migrated = True
        _logger.info('SpotMeter: removed obsolete `optics` from defaultToggles (moved to defaultLevels)')
    if 'defaultLevels' not in payload:
        payload['defaultLevels'] = {'optics': 4, 'vents': 0}
        migrated = True
        _logger.info('SpotMeter: added defaultLevels section to in-memory config')
    return migrated


def _apply_default_toggles():
    """Initialize _PICKER_TOGGLES from _CFG['defaultToggles']. Called at
    init() AND at the start of every battle (via _reset_battle_state) so
    each battle begins with a clean slate. Hot-reload of the config does
    NOT re-apply - that runs mid-battle and would surprise the player.
    """
    defaults = _CFG.get('defaultToggles')
    if not isinstance(defaults, dict):
        return
    for key in list(_PICKER_TOGGLES.keys()):
        if key in defaults:
            _PICKER_TOGGLES[key] = bool(defaults[key])


def _apply_default_levels():
    """Same idea as _apply_default_toggles but for multi-level states
    (opticsLevel, ventsLevel). Clamps to the valid range 0..len(factors)-1
    so a bad JSON value can't crash _picker_vr_for via index-out-of-range.
    """
    defaults = _CFG.get('defaultLevels') or {}
    for key in list(_PICKER_LEVELS.keys()):
        if key not in defaults:
            continue
        try:
            v = int(defaults[key])
        except (TypeError, ValueError):
            continue
        # Range guard: each level enum has 5 entries (0..4).
        if v < 0:
            v = 0
        elif v > 4:
            v = 4
        _PICKER_LEVELS[key] = v


def _reset_battle_state():
    """v6.0.0: zero out picker state at the start of each battle.

    Resets manual pick, auto pick, toggles, auto-pick enabled flag, live
    mode, position cache, descriptor cache, and the shot/movement timestamps
    (so a stale timestamp from the previous battle can't trigger the
    after-shot penalty for the first 3 s of the new one).

    Panel position (`battlePanelX/Y/W/H`) is intentionally NOT reset -
    those persist across battles, that's the whole point.

    Idempotent via `_BATTLE_RESET_DONE`: the minimap plugin fires
    `_invalidateMarkup` multiple times per battle (respawn, scenario
    reload) and we only want to reset on the first one. `patched_stop`
    clears the flag so the next battle gets a fresh reset.
    """
    global _BATTLE_RESET_DONE, _PICKED_VID, _AUTO_PICKED_VID
    global _LAST_SHOT_TIME, _LAST_MOVEMENT_TIME, _LIVE_MODE_ENABLED
    if _BATTLE_RESET_DONE:
        return
    _PICKED_VID = None
    _AUTO_PICKED_VID = None
    _ENEMY_POS_CACHE.clear()
    _PICKER_DESCR_CACHE.clear()
    _CFG['autoPickEnabled'] = _DEFAULT_AUTO_PICK_ENABLED
    _LAST_SHOT_TIME = 0.0
    _LAST_MOVEMENT_TIME = 0.0
    _LIVE_MODE_ENABLED = False
    _apply_default_toggles()
    _apply_default_levels()
    _BATTLE_RESET_DONE = True
    _logger.info(
        'SpotMeter: battle state reset (toggles+levels -> defaults, picks '
        'cleared, autoPick=%s, opticsLvl=%s, ventsLvl=%s)',
        _DEFAULT_AUTO_PICK_ENABLED,
        _PICKER_LEVELS.get('optics'), _PICKER_LEVELS.get('vents'))


def _write_config(path=None):
    """Atomically persist _CFG to disk as JSON. Used by the v6 menu's
    Save action; not called automatically by migration.

    Atomicity: writes to <target>.tmp then renames over <target>. On
    Windows rename fails if the destination exists, so we unlink first
    - that gives a brief (microsecond-scale) window where the file is
    missing, but the .tmp file is already complete, so a crash recovers
    by reading the tmp. Not fully POSIX-atomic but good enough.

    Returns the path written on success, None on failure.
    """
    target = path or _CFG_PATH or _CONFIG_CANDIDATES[0]
    parent = os.path.dirname(target)
    if parent and not os.path.isdir(parent):
        try:
            os.makedirs(parent)
        except OSError:
            _logger.exception('SpotMeter: cannot create config dir %s', parent)
            return None
    # Save only keys we know about - drops anything that snuck in.
    payload = {}
    for k in DEFAULT_CONFIG:
        if k in _CFG:
            payload[k] = _CFG[k]
    tmp = target + '.tmp'
    try:
        with open(tmp, 'wb') as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
        if os.path.exists(target):
            os.remove(target)
        os.rename(tmp, target)
    except (IOError, OSError):
        _logger.exception('SpotMeter: failed to write config to %s', target)
        try:
            os.remove(tmp)
        except OSError:
            pass
        return None
    _logger.info('SpotMeter: config saved to %s', target)
    return target


def init():
    global _DEFAULT_AUTO_PICK_ENABLED
    _logger.warning('SpotMeter: init() called')
    try:
        _read_config()
        if not _CFG.get('enabled', True):
            _logger.warning('SpotMeter: disabled by config')
            return
        _apply_default_toggles()
        _apply_default_levels()
        # Capture user's preferred auto-pick state once at WoT startup so
        # _reset_battle_state can restore it cleanly between battles.
        _DEFAULT_AUTO_PICK_ENABLED = bool(_CFG.get('autoPickEnabled', False))
        # v6.0.0 Phase 5.1 / WoT 2.x: register the floating views with
        # g_entitiesFactories at INIT time, not lazily on hangar populate.
        # The lobby app's loader snapshots known aliases at startup; late
        # registrations are silently ignored. Registration failures here
        # are not fatal - they just mean the menu UI is disabled for this
        # session. The minimap circle (the core feature) keeps working.
        try:
            _register_button_view()
        except Exception:
            _logger.exception('SpotMeter: early button view registration failed')
        try:
            _register_menu_view()
        except Exception:
            _logger.exception('SpotMeter: early menu view registration failed')
        try:
            _register_battle_view()
        except Exception:
            _logger.exception('SpotMeter: early battle view registration failed')
        _patch_plugin()
        _patch_avatar_shoot()
        # v6.0.0: eager-import our private GUIFlash so it's ready to
        # catch the LOBBY space-entered event WoT fires right after
        # init. The library auto-subscribes its own onGUISpaceEntered
        # hook in its __init__ - that hook is what actually triggers
        # the SWF View to load via app.loadView. If we lazy-imported
        # it later (e.g. inside _show_garage_panel), the subscription
        # would register AFTER the LOBBY event fired and Flash_UI._
        # populate never runs - the View stays a ghost, our cached
        # components never render. Battle path lucked out because
        # something else re-triggered the load; lobby path didn't.
        try:
            import gui.mods.spotmeter_gf  # noqa: F401
        except ImportError:
            _logger.exception('SpotMeter: failed to eager-import spotmeter_gf')
        # appLoader.onGUISpaceEntered/Left subscription drives BOTH
        # the in-battle panel and the garage panel show/hide. The
        # legacy menuButtonEnabled flag used to gate this but became
        # misleading after the pivot to space-events - we always want
        # the subscription active so individual panels can decide
        # independently via their own `*PanelEnabled` flags.
        _patch_hangar_lifecycle()
        _install_reload_hotkey()
        _logger.warning(
            'SpotMeter: initialised (version=%s, useOwnViewRange=%s, fire=%s, picker=%s)',
            MOD_VERSION, _CFG['useOwnViewRange'],
            _CFG['applyFirePenalty'], _CFG['pickerEnabled'])
    except Exception:
        _logger.exception('SpotMeter: init failed')


def fini():
    pass


def _state_for(plugin):
    s = _STATE.get(plugin)
    if s is None:
        s = {
            'circleId': None,
            'lastState': None,
            'lastRadius': 0.0,
            'callbackId': None,
            'attached': False,
        }
        _STATE[plugin] = s
    return s


def _is_player_vehicle_moving(speed_mps):
    return abs(speed_mps) > _CFG['movingSpeedThreshold']


def _get_player_vehicle():
    player = BigWorld.player()
    if player is None:
        return None
    vid = getattr(player, 'playerVehicleID', 0)
    if not vid:
        return None
    veh = BigWorld.entity(vid)
    if veh is None or not getattr(veh, 'isStarted', False):
        return None
    if getattr(veh, 'typeDescriptor', None) is None:
        return None
    return veh


def _scan_optional_devices(descr):
    """Inspect descriptor's optionalDevices for CamouflageNet and Stereoscope.

    Returns (camo_net_bonus, stereoscope_factor) where:
        camo_net_bonus  - additive bonus to invisibility[0] when net is active
                          (effectively the camo net's contribution after the
                          'competesBy' max() rule). 0.0 if no net equipped or
                          its bonus is dominated by static modifiers.
        stereoscope_factor - multiplicative factor for circularVisionRadius
                          when binoculars are active; this is what the game
                          would multiply the existing factor by (e.g. 1.0
                          if no binos, ~ activeValue / current_factor when
                          equipped).
    """
    camo_net_bonus = 0.0
    stereo_factor = 1.0
    devices = getattr(descr, 'optionalDevices', None) or ()
    try:
        from items.artefacts import CamouflageNet, Stereoscope
    except ImportError:
        return camo_net_bonus, stereo_factor
    for device in devices:
        if device is None:
            continue
        try:
            if isinstance(device, CamouflageNet):
                level = device.defineActiveLevel(descr)
                if level is None:
                    bonus_value = 0.0
                else:
                    bonus_value = device.defineActiveValueForSpecFactor(
                        descr, device.invisibilityBonusName, level) or 0.0
                static_value = float((descr.miscAttrs or {}).get('invisibilityAdditiveTerm', 0.0))
                # Mirrors CamouflageNet.transformFactors: only the part above
                # the static term contributes once 'still 3s' triggers.
                contribution = max(bonus_value, static_value) - static_value
                if contribution > camo_net_bonus:
                    camo_net_bonus = contribution
            elif isinstance(device, Stereoscope):
                level = device.defineActiveLevel(descr)
                active_value = None
                if level is not None and getattr(device, 'circularVisionRadiusFactor', None) is not None:
                    active_value = device.circularVisionRadiusFactor.getActiveValue(level)
                if active_value is not None:
                    current_factor = float((descr.miscAttrs or {}).get('circularVisionRadiusFactor', 1.0)) or 1.0
                    stereo_factor = float(active_value) / current_factor
        except Exception:
            _logger.exception('SpotMeter: failed to read optional device %r', device)
    return camo_net_bonus, stereo_factor


def _is_after_shot():
    if not _CFG.get('applyFirePenalty', True):
        return False
    if _LAST_SHOT_TIME <= 0.0:
        return False
    duration = float(_CFG.get('fireRevealDuration', 3.0))
    if duration <= 0.0:
        return False
    elapsed = BigWorld.time() - _LAST_SHOT_TIME
    return 0.0 <= elapsed < duration


def _compute_camo(vehicle, is_moving, after_shot, camo_net_active):
    # TODO(verify, flagged 2026-06): spot-distance output runs slightly HIGH
    # (we over-estimate the range we get spotted from). User prefers over- to
    # under-estimate, so left as-is for v6.0.0. Revisit this + _compute_spot_radius
    # and the crew/equipment camo factors to calibrate someday. Not a blocker.
    # Mirrors scripts/common/items/utils.py:getInvisibility. The
    # CompositeVehicleDescriptor wrapper handles siege mode automatically:
    # vehicle.typeDescriptor.type.invisibility and miscAttrs already reflect
    # the current siege state (CS-63, S-Conqueror, italian heavies, etc.).
    descr = vehicle.typeDescriptor
    inv_moving, inv_still = descr.type.invisibility
    misc = getattr(descr, 'miscAttrs', None) or {}
    veh_factor = misc.get('invisibilityFactor', 1.0)
    base_additive = misc.get('invisibilityBaseAdditive', 0.0)
    additive_term = misc.get('invisibilityAdditiveTerm', 0.0)
    mult_factor = misc.get('invisibilityMultFactor', 1.0)
    crew_bonus = float(_CFG.get('crewCamoBonus', 1.0))
    base = inv_moving if is_moving else inv_still
    base = base * veh_factor * crew_bonus
    # CVS: if the enemy currently picked has CVS equipped, our moving
    # camo gets multiplied by the level's factor (<1.0). Effect only
    # applies when WE are moving. Server hides enemy CVS the same way it
    # hides optics/vents, so this is a manual cyclable level (Numpad -).
    if is_moving:
        cvs_factors = _CFG.get('pickerCvsFactors') or [1.0]
        cvs_lvl = int(_PICKER_LEVELS.get('cvs', 0))
        cvs_lvl = max(0, min(cvs_lvl, len(cvs_factors) - 1))
        cvs_factor = float(cvs_factors[cvs_lvl])
        if cvs_factor < 0.999:
            base = base * cvs_factor
    additive = base_additive + additive_term
    if camo_net_active:
        # CamouflageNet contributes to factors['invisibility'][0], summed into
        # the additiveTerm in getInvisibility(). Activates after
        # activateWhenStillSec of NOT MOVING (firing doesn't reset it).
        net_bonus, _ = _scan_optional_devices(descr)
        if net_bonus <= 0.0:
            net_bonus = float(_CFG.get('camoNetFallbackBonus', 0.0))
        additive += net_bonus
    camo = max(0.0, (base + additive) * mult_factor)
    if after_shot:
        factor = misc.get('invisibilityFactorAtShot', 1.0)
        if factor < 1.0:
            camo *= factor
    if camo > 0.99:
        camo = 0.99
    return camo


def _is_camo_net_active(vehicle, is_moving):
    if not _CFG.get('applyCamoNet', True):
        return False
    if is_moving:
        return False
    if _LAST_MOVEMENT_TIME <= 0.0:
        return False
    threshold = float(_CFG.get('camoNetActivateSec', 3.0))
    return (BigWorld.time() - _LAST_MOVEMENT_TIME) >= threshold


def _has_camo_net(vehicle):
    try:
        from items.artefacts import CamouflageNet
    except ImportError:
        return False
    devices = getattr(vehicle.typeDescriptor, 'optionalDevices', None) or ()
    for device in devices:
        if isinstance(device, CamouflageNet):
            return True
    return False


def _resolve_enemy_view_range(plugin):
    # Returns raw VR; do NOT clamp here. The 445 m hard cap applies to the
    # FINAL spot distance, not to the input VR. A tank with 500 m VR and a
    # low-camo target still spots at 445 m (capped output), but the extra
    # VR above 445 m provides buffer against the target's camo.
    eff_vid, _src = _effective_picked_vid()
    if eff_vid is not None:
        vr = _picker_vr_for(plugin, eff_vid)
        if vr is not None:
            return vr
    if _CFG.get('useOwnViewRange', True):
        try:
            feedback = plugin.sessionProvider.shared.feedback
            if feedback is not None:
                vr = feedback.getVehicleAttrs().get('circularVisionRadius')
                if vr is not None and vr > 0.0:
                    return float(vr)
        except Exception:
            pass
    return float(_CFG.get('enemyViewRangeFallback', VISIBILITY.MAX_RADIUS))


def _picker_descr_facts(plugin, vid):
    """v5.6.4: cached descriptor decode. The expensive call is
    VehicleDescr(compactDescr=cd) - it re-parses the binary blob and
    instantiates chassis/turret/gun. Everything we read out of it is
    constant for the (vid, vehicleType) pair, so cache by vid. The
    cache is cleared when the minimap plugin stops (patched_stop).

    Returns a dict {base_vr, optics_factor, stereo_factor,
    has_stereo_fallback, short_name} or None if decode fails / vid
    unknown.
    """
    cached = _PICKER_DESCR_CACHE.get(vid)
    if cached is not None:
        return cached
    try:
        arenaDP = plugin.sessionProvider.getArenaDP()
    except Exception:
        return None
    vinfo = arenaDP.getVehicleInfo(vid)
    if vinfo is None or vinfo.vehicleType is None:
        return None
    cd = getattr(vinfo.vehicleType, 'strCompactDescr', None)
    if not cd:
        return None
    try:
        from items.vehicles import VehicleDescr
        descr = VehicleDescr(compactDescr=cd)
    except Exception:
        _logger.exception('SpotMeter: failed to decode descriptor for picked vid=%s', vid)
        return None
    try:
        base_vr = float(descr.turret.circularVisionRadius)
    except Exception:
        return None
    misc = getattr(descr, 'miscAttrs', None) or {}
    optics_factor = float(misc.get('circularVisionRadiusFactor', 1.0)) or 1.0
    _, stereo_factor = _scan_optional_devices(descr)
    facts = {
        'base_vr':              base_vr,
        'optics_factor':        optics_factor,
        'stereo_factor':        stereo_factor,
        'has_stereo_fallback':  _has_stereoscope_fallback(descr),
        'short_name':           vinfo.vehicleType.shortName or '',
    }
    _PICKER_DESCR_CACHE[vid] = facts
    return facts


def _picker_vr_for(plugin, vid):
    # v5.6.4: cheap math layer over cached descriptor facts. Decoding the
    # descriptor every tick (5x/sec) used to drop FPS hard; now decode
    # happens once per (vid, battle).
    facts = _picker_descr_facts(plugin, vid)
    if facts is None:
        return None
    base_vr = facts['base_vr']
    # Two-stage VR model (v5.6+, per user-corrected mechanic):
    #
    # Stage 1: amplify the BASE VR by crew-level boosters. Combat Rations
    #          (+4.30%) and BIA (+2.53%) raise the effective crew level,
    #          which mathematically translates to a flat % on base_vr.
    #          They DO NOT compound on each other - both compute against
    #          the unamplified base_vr.
    #
    #            crew_amplified = base_vr * (1 + rations_pct + BIA_pct)
    #
    # Stage 2: equipment (optics, stereo) and crew skills (Recon, SitAware)
    #          all compute their bonus against the AMPLIFIED baseline.
    #
    #            final = crew_amplified
    #                  + crew_amplified * (optics_factor * directive - 1)
    #                  + crew_amplified * (stereo_factor * directive - 1)
    #                  + crew_amplified * (reconSitAware - 1)
    #
    # Field upgrade applies to base_vr BEFORE stage 1 (capped at 445 m).
    if _PICKER_TOGGLES.get('fieldUpgrades', False):
        upgrade_pct = _lookup_field_upgrade_vr(facts['short_name'])
        if upgrade_pct > 0:
            cap = float(_CFG.get('pickerFieldUpgradeCap', 445.0))
            base_vr = min(base_vr * (1.0 + upgrade_pct), cap)

    # v6.0.0: Vents scales the additive crew bonuses (rations / BIA /
    # recon+SitA) multiplicatively. The factor lookup is into a 5-entry
    # list in _CFG: [OFF, basic, basicInSlot, Bonds, Deluxe].
    vents_factors = _CFG.get('pickerVentsFactors') or [1.0]
    vents_lvl = max(0, min(int(_PICKER_LEVELS.get('vents', 0)),
                           len(vents_factors) - 1))
    vents_mult = float(vents_factors[vents_lvl])

    # Stage 1: crew amplifier (Rations + BIA, both from base_vr,
    # scaled by vents).
    crew_amp = 1.0
    if _PICKER_TOGGLES.get('rations', True):
        crew_amp += (float(_CFG.get('pickerVRBonusRations', 1.0430)) - 1.0) * vents_mult
    if _PICKER_TOGGLES.get('BIA', True):
        crew_amp += (float(_CFG.get('pickerVRBonusBIA', 1.0253)) - 1.0) * vents_mult
    crew_amplified = base_vr * crew_amp
    final = crew_amplified

    # Stage 2: equipment + crew-skill bonuses, additive against crew_amplified.
    directive_active = _PICKER_TOGGLES.get('directives', False)
    directive_factor = float(_CFG.get('pickerVRBonusDirective', 1.025)) if directive_active else 1.0

    # Optics: server hides enemy optionalDevices in WoT 2.x, so we use
    # opticsLevel (cyclable via Numpad 6) to pick from a preset table.
    # If the descriptor DID happen to expose a real optics factor we'd
    # prefer that over the preset, but in practice descr factor stays 1.0
    # for enemies and we just read the level table.
    descr_optics = facts['optics_factor']
    optics_factors = _CFG.get('pickerOpticsFactors') or [1.0]
    optics_lvl = max(0, min(int(_PICKER_LEVELS.get('optics', 0)),
                            len(optics_factors) - 1))
    optics_factor = (descr_optics
                     if descr_optics > 1.001
                     else float(optics_factors[optics_lvl]))
    if optics_factor > 1.001:
        optics_total = optics_factor * directive_factor
        final += crew_amplified * (optics_total - 1.0)

    if _CFG.get('pickerAssumeStereoscope', True):
        stereo_factor = facts['stereo_factor']
        if stereo_factor < 1.001 and facts['has_stereo_fallback']:
            stereo_factor = float(_CFG.get('pickerStereoscopeFallback', 1.25))
        if stereo_factor > 1.001:
            stereo_total = stereo_factor * directive_factor
            final += crew_amplified * (stereo_total - 1.0)

    if _PICKER_TOGGLES.get('reconSitAware', True):
        rs_bonus = (float(_CFG.get('pickerVRBonusReconSitAware', 1.0739)) - 1.0) * vents_mult
        final += crew_amplified * rs_bonus

    return final


def _effective_picked_vid():
    """Resolve which vid drives the spot circle right now.

    Returns (vid, source) where source is 'manual' (user pressed Numpad
    2/8), 'auto' (auto-pick chose the nearest visible enemy), or None
    (nothing picked). Manual ALWAYS wins over auto - the user explicitly
    asked for that target and we don't second-guess. Auto only kicks in
    when autoPickEnabled is True AND there's a candidate cached.
    """
    if _PICKED_VID is not None:
        return _PICKED_VID, 'manual'
    if _CFG.get('autoPickEnabled', False) and _AUTO_PICKED_VID is not None:
        return _AUTO_PICKED_VID, 'auto'
    return None, None


def _update_enemy_pos_cache(plugin):
    """Refresh _ENEMY_POS_CACHE with currently-visible enemy positions and
    prune stale or no-longer-listed entries.

    BigWorld.entity(vid) returns the entity only while it sits in our AoI
    (so: while spotted by us or a teammate). When it disappears we keep
    the last known position for autoPickCacheTimeoutSec so the picker
    doesn't flicker each time a spotter blinks. Position comes back as
    a Vector3 (x, y, z) in BigWorld coords; we keep only x/z (2D ground
    distance is what matters for view-range purposes).
    """
    now = BigWorld.time()
    timeout = float(_CFG.get('autoPickCacheTimeoutSec', 5.0))
    try:
        arenaDP = plugin.sessionProvider.getArenaDP()
    except Exception:
        return
    if arenaDP is None:
        return
    my_team = arenaDP.getNumberOfTeam()
    listed_vids = set()
    try:
        for vinfo in arenaDP.getVehiclesInfoIterator():
            if vinfo.team == my_team:
                continue
            if not vinfo.isAlive():
                continue
            vid = vinfo.vehicleID
            listed_vids.add(vid)
            try:
                ent = BigWorld.entity(vid)
            except Exception:
                ent = None
            if ent is None:
                continue
            pos = getattr(ent, 'position', None)
            if pos is None:
                continue
            try:
                _ENEMY_POS_CACHE[vid] = (float(pos[0]), float(pos[2]), now)
            except (TypeError, IndexError):
                continue
    except Exception:
        _logger.exception('SpotMeter: failed to refresh enemy position cache')
        return
    # Prune: entries older than timeout, or for vehicles that are no longer
    # in the team listing (left battle / dead). Dead-filter happens above
    # via isAlive() - those won't reappear in listed_vids so they'll be
    # dropped here.
    for vid in list(_ENEMY_POS_CACHE.keys()):
        x, z, ts = _ENEMY_POS_CACHE[vid]
        if (now - ts) > timeout or vid not in listed_vids:
            del _ENEMY_POS_CACHE[vid]


def _select_auto_pick(plugin):
    """Choose the nearest cached enemy within autoPickRangeMeters; update
    _AUTO_PICKED_VID. Anti-flicker: if the previously-picked target is
    still in range and within 1 m^2 of the new best, keep it - avoids
    rapid switching when two enemies are roughly equidistant.
    """
    global _AUTO_PICKED_VID
    if not _ENEMY_POS_CACHE:
        if _AUTO_PICKED_VID is not None:
            _AUTO_PICKED_VID = None
        return
    veh = _get_player_vehicle()
    if veh is None:
        return
    try:
        my_pos = veh.position
        my_x = float(my_pos[0])
        my_z = float(my_pos[2])
    except Exception:
        return
    range_m = float(_CFG.get('autoPickRangeMeters', 445.0))
    range_sq = range_m * range_m
    best_vid = None
    best_dist_sq = None
    for vid, (x, z, _ts) in _ENEMY_POS_CACHE.iteritems():
        dx = x - my_x
        dz = z - my_z
        dsq = dx * dx + dz * dz
        if dsq > range_sq:
            continue
        if best_dist_sq is None or dsq < best_dist_sq:
            best_vid = vid
            best_dist_sq = dsq
    # Anti-flicker stickiness: keep current if it's still in range and
    # roughly tied with the new best (within ~1 m^2 of squared distance).
    if (_AUTO_PICKED_VID is not None
            and _AUTO_PICKED_VID in _ENEMY_POS_CACHE
            and best_vid != _AUTO_PICKED_VID
            and best_dist_sq is not None):
        cur_x, cur_z, _ = _ENEMY_POS_CACHE[_AUTO_PICKED_VID]
        cur_dsq = (cur_x - my_x) ** 2 + (cur_z - my_z) ** 2
        if cur_dsq <= range_sq and (cur_dsq - best_dist_sq) < 1.0:
            return
    _AUTO_PICKED_VID = best_vid


def _apply_auto_preset(plugin, vid):
    """Write the per-class auto preset into the live toggle/level state.

    Looks up the auto-picked tank's class tag, picks autoPresets[<class>]
    (falling back to autoPresets['default']) and sets rations / BIA /
    reconSitAware / directives / fieldUpgrades + optics/vents/cvs levels in
    _PICKER_TOGGLES / _PICKER_LEVELS. Called ONLY from the auto-enable path,
    so presets are an auto-mode-only behaviour; later Numpad presses just
    mutate the same dicts (override). No-op on any lookup failure.
    """
    presets = _CFG.get('autoPresets') or {}
    if not presets:
        return
    tags = ()
    try:
        arenaDP = plugin.sessionProvider.getArenaDP()
        vinfo = arenaDP.getVehicleInfo(vid) if arenaDP is not None else None
        if vinfo is not None and vinfo.vehicleType is not None:
            tags = getattr(vinfo.vehicleType, 'tags', None) or ()
    except Exception:
        _logger.exception('SpotMeter: auto-preset class lookup failed')
        return
    key = None
    for k in ('lightTank', 'mediumTank', 'heavyTank', 'AT-SPG', 'SPG'):
        if k in tags:
            key = k
            break
    preset = presets.get(key) or presets.get('default')
    if not isinstance(preset, dict):
        return
    for t in ('rations', 'BIA', 'reconSitAware', 'directives', 'fieldUpgrades'):
        if t in preset and t in _PICKER_TOGGLES:
            _PICKER_TOGGLES[t] = bool(preset[t])
    for lv in ('optics', 'vents', 'cvs'):
        if lv in preset and lv in _PICKER_LEVELS:
            _PICKER_LEVELS[lv] = int(preset[lv])
    _logger.info('SpotMeter: auto-preset applied (class=%s)', key or 'default')


def _toggle_auto_pick():
    """Runtime ON/OFF for auto-pick. When turning ON, do an immediate
    cache+pick pass so the spot circle reflects the change without
    waiting for the next 0.2 s tick. When turning OFF, drop the stale
    _AUTO_PICKED_VID. Either way clears any manual pick (Numpad 2/8) so the
    auto toggle is the most-recent action that decides the mode.
    """
    global _AUTO_PICKED_VID, _DEFAULT_AUTO_PICK_ENABLED, _PICKED_VID
    _CFG['autoPickEnabled'] = not _CFG.get('autoPickEnabled', False)
    # "Most recent action wins": toggling auto is a fresh mode choice, so it
    # supersedes a sticky manual pick (Numpad 2/8) - ON => auto drives the
    # circle, OFF => own tank. Drop the manual pick either way. (Symmetric
    # with _cycle_picker, where pressing 2/8 overrides an active auto pick.)
    _PICKED_VID = None
    # Garage-time toggle: also update the "default state at battle
    # start" so _reset_battle_state doesn't flip it back. In-memory
    # only; spotmeter.json on disk is unchanged.
    if _is_in_garage():
        _DEFAULT_AUTO_PICK_ENABLED = _CFG['autoPickEnabled']
    plugin = _get_picker_plugin()
    if _CFG['autoPickEnabled']:
        if plugin is not None:
            try:
                _update_enemy_pos_cache(plugin)
                _select_auto_pick(plugin)
                # Per-class preset, ONCE at enable time (off+on to re-apply).
                if _CFG.get('autoPresetsEnabled', True) and _AUTO_PICKED_VID is not None:
                    _apply_auto_preset(plugin, _AUTO_PICKED_VID)
            except Exception:
                _logger.exception('SpotMeter: auto-pick initial scan failed')
    else:
        _AUTO_PICKED_VID = None
    if plugin is not None:
        try:
            _tick(plugin)
        except Exception:
            _logger.exception('SpotMeter: tick after auto-pick toggle failed')
    _post_chat_line('auto-pick: %s' % ('ON' if _CFG['autoPickEnabled'] else 'OFF'))
    _refresh_garage_if_active()


def _lookup_field_upgrade_vr(short_name):
    """Return field-upgrade VR % bonus for the given tank short name.

    Returns 0 if tank not in the map (caller should treat as 'no
    upgrade'). Lookup is exact first, then case-insensitive substring.
    The table is in DEFAULT_CONFIG['pickerFieldUpgradeVR'] and can be
    overridden / extended via spotmeter.json.
    """
    tank_map = _CFG.get('pickerFieldUpgradeVR') or {}
    if not tank_map or not short_name:
        return 0.0
    if short_name in tank_map:
        return float(tank_map[short_name])
    short_lower = short_name.lower()
    for key, val in tank_map.items():
        try:
            if key.lower() in short_lower or short_lower in key.lower():
                return float(val)
        except Exception:
            continue
    return 0.0


def _has_stereoscope_fallback(descr):
    try:
        from items.artefacts import Stereoscope
    except ImportError:
        return False
    devices = getattr(descr, 'optionalDevices', None) or ()
    for device in devices:
        if isinstance(device, Stereoscope):
            return True
    return False


def _compute_spot_radius(camo, enemy_vr):
    radius = enemy_vr * (1.0 - camo)
    if radius < VISIBILITY.MIN_RADIUS:
        radius = VISIBILITY.MIN_RADIUS
    elif radius > VISIBILITY.MAX_RADIUS:
        radius = VISIBILITY.MAX_RADIUS
    return radius


def _ensure_circle_entry(plugin, state):
    if state['circleId'] is not None:
        return state['circleId']
    own_matrix = matrix_factory.makeAttachedVehicleMatrix()
    transformProps = _mm_settings.TRANSFORM_FLAG.DEFAULT ^ _mm_settings.TRANSFORM_FLAG.NO_ROTATION
    cid = plugin._addEntry(
        _S_NAME.VIEW_RANGE_CIRCLES,
        _C_NAME.PERSONAL,
        matrix=own_matrix,
        active=True,
        transformProps=transformProps,
    )
    if not cid:
        return None
    bottomLeft, upperRight = plugin._parentObj.getBoundingBox()
    width = upperRight[0] - bottomLeft[0]
    height = upperRight[1] - bottomLeft[1]
    plugin._invoke(cid, _AS3.AS_INIT_ARENA_SIZE, width, height)
    state['circleId'] = cid
    state['attached'] = False
    state['lastState'] = None
    state['lastRadius'] = 0.0
    return cid


def _add_dyn_circle(plugin, state, color, radius):
    cid = state['circleId']
    if cid is None:
        return
    plugin._invoke(cid, _AS3.AS_ADD_DYN_CIRCLE, color, _CFG['alpha'], radius)
    state['attached'] = True
    state['lastRadius'] = radius


def _update_dyn_circle(plugin, state, radius):
    cid = state['circleId']
    if cid is None:
        return
    plugin._invoke(cid, _AS3.AS_UPDATE_DYN_CIRCLE, radius)
    state['lastRadius'] = radius


def _remove_dyn_circle(plugin, state):
    cid = state['circleId']
    if cid is None or not state['attached']:
        return
    plugin._invoke(cid, _AS3.AS_DEL_DYN_CIRCLE)
    state['attached'] = False


def _set_active(plugin, state, active):
    cid = state['circleId']
    if cid is not None:
        plugin._setActive(cid, active)


def _refresh_spot_circle(plugin):
    if not plugin._isAlive() or plugin._getIsObserver():
        _stop_ticking(plugin)
        state = _state_for(plugin)
        _remove_dyn_circle(plugin, state)
        _set_active(plugin, state, False)
        return
    state = _state_for(plugin)
    if _ensure_circle_entry(plugin, state) is None:
        return
    _set_active(plugin, state, True)
    _tick(plugin)
    _start_ticking(plugin)


def _classify_state(is_moving, after_shot, camo_net_active):
    if after_shot:
        return 'afterShot'
    if is_moving:
        return 'moving'
    if camo_net_active:
        return 'stillNet'
    return 'still'


def _color_for_state(state_name):
    if state_name == 'afterShot':
        return _CFG['colorAfterShot']
    if state_name == 'moving':
        return _CFG['colorMoving']
    if state_name == 'stillNet':
        return _CFG.get('colorCamoNet', _CFG['colorStill'])
    return _CFG['colorStill']


def _tick(plugin):
    global _LAST_MOVEMENT_TIME, _LAST_SPOT_RADIUS
    state = _STATE.get(plugin)
    if state is None:
        return
    veh = _get_player_vehicle()
    if veh is None:
        return
    # Auto-pick: refresh enemy positions and re-select nearest. Manual pick
    # (Numpad 2/8) wins over auto - that priority is resolved later via
    # _effective_picked_vid() inside _resolve_enemy_view_range.
    if _CFG.get('autoPickEnabled', False):
        try:
            _update_enemy_pos_cache(plugin)
            _select_auto_pick(plugin)
        except Exception:
            _logger.exception('SpotMeter: auto-pick refresh failed')
    speed = 0.0
    try:
        speed = veh.getSpeed()
    except Exception:
        pass
    is_moving = _is_player_vehicle_moving(speed)
    if is_moving:
        _LAST_MOVEMENT_TIME = BigWorld.time()
    elif _LAST_MOVEMENT_TIME <= 0.0:
        # First tick while already still: timestamp anchors here.
        _LAST_MOVEMENT_TIME = BigWorld.time()
    after_shot = _is_after_shot()
    camo_net_active = (not is_moving) and _is_camo_net_active(veh, is_moving) and _has_camo_net(veh)
    new_state = _classify_state(is_moving, after_shot, camo_net_active)
    camo = _compute_camo(veh, is_moving, after_shot, camo_net_active)
    enemy_vr = _resolve_enemy_view_range(plugin)
    radius = _compute_spot_radius(camo, enemy_vr)
    _LAST_SPOT_RADIUS = radius
    color = _color_for_state(new_state)
    if _CFG.get('logCalcDetails'):
        _logger.info('SpotMeter: state=%s camo=%.3f vr=%.1fm radius=%.1fm net=%s shot=%s',
                     new_state, camo, enemy_vr, radius, camo_net_active, after_shot)
    state_changed = new_state != state['lastState']
    if state_changed:
        if state['attached']:
            _remove_dyn_circle(plugin, state)
        _add_dyn_circle(plugin, state, color, radius)
        state['lastState'] = new_state
        return
    if after_shot:
        if abs(radius - state['lastRadius']) > 0.1:
            _update_dyn_circle(plugin, state, radius)
        return
    if abs(radius - state['lastRadius']) > 0.5:
        _update_dyn_circle(plugin, state, radius)


def _start_ticking(plugin):
    state = _state_for(plugin)
    if state['callbackId'] is not None:
        return
    weak_plugin = weakref.ref(plugin)

    def _cb():
        p = weak_plugin()
        if p is None:
            return
        st = _STATE.get(p)
        if st is None:
            return
        st['callbackId'] = None
        try:
            _tick(p)
        except Exception:
            _logger.exception('SpotMeter: tick failed')
        st['callbackId'] = BigWorld.callback(_CFG['tickInterval'], _cb)

    state['callbackId'] = BigWorld.callback(_CFG['tickInterval'], _cb)


def _stop_ticking(plugin):
    state = _STATE.get(plugin)
    if state is None:
        return
    cb_id = state.get('callbackId')
    if cb_id is not None:
        try:
            BigWorld.cancelCallback(cb_id)
        except Exception:
            pass
        state['callbackId'] = None


def _patch_plugin():
    global _PATCHED
    if _PATCHED:
        return
    Plugin = _mm_plugins.PersonalEntriesPlugin

    orig_invalidateMarkup = Plugin._invalidateMarkup
    orig_hideMarkup = Plugin._hideMarkup
    orig_stop = Plugin.stop
    pm_attr = '_PersonalEntriesPlugin__onPostMortemSwitched'
    orig_onPostMortem = getattr(Plugin, pm_attr, None)

    def patched_invalidateMarkup(self, forceInvalidate=False):
        orig_invalidateMarkup(self, forceInvalidate)
        # v6.0.0: zero picker state on the first invalidate of this battle.
        # _reset_battle_state is idempotent (guards via _BATTLE_RESET_DONE).
        try:
            _reset_battle_state()
        except Exception:
            _logger.exception('SpotMeter: battle reset failed')
        try:
            _refresh_spot_circle(self)
        except Exception:
            _logger.exception('SpotMeter: failed to refresh spot circle')
        # v6.0: load the battle panel here too. _show_battle_view is
        # idempotent so multiple invalidateMarkup calls in one battle
        # (respawn, scenario reload) don't stack views.
        try:
            _show_battle_view()
        except Exception:
            _logger.exception('SpotMeter: failed to show battle panel')

    def patched_hideMarkup(self):
        try:
            state = _STATE.get(self)
            if state is not None:
                _stop_ticking(self)
                _remove_dyn_circle(self, state)
                _set_active(self, state, False)
        except Exception:
            _logger.exception('SpotMeter: failed to hide spot circle')
        try:
            _hide_battle_view()
        except Exception:
            _logger.exception('SpotMeter: failed to hide battle panel')
        orig_hideMarkup(self)

    def patched_stop(self):
        global _BATTLE_RESET_DONE
        try:
            _stop_ticking(self)
            state = _STATE.pop(self, None)
            if state is not None:
                state['circleId'] = None
                state['attached'] = False
            # v5.6.4: descriptor cache is per-battle; clear on battle end so
            # the next battle's vids (which may collide numerically with
            # last battle's) don't pick up a stale entry.
            _PICKER_DESCR_CACHE.clear()
            # v6.0.0: arm the per-battle reset for the next battle.
            _BATTLE_RESET_DONE = False
        except Exception:
            _logger.exception('SpotMeter: failed to clean up on stop')
        try:
            _hide_battle_view()
        except Exception:
            _logger.exception('SpotMeter: failed to hide battle panel on stop')
        orig_stop(self)

    Plugin._invalidateMarkup = patched_invalidateMarkup
    Plugin._hideMarkup = patched_hideMarkup
    Plugin.stop = patched_stop

    if orig_onPostMortem is not None:
        def patched_onPostMortem(self, noRespawnPossible, respawnAvailable):
            orig_onPostMortem(self, noRespawnPossible, respawnAvailable)
            try:
                state = _STATE.get(self)
                if state is not None:
                    _stop_ticking(self)
                    _remove_dyn_circle(self, state)
                    _set_active(self, state, False)
            except Exception:
                _logger.exception('SpotMeter: postmortem cleanup failed')
        setattr(Plugin, pm_attr, patched_onPostMortem)

    _PATCHED = True


def _record_shot():
    global _LAST_SHOT_TIME
    _LAST_SHOT_TIME = BigWorld.time()


def _patch_avatar_shoot():
    global _AVATAR_PATCHED
    if _AVATAR_PATCHED:
        return
    if not _CFG.get('applyFirePenalty', True):
        return
    try:
        import Avatar as _avatar_module
    except ImportError:
        _logger.info('SpotMeter: Avatar module unavailable, fire penalty disabled')
        return
    AvatarCls = getattr(_avatar_module, 'PlayerAvatar', None) or getattr(_avatar_module, 'Avatar', None)
    if AvatarCls is None:
        _logger.info('SpotMeter: Avatar class not found, fire penalty disabled')
        return

    orig_shoot = getattr(AvatarCls, 'shoot', None)
    orig_shootDualGun = getattr(AvatarCls, 'shootDualGun', None)

    if orig_shoot is not None:
        def patched_shoot(self, isRepeat=False):
            try:
                result = orig_shoot(self, isRepeat=isRepeat)
            except TypeError:
                result = orig_shoot(self, isRepeat)
            try:
                _record_shot()
            except Exception:
                _logger.exception('SpotMeter: failed to record shot')
            return result
        AvatarCls.shoot = patched_shoot

    if orig_shootDualGun is not None:
        def patched_shootDualGun(self, chargeActionType, isPrepared=False, isRepeat=False):
            result = orig_shootDualGun(self, chargeActionType, isPrepared=isPrepared, isRepeat=isRepeat)
            try:
                _record_shot()
            except Exception:
                _logger.exception('SpotMeter: failed to record dual-gun shot')
            return result
        AvatarCls.shootDualGun = patched_shootDualGun

    _AVATAR_PATCHED = True
    _logger.info('SpotMeter: Avatar.shoot hooked for fire penalty')


def _hot_reload():
    _logger.info('SpotMeter: hot-reloading config')
    _read_config()
    _force_panel_refresh()
    for plugin in list(_STATE.keys()):
        try:
            _refresh_spot_circle(plugin)
        except Exception:
            _logger.exception('SpotMeter: failed to refresh after reload')


def _get_picker_plugin():
    for plugin in _STATE.keys():
        return plugin
    return None


def _enemy_iterator(plugin):
    try:
        arenaDP = plugin.sessionProvider.getArenaDP()
    except Exception:
        return []
    if arenaDP is None:
        return []
    my_team = arenaDP.getNumberOfTeam()
    include_dead = bool(_CFG.get('pickerIncludeDeadEnemies', False))
    items = []
    try:
        for vinfo in arenaDP.getVehiclesInfoIterator():
            if vinfo.team == my_team:
                continue
            if vinfo.vehicleType is None or not vinfo.vehicleType.strCompactDescr:
                continue
            if not include_dead and not vinfo.isAlive():
                continue
            items.append((vinfo.vehicleID, vinfo))
    except Exception:
        _logger.exception('SpotMeter: failed to enumerate enemies')
        return []
    items.sort(key=lambda kv: (-(kv[1].vehicleType.level or 0), kv[1].vehicleType.shortName, kv[0]))
    return items


def _veh_type_key(vt):
    """Stable per-TYPE key for grouping + picked-highlight: same model =>
    same key. Uses vehicleType.name (e.g. 'germany:G89_Dravec') or shortName."""
    if vt is None:
        return None
    return getattr(vt, 'name', None) or vt.shortName or None


def _grouped_enemies(plugin):
    """Collapse _enemy_iterator() by vehicle type so identical tanks form a
    single entry: same model => same view range => same spot circle, so
    listing 5x the same tank as 5 rows just means cycling through identical
    circles. Returns [(rep_vid, vinfo, count), ...] preserving the
    _enemy_iterator sort order; the representative is the first (lowest-id)
    alive instance of each type. Honours battlePanelGroupSameTanks (set it
    False to fall back to one entry per enemy)."""
    enemies = _enemy_iterator(plugin)
    if not _CFG.get('battlePanelGroupSameTanks', True):
        return [(vid, vinfo, 1) for vid, vinfo in enemies]
    groups = []          # [rep_vid, vinfo, count]
    index = {}           # type key -> position in `groups`
    for vid, vinfo in enemies:
        vt = vinfo.vehicleType
        key = _veh_type_key(vt) or vid
        pos = index.get(key)
        if pos is None:
            index[key] = len(groups)
            groups.append([vid, vinfo, 1])
        else:
            groups[pos][2] += 1
    return [(g[0], g[1], g[2]) for g in groups]


def _active_perk_tags():
    tag_map = {
        'rations':       'rations',
        'BIA':           'BIA',
        'reconSitAware': 'reconSit',
        'directives':    'dyrektywy',
        'fieldUpgrades': 'ulepsz.polowe',
    }
    order = ('rations', 'BIA', 'reconSitAware', 'directives', 'fieldUpgrades')
    return [tag_map[k] for k in order if _PICKER_TOGGLES.get(k, False)]


def _dump_picker_descriptor(plugin):
    """Diagnostic dump for the currently-picked enemy. Logs to python.log:
      - The raw descriptor values the game transmitted to us (turret VR,
        miscAttrs factors, optionalDevices, enhancements).
      - A step-by-step breakdown of how OUR picker model uses those
        values to arrive at the final VR for this enemy, so we can
        verify equipment is being picked up correctly.

    Bound to pickerDiagDumpKey (default Numpad *).
    """
    if _PICKED_VID is None:
        _logger.warning('SpotMeter: dump requested but no target picked')
        _post_chat_line('diag: no picker target')
        return
    try:
        arenaDP = plugin.sessionProvider.getArenaDP()
    except Exception:
        return
    vinfo = arenaDP.getVehicleInfo(_PICKED_VID) if arenaDP else None
    if vinfo is None or vinfo.vehicleType is None:
        return
    cd = getattr(vinfo.vehicleType, 'strCompactDescr', None)
    if not cd:
        return
    try:
        from items.vehicles import VehicleDescr
        descr = VehicleDescr(compactDescr=cd)
    except Exception:
        _logger.exception('SpotMeter: dump - cannot decode descriptor')
        return
    short = vinfo.vehicleType.shortName or '?'
    misc = getattr(descr, 'miscAttrs', None) or {}
    devices = []
    for d in (getattr(descr, 'optionalDevices', None) or ()):
        if d is None:
            continue
        try:
            devices.append('%s(%s)' % (type(d).__name__, getattr(d, 'name', '?')))
        except Exception:
            devices.append(type(d).__name__)
    enhancements = []
    for e in (getattr(descr, 'enhancements', None) or ()):
        try:
            enhancements.append('%s %s %s' % (e.name, e.op, e.value))
        except Exception:
            pass

    # --- raw descriptor dump (what the server tells us) ---
    # Also dump ALL miscAttrs keys + values - in case the optics-related
    # key was renamed in WoT 2.x and we're reading a stale name.
    misc_full_lines = []
    try:
        for k in sorted(misc.keys()):
            v = misc[k]
            misc_full_lines.append('    %s = %s' % (k, v))
    except Exception:
        misc_full_lines.append('    (failed to iterate)')
    misc_full = '\n'.join(misc_full_lines) if misc_full_lines else '    (empty)'

    _logger.warning(
        'SpotMeter: descriptor dump for vid=%s name=%s\n'
        '  turret.circularVisionRadius        = %s\n'
        '  miscAttrs.circularVisionRadiusFactor = %s\n'
        '  miscAttrs.invisibilityFactor       = %s\n'
        '  miscAttrs.invisibilityBaseAdditive = %s\n'
        '  miscAttrs.invisibilityAdditiveTerm = %s\n'
        '  optionalDevices (%d): %s\n'
        '  enhancements (%d): %s\n'
        '  miscAttrs full (%d keys):\n%s',
        _PICKED_VID, short,
        getattr(descr.turret, 'circularVisionRadius', None),
        misc.get('circularVisionRadiusFactor'),
        misc.get('invisibilityFactor'),
        misc.get('invisibilityBaseAdditive'),
        misc.get('invisibilityAdditiveTerm'),
        len(devices), ', '.join(devices) or '(none)',
        len(enhancements), ' | '.join(enhancements) or '(none)',
        len(misc), misc_full)

    # --- our model breakdown (how we use the descriptor) ---
    facts = _picker_descr_facts(plugin, _PICKED_VID)
    if facts is None:
        _logger.warning('SpotMeter: VR breakdown unavailable - facts decode failed')
        _post_chat_line('diag: dumped %s descriptor to python.log' % short)
        return

    base_vr_orig = facts['base_vr']
    # Re-implement the same staged math from _picker_vr_for so each
    # line traces a real contribution.
    lines = ['SpotMeter: VR model breakdown for vid=%s name=%s' % (_PICKED_VID, short)]
    lines.append('  base_vr (turret.circularVisionRadius) = %.2fm'
                 % base_vr_orig)

    # Stage 0: field upgrade (toggle + per-tank table)
    fu_on = _PICKER_TOGGLES.get('fieldUpgrades', False)
    fu_pct = _lookup_field_upgrade_vr(facts['short_name']) if fu_on else 0.0
    if fu_on and fu_pct > 0:
        cap = float(_CFG.get('pickerFieldUpgradeCap', 445.0))
        base_vr = min(base_vr_orig * (1.0 + fu_pct), cap)
        lines.append('  + fieldUpgrades (toggle ON, %s = +%.1f%%, cap %dm)  -> base_vr = %.2fm'
                     % (facts['short_name'], fu_pct * 100.0, int(cap), base_vr))
    else:
        base_vr = base_vr_orig
        reason = 'toggle OFF' if not fu_on else '%s not in table' % facts['short_name']
        lines.append('  + fieldUpgrades skipped (%s)             -> base_vr stays %.2fm'
                     % (reason, base_vr))

    # Vents multiplier (shared by all crew bonuses)
    vents_factors = _CFG.get('pickerVentsFactors') or [1.0]
    vents_lvl = max(0, min(int(_PICKER_LEVELS.get('vents', 0)),
                           len(vents_factors) - 1))
    vents_mult = float(vents_factors[vents_lvl])
    vents_name = _LEVEL_NAMES[vents_lvl] if vents_lvl < len(_LEVEL_NAMES) else 'L%d' % vents_lvl
    lines.append('  + vents      (level %d=%s, x%.4f scales crew bonuses)'
                 % (vents_lvl, vents_name, vents_mult))

    # Stage 1: crew amplifier (rations + BIA), each scaled by vents
    crew_amp = 1.0
    if _PICKER_TOGGLES.get('rations', True):
        r = (float(_CFG.get('pickerVRBonusRations', 1.0430)) - 1.0) * vents_mult
        crew_amp += r
        lines.append('  + rations    (toggle ON, +%.2f%% after vents) -> crew_amp = %.4f'
                     % (r * 100, crew_amp))
    else:
        lines.append('  + rations    (toggle OFF)                  -> crew_amp = %.4f'
                     % crew_amp)
    if _PICKER_TOGGLES.get('BIA', True):
        b = (float(_CFG.get('pickerVRBonusBIA', 1.0253)) - 1.0) * vents_mult
        crew_amp += b
        lines.append('  + BIA        (toggle ON, +%.2f%% after vents) -> crew_amp = %.4f'
                     % (b * 100, crew_amp))
    else:
        lines.append('  + BIA        (toggle OFF)                  -> crew_amp = %.4f'
                     % crew_amp)
    crew_amplified = base_vr * crew_amp
    lines.append('  = crew_amplified = base_vr * crew_amp = %.2fm' % crew_amplified)

    # Stage 2: equipment + skills (additive against crew_amplified)
    final = crew_amplified
    directive_active = _PICKER_TOGGLES.get('directives', False)
    directive_factor = (float(_CFG.get('pickerVRBonusDirective', 1.025))
                        if directive_active else 1.0)
    descr_optics = facts['optics_factor']
    optics_factors = _CFG.get('pickerOpticsFactors') or [1.0]
    optics_lvl = max(0, min(int(_PICKER_LEVELS.get('optics', 0)),
                            len(optics_factors) - 1))
    optics_name = _LEVEL_NAMES[optics_lvl] if optics_lvl < len(_LEVEL_NAMES) else 'L%d' % optics_lvl
    if descr_optics > 1.001:
        optics_factor = descr_optics
        optics_source = 'descr (%.3f)' % descr_optics
    else:
        optics_factor = float(optics_factors[optics_lvl])
        optics_source = 'preset L%d=%s (%.3f)' % (optics_lvl, optics_name, optics_factor)
    if optics_factor > 1.001:
        optics_total = optics_factor * directive_factor
        add = crew_amplified * (optics_total - 1.0)
        final += add
        lines.append('  + optics     (%s * directive %.3f) -> +%.2fm = %.2fm'
                     % (optics_source, directive_factor, add, final))
    else:
        lines.append('  + optics     (level %d=OFF, no descr optics)         -> +0.00m = %.2fm'
                     % (optics_lvl, final))

    stereo_assume = _CFG.get('pickerAssumeStereoscope', True)
    stereo_factor = facts['stereo_factor']
    if stereo_factor < 1.001 and facts['has_stereo_fallback']:
        stereo_factor = float(_CFG.get('pickerStereoscopeFallback', 1.25))
    if stereo_assume and stereo_factor > 1.001:
        stereo_total = stereo_factor * directive_factor
        add = crew_amplified * (stereo_total - 1.0)
        final += add
        lines.append('  + stereo     (factor %.3f, assume=%s) -> +%.2fm = %.2fm'
                     % (stereo_factor, stereo_assume, add, final))
    else:
        lines.append('  + stereo     (factor=%.3f, assume=%s, fallback=%s) -> +0.00m = %.2fm'
                     % (stereo_factor, stereo_assume, facts['has_stereo_fallback'], final))

    if _PICKER_TOGGLES.get('reconSitAware', True):
        rs = (float(_CFG.get('pickerVRBonusReconSitAware', 1.0739)) - 1.0) * vents_mult
        add = crew_amplified * rs
        final += add
        lines.append('  + recon+SitA (toggle ON, +%.2f%% after vents) -> +%.2fm = %.2fm'
                     % (rs * 100, add, final))
    else:
        lines.append('  + recon+SitA (toggle OFF)                                  -> +0.00m = %.2fm'
                     % final)

    lines.append('  ============================================')
    lines.append('  final VR  = %.2fm' % final)
    _logger.warning('\n'.join(lines))

    _post_chat_line('diag: dumped %s descriptor + VR breakdown to python.log' % short)


def _format_picker_summary(plugin):
    eff_vid, src = _effective_picked_vid()
    if eff_vid is None:
        return None
    enemies = _enemy_iterator(plugin)
    for vid, vinfo in enemies:
        if vid == eff_vid:
            short = vinfo.vehicleType.shortName if vinfo.vehicleType else '?'
            vr = _picker_vr_for(plugin, eff_vid)
            vr_str = ('%.0fm' % vr) if vr is not None else '?'
            tags = _active_perk_tags()
            tags_str = (' [+' + ' +'.join(tags) + ']') if tags else ''
            src_str = ' (auto)' if src == 'auto' else ''
            return '%s VR=%s%s%s' % (short, vr_str, tags_str, src_str)
    return None


def _cycle_picker(direction):
    global _PICKED_VID
    plugin = _get_picker_plugin()
    if plugin is None:
        return
    # Cycle over GROUP representatives so identical tanks count as one stop
    # (Numpad 2/8 steps types, not every individual). With grouping off,
    # _grouped_enemies yields one group per enemy = the old behaviour.
    groups = _grouped_enemies(plugin)
    if not groups:
        _PICKED_VID = None
        _on_picker_changed(plugin, set())
        return
    vids = [rep_vid for rep_vid, _, _ in groups]
    affected = set()
    if _PICKED_VID is not None:
        affected.add(_PICKED_VID)
    if _PICKED_VID is None or _PICKED_VID not in vids:
        _PICKED_VID = vids[0] if direction >= 0 else vids[-1]
    else:
        idx = vids.index(_PICKED_VID)
        idx = (idx + (1 if direction > 0 else -1)) % len(vids)
        _PICKED_VID = vids[idx]
    affected.add(_PICKED_VID)
    _on_picker_changed(plugin, affected)


def _clear_picker():
    plugin = _get_picker_plugin()
    global _PICKED_VID
    affected = set()
    if _PICKED_VID is not None:
        affected.add(_PICKED_VID)
    _PICKED_VID = None
    _on_picker_changed(plugin, affected)


def _is_in_garage():
    """True when the player is currently in the lobby/hangar (no arena
    attached to the avatar). Used to decide whether a Numpad toggle
    should also rewrite the in-memory `defaultToggles`/`defaultLevels`
    so the change persists into the next battle's reset."""
    try:
        return not hasattr(BigWorld.player(), 'arena')
    except Exception:
        return False


def _toggle_perk(name):
    if name not in _PICKER_TOGGLES:
        return
    _PICKER_TOGGLES[name] = not _PICKER_TOGGLES[name]
    in_garage = _is_in_garage()
    _logger.warning('SpotMeter: toggle %s -> %s (in_garage=%s)',
                    name, _PICKER_TOGGLES[name], in_garage)
    # In the garage, also update the in-memory defaults so that the
    # next battle's _reset_battle_state picks up the new state instead
    # of clobbering it back to JSON. (We don't persist to disk - this
    # is a session-only override; restarting WoT reloads JSON values.)
    if in_garage:
        defaults = _CFG.setdefault('defaultToggles', {})
        defaults[name] = _PICKER_TOGGLES[name]
    plugin = _get_picker_plugin()
    _on_picker_changed(plugin, set())
    _post_chat_line('%s: %s' % (name, 'ON' if _PICKER_TOGGLES[name] else 'OFF'))
    _refresh_garage_if_active()


# Human-readable labels for level slots - keeps panel + log messages
# in sync. Index aligns with pickerOpticsFactors / pickerVentsFactors.
_LEVEL_NAMES = ['OFF', 'basic', 'slot', 'bonds', 'deluxe']


def _level_name_loc(lvl):
    """Localized level-value name (OFF/basic/slot/bonds/deluxe) for the panels.
    _LEVEL_NAMES stays English for logs/chat; this is the display version."""
    if 0 <= lvl < 5:
        return _t('lv_%d' % lvl)
    return 'L%d' % lvl


def _cycle_level(name):
    """Advance a multi-level picker state by one (wraps 0->1->2->3->4->0).
    Used by Numpad 6 (optics) and Numpad + (vents). Pulls the factor
    table from _CFG so a custom spotmeter.json table changes the wrap
    width without code changes.
    """
    if name not in _PICKER_LEVELS:
        return
    if name == 'optics':
        table = _CFG.get('pickerOpticsFactors') or [1.0]
    elif name == 'vents':
        table = _CFG.get('pickerVentsFactors') or [1.0]
    elif name == 'cvs':
        table = _CFG.get('pickerCvsFactors') or [1.0]
    else:
        table = [1.0]
    n = len(table)
    if n <= 1:
        return
    _PICKER_LEVELS[name] = (int(_PICKER_LEVELS.get(name, 0)) + 1) % n
    in_garage = _is_in_garage()
    _logger.warning('SpotMeter: cycle %s -> L%d (in_garage=%s)',
                    name, _PICKER_LEVELS[name], in_garage)
    # Same garage-side defaults sync as _toggle_perk - so cycling in the
    # lobby actually configures the next battle's starting level.
    if in_garage:
        defaults = _CFG.setdefault('defaultLevels', {})
        defaults[name] = _PICKER_LEVELS[name]
    plugin = _get_picker_plugin()
    _on_picker_changed(plugin, set())
    lvl = _PICKER_LEVELS[name]
    label = _LEVEL_NAMES[lvl] if lvl < len(_LEVEL_NAMES) else 'L%d' % lvl
    _post_chat_line('%s: L%d (%s, x%.3f)' % (name, lvl, label, table[lvl]))
    _refresh_garage_if_active()


def _toggle_live_mode():
    """Toggle the auto-refreshing status block. Default OFF; when ON, the
    block is re-posted every liveModeIntervalSec seconds. The chat will
    show a refreshing block; older blocks scroll out naturally.
    """
    global _LIVE_MODE_ENABLED, _LIVE_MODE_CALLBACK_ID
    _LIVE_MODE_ENABLED = not _LIVE_MODE_ENABLED
    plugin = _get_picker_plugin()
    if _LIVE_MODE_ENABLED:
        _post_chat_line(_t('chat_live_on')
                        % float(_CFG.get('liveModeIntervalSec', 3.0)))
        # Post immediately, then schedule the loop.
        if plugin is not None:
            _post_status_block(plugin)
        try:
            import BigWorld
            interval = float(_CFG.get('liveModeIntervalSec', 3.0))
            if interval < 0.5:
                interval = 0.5
            _LIVE_MODE_CALLBACK_ID = BigWorld.callback(interval, _live_mode_tick)
        except Exception:
            _logger.exception('SpotMeter: failed to start live-mode loop')
    else:
        _post_chat_line('live mode: OFF')
        # The callback will self-terminate when it fires and sees
        # _LIVE_MODE_ENABLED is False; we don't bother trying to cancel
        # it explicitly because BigWorld.cancelCallback is not always
        # exposed and the next tick will just no-op out.
        _LIVE_MODE_CALLBACK_ID = None


def _print_now():
    """One-shot snapshot of the status block (NumpadEnter hotkey).

    Same content as live-mode posts, but on demand. The block shows spot
    distance for all four states (ruch / postoj / siatka 3s / po strzale)
    plus picker / toggle / own-tank context. See _format_status_block.
    """
    plugin = _get_picker_plugin()
    if plugin is None:
        return
    _post_status_block(plugin)


def _on_picker_changed(plugin, affected_vids):
    summary = _format_picker_summary(plugin) if plugin is not None else None
    tags = ' '.join('+' + t for t in _active_perk_tags()) or '-'
    stereo_flag = 'stereo=%s' % ('on' if _CFG.get('pickerAssumeStereoscope', True) else 'off')
    _logger.info('SpotMeter: picker -> %s | perks=%s | %s',
                 summary or 'none', tags, stereo_flag)
    _force_panel_refresh(affected_vids)
    if plugin is not None:
        try:
            _tick(plugin)
        except Exception:
            _logger.exception('SpotMeter: tick after picker change failed')
    # User-action confirmation: short one-line message, not the full block.
    # The picker/toggle change is fully reflected in the next status block
    # snapshot (NumpadEnter) or live-mode tick.
    if summary:
        _post_chat_line('picker -> %s [%s]' % (summary, tags))
    elif _PICKED_VID is None:
        _post_chat_line('picker cleared')


def _post_chat_line(text):
    """Single short chat-line message - used for one-time confirmations on
    user actions (toggle change, picker change, diag dump confirmation).
    Does NOT loop or auto-fire; only called from user-triggered code paths.

    v6.0.0: silenced when the in-battle panel is enabled - the panel is the
    user-facing source of truth and chat noise is exactly what we're
    replacing. To get chat confirmations back, set
    `"battlePanelEnabled": false` in spotmeter.json.
    """
    if not _CFG.get('overlayEnabled', True):
        return
    if _CFG.get('battlePanelEnabled', True):
        return
    try:
        from messenger.MessengerEntry import g_instance as _messengerEntry
        _messengerEntry.gui.addClientMessage('[SpotMeter] ' + text, isCurrentPlayer=True)
    except Exception:
        _logger.exception('SpotMeter: failed to push chat line')


def _format_status_block(plugin):
    """Multi-line block showing spot distance for ALL four states at once
    (ruch / postoj / siatka 3s / po strzale), plus picker/toggle context.
    This is what the user sees on NumpadEnter and what live-mode refreshes.

    The same enemy_vr is used for all four computations (only state varies),
    so the user can compare how much each state buys them. Current state
    is marked with an arrow.
    """
    if plugin is None:
        return None
    veh = _get_player_vehicle()
    if veh is None:
        return None

    speed = 0.0
    try:
        speed = veh.getSpeed()
    except Exception:
        pass
    is_moving_now = _is_player_vehicle_moving(speed)
    after_shot_now = _is_after_shot()
    camo_net_active_now = (not is_moving_now) and _is_camo_net_active(veh, is_moving_now) and _has_camo_net(veh)
    current = _classify_state(is_moving_now, after_shot_now, camo_net_active_now)

    enemy_vr = _resolve_enemy_view_range(plugin)

    # Compute spot distance for each hypothetical state. _compute_camo's
    # signature is (veh, is_moving, after_shot, camo_net_active), so we
    # pass the four canonical combinations.
    def _spot_for(is_moving, after_shot, net):
        camo = _compute_camo(veh, is_moving, after_shot, net)
        return _compute_spot_radius(camo, enemy_vr)

    spot_moving = _spot_for(True,  False, False)
    spot_still  = _spot_for(False, False, False)
    spot_net    = _spot_for(False, False, True)
    spot_shot   = _spot_for(True,  True,  False)

    def _mark(state_key):
        return '  <-- AKTUALNY' if state_key == current else ''

    vr_source = 'own' if (_PICKED_VID is None and _CFG.get('useOwnViewRange', True)) \
                else ('picker' if _PICKED_VID is not None else 'fallback')

    lines = []
    lines.append('[SpotMeter v%s] vs VR=%.0fm (%s)' % (MOD_VERSION, enemy_vr, vr_source))
    lines.append('  ruch:        %4.0fm%s' % (spot_moving, _mark('moving')))
    lines.append('  postoj:      %4.0fm%s' % (spot_still,  _mark('still')))
    lines.append('  siatka 3s+:  %4.0fm%s' % (spot_net,    _mark('stillNet')))
    lines.append('  po strzale:  %4.0fm%s' % (spot_shot,   _mark('afterShot')))

    # Picker / toggle context
    eff_vid, _src = _effective_picked_vid()
    if eff_vid is None:
        if _CFG.get('autoPickEnabled', False):
            lines.append('picker: -- (auto on, brak celu w %dm)'
                         % int(_CFG.get('autoPickRangeMeters', 445)))
        elif _CFG.get('useOwnViewRange', True):
            lines.append('picker: -- (using own VR)')
        else:
            lines.append('picker: -- (fallback VR=%.0fm)' % _CFG.get('enemyViewRangeFallback', 445.0))
    else:
        summary = _format_picker_summary(plugin) or '?'
        lines.append('picker: %s' % summary)

    # Toggle status - show all five with +/- prefix.
    # Order: crew amplifiers (rations, BIA) first, then skills/equipment.
    def _tag(name, on):
        return ('+' if on else '-') + name
    lines.append('toggle: %s' % '  '.join([
        _tag('rations',    _PICKER_TOGGLES.get('rations', True)),
        _tag('BIA',        _PICKER_TOGGLES.get('BIA', True)),
        _tag('reconSit',   _PICKER_TOGGLES.get('reconSitAware', True)),
        _tag('directives', _PICKER_TOGGLES.get('directives', False)),
        _tag('fieldUpgr',  _PICKER_TOGGLES.get('fieldUpgrades', False)),
    ]))

    # Own-tank breakdown - useful to verify field upgrades are baked in
    descr = veh.typeDescriptor
    misc = getattr(descr, 'miscAttrs', None) or {}
    own_vr_factor = misc.get('circularVisionRadiusFactor', 1.0)
    own_base_vr = getattr(descr.turret, 'circularVisionRadius', 0.0)
    add_term = misc.get('invisibilityBaseAdditive', 0.0) + misc.get('invisibilityAdditiveTerm', 0.0)
    lines.append('own:    base_vr=%.0fm * factor=%.3f, camo_add=%.3f, live=%s, auto=%s'
                 % (own_base_vr, own_vr_factor, add_term,
                    'ON' if _LIVE_MODE_ENABLED else 'off',
                    'ON' if _CFG.get('autoPickEnabled', False) else 'off'))

    return '\n'.join(lines)


def _post_status_block(plugin):
    """Format and post a status block to the chat. No-op on failure.

    v6.0.0: silenced when the in-battle panel is enabled. The panel
    displays the same picker/toggle state graphically, so the chat block
    becomes redundant. Set `"battlePanelEnabled": false` to restore.
    """
    if _CFG.get('battlePanelEnabled', True):
        return
    text = _format_status_block(plugin)
    if not text:
        return
    try:
        from messenger.MessengerEntry import g_instance as _messengerEntry
        _messengerEntry.gui.addClientMessage(text, isCurrentPlayer=True)
    except Exception:
        _logger.exception('SpotMeter: failed to push status block')


def _live_mode_tick():
    """Periodic re-poster for live mode. Reschedules itself while
    _LIVE_MODE_ENABLED is True; otherwise terminates the loop.
    """
    global _LIVE_MODE_CALLBACK_ID
    _LIVE_MODE_CALLBACK_ID = None
    if not _LIVE_MODE_ENABLED:
        return
    plugin = _get_picker_plugin()
    if plugin is not None:
        _post_status_block(plugin)
    # Reschedule even if plugin was None - we'll retry next tick.
    try:
        import BigWorld
        interval = float(_CFG.get('liveModeIntervalSec', 3.0))
        if interval < 0.5:
            interval = 0.5  # safety floor
        _LIVE_MODE_CALLBACK_ID = BigWorld.callback(interval, _live_mode_tick)
    except Exception:
        _logger.exception('SpotMeter: failed to reschedule live-mode tick')


def _force_panel_refresh(affected_vids=None):
    # No-op. The enemy-name marker (a PlayerFullNameFormatter hook) was removed
    # in v6.0.1 - it never reliably rendered and is redundant now that the
    # battle panel shows the picked / auto-picked target. Visual feedback comes
    # from the minimap spot circle + the panel. Kept as a stub so the existing
    # call sites stay valid.
    return


# ----- Auto-hide the panel when a WG window opens (research/depot/dialogs in
# the garage, TAB-style overlays in battle) and restore it when the last one
# closes. Hooks the modern wulf windows_system (windowsManager.onWindowStatus
# Changed) - the system these windows ACTUALLY use - and re-evaluates the open
# window list on every status change (stateless). Pure subscription + our
# existing hide/show, all try/except, NO view-layer changes, so it can never
# hang load like the SUB_VIEW experiment did. -----
SPOTMETER_GF_ALIAS = 'SpotMeterGuiFlashView'  # our own GUIFlash view - never hide on it
_PANEL_AUTO_HIDDEN = False   # True when WE hid the panel because a window is open
_PANEL_USER_HIDDEN = False   # True when the USER explicitly hid the panel via the
                             # toggle key (PgDn). Blocks the auto-show paths
                             # (invalidateMarkup / space-entered) from reviving it.
                             # PERSISTS across battles + garage/battle transitions;
                             # cleared ONLY when the user presses PgDn again to show
                             # (initialised False at game launch -> panel shown).
_WW_ROUTE_BUSY = False        # True when the lobby route is a hangar loadout sub-state
_WW_HELD_HIDE_KEYS = set()    # battle overlay keys (TAB/N) currently held down
_WW_HIDE_KEY_IDS = None       # cached resolved key codes for battleHidePanelKeys
_WW_KEY_POLL_CB = None        # BigWorld.callback handle for the key-release poll
# Persistent base views that must NOT trigger a hide; everything else the
# player opens (techtree/depot/dialogs/menu/stronghold/...) does.
_WW_IGNORE_ALIASES = frozenset((
    SPOTMETER_GF_ALIAS,
    'hangar', 'HangarWindow', 'RandomHangar', 'MainWindow',
    'lobby', 'login', 'lobbyVehicleMarkerView', 'waiting',
    'crosshair', 'battle',
))


def _ww_window_alias(window):
    """View alias parsed from the window repr (it reliably contains 'alias=X'
    for SFWindows - direct attribute access returns None here); falls back to
    the window class name (e.g. HangarWindow / TechTreeWindow)."""
    try:
        s = str(window)
        i = s.find('alias=')
        if i >= 0:
            j = i + 6
            k = j
            while k < len(s) and s[k] not in ', ]':
                k += 1
            a = s[j:k].strip()
            if a:
                return a
    except Exception:
        pass
    return type(window).__name__


def _ww_window_layer(window):
    """WindowLayer int parsed from the window repr ('layer=N'); None if absent.
    Distinguishes blocking screens (content tabs = layer 5, dialogs / menus =
    layer >= 10) from coexisting overlays (layer 7: other mods' GUIFlash views,
    notifications, chat, mod-list buttons) that must NOT hide our panel."""
    try:
        s = str(window)
        i = s.find('layer=')
        if i >= 0:
            j = i + 6
            k = j
            while k < len(s) and s[k].isdigit():
                k += 1
            if k > j:
                return int(s[j:k])
    except Exception:
        pass
    return None


def _ww_is_real_window(window):
    """True if `window` is a player-opened SCREEN that should hide the panel -
    a content tab (techtree / depot / profile / loadout = layer 5) or a modal
    dialog / menu (layer >= 10). NOT the hangar, not us, not a tooltip, and
    crucially NOT a coexisting layer-7 overlay (other mods' GUIFlash views,
    notifications, chat, mod-list buttons) - those share the screen with the
    hangar and must leave our panel visible.

    Pre-2.3 this was a pure alias blacklist, which wrongly counted every other
    mod's window as blocking - in a modpack (XVM/champi/poliroid/...) that made
    the panel thrash and eventually stick hidden. The layer gate fixes that."""
    try:
        cls = type(window).__name__
        cls_l = cls.lower()
        if 'tooltip' in cls_l or 'contextmenu' in cls_l:
            return False
        alias = _ww_window_alias(window)
        if alias in _WW_IGNORE_ALIASES or cls in _WW_IGNORE_ALIASES:
            return False
        layer = _ww_window_layer(window)
        if layer is None:
            return False  # unknown layer -> don't hide (avoid false positives)
        return layer == 5 or layer >= 10
    except Exception:
        return False


def _ww_windows_manager():
    """The wulf windows manager - lives on the IGuiLoader dependency (NOT on
    the app, which only exposes the legacy containerManager)."""
    try:
        from helpers import dependency
        from skeletons.gui.impl import IGuiLoader
        loader = dependency.instance(IGuiLoader)
        return getattr(loader, 'windowsManager', None) if loader is not None else None
    except Exception:
        return None


def _ww_lobby_sm():
    """The lobby state machine (for hangar sub-state routes like loadout).
    getLobbyStateMachine lives in gui.Scaleform.lobby_entry."""
    try:
        from gui.Scaleform.lobby_entry import getLobbyStateMachine
        return getLobbyStateMachine()
    except Exception:
        return None


def _ww_reeval():
    """Lobby: hide for a real window or a hangar loadout route. Battle: hide
    ONLY while a configured overlay key (TAB/N) is held - battle HUD windows
    (strongholdBattlePage, etc.) are always present and must NOT hide the
    panel, so we ignore windows entirely in battle."""
    try:
        if _is_in_garage():
            wm = _ww_windows_manager()
            real = []
            if wm is not None:
                try:
                    real = wm.findWindows(_ww_is_real_window) or []
                except Exception:
                    real = []
            hide = bool(real) or _WW_ROUTE_BUSY
        else:
            hide = bool(_WW_HELD_HIDE_KEYS)
        if hide:
            _ww_hide_panel()
        else:
            _ww_show_panel()
    except Exception:
        _logger.exception('SpotMeter: window-watch reeval failed')


def _ww_on_window_status(uniqueID, newStatus):
    # Skip tooltip/context-menu churn - they fire constantly on hover and never
    # hide the panel, so re-evaluating the whole window list each time is waste.
    try:
        wm = _ww_windows_manager()
        w = wm.getWindow(uniqueID) if wm is not None else None
        if w is not None:
            cls = type(w).__name__.lower()
            if 'tooltip' in cls or 'contextmenu' in cls:
                return
    except Exception:
        pass
    _ww_reeval()


def _ww_on_route_changed(*args):
    """Lobby visible-route changed. Loadout sub-states (equipment/shells/
    consumables) render inside the hangar WITHOUT opening a window, so the
    windowsManager hook can't see them - catch them by route here. Other tabs
    already open windows and are handled by windowsManager."""
    global _WW_ROUTE_BUSY
    try:
        sm = _ww_lobby_sm()
        state = getattr(sm, 'visibleState', None) if sm is not None else None
        _WW_ROUTE_BUSY = ('loadout' in str(state).lower()) if state is not None else False
    except Exception:
        _WW_ROUTE_BUSY = False
    _ww_reeval()


def _ww_hide_key_ids():
    """Resolved key codes for battleHidePanelKeys (TAB / N by default)."""
    global _WW_HIDE_KEY_IDS
    if _WW_HIDE_KEY_IDS is None:
        ids = set()
        try:
            import Keys
            for name in (_CFG.get('battleHidePanelKeys') or ()):
                kid = getattr(Keys, name, None)
                if kid is not None:
                    ids.add(kid)
        except Exception:
            pass
        _WW_HIDE_KEY_IDS = ids
    return _WW_HIDE_KEY_IDS


def _ww_battle_key(key, is_down):
    """While a configured battle-overlay key (TAB / N) is held, hide the panel;
    show it on release. Battle only - in the garage these keys do nothing here
    (the window/route watchers cover the garage)."""
    try:
        if not _CFG.get('autoHidePanelOnWindow', True):
            return
        if _is_in_garage():
            if _WW_HELD_HIDE_KEYS:
                _WW_HELD_HIDE_KEYS.clear()
            return
        if key not in _ww_hide_key_ids():
            return
        if is_down:
            _WW_HELD_HIDE_KEYS.add(key)
            _ww_reeval()
            _ww_start_key_poll()  # TAB's key-UP isn't delivered to us - poll the real state
        else:
            _WW_HELD_HIDE_KEYS.discard(key)
            _ww_reeval()
    except Exception:
        _logger.exception('SpotMeter: battle key-hide failed')


def _ww_start_key_poll():
    """Start (once) a light poll that watches the real key state, since some
    games consume the key-UP for TAB so we never get a release event."""
    global _WW_KEY_POLL_CB
    if _WW_KEY_POLL_CB is not None:
        return
    try:
        _WW_KEY_POLL_CB = BigWorld.callback(0.1, _ww_key_poll_tick)
    except Exception:
        _WW_KEY_POLL_CB = None


def _ww_key_poll_tick():
    global _WW_KEY_POLL_CB
    _WW_KEY_POLL_CB = None
    try:
        still = set()
        for kid in list(_WW_HELD_HIDE_KEYS):
            try:
                if BigWorld.isKeyDown(kid):
                    still.add(kid)
            except Exception:
                pass
        _WW_HELD_HIDE_KEYS.clear()
        _WW_HELD_HIDE_KEYS.update(still)
        if _WW_HELD_HIDE_KEYS:
            _WW_KEY_POLL_CB = BigWorld.callback(0.1, _ww_key_poll_tick)
        else:
            _ww_reeval()  # all release keys up -> restore the panel
    except Exception:
        _logger.exception('SpotMeter: key-poll failed')


def _ww_on_space_entered(spaceID):
    """Reset state for the new space and (re)subscribe to its windowsManager -
    lobby and battle each have their own."""
    global _PANEL_AUTO_HIDDEN, _WW_ROUTE_BUSY
    _PANEL_AUTO_HIDDEN = False
    _WW_ROUTE_BUSY = False
    if not _CFG.get('autoHidePanelOnWindow', True):
        return
    try:
        wm = _ww_windows_manager()
        if wm is not None:
            try:
                wm.onWindowStatusChanged -= _ww_on_window_status
            except Exception:
                pass
            wm.onWindowStatusChanged += _ww_on_window_status
    except Exception:
        _logger.exception('SpotMeter: window-watch subscribe failed')
    # Lobby state machine - catches hangar loadout sub-states (equipment / ammo
    # / consumables) which switch route WITHOUT opening a window.
    try:
        sm = _ww_lobby_sm()
        if sm is not None and hasattr(sm, 'onVisibleRouteChanged'):
            try:
                sm.onVisibleRouteChanged -= _ww_on_route_changed
            except Exception:
                pass
            sm.onVisibleRouteChanged += _ww_on_route_changed
    except Exception:
        _logger.exception('SpotMeter: route-watch subscribe failed')


def _ww_hide_panel():
    global _PANEL_AUTO_HIDDEN
    if _is_in_garage():
        if _GARAGE_PANEL_ACTIVE:
            _hide_garage_panel()
            _PANEL_AUTO_HIDDEN = True
    elif _BATTLE_PANEL_ACTIVE:
        _hide_battle_view()
        _PANEL_AUTO_HIDDEN = True


def _ww_show_panel():
    # Idempotent reconcile: drive toward "shown" whenever nothing blocks and the
    # user hasn't hidden it with PgDn - regardless of how the panel got hidden.
    # (The old `if not _PANEL_AUTO_HIDDEN: return` guard could leave the panel
    # stuck hidden if anything other than the window-watch had cleared it.)
    global _PANEL_AUTO_HIDDEN
    _PANEL_AUTO_HIDDEN = False
    if _PANEL_USER_HIDDEN:
        return  # user hid it with PgDn - leave hidden until they toggle back
    try:
        if _is_in_garage():
            if not _GARAGE_PANEL_ACTIVE:
                _show_garage_panel(force=True)
        elif not _BATTLE_PANEL_ACTIVE:
            _show_battle_view(force=True)
    except Exception:
        _logger.exception('SpotMeter: window-watch show failed')


def _patch_hangar_lifecycle():
    """Subscribe to the appLoader's GUI-space-change events so we know when
    the player enters / leaves the garage and when they enter / leave a
    battle. This is the proven WoT 2.x pattern (reverse-engineered from
    GUIFlash / Spoter MoE) - patching RandomHangar._onShown also worked
    as a signal but the SAME hook here also covers battle entry, so we
    drop the hangar-specific patch and use a single lifecycle source.
    """
    global _HANGAR_PATCHED
    if _HANGAR_PATCHED:
        return
    try:
        from gui.shared.personality import ServicesLocator
        from skeletons.gui.app_loader import GuiGlobalSpaceID as SPACE_ID
    except ImportError:
        _logger.warning('SpotMeter: ServicesLocator / GuiGlobalSpaceID unavailable, GUI overlay disabled')
        return

    appLoader = getattr(ServicesLocator, 'appLoader', None)
    if appLoader is None:
        _logger.warning('SpotMeter: ServicesLocator.appLoader is None, GUI overlay disabled')
        return

    def _onSpaceEntered(spaceID):
        try:
            _logger.warning('SpotMeter: onGUISpaceEntered spaceID=%s', spaceID)
            if spaceID == SPACE_ID.LOBBY:
                _on_hangar_populate(None)
                _show_garage_panel()
            elif spaceID == SPACE_ID.BATTLE:
                _show_battle_view()
            _ww_on_space_entered(spaceID)
        except Exception:
            _logger.exception('SpotMeter: onGUISpaceEntered handler failed')

    def _onSpaceLeft(spaceID):
        try:
            _logger.warning('SpotMeter: onGUISpaceLeft spaceID=%s', spaceID)
            if spaceID == SPACE_ID.LOBBY:
                _hide_garage_panel()
                _on_hangar_dispose(None)
            elif spaceID == SPACE_ID.BATTLE:
                _hide_battle_view()
        except Exception:
            _logger.exception('SpotMeter: onGUISpaceLeft handler failed')

    try:
        appLoader.onGUISpaceEntered += _onSpaceEntered
        appLoader.onGUISpaceLeft    += _onSpaceLeft
    except Exception:
        _logger.exception('SpotMeter: failed to subscribe to appLoader space events')
        return

    _HANGAR_PATCHED = True
    _logger.warning('SpotMeter: subscribed to appLoader.onGUISpaceEntered/Left (lobby+battle)')


def _on_hangar_populate(hangar_view):
    """Called once on every garage entry. v6.0.0 MVP1: garage UI is
    deferred (the legacy floating-button Scaleform view doesn't satisfy
    WG's IView contract on WoT 2.x). The only thing the hangar hook
    currently does is mark the lifecycle in the log so we can verify
    the appLoader event subscription is alive. MVP2 brings the garage
    UI back via the GUIFlash-based pattern proven by the battle panel.
    """
    if _CFG.get('menuButtonEnabled', False):
        _logger.warning('SpotMeter: hangar populated - menuButtonEnabled=True ignored, garage UI is deferred to MVP2')
    else:
        _logger.info('SpotMeter: hangar populated (no UI - menuButtonEnabled=False)')


def _on_hangar_dispose(hangar_view):
    _logger.info('SpotMeter: hangar disposed')


# ============================================================================
# v6.0 menu button - floating Scaleform view loaded over the hangar.
#
# Architecture: we register a custom View subclass with WG's framework
# (g_entitiesFactories.addSettings) bound to spotmeter_button.swf. When the
# hangar populates, we fire a LoadViewEvent to load our view; the framework
# instantiates our Python class, calls _populate, and binds the AS3 SWF as
# self.flashObject.
#
# Python <-> AS3 communication:
#   - Python -> AS3:  self.flashObject.as_<methodName>(args)  (synchronous)
#   - AS3 -> Python:  POLLING via BigWorld.callback at 5 Hz. ExternalInterface
#                     is not bridged in Scaleform GFx, and generating a DAAPI
#                     Meta class would require build-time tooling we don't
#                     have. Polling is reliable, adds 200 ms click latency
#                     which is imperceptible for an "open settings" button.
# ============================================================================

SPOTMETER_BUTTON_ALIAS   = 'SpotMeterButtonView'
SPOTMETER_BUTTON_SWF_URL = 'spotmeter_button.swf'

_button_view_class       = None   # cached after first build (subclass of View)
_button_view_registered  = False  # ViewSettings added to g_entitiesFactories
_active_button_view      = None   # the currently populated view instance


def _build_button_view_class():
    """Define and return the View subclass that wraps spotmeter_button.swf.

    Imports the View base class lazily - if it ever moves between WoT
    versions, the failure is contained to "menu button disabled" rather
    than crashing module load."""
    global _button_view_class
    if _button_view_class is not None:
        return _button_view_class
    try:
        from gui.Scaleform.framework.entities.View import View as _BaseView
    except ImportError:
        _logger.warning('SpotMeter: gui.Scaleform.framework.entities.View unavailable; menu disabled')
        return None

    class SpotMeterButtonView(_BaseView):

        def __init__(self, *args, **kwargs):
            super(SpotMeterButtonView, self).__init__(*args, **kwargs)
            self._sm_poll_cb_id = None
            self._sm_initialized = False
            _logger.warning('SpotMeter: SpotMeterButtonView.__init__ called')

        def _populate(self):
            global _active_button_view
            _logger.warning('SpotMeter: SpotMeterButtonView._populate entering')
            super(SpotMeterButtonView, self)._populate()
            _active_button_view = self
            try:
                w = float(_CFG.get('menuButtonW', 90))
                h = float(_CFG.get('menuButtonH', 28))
                x = float(_CFG.get('menuButtonX', 720))
                y = float(_CFG.get('menuButtonY', 850))
                # AS3 clamps to stage bounds inside as_setPosition, so we
                # don't need to know screen dimensions here.
                fo = self.flashObject
                _logger.warning('SpotMeter: button flashObject=%r', fo)
                fo.as_setSize(w, h)
                fo.as_setPosition(x, y)
                fo.as_setLabel('SpotMeter')
                self._sm_initialized = True
                _logger.warning('SpotMeter: button view initialised at (%s,%s) size (%s,%s)', x, y, w, h)
            except Exception:
                _logger.exception('SpotMeter: failed to init button SWF')
            self._sm_poll_cb_id = BigWorld.callback(0.2, self._sm_poll)

        def _destroy(self):
            global _active_button_view
            if self._sm_poll_cb_id is not None:
                try:
                    BigWorld.cancelCallback(self._sm_poll_cb_id)
                except Exception:
                    pass
                self._sm_poll_cb_id = None
            if _active_button_view is self:
                _active_button_view = None
            super(SpotMeterButtonView, self)._destroy()

        def _sm_poll(self):
            """5 Hz tick: read consume-on-read flags from AS3 and dispatch
            to Python handlers. Reschedules itself indefinitely until the
            view is destroyed."""
            self._sm_poll_cb_id = None
            try:
                fo = self.flashObject
                if fo is not None and self._sm_initialized:
                    if fo.as_consumeClick():
                        _on_menu_button_click()
                    if fo.as_consumeDragEnd():
                        nx = fo.as_getX()
                        ny = fo.as_getY()
                        _on_menu_button_drag_end(nx, ny)
            except Exception:
                _logger.exception('SpotMeter: button poll failed')
            # Reschedule unless we've been torn down between ticks
            if _active_button_view is self:
                self._sm_poll_cb_id = BigWorld.callback(0.2, self._sm_poll)

    _button_view_class = SpotMeterButtonView
    return _button_view_class


def _register_button_view():
    """One-time view registration. Idempotent."""
    global _button_view_registered
    if _button_view_registered:
        _logger.warning('SpotMeter: button view already registered')
        return True
    cls = _build_button_view_class()
    if cls is None:
        _logger.warning('SpotMeter: button view class build failed')
        return False
    try:
        from gui.Scaleform.framework import g_entitiesFactories, ViewSettings, ScopeTemplates
        from frameworks.wulf import WindowLayer
    except ImportError:
        _logger.warning('SpotMeter: framework not importable, menu button disabled')
        return False
    try:
        settings = ViewSettings(
            alias=SPOTMETER_BUTTON_ALIAS,
            clazz=cls,
            url=SPOTMETER_BUTTON_SWF_URL,
            layer=WindowLayer.WINDOW,
            scope=ScopeTemplates.GLOBAL_SCOPE,
            canDrag=False,
            canClose=False,
            isModal=False,
            isCentered=False,
        )
        g_entitiesFactories.addSettings(settings)
        _button_view_registered = True
        _logger.warning('SpotMeter: button view ViewSettings ADDED to g_entitiesFactories (alias=%s, url=%s)',
                        SPOTMETER_BUTTON_ALIAS, SPOTMETER_BUTTON_SWF_URL)
        return True
    except Exception:
        _logger.exception('SpotMeter: addSettings failed for button view')
        return False


def _show_button_view():
    """Load the floating SpotMeter button view over the current Scaleform
    app (lobby). WoT 2.x pattern (reverse-engineered from GUIFlash /
    Spoter MoE):

      app = ServicesLocator.appLoader.getApp()
      app.loadView(SFViewLoadParams(alias, parent=getParentWindow()))

    The legacy `g_eventBus.handleEvent(LoadViewEvent(...))` path used by
    WG's own internal code is silently dropped for third-party views in
    2.x - direct loadView is what actually reaches the LoaderManager.
    """
    _logger.warning('SpotMeter: _show_button_view called')
    if not _register_button_view():
        _logger.warning('SpotMeter: _show_button_view aborted - registration failed')
        return
    if _active_button_view is not None:
        _logger.warning('SpotMeter: _show_button_view - view already up, skipping')
        return
    try:
        from gui.shared.personality import ServicesLocator
        from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
    except ImportError:
        _logger.warning('SpotMeter: ServicesLocator / SFViewLoadParams unavailable')
        return
    try:
        app = ServicesLocator.appLoader.getApp()
    except Exception:
        _logger.exception('SpotMeter: ServicesLocator.appLoader.getApp() failed')
        return
    if app is None:
        _logger.warning('SpotMeter: no active app, button load skipped')
        return
    parent = _get_parent_window()
    _logger.warning('SpotMeter: calling app.loadView (button) parent=%r app=%r', parent, app)
    try:
        app.loadView(SFViewLoadParams(SPOTMETER_BUTTON_ALIAS, parent=parent))
        _logger.warning('SpotMeter: app.loadView returned for button')
    except Exception:
        _logger.exception('SpotMeter: app.loadView failed for button')


def _get_parent_window():
    """Return the active main window via the Wulf IGuiLoader (the path
    that actually works in WoT 2.x). The legacy AS3_AppFactory().getMainWindow()
    returns the MainWindow object too, but the value isn't accepted by
    app.loadView - the Spoter/GUIFlash pattern resolves it through the
    DI-injected IGuiLoader skeleton instead.

    Returns None if the windows manager isn't ready yet (e.g. early init).
    """
    try:
        from skeletons.gui.impl import IGuiLoader
        from helpers import dependency
    except ImportError:
        _logger.warning('SpotMeter: IGuiLoader / dependency unavailable')
        return None
    try:
        uiLoader = dependency.instance(IGuiLoader)
    except Exception:
        _logger.exception('SpotMeter: failed to obtain IGuiLoader instance')
        return None
    if uiLoader is None:
        return None
    wm = getattr(uiLoader, 'windowsManager', None)
    if wm is None:
        return None
    try:
        return wm.getMainWindow()
    except Exception:
        _logger.exception('SpotMeter: windowsManager.getMainWindow failed')
        return None


# Back-compat aliases for any code path that still references the old names.
def _get_lobby_main_window():
    return _get_parent_window()

def _get_battle_main_window():
    return _get_parent_window()


def _install_loader_diagnostics():
    """Subscribe to LoaderManager events so we can see in python.log
    whether the framework even tries to load our view after LoadViewEvent
    is dispatched. Without this, a silent drop is indistinguishable from
    a successful-but-invisible load.

    Idempotent via the module-level flag.
    """
    global _LOADER_DIAG_INSTALLED
    if _LOADER_DIAG_INSTALLED:
        return
    try:
        from gui.app_loader import g_appLoader
    except ImportError:
        return
    try:
        app = g_appLoader.getApp()
    except Exception:
        app = None
    if app is None:
        _logger.warning('SpotMeter: loader-diag: no app yet, will retry later')
        BigWorld.callback(0.5, _install_loader_diagnostics)
        return
    try:
        loader = getattr(app, 'loaderManager', None)
        if loader is None:
            _logger.warning('SpotMeter: loader-diag: app has no loaderManager')
            return
        def _log_init(*a, **kw):
            _logger.warning('SpotMeter: LoaderManager.onViewLoadInit args=%r kw=%r', a, kw)
        def _log_loaded(*a, **kw):
            _logger.warning('SpotMeter: LoaderManager.onViewLoaded args=%r kw=%r', a, kw)
        def _log_err(*a, **kw):
            _logger.warning('SpotMeter: LoaderManager.onViewLoadError args=%r kw=%r', a, kw)
        def _log_cancel(*a, **kw):
            _logger.warning('SpotMeter: LoaderManager.onViewLoadCanceled args=%r kw=%r', a, kw)
        loader.onViewLoadInit     += _log_init
        loader.onViewLoaded       += _log_loaded
        loader.onViewLoadError    += _log_err
        loader.onViewLoadCanceled += _log_cancel
        _LOADER_DIAG_INSTALLED = True
        _logger.warning('SpotMeter: loader-diag subscribed to LoaderManager events')
    except Exception:
        _logger.exception('SpotMeter: loader-diag install failed')


def _hide_button_view():
    """Explicit destroy as a safety net. The framework usually tears the view
    down when its scope ends (hangar dispose), but if the scope outlives the
    hangar for some reason we don't want a stale button floating around."""
    view = _active_button_view
    if view is None:
        return
    try:
        view.destroy()
    except Exception:
        _logger.exception('SpotMeter: explicit button view destroy failed')


def _on_menu_button_click():
    """User clicked the floating SpotMeter button. Open the settings dialog
    (Phase 3.4: empty frame; Phase 4: widgets). Idempotent - if the dialog
    is already up, this is a no-op."""
    _logger.warning('SpotMeter: menu button clicked')
    try:
        _show_menu_view()
    except Exception:
        _logger.exception('SpotMeter: _show_menu_view failed')


def _on_menu_button_drag_end(new_x, new_y):
    """Persist new button position to JSON. _write_config is atomic
    (write to .tmp + rename) so a crash mid-write won't corrupt the file."""
    try:
        cx = int(round(float(new_x)))
        cy = int(round(float(new_y)))
    except (TypeError, ValueError):
        return
    _CFG['menuButtonX'] = cx
    _CFG['menuButtonY'] = cy
    _logger.info('SpotMeter: button position saved -> (%d, %d)', cx, cy)
    try:
        _write_config()
    except Exception:
        _logger.exception('SpotMeter: failed to persist button position')


# ============================================================================
# v6.0 menu dialog - opened by clicking the floating SpotMeter button.
#
# Phase 3.4 ships an empty modal-style frame (dim background + centered panel
# + title + close button + ESC handling). Phase 4 fills the content area with
# tabs and widgets. Same polling architecture as the button (5 Hz poll on
# self.flashObject.as_consumeClose).
# ============================================================================

SPOTMETER_MENU_ALIAS   = 'SpotMeterMenuView'
SPOTMETER_MENU_SWF_URL = 'spotmeter_menu.swf'

_menu_view_class       = None
_menu_view_registered  = False
_active_menu_view      = None


def _build_menu_view_class():
    global _menu_view_class
    if _menu_view_class is not None:
        return _menu_view_class
    try:
        from gui.Scaleform.framework.entities.View import View as _BaseView
    except ImportError:
        _logger.warning('SpotMeter: View base class unavailable; menu dialog disabled')
        return None

    class SpotMeterMenuView(_BaseView):

        def __init__(self, *args, **kwargs):
            super(SpotMeterMenuView, self).__init__(*args, **kwargs)
            self._sm_poll_cb_id = None
            self._sm_initialized = False

        def _populate(self):
            global _active_menu_view
            super(SpotMeterMenuView, self)._populate()
            _active_menu_view = self
            try:
                # The SWF reads stage size in as_populate; we pass it explicitly
                # too in case the stage isn't attached at __init__ time. Defaults
                # are conservative; AS3 re-layouts on as_setStageSize anyway.
                self.flashObject.as_setStageSize(1920.0, 1080.0)
                self.flashObject.as_setTitle('SpotMeter Settings')
                self._sm_initialized = True
            except Exception:
                _logger.exception('SpotMeter: failed to init menu SWF')
            self._sm_poll_cb_id = BigWorld.callback(0.2, self._sm_poll)

        def _destroy(self):
            global _active_menu_view
            if self._sm_poll_cb_id is not None:
                try:
                    BigWorld.cancelCallback(self._sm_poll_cb_id)
                except Exception:
                    pass
                self._sm_poll_cb_id = None
            if _active_menu_view is self:
                _active_menu_view = None
            super(SpotMeterMenuView, self)._destroy()

        def _sm_poll(self):
            self._sm_poll_cb_id = None
            try:
                fo = self.flashObject
                if fo is not None and self._sm_initialized:
                    if fo.as_consumeClose():
                        _on_menu_close()
                        return  # don't reschedule - we're closing
            except Exception:
                _logger.exception('SpotMeter: menu poll failed')
            if _active_menu_view is self:
                self._sm_poll_cb_id = BigWorld.callback(0.2, self._sm_poll)

    _menu_view_class = SpotMeterMenuView
    return _menu_view_class


def _register_menu_view():
    global _menu_view_registered
    if _menu_view_registered:
        return True
    cls = _build_menu_view_class()
    if cls is None:
        return False
    try:
        from gui.Scaleform.framework import g_entitiesFactories, ViewSettings, ScopeTemplates
        from frameworks.wulf import WindowLayer
    except ImportError:
        _logger.warning('SpotMeter: framework not importable, menu dialog disabled')
        return False
    try:
        settings = ViewSettings(
            alias=SPOTMETER_MENU_ALIAS,
            clazz=cls,
            url=SPOTMETER_MENU_SWF_URL,
            # TOP_WINDOW so the menu draws above the floating button (WINDOW layer).
            # If TOP_WINDOW isn't right, try WINDOW or OVERLAY; AS3 dim layer
            # already gives modal feel regardless of z-order.
            layer=WindowLayer.TOP_WINDOW,
            scope=ScopeTemplates.GLOBAL_SCOPE,
            canDrag=False,
            canClose=True,
            isModal=True,
            isCentered=True,
        )
        g_entitiesFactories.addSettings(settings)
        _menu_view_registered = True
        _logger.warning('SpotMeter: menu view registered (alias=%s, url=%s)',
                        SPOTMETER_MENU_ALIAS, SPOTMETER_MENU_SWF_URL)
        return True
    except Exception:
        _logger.exception('SpotMeter: addSettings failed for menu view')
        return False


def _show_menu_view():
    if _active_menu_view is not None:
        return  # already open
    if not _register_menu_view():
        return
    try:
        from gui.shared.personality import ServicesLocator
        from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
    except ImportError:
        _logger.warning('SpotMeter: ServicesLocator / SFViewLoadParams unavailable (menu)')
        return
    try:
        app = ServicesLocator.appLoader.getApp()
    except Exception:
        _logger.exception('SpotMeter: getApp failed for menu')
        return
    if app is None:
        _logger.warning('SpotMeter: no active app, menu load skipped')
        return
    parent = _get_parent_window()
    try:
        app.loadView(SFViewLoadParams(SPOTMETER_MENU_ALIAS, parent=parent))
        _logger.warning('SpotMeter: app.loadView returned for menu parent=%r', parent)
    except Exception:
        _logger.exception('SpotMeter: app.loadView failed (menu)')


def _hide_menu_view():
    view = _active_menu_view
    if view is None:
        return
    try:
        view.destroy()
    except Exception:
        _logger.exception('SpotMeter: explicit menu view destroy failed')


def _on_menu_close():
    """User asked to close the dialog (X / Close button / dim background / ESC).
    Tear down the view; Phase 4 will also persist any pending widget edits here."""
    _logger.info('SpotMeter: menu close requested')
    _hide_menu_view()


# ============================================================================
# v6.0 in-battle picker panel - always-visible floating Scaleform view loaded
# over the battle HUD. Replaces the chat-based status block as the primary
# picker interface: enemy list (click row -> pick), VR readout, toggle
# checkboxes, auto-pick checkbox.
#
# Lifecycle: piggybacks on the existing PersonalEntriesPlugin patches.
# patched_invalidateMarkup loads the panel; patched_hideMarkup / patched_stop
# tear it down. This is more reliable than hooking BattlePage directly
# because the minimap plugin is the canonical "battle UI is alive" signal
# that's already proven across siege / postmortem / scenario transitions.
#
# Python <-> AS3 push/pull:
#   - Each 5 Hz poll tick:
#       a) Read consume-on-read flags (vid click, toggle click, autopick click,
#          drag end) and dispatch to the existing picker functions.
#       b) Push current state (enemy list, selected, toggles, autopick) so the
#          panel always reflects keyboard-driven changes (Numpad hotkeys still
#          work alongside mouse clicks).
# ============================================================================

SPOTMETER_BATTLE_ALIAS   = 'SpotMeterBattleView'
SPOTMETER_BATTLE_SWF_URL = 'spotmeter_battle.swf'

_battle_view_class       = None
_battle_view_registered  = False
_active_battle_view      = None


def _build_battle_view_class():
    global _battle_view_class
    if _battle_view_class is not None:
        return _battle_view_class
    try:
        from gui.Scaleform.framework.entities.View import View as _BaseView
    except ImportError:
        _logger.warning('SpotMeter: View base class unavailable; battle panel disabled')
        return None

    class SpotMeterBattleView(_BaseView):

        def __init__(self, *args, **kwargs):
            super(SpotMeterBattleView, self).__init__(*args, **kwargs)
            self._sm_poll_cb_id = None
            self._sm_initialized = False
            # Cache the last pushed payload so we don't burn AS3 calls on
            # unchanged state. Each entry is the serializable shape passed
            # into as_set*; we compare with the new shape before pushing.
            self._sm_last_enemies = None    # (vids_tuple, labels_tuple, classes_tuple)
            self._sm_last_selected = None   # (vid, name, vr_int)
            self._sm_last_toggles = None    # (r, b, rs, d, fu)
            self._sm_last_autopick = None   # bool

        def _populate(self):
            global _active_battle_view
            super(SpotMeterBattleView, self)._populate()
            _active_battle_view = self
            try:
                w = float(_CFG.get('battlePanelW', 280))
                h = float(_CFG.get('battlePanelH', 360))
                x = float(_CFG.get('battlePanelX', 10))
                y = float(_CFG.get('battlePanelY', 400))
                self.flashObject.as_setSize(w, h)
                self.flashObject.as_setPosition(x, y)
                self._sm_initialized = True
            except Exception:
                _logger.exception('SpotMeter: failed to init battle panel SWF')
            self._sm_poll_cb_id = BigWorld.callback(0.2, self._sm_poll)

        def _destroy(self):
            global _active_battle_view
            if self._sm_poll_cb_id is not None:
                try:
                    BigWorld.cancelCallback(self._sm_poll_cb_id)
                except Exception:
                    pass
                self._sm_poll_cb_id = None
            if _active_battle_view is self:
                _active_battle_view = None
            super(SpotMeterBattleView, self)._destroy()

        def _sm_poll(self):
            self._sm_poll_cb_id = None
            try:
                fo = self.flashObject
                if fo is not None and self._sm_initialized:
                    self._sm_handle_inputs(fo)
                    self._sm_push_state(fo)
            except Exception:
                _logger.exception('SpotMeter: battle panel poll failed')
            if _active_battle_view is self:
                self._sm_poll_cb_id = BigWorld.callback(0.2, self._sm_poll)

        # ---- input dispatch ----

        def _sm_handle_inputs(self, fo):
            try:
                vid_raw = fo.as_consumeSelectedVid()
                vid = int(vid_raw) if vid_raw else 0
                if vid > 0:
                    _battle_panel_on_pick(vid)
            except Exception:
                _logger.exception('SpotMeter: battle panel consumeSelectedVid failed')
            try:
                tname = fo.as_consumeToggleName()
                if tname:
                    _battle_panel_on_toggle(str(tname))
            except Exception:
                _logger.exception('SpotMeter: battle panel consumeToggleName failed')
            try:
                if fo.as_consumeAutoPickClick():
                    _battle_panel_on_auto_click()
            except Exception:
                _logger.exception('SpotMeter: battle panel consumeAutoPickClick failed')
            try:
                if fo.as_consumeDragEnd():
                    nx = fo.as_getX()
                    ny = fo.as_getY()
                    _battle_panel_on_drag_end(nx, ny)
            except Exception:
                _logger.exception('SpotMeter: battle panel consumeDragEnd failed')

        # ---- state push (diff to avoid churn) ----

        def _sm_push_state(self, fo):
            plugin = _get_picker_plugin()
            # Enemies: tuples of (vids, labels, class_codes). Skip the AS3
            # call if the shape hasn't changed since last push.
            vids, labels, class_codes = _battle_panel_enemy_payload(plugin)
            enemies_key = (tuple(vids), tuple(labels), tuple(class_codes))
            if enemies_key != self._sm_last_enemies:
                try:
                    fo.as_setEnemies(vids, labels, class_codes)
                except Exception:
                    _logger.exception('SpotMeter: as_setEnemies failed')
                self._sm_last_enemies = enemies_key

            # Selected (current pick) + computed VR
            sel_vid, sel_name, sel_vr = _battle_panel_selected_payload(plugin)
            sel_key = (sel_vid, sel_name, int(sel_vr) if sel_vr else 0)
            if sel_key != self._sm_last_selected:
                try:
                    fo.as_setSelected(sel_vid, sel_name, sel_vr)
                except Exception:
                    _logger.exception('SpotMeter: as_setSelected failed')
                self._sm_last_selected = sel_key

            # Toggle states
            tog_key = (
                bool(_PICKER_TOGGLES.get('rations', True)),
                bool(_PICKER_TOGGLES.get('BIA', True)),
                bool(_PICKER_TOGGLES.get('reconSitAware', True)),
                bool(_PICKER_TOGGLES.get('directives', False)),
                bool(_PICKER_TOGGLES.get('fieldUpgrades', False)),
            )
            if tog_key != self._sm_last_toggles:
                try:
                    fo.as_setToggles(*tog_key)
                except Exception:
                    _logger.exception('SpotMeter: as_setToggles failed')
                self._sm_last_toggles = tog_key

            # Auto-pick state
            ap = bool(_CFG.get('autoPickEnabled', False))
            if ap != self._sm_last_autopick:
                try:
                    fo.as_setAutoPick(ap)
                except Exception:
                    _logger.exception('SpotMeter: as_setAutoPick failed')
                self._sm_last_autopick = ap

    _battle_view_class = SpotMeterBattleView
    return _battle_view_class


def _register_battle_view():
    global _battle_view_registered
    if _battle_view_registered:
        return True
    cls = _build_battle_view_class()
    if cls is None:
        return False
    try:
        from gui.Scaleform.framework import g_entitiesFactories, ViewSettings, ScopeTemplates
        from frameworks.wulf import WindowLayer
    except ImportError:
        _logger.warning('SpotMeter: framework not importable, battle panel disabled')
        return False
    try:
        settings = ViewSettings(
            alias=SPOTMETER_BATTLE_ALIAS,
            clazz=cls,
            url=SPOTMETER_BATTLE_SWF_URL,
            layer=WindowLayer.WINDOW,
            scope=ScopeTemplates.GLOBAL_SCOPE,
            canDrag=False,
            canClose=False,
            isModal=False,
            isCentered=False,
        )
        g_entitiesFactories.addSettings(settings)
        _battle_view_registered = True
        _logger.warning('SpotMeter: battle panel view registered (alias=%s, url=%s)',
                        SPOTMETER_BATTLE_ALIAS, SPOTMETER_BATTLE_SWF_URL)
        return True
    except Exception:
        _logger.exception('SpotMeter: addSettings failed for battle view')
        return False


_GUIFLASH_HOOK_INSTALLED = False
_BATTLE_PANEL_ACTIVE = False
_BATTLE_PANEL_REFRESH_CB = None
_BATTLE_PANEL_LAST = {}    # alias -> last rendered html (diff guard)
_BATTLE_PANEL_ENEMY_VIDS = set()  # currently rendered enemy_* components
SPOTMETER_PANEL_ROOT = 'spotmeter'
SPOTMETER_PANEL_REFRESH_SEC = 0.5
SPOTMETER_MAX_ENEMY_ROWS = 15

# v6.0.0 garage info panel. Separate alias tree so battle and garage
# panels coexist within the same GUIFlash view instance - components
# get lobby=True (instead of battle=True) so they only render in the
# garage. Refresh is slower than battle (no per-tick state need); 2s
# is enough to pick up Numpad toggle changes if the user toggles
# something mid-session from a previous battle.
_GARAGE_PANEL_ACTIVE = False
_GARAGE_PANEL_REFRESH_CB = None
_GARAGE_PANEL_LAST = {}
SPOTMETER_GARAGE_ROOT = 'sm_garage'
SPOTMETER_GARAGE_REFRESH_SEC = 2.0

# Visual layout constants for the in-battle panel. Pixel offsets are
# relative to the root Panel; the root is positioned via battlePanelX/Y
# and the children inherit that translation. Update these if the panel
# starts to feel cramped at lower resolutions.
_LAYOUT = {
    'title_y':       4,
    'target_y':      24,
    'auto_y':        46,
    'toggles_row1_y': 72,
    'toggles_row2_y': 94,
    'toggles_row3_y': 116,
    'enemies_y0':    142,
    'enemies_step':  18,
}

# Toggle name -> (alias_suffix, hotkey_label, display_name). The
# display_name is shown in the panel; alias_suffix is the click target
# (also used to route the click back to _toggle_perk).
_TOGGLE_ROWS = [
    ('rations',       'tog_rations',    'N7',  'rations'),
    ('BIA',           'tog_BIA',        'N3',  'BIA'),
    ('reconSitAware', 'tog_recon',      'N4',  'recon'),
    ('directives',    'tog_directives', 'N1',  'dyrekt.'),
    ('fieldUpgrades', 'tog_fieldUpgr',  'N0',  'fieldUpgr'),
]

# Multi-level cycling controls. Same cell shape as toggles but with
# level state read from _PICKER_LEVELS instead of _PICKER_TOGGLES.
_LEVEL_ROWS = [
    ('optics', 'lvl_optics', 'N6', 'optics'),
    ('vents',  'lvl_vents',  'N+', 'vents'),
    ('cvs',    'lvl_cvs',    'N-', 'CVS'),
]

# Battle-panel grid order: binary toggles for the "always-relevant"
# crew items first, then the three level-cyclers (assumed enemy gear),
# then the rare-case binary toggles. 8 cells total in a 3+3+2 grid.
_PANEL_CELLS = [
    ('toggle', _TOGGLE_ROWS[0]),   # rations
    ('toggle', _TOGGLE_ROWS[1]),   # BIA
    ('toggle', _TOGGLE_ROWS[2]),   # reconSitAware
    ('level',  _LEVEL_ROWS[0]),    # optics
    ('level',  _LEVEL_ROWS[1]),    # vents
    ('level',  _LEVEL_ROWS[2]),    # cvs
    ('toggle', _TOGGLE_ROWS[3]),   # directives
    ('toggle', _TOGGLE_ROWS[4]),   # fieldUpgrades
]


def _show_battle_view(force=False):
    """Build the in-battle SpotMeter panel using our private forked
    GUIFlash. Components are individually clickable:
      - .auto              -> toggle auto-pick
      - .tog_<name>        -> toggle the corresponding perk/equipment
      - .enemy_<vid>       -> pick that enemy

    All clicks are routed through COMPONENT_EVENT.CLICKED, which our
    forked Flash_UI fires whenever an AS3 component receives a
    MouseEvent.CLICK. The same panel is also draggable via the
    .drag=true prop on the root; drag-end persists battlePanelX/Y.
    """
    global _BATTLE_PANEL_ACTIVE
    if not force and not _CFG.get('battlePanelEnabled', True):
        return
    if not force and _PANEL_USER_HIDDEN:
        return  # user hid it with PgDn - don't let invalidateMarkup revive it
    if _BATTLE_PANEL_ACTIVE:
        return

    try:
        from gui.mods.spotmeter_gf import g_smGuiFlash
    except ImportError:
        _logger.warning(
            'SpotMeter: spotmeter_gf wrapper not importable - in-battle '
            'panel disabled. Reinstall the wotmod.')
        return

    _install_guiflash_event_hook()

    x = float(_CFG.get('battlePanelX', 10))
    y = float(_CFG.get('battlePanelY', 400))
    w = float(_CFG.get('battlePanelW', 320))
    h = float(_CFG.get('battlePanelH', 400))

    try:
        # Root draggable panel. limit=True clamps drag to stage bounds
        # so the user can't yeet it off-screen.
        g_smGuiFlash.createComponent(SPOTMETER_PANEL_ROOT, 'Panel', {
            'x': x, 'y': y,
            'width': w, 'height': h,
            'drag': True, 'limit': True,
        })
        # Title is non-clickable, just identification.
        g_smGuiFlash.createComponent(SPOTMETER_PANEL_ROOT + '.title', 'Label', {
            'x': 8, 'y': _LAYOUT['title_y'],
            'text': '<font size="14" color="#FFFFFF"><b>SpotMeter v%s</b></font> '
                    '<font size="9" color="#888888">by %s</font>'
                    % (MOD_VERSION_SHORT, MOD_AUTHOR),
            'isHtml': True, 'shadow': None,
            'autoSize': True,
        })
        # Bottom hint: how to hide the panel (PageDown by default).
        g_smGuiFlash.createComponent(SPOTMETER_PANEL_ROOT + '.hint', 'Label', {
            'x': 8, 'y': _LAYOUT['enemies_y0'],
            'text': '<font size="9" color="#666666"><i>%s</i></font>' % _t('battle_hide_hint'),
            'isHtml': True, 'shadow': None,
            'autoSize': True,
        })
        # Target line is non-clickable info.
        g_smGuiFlash.createComponent(SPOTMETER_PANEL_ROOT + '.target', 'Label', {
            'x': 8, 'y': _LAYOUT['target_y'],
            'text': '<font size="12" color="#FFCC66">Target: --</font>',
            'isHtml': True, 'shadow': None,
            'autoSize': True,
        })
        # Auto-pick line is CLICKABLE - toggles auto-pick on/off.
        g_smGuiFlash.createComponent(SPOTMETER_PANEL_ROOT + '.auto', 'Label', {
            'x': 8, 'y': _LAYOUT['auto_y'],
            'text': _fmt_auto_label(),
            'isHtml': True, 'shadow': None,
            'autoSize': True,
            'customBackground': {
                'color': 0x222B36, 'alpha': 0.6,
                'border': True, 'borderColor': 0x4A5868,
                'thickness': 1, 'margin': 3, 'ellipseWidth': 4,
            },
        })
        # Seven cells (5 binary toggles + 2 multi-level controls) in a
        # 3+3+1 grid. _PANEL_CELLS holds them in display order with a
        # kind discriminator so we can format toggles vs levels in the
        # same loop.
        cells_per_row = 3
        cell_w = (w - 16) / cells_per_row
        # Row Y baseline: keep existing row1/row2 spacing, add row3.
        row_y = [
            _LAYOUT['toggles_row1_y'],
            _LAYOUT['toggles_row2_y'],
            _LAYOUT['toggles_row3_y'],
        ]
        for i, (kind, item) in enumerate(_PANEL_CELLS):
            row = i // cells_per_row
            col = i % cells_per_row
            key, suffix, hotkey, dispname = item
            cx = 8 + col * cell_w
            cy = row_y[row] if row < len(row_y) else row_y[-1]
            if kind == 'toggle':
                text = _fmt_toggle_label(key, dispname, hotkey)
            else:  # level
                text = _fmt_level_label(key, dispname, hotkey)
            g_smGuiFlash.createComponent(
                SPOTMETER_PANEL_ROOT + '.' + suffix, 'Label', {
                    'x': cx, 'y': cy,
                    'text': text,
                    'isHtml': True, 'shadow': None,
                    'autoSize': True,
                    'customBackground': {
                        'color': 0x222B36, 'alpha': 0.5,
                        'border': True, 'borderColor': 0x4A5868,
                        'thickness': 1, 'margin': 3, 'ellipseWidth': 4,
                    },
                })
        # Enemy rows are created dynamically on first refresh.
    except Exception:
        _logger.exception('SpotMeter: failed to create GUIFlash panel components')
        return

    _BATTLE_PANEL_ACTIVE = True
    _BATTLE_PANEL_LAST.clear()
    _BATTLE_PANEL_ENEMY_VIDS.clear()
    _logger.warning('SpotMeter: GUIFlash battle panel created at (%s,%s)', x, y)
    _schedule_panel_refresh()


def _hide_battle_view():
    """Tear down the GUIFlash panel cleanly. Safe to call multiple times."""
    global _BATTLE_PANEL_ACTIVE, _BATTLE_PANEL_REFRESH_CB
    if not _BATTLE_PANEL_ACTIVE:
        return
    if _BATTLE_PANEL_REFRESH_CB is not None:
        try:
            BigWorld.cancelCallback(_BATTLE_PANEL_REFRESH_CB)
        except Exception:
            pass
        _BATTLE_PANEL_REFRESH_CB = None
    try:
        from gui.mods.spotmeter_gf import g_smGuiFlash
        # Delete child enemy components first so the cache stays consistent.
        for vid in list(_BATTLE_PANEL_ENEMY_VIDS):
            try:
                g_smGuiFlash.deleteComponent(
                    SPOTMETER_PANEL_ROOT + '.enemy_' + str(vid))
            except Exception:
                pass
        # Then the fixed children: title/target/auto + every cell in the
        # panel grid (binary toggles + level cyclers).
        fixed_suffixes = ['title', 'target', 'auto', 'hint']
        for _kind, item in _PANEL_CELLS:
            fixed_suffixes.append(item[1])  # item = (key, suffix, hotkey, dispname)
        for suffix in fixed_suffixes:
            try:
                g_smGuiFlash.deleteComponent(SPOTMETER_PANEL_ROOT + '.' + suffix)
            except Exception:
                pass
        g_smGuiFlash.deleteComponent(SPOTMETER_PANEL_ROOT)
    except Exception:
        _logger.exception('SpotMeter: failed to delete GUIFlash panel')
    _BATTLE_PANEL_ACTIVE = False
    _BATTLE_PANEL_LAST.clear()
    _BATTLE_PANEL_ENEMY_VIDS.clear()
    _logger.info('SpotMeter: GUIFlash battle panel destroyed')


def _install_guiflash_event_hook():
    """Subscribe to our forked GUIFlash's CLICKED + UPDATED events.
    CLICKED routes to the appropriate picker handler by alias; UPDATED
    persists drag-end coords."""
    global _GUIFLASH_HOOK_INSTALLED
    if _GUIFLASH_HOOK_INSTALLED:
        return
    try:
        from gui.mods.spotmeter_gf.flash import COMPONENT_EVENT
    except ImportError:
        _logger.warning('SpotMeter: spotmeter_gf.flash COMPONENT_EVENT not importable')
        return
    try:
        COMPONENT_EVENT.UPDATED += _on_guiflash_component_updated
        COMPONENT_EVENT.CLICKED += _on_guiflash_component_clicked
        _GUIFLASH_HOOK_INSTALLED = True
        _logger.info('SpotMeter: subscribed to spotmeter_gf COMPONENT_EVENT')
    except Exception:
        _logger.exception('SpotMeter: failed to subscribe to spotmeter_gf events')


def _on_guiflash_component_clicked(alias):
    """Dispatch click on any panel component to the right picker handler.
    Aliases like 'spotmeter.tog_rations.label' also dispatch to the same
    handler as the bare 'spotmeter.tog_rations' so clicks on inner text
    work too (though our current layout has no inner children)."""
    if not alias or not alias.startswith(SPOTMETER_PANEL_ROOT + '.'):
        return
    leaf = alias[len(SPOTMETER_PANEL_ROOT) + 1:].split('.', 1)[0]
    if leaf == 'auto':
        _toggle_auto_pick()
        return
    for key, suffix, _hotkey, _disp in _TOGGLE_ROWS:
        if leaf == suffix:
            _toggle_perk(key)
            return
    for key, suffix, _hotkey, _disp in _LEVEL_ROWS:
        if leaf == suffix:
            _cycle_level(key)
            return
    if leaf.startswith('enemy_'):
        try:
            vid = int(leaf[len('enemy_'):])
        except ValueError:
            return
        _battle_panel_on_pick(vid)
        return
    # Title / target are explicitly non-interactive (no handler).


def _on_guiflash_component_updated(alias, props):
    """Called whenever any GUIFlash component changes. We persist drag-end
    coords for our draggable root panels (battle + garage). Other updates
    are ignored - we don't react to text-change or property-change events
    coming back to Python."""
    if not isinstance(props, dict):
        return
    if 'x' not in props and 'y' not in props:
        return
    # Determine which panel was dragged.
    if alias == SPOTMETER_PANEL_ROOT:
        cfg_x_key, cfg_y_key, label = 'battlePanelX', 'battlePanelY', 'battle'
    elif alias == SPOTMETER_GARAGE_ROOT:
        cfg_x_key, cfg_y_key, label = 'garagePanelX', 'garagePanelY', 'garage'
    else:
        return
    new_x = props.get('x', _CFG.get(cfg_x_key))
    new_y = props.get('y', _CFG.get(cfg_y_key))
    try:
        cx = int(round(float(new_x)))
        cy = int(round(float(new_y)))
    except (TypeError, ValueError):
        return
    if cx == _CFG.get(cfg_x_key) and cy == _CFG.get(cfg_y_key):
        return  # no actual change
    _CFG[cfg_x_key] = cx
    _CFG[cfg_y_key] = cy
    _logger.info('SpotMeter: %s panel dragged to (%d, %d), saving config', label, cx, cy)
    try:
        _write_config()
    except Exception:
        _logger.exception('SpotMeter: failed to persist %s panel position', label)


def _schedule_panel_refresh():
    """One-shot scheduling helper; rescheduled by _battle_panel_tick."""
    global _BATTLE_PANEL_REFRESH_CB
    if not _BATTLE_PANEL_ACTIVE:
        return
    try:
        _BATTLE_PANEL_REFRESH_CB = BigWorld.callback(
            SPOTMETER_PANEL_REFRESH_SEC, _battle_panel_tick)
    except Exception:
        _logger.exception('SpotMeter: failed to schedule panel refresh')


def _battle_panel_tick():
    """Periodic refresh of the panel content. Diff-guarded against
    _BATTLE_PANEL_LAST so we only call updateComponent when text changes -
    GUIFlash updates re-render the whole component, so flicker is real
    if we push every tick blindly.
    """
    global _BATTLE_PANEL_REFRESH_CB
    _BATTLE_PANEL_REFRESH_CB = None
    if not _BATTLE_PANEL_ACTIVE:
        return
    try:
        _refresh_panel_state()
    except Exception:
        _logger.exception('SpotMeter: panel refresh tick failed')
    _schedule_panel_refresh()


def _refresh_panel_state():
    """Compute current state text for each label and push only the ones
    that actually changed. Also reconciles the dynamic enemy_<vid> rows
    against the current enemy listing - creating new ones, deleting
    dead ones, updating survivors."""
    try:
        from gui.mods.spotmeter_gf import g_smGuiFlash
    except ImportError:
        return
    plugin = _get_picker_plugin()

    _maybe_update_label(g_smGuiFlash, SPOTMETER_PANEL_ROOT + '.target',
                        _fmt_target_label(plugin))
    _maybe_update_label(g_smGuiFlash, SPOTMETER_PANEL_ROOT + '.auto',
                        _fmt_auto_label())
    for kind, (key, suffix, hotkey, dispname) in _PANEL_CELLS:
        if kind == 'toggle':
            text = _fmt_toggle_label(key, dispname, hotkey)
        else:
            text = _fmt_level_label(key, dispname, hotkey)
        _maybe_update_label(g_smGuiFlash, SPOTMETER_PANEL_ROOT + '.' + suffix, text)

    _refresh_enemy_rows(g_smGuiFlash, plugin)


def _maybe_update_label(g_smGuiFlash, alias, html):
    if _BATTLE_PANEL_LAST.get(alias) == html:
        return
    _BATTLE_PANEL_LAST[alias] = html
    try:
        g_smGuiFlash.updateComponent(alias, {'text': html})
    except Exception:
        _logger.exception('SpotMeter: updateComponent failed for %s', alias)


def _refresh_enemy_rows(g_smGuiFlash, plugin):
    """Reconcile per-enemy components against the live picker listing.
    Each enemy gets its own clickable Label at spotmeter.enemy_<vid>.
    Stacks vertically; row height fixed by _LAYOUT['enemies_step']."""
    if plugin is None:
        # No plugin -> remove anything stale
        _purge_enemy_rows(g_smGuiFlash, keep=set())
        return
    groups = _grouped_enemies(plugin)
    listing = groups[:SPOTMETER_MAX_ENEMY_ROWS]
    desired_vids = set(rep_vid for rep_vid, _, _ in listing)
    _purge_enemy_rows(g_smGuiFlash, keep=desired_vids)

    eff_vid, src = _effective_picked_vid()
    # Resolve the picked tank's TYPE so a group row still highlights when the
    # picked vid is a non-representative member (e.g. an auto-picked instance).
    picked_key = None
    if eff_vid is not None:
        try:
            arenaDP = plugin.sessionProvider.getArenaDP()
            ev = arenaDP.getVehicleInfo(eff_vid) if arenaDP is not None else None
            if ev is not None:
                picked_key = _veh_type_key(ev.vehicleType)
        except Exception:
            picked_key = None
    y0 = _LAYOUT['enemies_y0']
    step = _LAYOUT['enemies_step']
    panel_w = float(_CFG.get('battlePanelW', 320))

    for idx, (vid, vinfo, count) in enumerate(listing):
        alias = SPOTMETER_PANEL_ROOT + '.enemy_' + str(vid)
        is_picked = (vid == eff_vid) or (picked_key is not None
                     and _veh_type_key(vinfo.vehicleType) == picked_key)
        text = _fmt_enemy_row(plugin, vid, vinfo, is_picked, src, count)
        if vid not in _BATTLE_PANEL_ENEMY_VIDS:
            # Create a new clickable row.
            try:
                g_smGuiFlash.createComponent(alias, 'Label', {
                    'x': 8, 'y': y0 + idx * step,
                    'text': text,
                    'isHtml': True, 'shadow': None,
                    'autoSize': False,
                    'width': panel_w - 16,
                    'height': step,
                    'customBackground': {
                        'color': (0x4A6378 if is_picked else 0x1A2230),
                        'alpha': (0.85 if is_picked else 0.40),
                        'border': False,
                        'thickness': 0,
                        'margin': 1,
                        'ellipseWidth': 3,
                    },
                })
                _BATTLE_PANEL_ENEMY_VIDS.add(vid)
                _BATTLE_PANEL_LAST[alias] = text
            except Exception:
                _logger.exception('SpotMeter: failed to create enemy row %s', alias)
        else:
            # Just update text + position (in case the list order shifted).
            _maybe_update_label(g_smGuiFlash, alias, text)
            try:
                g_smGuiFlash.updateComponent(alias, {
                    'y': y0 + idx * step,
                    'customBackground': {
                        'color': (0x4A6378 if is_picked else 0x1A2230),
                        'alpha': (0.85 if is_picked else 0.40),
                        'border': False,
                        'thickness': 0,
                        'margin': 1,
                        'ellipseWidth': 3,
                    },
                })
            except Exception:
                _logger.exception('SpotMeter: failed to reposition enemy row %s', alias)

    # Keep the "press PgDn to hide" hint right under the enemy list (adapts to
    # the tank count) instead of pinned at the panel bottom.
    try:
        g_smGuiFlash.updateComponent(SPOTMETER_PANEL_ROOT + '.hint',
                                     {'y': y0 + len(listing) * step + 6})
    except Exception:
        pass


def _purge_enemy_rows(g_smGuiFlash, keep):
    """Delete any enemy_<vid> components whose vid isn't in `keep`."""
    stale = [vid for vid in _BATTLE_PANEL_ENEMY_VIDS if vid not in keep]
    for vid in stale:
        alias = SPOTMETER_PANEL_ROOT + '.enemy_' + str(vid)
        try:
            g_smGuiFlash.deleteComponent(alias)
        except Exception:
            _logger.exception('SpotMeter: failed to delete stale enemy row %s', alias)
        _BATTLE_PANEL_ENEMY_VIDS.discard(vid)
        _BATTLE_PANEL_LAST.pop(alias, None)


# ----- label formatters -----

def _own_vehicle_short_name(plugin):
    """shortName of the player's own tank (for the 'own VR' target readout)."""
    try:
        vid = getattr(BigWorld.player(), 'playerVehicleID', 0)
        if not vid:
            return ''
        arenaDP = plugin.sessionProvider.getArenaDP()
        if arenaDP is None:
            return ''
        vinfo = arenaDP.getVehicleInfo(vid)
        if vinfo is not None and vinfo.vehicleType is not None:
            return vinfo.vehicleType.shortName or ''
    except Exception:
        pass
    return ''


def _fmt_target_label(plugin):
    eff_vid, src = _effective_picked_vid()
    if eff_vid is None or plugin is None:
        # Nothing picked + no auto -> the circle uses our OWN view range; show
        # our own tank instead of just "--".
        own_name = (_own_vehicle_short_name(plugin)
                    if plugin is not None and _CFG.get('useOwnViewRange', True) else '')
        if own_name:
            spot = _LAST_SPOT_RADIUS
            spot_str = ('%.0fm' % spot) if spot else '--m'
            return ('<font size="12" color="#FFCC66">%s <b>%s</b>  '
                    '<font color="#FFFFFF">spot=%s</font> '
                    '<font color="#88AABB">(%s)</font></font>'
                    % (_t('battle_target'), _html_escape(own_name), spot_str,
                       _t('battle_target_own')))
        return ('<font size="12" color="#888888">%s '
                '<i>--  %s</i></font>'
                % (_t('battle_target'), _t('battle_target_hint')))
    name = ''
    try:
        arenaDP = plugin.sessionProvider.getArenaDP()
        if arenaDP is not None:
            vinfo = arenaDP.getVehicleInfo(eff_vid)
            if vinfo is not None and vinfo.vehicleType is not None:
                name = vinfo.vehicleType.shortName or ''
    except Exception:
        pass
    # Show the distance from which THIS target spots us (the live spot-circle
    # radius for the current state) instead of the raw enemy VR.
    spot = _LAST_SPOT_RADIUS
    spot_str = ('%.0fm' % spot) if spot else '--m'
    src_str = ' <font color="#88AABB">(auto)</font>' if src == 'auto' else ''
    return ('<font size="12" color="#FFCC66">%s <b>%s</b>  '
            '<font color="#FFFFFF">spot=%s</font>%s</font>'
            % (_t('battle_target'), _html_escape(name), spot_str, src_str))


def _fmt_auto_label():
    auto_on = bool(_CFG.get('autoPickEnabled', False))
    range_m = int(float(_CFG.get('autoPickRangeMeters', 445.0)))
    color = '#88FF88' if auto_on else '#AAAAAA'
    label = 'ON, %dm' % range_m if auto_on else 'OFF'
    return ('<font size="11" color="%s">[Auto-pick: %s]</font>'
            '<font size="10" color="#555555"> %s</font>'
            % (color, label, _t('battle_auto_hint')))


def _fmt_toggle_label(key, dispname, hotkey):
    on = bool(_PICKER_TOGGLES.get(key, False))
    color = '#88FF88' if on else '#AAAAAA'
    sym = '+' if on else '-'
    return ('<font size="11" color="%s">[%s%s]</font>'
            '<font size="9" color="#555555"> %s</font>'
            % (color, sym, _html_escape(_t('tl_' + key)), hotkey))


def _fmt_level_label(key, dispname, hotkey):
    """Render a multi-level cell. Shows current level name (OFF/basic/
    slot/bonds/deluxe). Color is dim when at level 0 (OFF), green when
    at any positive level. Same cell shape as toggles so the 3-column
    grid stays uniform."""
    lvl = int(_PICKER_LEVELS.get(key, 0))
    lvl = max(0, min(lvl, len(_LEVEL_NAMES) - 1))
    name = _level_name_loc(lvl)
    color = '#88FF88' if lvl > 0 else '#AAAAAA'
    return ('<font size="11" color="%s">[%s:%s]</font>'
            '<font size="9" color="#555555"> %s</font>'
            % (color, _html_escape(_t('tl_' + key)), name, hotkey))


def _fmt_enemy_row(plugin, vid, vinfo, is_picked, src, count=1):
    vt = vinfo.vehicleType
    if vt is None:
        return ''
    klass = _class_code_for(vt) or '??'
    short = _html_escape(vt.shortName or '?')
    count_str = (' x%d' % count) if count > 1 else ''
    level = vt.level or 0
    vr_val = _picker_vr_for(plugin, vid)
    vr_str = 'VR=%dm' % int(vr_val) if vr_val else 'VR=?'
    if is_picked:
        line_color = '#FFCC66'
        marker = '<font color="#FFCC66"><b>&#9654;</b></font> '
        if src == 'auto':
            marker = '<font color="#88AABB"><b>&#9675;</b></font> '
    else:
        line_color = '#CCCCCC'
        marker = '<font color="#444444">&nbsp;&nbsp;</font>'
    return ('<font size="10" color="%s">%s[%s] %s%s T%d  %s</font>'
            % (line_color, marker, klass, short, count_str, level, vr_str))


def _html_escape(s):
    """Minimal HTML escape for label text. GUIFlash's Label uses Flash
    htmlText; <, >, & break the markup if not encoded. Tank shortNames
    sometimes contain '&' (e.g. 'M48A1 + dozer' on some skins)."""
    if s is None:
        return ''
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;'))


# ============================================================================
# v6.0.0 garage info panel. Read-only readout of current session state +
# Numpad hotkey reference. No interactivity (clickless GUIFlash) - user
# edits spotmeter.json to change defaults. Draggable, position persists
# via the same COMPONENT_EVENT.UPDATED hook the battle panel uses.
# ============================================================================

def _show_garage_panel(force=False):
    """Build the garage info panel using GUIFlash. Components are tagged
    lobby=True, battle=False so they only render in the garage; the
    same GUIFlash view instance handles both the in-battle panel and
    this one without conflict.
    """
    global _GARAGE_PANEL_ACTIVE
    if not force and not _CFG.get('garagePanelEnabled', True):
        return
    if not force and _PANEL_USER_HIDDEN:
        return  # user hid it with PgDn - don't let the hangar hooks revive it
    if _GARAGE_PANEL_ACTIVE:
        return
    try:
        from gui.mods.spotmeter_gf import g_smGuiFlash
    except ImportError:
        _logger.warning('SpotMeter: spotmeter_gf wrapper missing; garage panel disabled')
        return
    _install_guiflash_event_hook()

    x = float(_CFG.get('garagePanelX', 1500))
    y = float(_CFG.get('garagePanelY', 320))
    w = float(_CFG.get('garagePanelW', 380))
    h = float(_CFG.get('garagePanelH', 320))

    try:
        g_smGuiFlash.createComponent(SPOTMETER_GARAGE_ROOT, 'Panel', {
            'x': x, 'y': y,
            'width': w, 'height': h,
            'drag': True, 'limit': True,
        }, battle=False, lobby=True)
        g_smGuiFlash.createComponent(SPOTMETER_GARAGE_ROOT + '.title', 'Label', {
            'x': 8, 'y': 4,
            'text': '<font size="14" color="#FFFFFF"><b>SpotMeter v%s</b></font> '
                    '<font size="10" color="#888888">%s</font> '
                    '<font size="9" color="#888888">by %s</font>'
                    % (MOD_VERSION_SHORT, _t('garage_title_suffix'), MOD_AUTHOR),
            'isHtml': True, 'shadow': None,
            'autoSize': True,
        }, battle=False, lobby=True)
        g_smGuiFlash.createComponent(SPOTMETER_GARAGE_ROOT + '.defaults', 'Label', {
            'x': 8, 'y': 28,
            'text': _fmt_garage_defaults(),
            'isHtml': True, 'shadow': None,
            'autoSize': True,
            'multiline': True,
        }, battle=False, lobby=True)
        g_smGuiFlash.createComponent(SPOTMETER_GARAGE_ROOT + '.battle_panel', 'Label', {
            'x': 8, 'y': 84,
            'text': _fmt_garage_battle_panel(),
            'isHtml': True, 'shadow': None,
            'autoSize': True,
            'multiline': True,
        }, battle=False, lobby=True)
        g_smGuiFlash.createComponent(SPOTMETER_GARAGE_ROOT + '.hotkeys', 'Label', {
            'x': 8, 'y': 108,
            'text': _fmt_garage_hotkeys(),
            'isHtml': True, 'shadow': None,
            'autoSize': True,
            'multiline': True,
        }, battle=False, lobby=True)
        g_smGuiFlash.createComponent(SPOTMETER_GARAGE_ROOT + '.footer', 'Label', {
            'x': 8, 'y': h - 24,
            'text': '<font size="9" color="#666666"><i>%s</i></font>' % _t('garage_footer'),
            'isHtml': True, 'shadow': None,
            'autoSize': True,
        }, battle=False, lobby=True)
    except Exception:
        _logger.exception('SpotMeter: failed to create garage panel components')
        return

    _GARAGE_PANEL_ACTIVE = True
    _GARAGE_PANEL_LAST.clear()
    _logger.warning('SpotMeter: garage panel created at (%s,%s)', x, y)
    _schedule_garage_refresh()


def _hide_garage_panel():
    """Tear down the garage panel cleanly. Safe to call multiple times."""
    global _GARAGE_PANEL_ACTIVE, _GARAGE_PANEL_REFRESH_CB
    if not _GARAGE_PANEL_ACTIVE:
        return
    if _GARAGE_PANEL_REFRESH_CB is not None:
        try:
            BigWorld.cancelCallback(_GARAGE_PANEL_REFRESH_CB)
        except Exception:
            pass
        _GARAGE_PANEL_REFRESH_CB = None
    try:
        from gui.mods.spotmeter_gf import g_smGuiFlash
        for suffix in ('title', 'defaults', 'battle_panel', 'hotkeys', 'footer'):
            try:
                g_smGuiFlash.deleteComponent(SPOTMETER_GARAGE_ROOT + '.' + suffix)
            except Exception:
                pass
        g_smGuiFlash.deleteComponent(SPOTMETER_GARAGE_ROOT)
    except Exception:
        _logger.exception('SpotMeter: failed to delete garage panel')
    _GARAGE_PANEL_ACTIVE = False
    _GARAGE_PANEL_LAST.clear()
    _logger.info('SpotMeter: garage panel destroyed')


def _toggle_panel():
    """Show/hide the SpotMeter panel (PageDown by default). Context-aware:
    flips the garage panel when in the garage, the battle panel otherwise.
    Passes force=True so it can summon a panel even when its *PanelEnabled
    flag is False - that flag only governs whether the panel auto-shows at
    startup, while this key controls live visibility either way.
    """
    global _PANEL_USER_HIDDEN
    if _is_in_garage():
        if _GARAGE_PANEL_ACTIVE:
            _hide_garage_panel()
            _PANEL_USER_HIDDEN = True
        else:
            _PANEL_USER_HIDDEN = False
            _show_garage_panel(force=True)
    else:
        if _BATTLE_PANEL_ACTIVE:
            _hide_battle_view()
            _PANEL_USER_HIDDEN = True
        else:
            _PANEL_USER_HIDDEN = False
            _show_battle_view(force=True)


def _schedule_garage_refresh():
    global _GARAGE_PANEL_REFRESH_CB
    if not _GARAGE_PANEL_ACTIVE:
        return
    try:
        _GARAGE_PANEL_REFRESH_CB = BigWorld.callback(
            SPOTMETER_GARAGE_REFRESH_SEC, _garage_panel_tick)
    except Exception:
        _logger.exception('SpotMeter: failed to schedule garage refresh')


def _garage_panel_tick():
    """Refresh dynamic text in the garage panel. Slow tick (2s) since
    state rarely changes in the garage - only when user pressed a
    Numpad toggle mid-session from a previous battle's mod state."""
    global _GARAGE_PANEL_REFRESH_CB
    _GARAGE_PANEL_REFRESH_CB = None
    if not _GARAGE_PANEL_ACTIVE:
        return
    try:
        _refresh_garage_state()
    except Exception:
        _logger.exception('SpotMeter: garage refresh tick failed')
    _schedule_garage_refresh()


def _refresh_garage_state():
    try:
        from gui.mods.spotmeter_gf import g_smGuiFlash
    except ImportError:
        return
    _maybe_update_garage_label(g_smGuiFlash, SPOTMETER_GARAGE_ROOT + '.defaults',
                               _fmt_garage_defaults())
    _maybe_update_garage_label(g_smGuiFlash, SPOTMETER_GARAGE_ROOT + '.battle_panel',
                               _fmt_garage_battle_panel())
    # Hotkeys are static, no refresh needed.


def _refresh_garage_if_active():
    """Repaint the garage panel immediately after a Numpad action so the
    change shows at once instead of waiting for the ~2s tick. No-op in
    battle (the garage panel is inactive there)."""
    if not _GARAGE_PANEL_ACTIVE:
        return
    try:
        _refresh_garage_state()
    except Exception:
        _logger.exception('SpotMeter: immediate garage refresh failed')


def _maybe_update_garage_label(g_smGuiFlash, alias, html):
    if _GARAGE_PANEL_LAST.get(alias) == html:
        return
    _GARAGE_PANEL_LAST[alias] = html
    try:
        g_smGuiFlash.updateComponent(alias, {'text': html})
    except Exception:
        _logger.exception('SpotMeter: updateComponent failed for %s', alias)


def _fmt_garage_defaults():
    """Render the current session's toggle state. Distinguish 'config
    default' (what loads at battle start) from 'current session' (what
    Numpad presses changed mid-session) so the user can tell when their
    in-session changes will reset."""
    defaults = _CFG.get('defaultToggles') or {}
    pairs = [
        ('rations',       'N7'),
        ('BIA',           'N3'),
        ('reconSitAware', 'N4'),
        ('directives',    'N1'),
        ('fieldUpgrades', 'N0'),
    ]
    rows = []
    for key, hotkey in pairs:
        label = _t('tl_' + key)
        default_on = bool(defaults.get(key, False))
        current_on = bool(_PICKER_TOGGLES.get(key, False))
        default_sym = '+' if default_on else '-'
        current_sym = '+' if current_on else '-'
        if default_on == current_on:
            color = '#88FF88' if current_on else '#888888'
            rows.append(
                '<font color="%s">%s%s</font> '
                '<font color="#555555">(%s)</font>'
                % (color, current_sym, label, hotkey))
        else:
            rows.append(
                '<font color="#FFCC66">%s%s</font> '
                '<font color="#555555">(%s, default %s)</font>'
                % (current_sym, label, hotkey, default_sym))

    # Auto-pick is a mode toggle with its own state vars (not _PICKER_TOGGLES).
    auto_on = bool(_CFG.get('autoPickEnabled', False))
    auto_def = bool(_DEFAULT_AUTO_PICK_ENABLED)
    auto_sym = '+' if auto_on else '-'
    if auto_on == auto_def:
        auto_color = '#88FF88' if auto_on else '#888888'
        rows.append('<font color="%s">%s%s</font> '
                    '<font color="#555555">(N/)</font>'
                    % (auto_color, auto_sym, _t('tl_auto')))
    else:
        rows.append('<font color="#FFCC66">%s%s</font> '
                    '<font color="#555555">(N/, default %s)</font>'
                    % (auto_sym, _t('tl_auto'), '+' if auto_def else '-'))

    # Multi-level cells (optics + vents + cvs) go on their OWN second line
    # so the on/off toggles above don't run off the panel width.
    level_rows = []
    default_levels = _CFG.get('defaultLevels') or {}
    for key, hotkey in [('optics', 'N6'), ('vents', 'N+'), ('cvs', 'N-')]:
        label = _t('tl_' + key)
        cur_lvl = int(_PICKER_LEVELS.get(key, 0))
        def_lvl = int(default_levels.get(key, 0))
        cur_lvl = max(0, min(cur_lvl, len(_LEVEL_NAMES) - 1))
        cur_name = _level_name_loc(cur_lvl)
        if cur_lvl == def_lvl:
            color = '#88FF88' if cur_lvl > 0 else '#888888'
            level_rows.append(
                '<font color="%s">%s:%s</font> '
                '<font color="#555555">(%s)</font>'
                % (color, label, cur_name, hotkey))
        else:
            def_name = _level_name_loc(def_lvl)
            level_rows.append(
                '<font color="#FFCC66">%s:%s</font> '
                '<font color="#555555">(%s, default %s)</font>'
                % (label, cur_name, hotkey, def_name))

    # Two lines: line 1 = on/off toggles (+auto), line 2 = equipment levels.
    return ('<font size="11" color="#88AABB"><b>' + _t('garage_loadout_header') + '</b></font><br>'
            '<font size="11">  ' + '  '.join(rows) + '</font><br>'
            '<font size="11">  ' + '  '.join(level_rows) + '</font>')


def _fmt_garage_battle_panel():
    on = bool(_CFG.get('battlePanelEnabled', True))
    px = int(_CFG.get('battlePanelX', 10))
    py = int(_CFG.get('battlePanelY', 400))
    color = '#88FF88' if on else '#888888'
    state = 'ON' if on else 'OFF'
    return ('<font size="11" color="#88AABB"><b>%s</b></font> '
            '<font size="11" color="%s">%s</font> '
            '<font size="10" color="#888888">@ (%d, %d)</font>'
            % (_t('garage_battle_panel'), color, state, px, py))


def _fmt_garage_hotkeys():
    return _t('garage_hotkeys')


# ---- battle-panel event handlers (Python side) ----

def _battle_panel_on_pick(vid):
    """User clicked an enemy row in the panel. Set _PICKED_VID and refresh
    the spot circle. Mirrors what Numpad 2/8 does, but jumps directly to a
    specific vid instead of cycling.
    """
    global _PICKED_VID
    plugin = _get_picker_plugin()
    if plugin is None:
        return
    # Validate vid is still in the enemy listing (avoid setting a stale id
    # from a row that was alive when we pushed but died between push and
    # click - unlikely at 5 Hz but cheap to guard).
    enemies = _enemy_iterator(plugin)
    valid_vids = set(v for v, _ in enemies)
    if vid not in valid_vids:
        _logger.info('SpotMeter: battle panel pick ignored - vid %s not in enemy list', vid)
        return
    affected = set()
    if _PICKED_VID is not None:
        affected.add(_PICKED_VID)
    _PICKED_VID = vid
    affected.add(vid)
    _on_picker_changed(plugin, affected)


def _battle_panel_on_toggle(name):
    """User clicked a toggle checkbox. Mirrors a Numpad toggle press."""
    _toggle_perk(name)


def _battle_panel_on_auto_click():
    """User clicked the auto-pick checkbox. Mirrors Numpad/."""
    _toggle_auto_pick()


def _battle_panel_on_drag_end(new_x, new_y):
    """User dropped the panel after dragging. Persist new position."""
    try:
        cx = int(round(float(new_x)))
        cy = int(round(float(new_y)))
    except (TypeError, ValueError):
        return
    _CFG['battlePanelX'] = cx
    _CFG['battlePanelY'] = cy
    _logger.info('SpotMeter: battle panel position saved -> (%d, %d)', cx, cy)
    try:
        _write_config()
    except Exception:
        _logger.exception('SpotMeter: failed to persist battle panel position')


# ---- battle-panel state payload helpers ----

def _battle_panel_enemy_payload(plugin):
    """Return (vids, labels, class_codes) for the current enemy listing,
    collapsed by vehicle type via _grouped_enemies (identical tanks share
    one row, labelled "Name xN"). vids hold the group representative, so the
    existing parallel-array AS3 protocol and the click->pick path stay
    unchanged. Empty tuples if plugin is None or no enemies."""
    if plugin is None:
        return [], [], []
    vids = []
    labels = []
    classes = []
    for rep_vid, vinfo, count in _grouped_enemies(plugin):
        vt = vinfo.vehicleType
        if vt is None:
            continue
        short = vt.shortName or '?'
        level = vt.level or 0
        # "Obj. 907  T10", or "Obj. 907 x3  T10" when several are present.
        if count > 1:
            label = '%s x%d  T%d' % (short, count, level)
        else:
            label = '%s  T%d' % (short, level)
        vids.append(rep_vid)
        labels.append(label)
        classes.append(_class_code_for(vt))
    return vids, labels, classes


def _class_code_for(vehicleType):
    """Map vehicleType -> two/three-letter class code shown in the panel.
    Falls back to '' if unrecognized."""
    tags = getattr(vehicleType, 'tags', None) or ()
    if 'heavyTank' in tags:
        return 'HT'
    if 'mediumTank' in tags:
        return 'MT'
    if 'lightTank' in tags:
        return 'LT'
    if 'AT-SPG' in tags:
        return 'TD'
    if 'SPG' in tags:
        return 'SPG'
    return ''


def _battle_panel_selected_payload(plugin):
    """Return (vid, name, vr) for the effective pick (manual or auto), or
    (0, '', 0.0) when nothing is picked. VR uses the same _picker_vr_for
    that drives the spot circle, so the panel reading matches the circle."""
    eff_vid, _src = _effective_picked_vid()
    if eff_vid is None or plugin is None:
        return 0, '', 0.0
    # Resolve display name from arenaDP.
    name = ''
    try:
        arenaDP = plugin.sessionProvider.getArenaDP()
        if arenaDP is not None:
            vinfo = arenaDP.getVehicleInfo(eff_vid)
            if vinfo is not None and vinfo.vehicleType is not None:
                name = vinfo.vehicleType.shortName or ''
    except Exception:
        _logger.exception('SpotMeter: failed to resolve picked vinfo')
    vr = _picker_vr_for(plugin, eff_vid)
    if vr is None:
        vr = 0.0
    return eff_vid, name, float(vr)


def _install_reload_hotkey():
    # v5.6.4: idempotency guard. Each call to this function adds a NEW
    # _on_key_event closure to gui.g_keyEventHandlers. Set semantics treat
    # distinct closures as distinct entries, so a re-call would multiply
    # fires per keypress (N copies of the handler = N action fires).
    global _HOTKEYS_INSTALLED
    if _HOTKEYS_INSTALLED:
        return
    try:
        import Keys
    except ImportError:
        _logger.warning('SpotMeter: Keys module unavailable - cannot bind hotkeys')
        return

    bindings = []
    # Backwards-compat / NumLock-off aliases. NumLock-off on most keyboards
    # remaps the numpad navigation cluster to KEY_HOME/END/PGUP/PGDN/etc.,
    # so we register both the numpad scancode AND the alternate one for the
    # navigation actions. That way the hotkeys work whether NumLock is on or
    # off and regardless of which name the user put in their config.
    #
    # v5.6.4 fix: NUMPAD2 used to alias to KEY_PGDN and NUMPAD8 to KEY_PGUP,
    # but with NumLock off Numpad2 -> DownArrow and Numpad3 -> PgDn (same
    # for 8 vs 9). Since picker-next is bound first and the dispatch loop
    # picks the FIRST matching binding, pressing Numpad3 (BIA) actually
    # fired picker-next - which spammed 'picker -> ...' to chat. The wrong
    # PgDn/PgUp entries are removed below.
    _key_aliases = {
        'KEY_PRIOR': ['KEY_PGUP'],
        'KEY_NEXT': ['KEY_PGDN'],
        'KEY_PAGEUP': ['KEY_PGUP'],
        'KEY_PAGEDOWN': ['KEY_PGDN'],
        # Numpad -> nav cluster fallbacks for NumLock-off case
        'KEY_NUMPAD0': ['KEY_INSERT'],
        'KEY_NUMPAD1': ['KEY_END'],
        'KEY_NUMPAD2': ['KEY_DOWNARROW'],
        'KEY_NUMPAD3': [],  # KEY_PGDN freed -> reused as panelToggleKey
        'KEY_NUMPAD4': ['KEY_LEFT'],
        'KEY_NUMPAD5': [],
        'KEY_NUMPAD6': ['KEY_RIGHT'],
        'KEY_NUMPAD7': ['KEY_HOME'],
        'KEY_NUMPAD8': ['KEY_UPARROW'],
        'KEY_NUMPAD9': ['KEY_PGUP'],
        'KEY_NUMPADPERIOD': ['KEY_DELETE'],
    }

    def _resolve_keys(cfg_key):
        key_name = _CFG.get(cfg_key) or ''
        if not key_name:
            return []
        names = [key_name] + _key_aliases.get(key_name, [])
        ids = []
        unknown = []
        for n in names:
            kid = getattr(Keys, n, None)
            if kid is None:
                unknown.append(n)
            elif kid not in ids:
                ids.append(kid)
        if unknown and not ids:
            _logger.warning(
                'SpotMeter: hotkey for %s = %r not found in Keys module. '
                'Common names: KEY_F1..F12, KEY_PGUP, KEY_PGDN, KEY_HOME, '
                'KEY_END, KEY_INSERT, KEY_DELETE, KEY_NUMPAD0..9.',
                cfg_key, _CFG.get(cfg_key))
        return [(kid, key_name) for kid in ids]

    def _bind(cfg_key, action, label):
        for key_id, key_name in _resolve_keys(cfg_key):
            bindings.append((key_id, action, label, key_name))

    _bind('reloadKey', _hot_reload, 'reload')
    _bind('panelToggleKey', _toggle_panel, 'panel-toggle')
    if _CFG.get('pickerEnabled', True):
        _bind('pickerNextKey', lambda: _cycle_picker(+1), 'picker-next')
        _bind('pickerPrevKey', lambda: _cycle_picker(-1), 'picker-prev')
        _bind('pickerClearKey', _clear_picker, 'picker-clear')
        _bind('pickerRationsKey',
              lambda: _toggle_perk('rations'), 'rations')
        _bind('pickerBIAKey',
              lambda: _toggle_perk('BIA'), 'BIA')
        _bind('pickerReconSitAwareKey',
              lambda: _toggle_perk('reconSitAware'), 'recon-sitaware')
        _bind('pickerOpticsKey',
              lambda: _cycle_level('optics'), 'optics-cycle')
        _bind('pickerVentsKey',
              lambda: _cycle_level('vents'), 'vents-cycle')
        _bind('pickerCvsKey',
              lambda: _cycle_level('cvs'), 'cvs-cycle')
        _bind('pickerDirectivesKey',
              lambda: _toggle_perk('directives'), 'directives')
        _bind('pickerFieldUpgradesKey',
              lambda: _toggle_perk('fieldUpgrades'), 'field-upgrades')
        _bind('pickerDiagDumpKey',
              lambda: _dump_picker_descriptor(_get_picker_plugin()),
              'diag-dump')
        _bind('autoPickToggleKey', _toggle_auto_pick, 'auto-pick-toggle')
    if _CFG.get('overlayEnabled', True):
        _bind('overlayToggleKey', _toggle_live_mode, 'live-mode-toggle')
        _bind('overlayPrintNowKey', _print_now, 'status-snapshot')

    if not bindings:
        _logger.warning('SpotMeter: no hotkeys registered (check Keys names in config)')
        return

    # v6.0.0: dedupe state. We register the SAME handler on TWO key
    # channels (see below) so hotkeys fire in both the garage and in
    # battle. In battle both channels deliver the same press, which
    # would toggle ON-then-OFF (net zero). The debounce drops a repeat
    # of the same key within _KEY_DEBOUNCE_SEC.
    import time as _time_mod
    _last_key = {'id': None, 't': 0.0}
    _KEY_DEBOUNCE_SEC = 0.12

    def _on_key_event(event):
        try:
            is_down = event.isKeyDown()
        except Exception:
            return False
        key = getattr(event, 'key', None)
        if key is not None:
            _ww_battle_key(key, is_down)   # battle TAB/N overlay auto-hide (down+up)
        if not is_down:
            return False
        if key is None:
            return False
        now = _time_mod.time()
        if (_last_key['id'] == key
                and (now - _last_key['t']) < _KEY_DEBOUNCE_SEC):
            return False  # duplicate from the other channel - ignore
        for key_id, action, label, _name in bindings:
            if key == key_id:
                _last_key['id'] = key
                _last_key['t'] = now
                try:
                    action()
                except Exception:
                    _logger.exception('SpotMeter: hotkey %s failed', label)
                return False  # don't consume - let other handlers see it too
        return False

    # Register on BOTH key channels:
    #   - gui.g_keyEventHandlers : the battle catch-all (fires in-battle
    #     only - the garage routes keys elsewhere).
    #   - InputHandler.g_instance.onKeyDown : fires in the garage/lobby
    #     too, so Numpad pre-configuration works before a battle.
    # The debounce above absorbs the double-delivery that happens in
    # battle when both channels see the same press.
    bound = []
    try:
        import gui as _gui_mod
        if hasattr(_gui_mod, 'g_keyEventHandlers'):
            _gui_mod.g_keyEventHandlers.add(_on_key_event)
            bound.append('gui.g_keyEventHandlers')
    except Exception:
        _logger.exception('SpotMeter: failed to bind via gui.g_keyEventHandlers')
    try:
        from gui import InputHandler as _IH
        _IH.g_instance.onKeyDown += _on_key_event
        bound.append('InputHandler.onKeyDown')
    except Exception:
        _logger.exception('SpotMeter: failed to bind via InputHandler.g_instance.onKeyDown')

    names = ', '.join('%s=%s' % (label, name) for _, _, label, name in bindings)
    _logger.warning('SpotMeter: hotkeys bound via [%s] - %d entries: %s',
                    ' + '.join(bound) or 'NONE', len(bindings), names)
    if bound:
        _HOTKEYS_INSTALLED = True
