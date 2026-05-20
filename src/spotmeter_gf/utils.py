# -*- coding: utf-8 -*-
# SpotMeter's GUIFlash fork - utility helpers.
# Adapted from gambiter.guiflash 0.6.4 / utils.py (MIT).
IS_DEBUG = False


def LOG(arg, *args):
    print str(arg), (' ').join([str(a) for a in args])


def LOG_NOTE(*args):
    LOG('SpotMeter[GF]: [NOTE]', *args)


def LOG_ERROR(*args):
    LOG('SpotMeter[GF]: [ERROR]', *args)


def LOG_DEBUG(*args):
    if IS_DEBUG:
        LOG('SpotMeter[GF]: [DEBUG]', *args)


def LOG_TRACE(exc=None):
    import traceback
    print '=' * 25
    if exc is not None:
        LOG_ERROR(exc)
        traceback.print_exc()
    else:
        traceback.print_stack()
    print '=' * 25


def getParentWindow():
    """Return the lobby/battle Wulf main window for SFViewLoadParams.parent.
    Without it the framework silently drops third-party view loads on
    WoT 2.x."""
    from skeletons.gui.impl import IGuiLoader
    from helpers import dependency
    uiLoader = dependency.instance(IGuiLoader)
    if uiLoader and uiLoader.windowsManager:
        return uiLoader.windowsManager.getMainWindow()
    return None
