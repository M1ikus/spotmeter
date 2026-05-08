# -*- coding: utf-8 -*-
# WoT mod: Spot Circle on minimap
# Adds an extra dynamic circle to the player's minimap showing the distance from
# which the player's tank can be spotted by an enemy with the configured view range.
# Works alongside the game's existing view-range circles (does not replace them).
#
# Loader entry: scripts/client/gui/mods/mod_spot_circle.pyc
# Game version: World of Tanks 2.2.1.2 (Python 2.7 bytecode)
import json
import logging
import weakref

import BigWorld
from constants import VISIBILITY
from gui.Scaleform.daapi.view.battle.shared.minimap import plugins as _mm_plugins
from gui.Scaleform.daapi.view.battle.shared.minimap import settings as _mm_settings
from gui.battle_control import matrix_factory

_logger = logging.getLogger('SpotCircleMod')

_S_NAME = _mm_settings.ENTRY_SYMBOL_NAME
_C_NAME = _mm_settings.CONTAINER_NAME
_AS3 = _mm_settings.VIEW_RANGE_CIRCLES_AS3_DESCR

_CONFIG_CANDIDATES = (
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
    'alpha': 70,
    'tickInterval': 0.2,
    'movingSpeedThreshold': 0.5,
    'applyFirePenalty': True,
    'fireRevealDuration': 3.0,
    'logCalcDetails': False,
    'reloadKey': 'KEY_F8',
    # v4 picker
    'pickerEnabled': True,
    'pickerNextKey': 'KEY_NEXT',
    'pickerPrevKey': 'KEY_PRIOR',
    'pickerClearKey': 'KEY_HOME',
    'pickerRationsKey': 'KEY_DELETE',
    'pickerPerksKey': 'KEY_END',
    'pickerVRBonusRations': 1.10,
    'pickerVRBonusPerks': 1.10,
    'pickerMarker': u'● ',
    'pickerIncludeDeadEnemies': False,
}

_CFG = dict(DEFAULT_CONFIG)
_PATCHED = False
_AVATAR_PATCHED = False
_FORMATTER_PATCHED = False
_STATE = weakref.WeakKeyDictionary()
_LAST_SHOT_TIME = 0.0
_PICKED_VID = None
_PICKER_RATIONS = False
_PICKER_PERKS = False


def _read_config():
    for path in _CONFIG_CANDIDATES:
        try:
            with open(path, 'rb') as fh:
                payload = json.load(fh)
            if isinstance(payload, dict):
                for k, v in payload.iteritems():
                    if k in DEFAULT_CONFIG:
                        _CFG[k] = v
                _logger.info('SpotCircleMod: config loaded from %s', path)
                return
        except IOError:
            continue
        except (ValueError, KeyError) as exc:
            _logger.warning('SpotCircleMod: bad config at %s: %s', path, exc)
            return
    _logger.info('SpotCircleMod: no config file found, using defaults')


def init():
    try:
        _read_config()
        if not _CFG.get('enabled', True):
            _logger.info('SpotCircleMod: disabled by config')
            return
        _patch_plugin()
        _patch_avatar_shoot()
        if _CFG.get('pickerEnabled', True):
            _patch_player_name_formatter()
        _install_reload_hotkey()
        _logger.info('SpotCircleMod: initialised (useOwnViewRange=%s, fire=%s, picker=%s)',
                     _CFG['useOwnViewRange'], _CFG['applyFirePenalty'], _CFG['pickerEnabled'])
    except Exception:
        _logger.exception('SpotCircleMod: init failed')


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


def _compute_camo(vehicle, is_moving, after_shot):
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
    camo = max(0.0, (base + base_additive + additive_term) * mult_factor)
    if after_shot:
        # invisibilityFactorAtShot comes from the gun (e.g. ~0.75 for tank guns,
        # ~0.25-0.5 for big TD guns). Mirrors params.py: moving * factorAtShot.
        factor = misc.get('invisibilityFactorAtShot', 1.0)
        if factor < 1.0:
            camo *= factor
    if camo > 0.99:
        camo = 0.99
    return camo


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
        _logger.exception('SpotCircleMod: failed to decode descriptor for picked vid=%s', _PICKED_VID)
        return None
    try:
        base_vr = float(descr.turret.circularVisionRadius)
    except Exception:
        return None
    misc = getattr(descr, 'miscAttrs', None) or {}
    factor = float(misc.get('circularVisionRadiusFactor', 1.0)) or 1.0
    vr = base_vr * factor
    if _PICKER_RATIONS:
        vr *= float(_CFG.get('pickerVRBonusRations', 1.10))
    if _PICKER_PERKS:
        vr *= float(_CFG.get('pickerVRBonusPerks', 1.10))
    return vr


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


def _classify_state(is_moving, after_shot):
    if after_shot:
        return 'afterShot'
    return 'moving' if is_moving else 'still'


def _color_for_state(state_name):
    if state_name == 'afterShot':
        return _CFG['colorAfterShot']
    if state_name == 'moving':
        return _CFG['colorMoving']
    return _CFG['colorStill']


def _tick(plugin):
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
    after_shot = _is_after_shot()
    new_state = _classify_state(is_moving, after_shot)
    camo = _compute_camo(veh, is_moving, after_shot)
    enemy_vr = _resolve_enemy_view_range(plugin)
    radius = _compute_spot_radius(camo, enemy_vr)
    color = _color_for_state(new_state)
    if _CFG.get('logCalcDetails'):
        _logger.info('SpotCircleMod: state=%s camo=%.3f vr=%.1fm radius=%.1fm',
                     new_state, camo, enemy_vr, radius)
    state_changed = new_state != state['lastState']
    if state_changed:
        if state['attached']:
            _remove_dyn_circle(plugin, state)
        _add_dyn_circle(plugin, state, color, radius)
        state['lastState'] = new_state
        return
    if after_shot:
        # During the fire-reveal window the radius shrinks/grows quickly as
        # the penalty applies — keep updating every tick rather than waiting
        # for the next state transition.
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
            _logger.exception('SpotCircleMod: tick failed')
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
            _logger.exception('SpotCircleMod: failed to refresh spot circle')

    def patched_hideMarkup(self):
        try:
            state = _STATE.get(self)
            if state is not None:
                _stop_ticking(self)
                _remove_dyn_circle(self, state)
                _set_active(self, state, False)
        except Exception:
            _logger.exception('SpotCircleMod: failed to hide spot circle')
        orig_hideMarkup(self)

    def patched_stop(self):
        try:
            _stop_ticking(self)
            state = _STATE.pop(self, None)
            if state is not None:
                state['circleId'] = None
                state['attached'] = False
        except Exception:
            _logger.exception('SpotCircleMod: failed to clean up on stop')
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
                _logger.exception('SpotCircleMod: postmortem cleanup failed')
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
        _logger.info('SpotCircleMod: Avatar module unavailable, fire penalty disabled')
        return
    AvatarCls = getattr(_avatar_module, 'PlayerAvatar', None) or getattr(_avatar_module, 'Avatar', None)
    if AvatarCls is None:
        _logger.info('SpotCircleMod: Avatar class not found, fire penalty disabled')
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
                _logger.exception('SpotCircleMod: failed to record shot')
            return result
        AvatarCls.shoot = patched_shoot

    if orig_shootDualGun is not None:
        def patched_shootDualGun(self, chargeActionType, isPrepared=False, isRepeat=False):
            result = orig_shootDualGun(self, chargeActionType, isPrepared=isPrepared, isRepeat=isRepeat)
            try:
                _record_shot()
            except Exception:
                _logger.exception('SpotCircleMod: failed to record dual-gun shot')
            return result
        AvatarCls.shootDualGun = patched_shootDualGun

    _AVATAR_PATCHED = True
    _logger.info('SpotCircleMod: Avatar.shoot hooked for fire penalty')


def _hot_reload():
    _logger.info('SpotCircleMod: hot-reloading config')
    _read_config()
    _force_panel_refresh()
    for plugin in list(_STATE.keys()):
        try:
            _refresh_spot_circle(plugin)
        except Exception:
            _logger.exception('SpotCircleMod: failed to refresh after reload')


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
        _logger.exception('SpotCircleMod: failed to enumerate enemies')
        return []
    items.sort(key=lambda kv: (-(kv[1].vehicleType.level or 0), kv[1].vehicleType.shortName, kv[0]))
    return items


def _format_picker_summary(plugin):
    if _PICKED_VID is None:
        return None
    enemies = _enemy_iterator(plugin)
    for vid, vinfo in enemies:
        if vid == _PICKED_VID:
            short = vinfo.vehicleType.shortName if vinfo.vehicleType else '?'
            vr = _picker_vr(plugin)
            vr_str = ('%.0fm' % vr) if vr is not None else '?'
            tags = []
            if _PICKER_RATIONS:
                tags.append('+rations')
            if _PICKER_PERKS:
                tags.append('+perks')
            tags_str = (' [' + ' '.join(tags) + ']') if tags else ''
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


def _toggle_rations():
    global _PICKER_RATIONS
    _PICKER_RATIONS = not _PICKER_RATIONS
    plugin = _get_picker_plugin()
    _on_picker_changed(plugin, set())


def _toggle_perks():
    global _PICKER_PERKS
    _PICKER_PERKS = not _PICKER_PERKS
    plugin = _get_picker_plugin()
    _on_picker_changed(plugin, set())


def _on_picker_changed(plugin, affected_vids):
    summary = _format_picker_summary(plugin) if plugin is not None else None
    _logger.info('SpotCircleMod: picker -> %s | rations=%s perks=%s',
                 summary or 'none', _PICKER_RATIONS, _PICKER_PERKS)
    _force_panel_refresh(affected_vids)
    if plugin is not None:
        try:
            _tick(plugin)
        except Exception:
            _logger.exception('SpotCircleMod: tick after picker change failed')


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
        _logger.info('SpotCircleMod: player_format unavailable, skipping picker marker')
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
            _logger.exception('SpotCircleMod: failed to inject marker')
        return result

    Formatter.format = patched_format
    _FORMATTER_PATCHED = True
    _logger.info('SpotCircleMod: PlayerFullNameFormatter hooked for marker')


def _install_reload_hotkey():
    try:
        import Keys
        from gui import InputHandler
    except ImportError:
        _logger.info('SpotCircleMod: hotkey support unavailable, edits to config require battle restart')
        return

    bindings = []

    def _bind(cfg_key, action, label):
        key_name = _CFG.get(cfg_key) or ''
        key_id = getattr(Keys, key_name, None) if key_name else None
        if key_id is None:
            return
        bindings.append((key_id, action, label, key_name))

    _bind('reloadKey', _hot_reload, 'reload')
    if _CFG.get('pickerEnabled', True):
        _bind('pickerNextKey', lambda: _cycle_picker(+1), 'picker-next')
        _bind('pickerPrevKey', lambda: _cycle_picker(-1), 'picker-prev')
        _bind('pickerClearKey', _clear_picker, 'picker-clear')
        _bind('pickerRationsKey', _toggle_rations, 'picker-rations')
        _bind('pickerPerksKey', _toggle_perks, 'picker-perks')

    if not bindings:
        _logger.info('SpotCircleMod: no hotkeys registered')
        return

    def _on_key(event):
        if not event.isKeyDown():
            return
        key = event.key
        for key_id, action, label, _name in bindings:
            if key == key_id:
                try:
                    action()
                except Exception:
                    _logger.exception('SpotCircleMod: hotkey %s failed', label)
                return

    try:
        InputHandler.g_instance.onKeyDown += _on_key
        names = ', '.join('%s=%s' % (label, name) for _, _, label, name in bindings)
        _logger.info('SpotCircleMod: hotkeys bound (%s)', names)
    except Exception:
        _logger.exception('SpotCircleMod: cannot bind hotkeys')
