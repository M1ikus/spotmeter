# -*- coding: utf-8 -*-
# SpotMeter's private GUIFlash fork - main module.
# Adapted from gambiter.guiflash 0.6.4 / flash.py (MIT).
#
# Notable changes vs upstream:
#   - VIEW_ALIAS / FILE_NAME point at our bundled spotmeter_guiflash.swf
#     so this coexists with a user-installed gambiter.guiflash.wotmod
#     (each Scaleform view gets its own ApplicationDomain, but the
#     ViewSettings registry is global - distinct aliases keep them apart).
#   - COMPONENT_EVENT.CLICKED added. The forked SWF's UIComponentEx fires
#     `py_update(alias, {_click: true})` on mouse click; we decode that
#     sentinel here and re-emit as a dedicated event so client code can
#     subscribe without sniffing dict keys.
#   - getParentWindow / LOG_* helpers live in our spotmeter_gf.utils.

__all__ = ['COMPONENT_TYPE', 'COMPONENT_ALIGN', 'COMPONENT_EVENT', 'GUIFlash']

import codecs
import json
import BigWorld
import GUI
import BattleReplay
import Event
from frameworks.wulf import WindowLayer
from gui import g_guiResetters
from gui.Scaleform.framework import g_entitiesFactories, ScopeTemplates, ViewSettings
from gui.Scaleform.framework.entities.View import View
from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
from gui.shared import EVENT_BUS_SCOPE, events, g_eventBus
from gui.shared.personality import ServicesLocator
from helpers import dependency
from skeletons.gui.app_loader import GuiGlobalSpaceID as SPACE_ID
from skeletons.gui.battle_session import IBattleSessionProvider
from gui.mods.spotmeter_gf.utils import LOG_DEBUG, LOG_ERROR, LOG_NOTE, getParentWindow


class CONSTANTS(object):
    FILE_NAME = 'spotmeter_guiflash.swf'
    VIEW_ALIAS = 'SpotMeterGuiFlashView'


class COMPONENT_TYPE(object):
    PANEL = 'Panel'
    LABEL = 'Label'
    IMAGE = 'Image'
    SHAPE = 'Shape'


ALL_COMPONENT_TYPES = (
    COMPONENT_TYPE.PANEL, COMPONENT_TYPE.LABEL,
    COMPONENT_TYPE.IMAGE, COMPONENT_TYPE.SHAPE,
)


class COMPONENT_ALIGN(object):
    LEFT = 'left'
    RIGHT = 'right'
    CENTER = 'center'
    TOP = 'top'
    BOTTOM = 'bottom'
    NONE = 'none'


class COMPONENT_STATE(object):
    INIT = 1
    LOAD = 2
    UNLOAD = 3
    DESTROY = 4


class COMPONENT_EVENT(object):
    # `LOADED(alias)`        - upstream gambiter event; not currently fired
    #                          here (our SWF doesn't emit it). Reserved.
    # `UPDATED(alias, props)` - fired on drag-end and on AS3-side property
    #                           change. Subscribe to persist position.
    # `UNLOADED(alias)`       - reserved.
    # `CLICKED(alias)`        - SpotMeter fork only. Fired when the user
    #                           clicks any component. The forked AS3
    #                           UIComponentEx emits this via the existing
    #                           py_update channel with `_click: true`,
    #                           which we decode below.
    LOADED   = Event.Event()
    UPDATED  = Event.Event()
    UNLOADED = Event.Event()
    CLICKED  = Event.Event()


class Cache(object):

    def __init__(self):
        self.components = {}

    def create(self, alias, _type, props, battle=True, lobby=False):
        LOG_DEBUG("Create cache: '%s' [%s] -> Properties: %s, battle: %s, lobby: %s"
                  % (alias, _type, props, battle, lobby))
        self.components[alias] = {
            'type': _type, 'props': props,
            'battle': battle, 'lobby': lobby,
        }

    def update(self, alias, props):
        LOG_DEBUG("Change cache: '%s' -> Properties: %s" % (alias, props))
        self.components[alias].get('props').update(props)

    def delete(self, alias):
        LOG_DEBUG("Destroy cache: '%s'" % alias)
        del self.components[alias]

    def isComponent(self, alias):
        return alias in self.components

    def isActiveComponent(self, alias):
        if alias not in self.components:
            return False
        if hasattr(BigWorld.player(), 'arena'):
            return self.components[alias]['battle']
        return self.components[alias]['lobby']

    def getComponent(self, alias=None):
        if alias is None:
            return self.components
        return self.components.get(alias)

    def getKeys(self):
        return sorted(filter(self.isActiveComponent, self.components.keys()))

    def getCustomizedType(self, compType):
        return ('').join(compType.split()).capitalize()

    def isTypeValid(self, compType):
        return compType in ALL_COMPONENT_TYPES


class Views(object):

    def __init__(self):
        self.ui = None

    def createAll(self):
        for alias in g_guiCache.getKeys():
            component = g_guiCache.getComponent(alias)
            self.create(alias, component.get('type'), component.get('props'))
        if not hasattr(BigWorld.player(), 'arena'):
            self.cursor(True)

    def create(self, alias, compType, props):
        if self.ui is not None:
            LOG_DEBUG("Create component: '%s' [%s] -> Properties: %s" % (alias, compType, props))
            self.ui.as_createS(alias, compType, props)

    def update(self, alias, props, params):
        if self.ui is not None:
            LOG_DEBUG("Change component: '%s' -> Properties: %s | Parameters: %s" % (alias, props, params))
            self.ui.as_updateS(alias, props, params)

    def delete(self, alias):
        if self.ui is not None:
            LOG_DEBUG("Destroy component: '%s'" % alias)
            self.ui.as_deleteS(alias)

    def resize(self):
        if self.ui is not None:
            width, height = GUI.screenResolution()
            scale = float(ServicesLocator.settingsCore.interfaceScale.get())
            self.ui.as_resizeS(int(width / scale), int(height / scale))

    def cursor(self, isShow):
        if self.ui is not None:
            self.ui.as_cursorS(isShow)


class Hooks(object):
    sessionProvider = dependency.descriptor(IBattleSessionProvider)

    def _start(self):
        ServicesLocator.appLoader.onGUISpaceEntered += self.__onGUISpaceEntered
        ServicesLocator.appLoader.onGUISpaceLeft   += self.__onGUISpaceLeft

    def _destroy(self):
        ServicesLocator.appLoader.onGUISpaceEntered -= self.__onGUISpaceEntered
        ServicesLocator.appLoader.onGUISpaceLeft   -= self.__onGUISpaceLeft

    def _populate(self):
        g_eventBus.addListener(events.GameEvent.SHOW_CURSOR, self.__handleShowCursor, EVENT_BUS_SCOPE.GLOBAL)
        g_eventBus.addListener(events.GameEvent.HIDE_CURSOR, self.__handleHideCursor, EVENT_BUS_SCOPE.GLOBAL)
        g_guiResetters.add(self.__onResizeStage)

    def _dispose(self):
        g_eventBus.removeListener(events.GameEvent.SHOW_CURSOR, self.__handleShowCursor, EVENT_BUS_SCOPE.GLOBAL)
        g_eventBus.removeListener(events.GameEvent.HIDE_CURSOR, self.__handleHideCursor, EVENT_BUS_SCOPE.GLOBAL)
        g_guiResetters.discard(self.__onResizeStage)

    def __onGUISpaceEntered(self, spaceID):
        if spaceID == SPACE_ID.LOBBY:
            g_guiEvents.goToLobby()
        elif spaceID == SPACE_ID.BATTLE:
            g_guiEvents.goToBattle()

    def __onGUISpaceLeft(self, spaceID):
        if spaceID == SPACE_ID.LOBBY:
            g_guiEvents.leaveLobby()
        elif spaceID == SPACE_ID.BATTLE:
            g_guiEvents.leaveBattle()

    def __onResizeStage(self):
        g_guiEvents.resizeStage()

    def __handleShowCursor(self, _):
        g_guiEvents.toggleCursor(True)

    def __handleHideCursor(self, _):
        g_guiEvents.toggleCursor(False)


class Events(object):

    def goToLobby(self):
        ServicesLocator.appLoader.getApp().loadView(
            SFViewLoadParams(CONSTANTS.VIEW_ALIAS, parent=getParentWindow()))

    def goToBattle(self):
        ServicesLocator.appLoader.getApp().loadView(
            SFViewLoadParams(CONSTANTS.VIEW_ALIAS, parent=getParentWindow()))

    def leaveLobby(self):
        if g_guiViews.ui is not None:
            g_guiViews.ui.destroy()

    def leaveBattle(self):
        if g_guiViews.ui is not None:
            g_guiViews.ui.destroy()

    def resizeStage(self):
        g_guiViews.resize()

    def toggleCursor(self, isShow):
        g_guiViews.cursor(isShow)


class Settings(object):

    def _start(self):
        g_entitiesFactories.addSettings(
            ViewSettings(CONSTANTS.VIEW_ALIAS, Flash_UI, CONSTANTS.FILE_NAME,
                         WindowLayer.WINDOW, None, ScopeTemplates.GLOBAL_SCOPE))

    def _destroy(self):
        g_entitiesFactories.removeSettings(CONSTANTS.VIEW_ALIAS)


class Flash_Meta(View):

    def py_log(self, *args):
        self._printOverrideError('py_log')

    def py_update(self, alias, props):
        self._printOverrideError('py_update')

    def as_createS(self, alias, compType, props):
        if self._isDAAPIInited():
            return self.flashObject.as_create(alias, compType, props)

    def as_updateS(self, alias, props, params):
        if self._isDAAPIInited():
            return self.flashObject.as_update(alias, props, params)

    def as_deleteS(self, alias):
        if self._isDAAPIInited():
            return self.flashObject.as_delete(alias)

    def as_resizeS(self, width, height):
        if self._isDAAPIInited():
            return self.flashObject.as_resize(width, height)

    def as_cursorS(self, isVisible):
        if self._isDAAPIInited():
            return self.flashObject.as_cursor(isVisible)


class Flash_UI(Flash_Meta):

    def _populate(self):
        super(Flash_UI, self)._populate()
        g_guiHooks._populate()
        g_guiViews.ui = self
        g_guiViews.resize()
        g_guiViews.createAll()

    def _dispose(self):
        g_guiViews.ui = None
        g_guiHooks._dispose()
        super(Flash_UI, self)._dispose()

    def py_log(self, *args):
        LOG_NOTE(*args)

    def py_update(self, alias, props):
        # SpotMeter fork: the forked SWF's UIComponentEx onComponentClick
        # handler sends `py_update(alias, {_click: true})` on every mouse
        # click. We decode that here and fire COMPONENT_EVENT.CLICKED so
        # client code (mod_spotmeter) can subscribe with a clean API,
        # without sniffing dict contents. Drag-end and other genuine
        # property updates pass through unchanged to COMPONENT_EVENT.UPDATED.
        if not g_guiCache.isComponent(alias):
            return
        d = props.toDict() if hasattr(props, 'toDict') else dict(props or {})
        clicked = bool(d.pop('_click', False))
        if clicked:
            COMPONENT_EVENT.CLICKED(alias)
        if d:
            g_guiCache.update(alias, d)
            COMPONENT_EVENT.UPDATED(alias, d)


class GUIFlash(object):

    def __init__(self):
        g_guiSettings._start()
        g_guiHooks._start()

    def __del__(self):
        g_guiHooks._destroy()
        g_guiSettings._destroy()

    def createComponent(self, alias, compType, props=None, battle=True, lobby=False):
        if g_guiCache.isComponent(alias):
            LOG_ERROR("Component '%s' already exists!" % alias)
            return
        compType = g_guiCache.getCustomizedType(compType)
        if not g_guiCache.isTypeValid(compType):
            LOG_ERROR("Invalid component type '%s'!" % alias)
            return
        g_guiCache.create(alias, compType, props, battle, lobby)
        if g_guiCache.isActiveComponent(alias):
            g_guiViews.create(alias, compType, props)

    def updateComponent(self, alias, props, params=None):
        if not g_guiCache.isComponent(alias):
            LOG_ERROR("Component '%s' not found!" % alias)
            return
        g_guiCache.update(alias, props)
        if g_guiCache.isActiveComponent(alias):
            g_guiViews.update(alias, props, params)

    def deleteComponent(self, alias):
        if not g_guiCache.isComponent(alias):
            LOG_ERROR("Component '%s' not found" % alias)
            return
        if g_guiCache.isActiveComponent(alias):
            g_guiViews.delete(alias)
        g_guiCache.delete(alias)


g_guiCache    = Cache()
g_guiViews    = Views()
g_guiHooks    = Hooks()
g_guiEvents   = Events()
g_guiSettings = Settings()
