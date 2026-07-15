# -*- coding: utf-8 -*-
"""SpotMeter v7 in-battle panel - Gameface render layer.

Replaces the GUIFlash/Scaleform panel. Owns ONLY the rendering: registers its
layout via net.openwg.gameface, hosts a Wulf ViewImpl in a panel-sized
WindowImpl on the OVERLAY layer, pushes a JSON `state` string to JS, routes
row/cell clicks + drag back to callbacks the main mod supplies. All spot-distance
math, picker and grouping stays in mod_spotmeter.

Proven in-client (research/spike_gameface v0.0.8):
  - layout id via openwg_gameface.res_id_by_key (guard INVALID_RES_ID)
  - live data: viewModel.transaction() + _setString(0, json); JS reads
    window.model.state and re-renders on viewEnv.onDataChanged
  - commands: _addCommand + _getEvents binding; JS calls
    window.model.<cmd>({param: N}) - arg is an OBJECT keyed by param name.

Drag: chromeless windows have no native drag handle, so JS signals drag
start/end (mousedown on the header / document mouseup) and Python runs a
per-frame loop reading GUI.mcursor and calling window.move (absolute cursor
avoids the moving-view feedback bug). Position persists via the on_move callback.
"""
import json
import logging

_logger = logging.getLogger('SpotMeter.gfpanel')

# Must match the itemID in the shipped res_map JSON + the coui:// HTML path.
LAYOUT_KEY = 'mods/spotmeter/panelLayout'

_available = None          # tri-state probe cache
_layout_id = None          # resolved numeric layout id (None until ready)
_view = None               # live ViewImpl instance
_window = None             # live WindowImpl instance
_on_pick = None            # callable(vid:int)      - a row was clicked
_on_action = None          # callable(key:str)      - a cell/auto control clicked
_on_move = None            # callable(x:int, y:int) - drag ended, persist position
_on_collapse = None        # callable(on:bool)      - collapse arrow toggled
_last_state = None         # last pushed json (skip redundant transactions)
_drag_cb = None            # BigWorld callback id while dragging
_drag_c0 = None            # cursor px at drag start
_drag_w0 = None            # window pos at drag start


def is_available():
    """True when net.openwg.gameface and the Wulf/impl bases can be imported."""
    global _available
    if _available is not None:
        return _available
    try:
        import openwg_gameface  # noqa: F401
        from gui.impl.pub.window_impl import WindowImpl  # noqa: F401
        from frameworks.wulf import ViewFlags  # noqa: F401
        _available = True
    except Exception:
        _logger.warning('SpotMeter: Gameface backend unavailable '
                        '(net.openwg.gameface not installed?) - panel disabled')
        _available = False
    return _available


def set_handlers(on_pick=None, on_action=None, on_move=None, on_collapse=None):
    """Register the callbacks the main mod uses to react to panel input."""
    global _on_pick, _on_action, _on_move, _on_collapse
    _on_pick = on_pick
    _on_action = on_action
    _on_move = on_move
    _on_collapse = on_collapse


def resolve_layout(on_done=None):
    """Resolve our registered layout id (async via openwg on_ready). Triggers
    OpenWG's res_map machinery (hence its one-time restart on first install)."""
    if not is_available():
        if on_done:
            on_done(False)
        return
    try:
        import openwg_gameface
        from gui.impl.gen_utils import INVALID_RES_ID
    except Exception:
        _logger.exception('SpotMeter: openwg import failed')
        if on_done:
            on_done(False)
        return

    def _cb():
        global _layout_id
        try:
            lid = openwg_gameface.res_id_by_key(LAYOUT_KEY)
        except Exception:
            _logger.exception('SpotMeter: res_id_by_key failed')
            lid = INVALID_RES_ID
        if lid == INVALID_RES_ID:
            _logger.warning('SpotMeter: Gameface layout %r not registered '
                            '(res_map missing, or client not restarted yet)',
                            LAYOUT_KEY)
            if on_done:
                on_done(False)
            return
        _layout_id = lid
        _logger.info('SpotMeter: Gameface panel layout resolved (id=%s)', lid)
        if on_done:
            on_done(True)

    try:
        openwg_gameface.on_ready(_cb)
    except Exception:
        _logger.exception('SpotMeter: openwg on_ready failed')
        if on_done:
            on_done(False)


def is_active():
    return _window is not None


def _extract(payload, key):
    """Pull a value out of the {key: value} object JS marshals to a command."""
    try:
        if isinstance(payload, dict):
            return payload.get(key)
    except Exception:
        pass
    return None


# --- drag (chromeless window, Python-side cursor tracking) ------------------ #

def _win_pos():
    p = _window.position
    try:
        return (float(p.x), float(p.y))
    except Exception:
        return (float(p[0]), float(p[1]))


def _cursor_px():
    """Absolute cursor position in physical pixels."""
    import GUI
    res = GUI.screenResolution()
    w = float(res[0])
    h = float(res[1])
    pos = GUI.mcursor().position   # normalized clip space [-1, 1], y up
    return ((pos.x * 0.5 + 0.5) * w, (0.5 - pos.y * 0.5) * h)


def _left_mouse_down():
    try:
        import BigWorld
        import Keys
        return bool(BigWorld.isKeyDown(Keys.KEY_LEFTMOUSE))
    except Exception:
        return True


def _drag_start():
    global _drag_c0, _drag_w0
    if _window is None:
        return
    try:
        _drag_c0 = _cursor_px()
        _drag_w0 = _win_pos()
    except Exception:
        _logger.exception('SpotMeter: drag start failed')
        _drag_c0 = None
        return
    _logger.info('SpotMeter: panel drag start cursor=%s win=%s', _drag_c0, _drag_w0)
    _drag_tick()


def _drag_tick():
    global _drag_cb
    _drag_cb = None
    if _window is None or _drag_c0 is None:
        return
    if not _left_mouse_down():   # recover from a lost mouse-up
        _drag_end()
        return
    try:
        cx, cy = _cursor_px()
        nx = int(_drag_w0[0] + (cx - _drag_c0[0]))
        ny = int(_drag_w0[1] + (cy - _drag_c0[1]))
        _window.move(nx, ny)
    except Exception:
        _logger.exception('SpotMeter: drag tick failed')
        return
    try:
        import BigWorld
        _drag_cb = BigWorld.callback(0.0, _drag_tick)
    except Exception:
        pass


def _drag_end():
    global _drag_cb, _drag_c0
    if _drag_cb is not None:
        try:
            import BigWorld
            BigWorld.cancelCallback(_drag_cb)
        except Exception:
            pass
        _drag_cb = None
    was_dragging = _drag_c0 is not None
    _drag_c0 = None
    if was_dragging and _window is not None and _on_move is not None:
        try:
            x, y = _win_pos()
            _on_move(int(x), int(y))
            _logger.info('SpotMeter: panel drag end -> saved (%d,%d)', int(x), int(y))
        except Exception:
            _logger.exception('SpotMeter: drag end persist failed')


def _build_view():
    """Create the ViewImpl + ViewModel classes (needs in-client Wulf imports)."""
    from frameworks.wulf import ViewSettings, ViewFlags, ViewModel
    from gui.impl.pub.view_impl import ViewImpl

    class _PanelVM(ViewModel):
        def __init__(self):
            super(_PanelVM, self).__init__(properties=1, commands=5)

        def _initialize(self):
            super(_PanelVM, self)._initialize()
            self._addStringProperty('state', '{}')
            self.onRowClick = self._addCommand('onRowClick')
            self.onAction = self._addCommand('onAction')
            self.onDrag = self._addCommand('onDrag')
            self.onCollapse = self._addCommand('onCollapse')
            self.onReady = self._addCommand('onReady')

        def set_state(self, s):
            with self.transaction() as m:
                m._setString(0, s)

    class _PanelView(ViewImpl):
        def __init__(self):
            super(_PanelView, self).__init__(
                ViewSettings(_layout_id, ViewFlags.VIEW, _PanelVM()))

        @property
        def viewModel(self):
            return super(_PanelView, self).getViewModel()

        def _getEvents(self):
            vm = self.viewModel
            return (
                (vm.onRowClick, self._handle_row_click),
                (vm.onAction, self._handle_action),
                (vm.onDrag, self._handle_drag),
                (vm.onCollapse, self._handle_collapse),
            )

        def _handle_row_click(self, payload=None, *a, **k):
            vid = _extract(payload, 'vid')
            if vid is None or _on_pick is None:
                return
            try:
                _on_pick(int(vid))
            except Exception:
                _logger.exception('SpotMeter: on_pick handler failed')

        def _handle_action(self, payload=None, *a, **k):
            key = _extract(payload, 'key')
            if key is None or _on_action is None:
                return
            try:
                _on_action(str(key))
            except Exception:
                _logger.exception('SpotMeter: on_action handler failed')

        def _handle_drag(self, payload=None, *a, **k):
            phase = _extract(payload, 'phase')
            try:
                if phase == 'start':
                    _drag_start()
                elif phase == 'end':
                    _drag_end()
            except Exception:
                _logger.exception('SpotMeter: drag %s failed', phase)

        def _handle_collapse(self, payload=None, *a, **k):
            if _on_collapse is None:
                return
            try:
                _on_collapse(bool(_extract(payload, 'on')))
            except Exception:
                _logger.exception('SpotMeter: on_collapse handler failed')

    return _PanelView


def show(x=None, y=None):
    """Create + load the panel window (idempotent). Returns True if a window is
    active afterwards. Requires resolve_layout() to have succeeded + the main
    window to be LOADED."""
    global _view, _window, _last_state
    if _window is not None:
        return True
    if _layout_id is None:
        _logger.warning('SpotMeter: show() before layout resolved - ignored')
        return False
    try:
        from frameworks.wulf import WindowStatus
        try:
            from frameworks.wulf import WindowFlags, WindowLayer
        except Exception:
            from frameworks.wulf.gui_constants import WindowFlags, WindowLayer
        from gui.impl.pub.window_impl import WindowImpl
        from helpers import dependency
        from skeletons.gui.impl import IGuiLoader
    except Exception:
        _logger.exception('SpotMeter: Gameface window imports failed')
        return False

    gui = dependency.instance(IGuiLoader)
    main_window = gui.windowsManager.getMainWindow() if gui else None
    if main_window is None or main_window.windowStatus != WindowStatus.LOADED:
        _logger.warning('SpotMeter: main window not ready for panel')
        return False

    try:
        _view = _build_view()()
        _last_state = None
        _window = WindowImpl(WindowFlags.WINDOW, layer=WindowLayer.OVERLAY,
                             content=_view, parent=main_window)
        if x is not None and y is not None:
            _window.onStatusChanged += _make_move_once(float(x), float(y))
        _window.load()
        _logger.info('SpotMeter: Gameface panel shown')
        return True
    except Exception:
        _logger.exception('SpotMeter: failed to create Gameface panel window')
        _view = None
        _window = None
        return False


def _make_move_once(x, y):
    from frameworks.wulf import WindowStatus

    def _cb(status):
        if status == WindowStatus.LOADED and _window is not None:
            try:
                _window.move(int(x), int(y))
            except Exception:
                _logger.exception('SpotMeter: panel move failed')
    return _cb


def push_state(state):
    """Serialize `state` (a dict) and push it to the view. No-op if not active
    or identical to the last push (avoids redundant transactions)."""
    global _last_state
    if _view is None:
        return
    try:
        s = json.dumps(state)
    except Exception:
        _logger.exception('SpotMeter: state serialization failed')
        return
    if s == _last_state:
        return
    _last_state = s
    try:
        _view.viewModel.set_state(s)
    except Exception:
        _logger.exception('SpotMeter: panel set_state failed')


def hide():
    """Destroy the panel window (safe to call when not active)."""
    global _view, _window, _last_state
    _drag_end()
    w = _window
    _window = None
    _view = None
    _last_state = None
    if w is not None:
        try:
            w.destroy()
        except Exception:
            _logger.exception('SpotMeter: panel destroy failed')


# space-leave / battle teardown alias
destroy = hide
