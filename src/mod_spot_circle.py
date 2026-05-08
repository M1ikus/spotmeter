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
    'alpha': 70,
    'tickInterval': 0.2,
    'movingSpeedThreshold': 0.5,
    'logCalcDetails': False,
    'reloadKey': 'KEY_F8',
}

_CFG = dict(DEFAULT_CONFIG)
_PATCHED = False
_STATE = weakref.WeakKeyDictionary()


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
        _install_reload_hotkey()
        _logger.info('SpotCircleMod: initialised (useOwnViewRange=%s)',
                     _CFG['useOwnViewRange'])
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


def _compute_camo(vehicle, is_moving):
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
    if camo > 0.99:
        camo = 0.99
    return camo


def _resolve_enemy_view_range(plugin):
    # Returns raw VR; do NOT clamp here. The 445 m hard cap applies to the
    # FINAL spot distance, not to the input VR. A tank with 500 m VR and a
    # low-camo target still spots at 445 m (capped output), but the extra
    # VR above 445 m provides buffer against the target's camo.
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
    new_state = 'moving' if is_moving else 'still'
    camo = _compute_camo(veh, is_moving)
    enemy_vr = _resolve_enemy_view_range(plugin)
    radius = _compute_spot_radius(camo, enemy_vr)
    color = _CFG['colorMoving'] if is_moving else _CFG['colorStill']
    if _CFG.get('logCalcDetails'):
        _logger.info('SpotCircleMod: state=%s camo=%.3f vr=%.1fm radius=%.1fm',
                     new_state, camo, enemy_vr, radius)
    if new_state != state['lastState']:
        if state['attached']:
            _remove_dyn_circle(plugin, state)
        _add_dyn_circle(plugin, state, color, radius)
        state['lastState'] = new_state
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


def _hot_reload():
    _logger.info('SpotCircleMod: hot-reloading config')
    _read_config()
    for plugin in list(_STATE.keys()):
        try:
            _refresh_spot_circle(plugin)
        except Exception:
            _logger.exception('SpotCircleMod: failed to refresh after reload')


def _install_reload_hotkey():
    try:
        import Keys
        from gui import InputHandler
    except ImportError:
        _logger.info('SpotCircleMod: hotkey support unavailable, edits to config require battle restart')
        return
    key_name = _CFG.get('reloadKey') or ''
    key_id = getattr(Keys, key_name, None) if key_name else None
    if key_id is None:
        _logger.info('SpotCircleMod: reloadKey %r not recognised, skipping hotkey', key_name)
        return

    def _on_key(event):
        if event.isKeyDown() and event.key == key_id:
            _hot_reload()

    try:
        InputHandler.g_instance.onKeyDown += _on_key
        _logger.info('SpotCircleMod: hot-reload bound to %s', key_name)
    except Exception:
        _logger.exception('SpotCircleMod: cannot bind hotkey')
