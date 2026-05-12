# -*- coding: utf-8 -*-
# SpotMeter — World of Tanks minimap mod.
# Adds an extra dynamic circle to the player's minimap showing the distance
# from which the tank can be spotted, plus an in-battle picker for sizing
# the circle to a specific enemy's view range.
# Works alongside the game's existing view-range circles (does not replace them).
#
# Loader entry: scripts/client/gui/mods/mod_spotmeter.pyc
# Game version: World of Tanks 2.2.1.2 (Python 2.7 bytecode)
import json
import logging
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
MOD_VERSION = '5.6.1'
_logger.warning('SpotMeter: module loaded (version=%s)', MOD_VERSION)

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
    'pickerDirectivesKey':      'KEY_NUMPAD1',  # default OFF - boost auto-detected equipment by 1.025
    'pickerFieldUpgradesKey':   'KEY_NUMPAD0',  # default OFF - VR-related field upgrades (per-tank)
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
    'pickerMarker': u'● ',
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
}

_CFG = dict(DEFAULT_CONFIG)
_PATCHED = False
_AVATAR_PATCHED = False
_FORMATTER_PATCHED = False
_STATE = weakref.WeakKeyDictionary()
_LAST_SHOT_TIME = 0.0
_LAST_MOVEMENT_TIME = 0.0
_PICKED_VID = None
_PICKER_TOGGLES = {
    'rations':       True,   # default ON:  assume enemy has Combat Rations active
    'BIA':           True,   # default ON:  assume enemy has Brothers in Arms
    'reconSitAware': True,   # default ON:  assume enemy has Recon + Sit. Awareness
    'directives':    False,  # default OFF: assume no directives on equipment slots
    'fieldUpgrades': False,  # default OFF: assume no VR field upgrades
}
_LIVE_MODE_ENABLED = False  # default OFF - user enables via Numpad9 if they want auto-refreshing block
_LIVE_MODE_CALLBACK_ID = None  # BigWorld.callback handle for the periodic poster


def _read_config():
    for path in _CONFIG_CANDIDATES:
        try:
            with open(path, 'rb') as fh:
                payload = json.load(fh)
            if isinstance(payload, dict):
                for k, v in payload.iteritems():
                    if k in DEFAULT_CONFIG:
                        _CFG[k] = v
                _logger.info('SpotMeter: config loaded from %s', path)
                return
        except IOError:
            continue
        except (ValueError, KeyError) as exc:
            _logger.warning('SpotMeter: bad config at %s: %s', path, exc)
            return
    _logger.info('SpotMeter: no config file found, using defaults')


def init():
    _logger.warning('SpotMeter: init() called')
    try:
        _read_config()
        if not _CFG.get('enabled', True):
            _logger.warning('SpotMeter: disabled by config')
            return
        _patch_plugin()
        _patch_avatar_shoot()
        if _CFG.get('pickerEnabled', True):
            _patch_player_name_formatter()
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
    if _PICKED_VID is not None:
        vr = _picker_vr(plugin)
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


def _picker_vr(plugin):
    try:
        arenaDP = plugin.sessionProvider.getArenaDP()
    except Exception:
        return None
    vinfo = arenaDP.getVehicleInfo(_PICKED_VID)
    if vinfo is None or vinfo.vehicleType is None:
        return None
    cd = getattr(vinfo.vehicleType, 'strCompactDescr', None)
    if not cd:
        return None
    try:
        from items.vehicles import VehicleDescr
        descr = VehicleDescr(compactDescr=cd)
    except Exception:
        _logger.exception('SpotMeter: failed to decode descriptor for picked vid=%s', _PICKED_VID)
        return None
    try:
        base_vr = float(descr.turret.circularVisionRadius)
    except Exception:
        return None
    misc = getattr(descr, 'miscAttrs', None) or {}
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
    #          This reflects the in-game reality that a higher effective
    #          crew level makes those skills/equipment deliver more raw VR.
    #
    #            final = crew_amplified
    #                  + crew_amplified * (optics_factor * directive - 1)
    #                  + crew_amplified * (stereo_factor * directive - 1)
    #                  + crew_amplified * (reconSitAware - 1)
    #
    # Field upgrade applies to base_vr BEFORE stage 1 (capped at 445 m),
    # which means the upgrade then naturally compounds through both stages.

    # Field upgrade on base_vr (per-tank table, capped).
    if _PICKER_TOGGLES.get('fieldUpgrades', False):
        upgrade_pct = _lookup_field_upgrade_vr(
            (vinfo.vehicleType.shortName or ''))
        if upgrade_pct > 0:
            cap = float(_CFG.get('pickerFieldUpgradeCap', 445.0))
            base_vr = min(base_vr * (1.0 + upgrade_pct), cap)

    # Stage 1: crew amplifier (Rations + BIA, both from base_vr).
    crew_amp = 1.0
    if _PICKER_TOGGLES.get('rations', True):
        crew_amp += float(_CFG.get('pickerVRBonusRations', 1.0430)) - 1.0
    if _PICKER_TOGGLES.get('BIA', True):
        crew_amp += float(_CFG.get('pickerVRBonusBIA', 1.0253)) - 1.0
    crew_amplified = base_vr * crew_amp
    final = crew_amplified

    # Stage 2: equipment + crew-skill bonuses, additive against crew_amplified.
    directive_active = _PICKER_TOGGLES.get('directives', False)
    directive_factor = float(_CFG.get('pickerVRBonusDirective', 1.025)) if directive_active else 1.0

    # Optics from descriptor (Coated Optics basic 1.10, deluxe 1.135, etc).
    optics_factor = float(misc.get('circularVisionRadiusFactor', 1.0)) or 1.0
    if optics_factor > 1.001:
        optics_total = optics_factor * directive_factor
        final += crew_amplified * (optics_total - 1.0)

    # Stereoscope from descriptor (gated by pickerAssumeStereoscope config).
    if _CFG.get('pickerAssumeStereoscope', True):
        _, stereo_factor = _scan_optional_devices(descr)
        if stereo_factor < 1.001 and _has_stereoscope_fallback(descr):
            stereo_factor = float(_CFG.get('pickerStereoscopeFallback', 1.25))
        if stereo_factor > 1.001:
            stereo_total = stereo_factor * directive_factor
            final += crew_amplified * (stereo_total - 1.0)

    # Recon + SitAware bundle (commander + radio op skills).
    if _PICKER_TOGGLES.get('reconSitAware', True):
        rs_factor = float(_CFG.get('pickerVRBonusReconSitAware', 1.0739))
        final += crew_amplified * (rs_factor - 1.0)

    return final


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
    global _LAST_MOVEMENT_TIME
    state = _STATE.get(plugin)
    if state is None:
        return
    veh = _get_player_vehicle()
    if veh is None:
        return
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
        try:
            _refresh_spot_circle(self)
        except Exception:
            _logger.exception('SpotMeter: failed to refresh spot circle')

    def patched_hideMarkup(self):
        try:
            state = _STATE.get(self)
            if state is not None:
                _stop_ticking(self)
                _remove_dyn_circle(self, state)
                _set_active(self, state, False)
        except Exception:
            _logger.exception('SpotMeter: failed to hide spot circle')
        orig_hideMarkup(self)

    def patched_stop(self):
        try:
            _stop_ticking(self)
            state = _STATE.pop(self, None)
            if state is not None:
                state['circleId'] = None
                state['attached'] = False
        except Exception:
            _logger.exception('SpotMeter: failed to clean up on stop')
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
    """Log everything we read from the picked enemy's descriptor.

    Use to verify what the server actually transmits about an enemy. Bound
    to the diagnostic hotkey (pickerDiagDumpKey, default Numpad *).
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
    _logger.warning(
        'SpotMeter: descriptor dump for vid=%s name=%s\n'
        '  turret.circularVisionRadius = %s\n'
        '  miscAttrs.circularVisionRadiusFactor = %s\n'
        '  miscAttrs.invisibilityFactor = %s\n'
        '  miscAttrs.invisibilityBaseAdditive = %s\n'
        '  miscAttrs.invisibilityAdditiveTerm = %s\n'
        '  optionalDevices (%d): %s\n'
        '  enhancements (%d): %s',
        _PICKED_VID, short,
        getattr(descr.turret, 'circularVisionRadius', None),
        misc.get('circularVisionRadiusFactor'),
        misc.get('invisibilityFactor'),
        misc.get('invisibilityBaseAdditive'),
        misc.get('invisibilityAdditiveTerm'),
        len(devices), ', '.join(devices) or '(none)',
        len(enhancements), ' | '.join(enhancements) or '(none)')
    _post_chat_line('diag: dumped %s descriptor to python.log' % short)


def _format_picker_summary(plugin):
    if _PICKED_VID is None:
        return None
    enemies = _enemy_iterator(plugin)
    for vid, vinfo in enemies:
        if vid == _PICKED_VID:
            short = vinfo.vehicleType.shortName if vinfo.vehicleType else '?'
            vr = _picker_vr(plugin)
            vr_str = ('%.0fm' % vr) if vr is not None else '?'
            tags = _active_perk_tags()
            tags_str = (' [+' + ' +'.join(tags) + ']') if tags else ''
            return '%s VR=%s%s' % (short, vr_str, tags_str)
    return None


def _cycle_picker(direction):
    global _PICKED_VID
    plugin = _get_picker_plugin()
    if plugin is None:
        return
    enemies = _enemy_iterator(plugin)
    if not enemies:
        _PICKED_VID = None
        _on_picker_changed(plugin, set())
        return
    vids = [vid for vid, _ in enemies]
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


def _toggle_perk(name):
    if name not in _PICKER_TOGGLES:
        return
    _PICKER_TOGGLES[name] = not _PICKER_TOGGLES[name]
    plugin = _get_picker_plugin()
    _on_picker_changed(plugin, set())
    _post_chat_line('%s: %s' % (name, 'ON' if _PICKER_TOGGLES[name] else 'OFF'))


def _toggle_live_mode():
    """Toggle the auto-refreshing status block. Default OFF; when ON, the
    block is re-posted every liveModeIntervalSec seconds. The chat will
    show a refreshing block; older blocks scroll out naturally.
    """
    global _LIVE_MODE_ENABLED, _LIVE_MODE_CALLBACK_ID
    _LIVE_MODE_ENABLED = not _LIVE_MODE_ENABLED
    plugin = _get_picker_plugin()
    if _LIVE_MODE_ENABLED:
        _post_chat_line('live mode: ON (refresh co %.1fs - Numpad9 zeby wylaczyc)'
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
    """
    if not _CFG.get('overlayEnabled', True):
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
    if _PICKED_VID is None:
        if _CFG.get('useOwnViewRange', True):
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
    lines.append('own:    base_vr=%.0fm * factor=%.3f, camo_add=%.3f, live=%s'
                 % (own_base_vr, own_vr_factor, add_term,
                    'ON' if _LIVE_MODE_ENABLED else 'off'))

    return '\n'.join(lines)


def _post_status_block(plugin):
    """Format and post a status block to the chat. No-op on failure."""
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
    # The classic players panel does not expose a Python-side method for
    # re-rendering individual rows. The hooked PlayerFullNameFormatter is
    # consulted by the panel only on natural redraws (HP changes, death,
    # mode switch), so the marker may not appear instantly. Primary visual
    # feedback comes from the minimap spot circle changing radius.
    return


def _patch_player_name_formatter():
    global _FORMATTER_PATCHED
    if _FORMATTER_PATCHED:
        return
    try:
        from gui.battle_control.arena_info import player_format
    except ImportError:
        _logger.info('SpotMeter: player_format unavailable, skipping picker marker')
        return
    Formatter = getattr(player_format, 'PlayerFullNameFormatter', None)
    if Formatter is None:
        return
    orig_format = Formatter.format
    marker = _CFG.get('pickerMarker', u'● ')

    def patched_format(self, vInfoVO, playerName=None):
        result = orig_format(self, vInfoVO, playerName=playerName)
        try:
            if _PICKED_VID is not None and getattr(vInfoVO, 'vehicleID', None) == _PICKED_VID:
                from gui.battle_control.arena_info.player_format import PlayerFormatResult
                return PlayerFormatResult(
                    marker + result.playerFullName,
                    result.playerName, result.playerFakeName,
                    result.clanAbbrev, result.regionCode, result.vehicleName)
        except Exception:
            _logger.exception('SpotMeter: failed to inject marker')
        return result

    Formatter.format = patched_format
    _FORMATTER_PATCHED = True
    _logger.info('SpotMeter: PlayerFullNameFormatter hooked for marker')


def _install_reload_hotkey():
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
    _key_aliases = {
        'KEY_PRIOR': ['KEY_PGUP'],
        'KEY_NEXT': ['KEY_PGDN'],
        'KEY_PAGEUP': ['KEY_PGUP'],
        'KEY_PAGEDOWN': ['KEY_PGDN'],
        # Numpad -> nav cluster fallbacks for NumLock-off case
        'KEY_NUMPAD0': ['KEY_INSERT'],
        'KEY_NUMPAD1': ['KEY_END'],
        'KEY_NUMPAD2': ['KEY_DOWNARROW', 'KEY_PGDN'],
        'KEY_NUMPAD3': ['KEY_PGDN'],
        'KEY_NUMPAD4': ['KEY_LEFT'],
        'KEY_NUMPAD5': [],
        'KEY_NUMPAD6': ['KEY_RIGHT'],
        'KEY_NUMPAD7': ['KEY_HOME'],
        'KEY_NUMPAD8': ['KEY_UPARROW', 'KEY_PGUP'],
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
        _bind('pickerDirectivesKey',
              lambda: _toggle_perk('directives'), 'directives')
        _bind('pickerFieldUpgradesKey',
              lambda: _toggle_perk('fieldUpgrades'), 'field-upgrades')
        _bind('pickerDiagDumpKey',
              lambda: _dump_picker_descriptor(_get_picker_plugin()),
              'diag-dump')
    if _CFG.get('overlayEnabled', True):
        _bind('overlayToggleKey', _toggle_live_mode, 'live-mode-toggle')
        _bind('overlayPrintNowKey', _print_now, 'status-snapshot')

    if not bindings:
        _logger.warning('SpotMeter: no hotkeys registered (check Keys names in config)')
        return

    def _on_key_event(event):
        if not event.isKeyDown():
            return False
        key = event.key
        for key_id, action, label, _name in bindings:
            if key == key_id:
                try:
                    action()
                except Exception:
                    _logger.exception('SpotMeter: hotkey %s failed', label)
                return False  # don't consume - let other handlers see it too
        return False

    # game.handleKeyEvent dispatches a single key event through BOTH
    # InputHandler.g_instance.handleKeyEvent and the g_keyEventHandlers
    # set. Registering in both fires our action twice per press (ON
    # then immediately OFF for toggles). Pick exactly one channel:
    # prefer g_keyEventHandlers because that's the standard catch-all
    # mod hook iterated last, so it sees keys even when other handlers
    # have already processed them. Fall back to InputHandler.onKeyDown
    # only if g_keyEventHandlers is unavailable for some reason.
    bound_via = None
    try:
        import gui as _gui_mod
        if hasattr(_gui_mod, 'g_keyEventHandlers'):
            _gui_mod.g_keyEventHandlers.add(_on_key_event)
            bound_via = 'gui.g_keyEventHandlers'
    except Exception:
        _logger.exception('SpotMeter: failed to bind via gui.g_keyEventHandlers')

    if bound_via is None:
        try:
            from gui import InputHandler as _IH
            _IH.g_instance.onKeyDown += _on_key_event
            bound_via = 'InputHandler.onKeyDown'
        except Exception:
            _logger.exception('SpotMeter: failed to bind via InputHandler.g_instance.onKeyDown')

    names = ', '.join('%s=%s' % (label, name) for _, _, label, name in bindings)
    _logger.warning('SpotMeter: hotkeys bound via [%s] - %d entries: %s',
                    bound_via or 'NONE', len(bindings), names)
