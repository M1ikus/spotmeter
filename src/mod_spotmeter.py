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
MOD_VERSION = '5.3.4'
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
    'pickerClearKey': 'KEY_NUMPAD0',
    # Per-perk toggle keys
    'pickerRationsKey': 'KEY_NUMPAD1',
    'pickerVentsKey': 'KEY_NUMPAD3',
    'pickerBIAKey': 'KEY_NUMPAD4',
    'pickerReconKey': 'KEY_NUMPAD5',
    'pickerSitAwareKey': 'KEY_NUMPAD6',
    'pickerStereoKey': 'KEY_NUMPAD7',
    # Picker VR multipliers. Game-UI-matching additive model: baseline =
    # base_vr * rations_factor (if rations on) or base_vr (off), and each
    # other toggle adds baseline * (factor - 1). Default factors are
    # calibrated against in-game observations on a 340m base tank with
    # 100% trained crew, so the per-toggle bonus the picker computes
    # matches what the hangar UI shows for the same setup.
    'pickerVRBonusRations':  1.0430,   # vs pure base
    'pickerVRBonusBIA':      1.0243,   # vs base+rations baseline
    'pickerVRBonusVents':    1.0243,   # assumed (no direct measurement)
    'pickerVRBonusRecon':    1.0277,
    'pickerVRBonusSitAware': 1.0433,
    'pickerAssumeStereoscope': True,
    'pickerStereoscopeFallback': 1.25,
    'pickerMarker': u'● ',
    'pickerIncludeDeadEnemies': False,
    'pickerDiagDumpKey': 'KEY_NUMPADSTAR',
    # v5 overlay
    'overlayEnabled': True,
    'overlayToggleKey': 'KEY_NUMPAD9',
    'overlayShowOnTickChange': True,
    'overlayMinRadiusDelta': 15.0,
    'overlayPrintNowKey': 'KEY_NUMPADENTER',
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
    'rations': False,
    'vents': False,
    'bia': False,
    'recon': False,
    'sitAware': False,
}
_OVERLAY_ENABLED_RUNTIME = True
_LAST_OVERLAY_RADIUS = 0.0
_LAST_OVERLAY_STATE = None


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
    # Game-UI-matching additive bonus model. baseline = base_vr if rations
    # is off, base_vr * rations_factor if rations is on. Each other toggle
    # adds a bonus = baseline * (factor - 1). All bonuses are summed to
    # form the total VR.
    #
    # Mirrors WoT's hangar UI exactly: rations applies first to the base,
    # then each remaining toggle's bonus is presented as a percentage of
    # the (base + rations) state.
    #
    # Verified on user setup (340m base + BIA + Rations + Recon + SitAware
    # + deluxe optics):
    #     340 + 14.62 + 47.87 + 8.61 + 9.82 + 15.36 = 436.28 m
    # vs in-game 436 m.
    rations_factor = float(_CFG.get('pickerVRBonusRations', 1.043))
    if _PICKER_TOGGLES.get('rations', False):
        baseline = base_vr * rations_factor
    else:
        baseline = base_vr
    final = baseline
    # Optics bonus from descriptor factor (Coated Optics / deluxe / etc).
    optics_factor = float(misc.get('circularVisionRadiusFactor', 1.0)) or 1.0
    if optics_factor > 1.001:
        final += baseline * (optics_factor - 1.0)
    # Stereoscope bonus (auto from descriptor, gated by toggle).
    if _CFG.get('pickerAssumeStereoscope', True):
        _, stereo_factor = _scan_optional_devices(descr)
        if stereo_factor > 1.001:
            final += baseline * (stereo_factor - 1.0)
        elif _has_stereoscope_fallback(descr):
            final += baseline * (float(_CFG.get('pickerStereoscopeFallback', 1.25)) - 1.0)
    # Manual toggles. Factors are baseline-relative (i.e. how the game
    # shows them when measured against base+rations). Defaults from
    # in-game observations on a 340m base tank.
    perk_keys = (
        ('bia',      'pickerVRBonusBIA',      1.0243),
        ('vents',    'pickerVRBonusVents',    1.0243),
        ('recon',    'pickerVRBonusRecon',    1.0277),
        ('sitAware', 'pickerVRBonusSitAware', 1.0433),
    )
    for toggle_name, cfg_key, default_factor in perk_keys:
        if _PICKER_TOGGLES.get(toggle_name, False):
            factor = float(_CFG.get(cfg_key, default_factor))
            final += baseline * (factor - 1.0)
    return final


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
        _maybe_post_tick_overlay(plugin, radius, new_state)
        return
    if after_shot:
        if abs(radius - state['lastRadius']) > 0.1:
            _update_dyn_circle(plugin, state, radius)
        _maybe_post_tick_overlay(plugin, radius, new_state)
        return
    if abs(radius - state['lastRadius']) > 0.5:
        _update_dyn_circle(plugin, state, radius)
    _maybe_post_tick_overlay(plugin, radius, new_state)


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
        'rations': 'rations',
        'vents': 'vents',
        'bia': 'BIA',
        'recon': 'recon',
        'sitAware': 'sitAware',
    }
    order = ('rations', 'vents', 'bia', 'recon', 'sitAware')
    return [tag_map[k] for k in order if _PICKER_TOGGLES.get(k, False)]


def _dump_picker_descriptor(plugin):
    """Log everything we read from the picked enemy's descriptor.

    Use to verify what the server actually transmits about an enemy. Bound
    to the diagnostic hotkey (pickerDiagDumpKey, default Numpad *).
    """
    if _PICKED_VID is None:
        _logger.warning('SpotMeter: dump requested but no target picked')
        _post_chat_overlay(plugin, force=True, prefix='diag: no picker target')
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
    _post_chat_overlay(plugin, force=True,
                       prefix='diag: dumped %s descriptor to python.log' % short)


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
    _post_chat_overlay(plugin, force=True, prefix='%s: %s' % (name, 'ON' if _PICKER_TOGGLES[name] else 'OFF'))


def _toggle_stereoscope():
    _CFG['pickerAssumeStereoscope'] = not _CFG.get('pickerAssumeStereoscope', True)
    plugin = _get_picker_plugin()
    _on_picker_changed(plugin, set())
    _post_chat_overlay(plugin, force=True,
                       prefix='stereoscope: %s' % ('ON' if _CFG['pickerAssumeStereoscope'] else 'OFF'))


def _toggle_overlay():
    global _OVERLAY_ENABLED_RUNTIME
    _OVERLAY_ENABLED_RUNTIME = not _OVERLAY_ENABLED_RUNTIME
    plugin = _get_picker_plugin()
    _post_chat_overlay(plugin, force=True,
                       prefix='overlay: %s' % ('ON' if _OVERLAY_ENABLED_RUNTIME else 'OFF'))


def _print_now():
    """Show a full status snapshot - all toggles, picker target, computed values."""
    plugin = _get_picker_plugin()
    if plugin is None:
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
    after_shot = _is_after_shot()
    camo_net_active = (not is_moving) and _is_camo_net_active(veh, is_moving) and _has_camo_net(veh)
    state_name = _classify_state(is_moving, after_shot, camo_net_active)
    camo = _compute_camo(veh, is_moving, after_shot, camo_net_active)
    enemy_vr = _resolve_enemy_view_range(plugin)
    radius = _compute_spot_radius(camo, enemy_vr)

    lines = ['[SpotMeter] STATUS:']
    state_label = {
        'moving': 'ruch',
        'still': 'postoj',
        'stillNet': 'siatka aktywna',
        'afterShot': 'po strzale',
    }.get(state_name, state_name)
    lines.append('  state=%s, camo=%.3f, vr=%.0fm -> spot=%.0fm'
                 % (state_label, camo, enemy_vr, radius))
    # Own-tank descriptor breakdown - shows whether crew skills, equipment
    # and field upgrades (vehPostProgression) are baked into miscAttrs.
    # If invisibilityBaseAdditive > 0 or invisibilityMultFactor != 1 you
    # have field-upgrade modifiers active; descr is being built with extData.
    descr = veh.typeDescriptor
    invMov, invStill = descr.type.invisibility
    misc = getattr(descr, 'miscAttrs', None) or {}
    lines.append(
        '  myCamo: base(mov=%.3f,still=%.3f) * turret=%.2f * crew=%.2f + add=%.3f'
        % (invMov, invStill,
           misc.get('invisibilityFactor', 1.0),
           float(_CFG.get('crewCamoBonus', 1.0)),
           misc.get('invisibilityBaseAdditive', 0.0) + misc.get('invisibilityAdditiveTerm', 0.0)))
    own_vr_factor = misc.get('circularVisionRadiusFactor', 1.0)
    own_base_vr = getattr(descr.turret, 'circularVisionRadius', 0.0)
    lines.append(
        '  myVR: base=%.0fm * factor=%.3f (factor>1 = optyka/lorna/ulepsz. polowe naliczone)'
        % (own_base_vr, own_vr_factor))
    lines.append('  kara-strzal=%s, overlay-tekstu=%s'
                 % ('ON' if after_shot else 'off',
                    'ON' if _OVERLAY_ENABLED_RUNTIME else 'off'))
    if _PICKED_VID is None:
        if _CFG.get('useOwnViewRange', True):
            lines.append('  picker: NONE (using own VR)')
        else:
            lines.append('  picker: NONE (using fallback VR=%.0fm)'
                         % _CFG.get('enemyViewRangeFallback', 445.0))
    else:
        summary = _format_picker_summary(plugin) or '?'
        lines.append('  picker: %s' % summary)
        tags = _active_perk_tags()
        lines.append('  perki=%s, lornetka-enemy(zal.)=%s'
                     % ('+'.join(tags) if tags else 'brak',
                        'ON' if _CFG.get('pickerAssumeStereoscope', True) else 'off'))
    text = '\n'.join(lines)
    try:
        from messenger.MessengerEntry import g_instance as _messengerEntry
        _messengerEntry.gui.addClientMessage(text, isCurrentPlayer=True)
    except Exception:
        _logger.exception('SpotMeter: failed to push status overlay')


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
    _post_chat_overlay(plugin, force=True)


def _format_overlay_text(plugin, radius, state_name, enemy_vr, prefix=None):
    parts = []
    if prefix:
        parts.append('[SpotMeter] ' + prefix)
    state_label = {
        'moving': 'ruch',
        'still': 'postoj',
        'stillNet': 'siatka',
        'afterShot': 'po strzale',
    }.get(state_name, state_name)
    spot_str = '%.0f m' % radius
    vr_str = '%.0f m' % enemy_vr
    body = '[SpotMeter] Spot: %s (%s, vs VR %s)' % (spot_str, state_label, vr_str)
    if _PICKED_VID is not None and plugin is not None:
        summary = _format_picker_summary(plugin)
        if summary:
            body += ' | target: ' + summary
    parts.append(body)
    return '\n'.join(parts)


def _post_chat_overlay(plugin, force=False, prefix=None):
    if not _CFG.get('overlayEnabled', True):
        return
    if not _OVERLAY_ENABLED_RUNTIME and not force:
        return
    if plugin is None:
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
    after_shot = _is_after_shot()
    camo_net_active = (not is_moving) and _is_camo_net_active(veh, is_moving) and _has_camo_net(veh)
    state_name = _classify_state(is_moving, after_shot, camo_net_active)
    camo = _compute_camo(veh, is_moving, after_shot, camo_net_active)
    enemy_vr = _resolve_enemy_view_range(plugin)
    radius = _compute_spot_radius(camo, enemy_vr)
    text = _format_overlay_text(plugin, radius, state_name, enemy_vr, prefix=prefix)
    try:
        from messenger.MessengerEntry import g_instance as _messengerEntry
        _messengerEntry.gui.addClientMessage(text, isCurrentPlayer=True)
    except Exception:
        _logger.exception('SpotMeter: failed to push overlay message')


def _maybe_post_tick_overlay(plugin, radius, state_name):
    global _LAST_OVERLAY_RADIUS, _LAST_OVERLAY_STATE
    if not _CFG.get('overlayEnabled', True):
        return
    if not _OVERLAY_ENABLED_RUNTIME:
        return
    if not _CFG.get('overlayShowOnTickChange', True):
        return
    delta = float(_CFG.get('overlayMinRadiusDelta', 15.0))
    if state_name == _LAST_OVERLAY_STATE and abs(radius - _LAST_OVERLAY_RADIUS) < delta:
        return
    _LAST_OVERLAY_RADIUS = radius
    _LAST_OVERLAY_STATE = state_name
    _post_chat_overlay(plugin)


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
        _bind('pickerRationsKey', lambda: _toggle_perk('rations'), 'rations')
        _bind('pickerVentsKey', lambda: _toggle_perk('vents'), 'vents')
        _bind('pickerBIAKey', lambda: _toggle_perk('bia'), 'bia')
        _bind('pickerReconKey', lambda: _toggle_perk('recon'), 'recon')
        _bind('pickerSitAwareKey', lambda: _toggle_perk('sitAware'), 'sitAware')
        _bind('pickerStereoKey', _toggle_stereoscope, 'stereoscope')
        _bind('pickerDiagDumpKey',
              lambda: _dump_picker_descriptor(_get_picker_plugin()),
              'diag-dump')
    if _CFG.get('overlayEnabled', True):
        _bind('overlayToggleKey', _toggle_overlay, 'overlay-toggle')
        _bind('overlayPrintNowKey', _print_now, 'status')

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
