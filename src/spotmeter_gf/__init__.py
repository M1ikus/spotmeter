# -*- coding: utf-8 -*-
# SpotMeter's private GUIFlash fork. Adapted from gambiter.guiflash 0.6.4
# by GambitER / CH4MPi (MIT). Bundled inside spotmeter-*.wotmod under our
# own namespace so it doesn't conflict with a user-installed gambiter copy.
#
# The forked SWF (res/gui/flash/spotmeter_guiflash.swf) adds a MouseEvent.CLICK
# listener to UIComponentEx; the click is forwarded to Python via the
# existing py_update channel with a `_click: true` sentinel, which we
# decode in Flash_UI.py_update and re-emit as COMPONENT_EVENT.CLICKED(alias).
from flash import GUIFlash, COMPONENT_EVENT, COMPONENT_TYPE, COMPONENT_ALIGN

SPOTMETER_GF_VERSION = '0.6.4+spotmeter-click'

g_smGuiFlash = GUIFlash()
print 'SpotMeter[GF] v%s initialised (forked from GUIFlash 0.6.4 by GambitER / CH4MPi)' % SPOTMETER_GF_VERSION
