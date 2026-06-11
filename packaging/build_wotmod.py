"""Build a .wotmod package for SpotMeter.

A .wotmod file is a regular ZIP archive that World of Tanks reads from
its mods/<version>/ directory. It must contain a meta.xml at the root
plus any game-relative resources (e.g. scripts/client/...). This
script also bundles a default config alongside the .wotmod for the
user to optionally drop into mods/configs/.

Run:
    python packaging/build_wotmod.py
The output goes to dist/.
"""
from __future__ import print_function
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PYC = os.path.join(ROOT, 'build', 'mod_spotmeter.pyc')
SRC_JSON = os.path.join(ROOT, 'src', 'spotmeter.json')
SRC_SWF_BUTTON = os.path.join(ROOT, 'swf', 'spotmeter_button.swf')
SRC_SWF_MENU   = os.path.join(ROOT, 'swf', 'spotmeter_menu.swf')
SRC_SWF_BATTLE = os.path.join(ROOT, 'swf', 'spotmeter_battle.swf')
SRC_SWF_GF     = os.path.join(ROOT, 'swf', 'spotmeter_guiflash.swf')
SRC_GF_INIT    = os.path.join(ROOT, 'build', 'spotmeter_gf', '__init__.pyc')
SRC_GF_FLASH   = os.path.join(ROOT, 'build', 'spotmeter_gf', 'flash.pyc')
SRC_GF_UTILS   = os.path.join(ROOT, 'build', 'spotmeter_gf', 'utils.pyc')
META_XML = os.path.join(ROOT, 'packaging', 'meta.xml')
INSTALL_TXT = os.path.join(ROOT, 'packaging', 'INSTALL.txt')
DIST = os.path.join(ROOT, 'dist')


def read_version():
    with open(META_XML, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('<version>') and line.endswith('</version>'):
                return line[len('<version>'):-len('</version>')]
    raise RuntimeError('version not found in meta.xml')


def main():
    if not os.path.exists(SRC_PYC):
        print('error: %s does not exist - compile the mod first' % SRC_PYC, file=sys.stderr)
        return 1
    if not os.path.exists(META_XML):
        print('error: %s does not exist' % META_XML, file=sys.stderr)
        return 1
    if not os.path.exists(DIST):
        os.makedirs(DIST)

    version = read_version()
    out_path = os.path.join(DIST, 'spotmeter-v%s.wotmod' % version)

    # Two requirements for WoT 2.x .wotmod files (verified against
    # working community mods like wot-public-mods/replays-manager):
    #
    #   1. ZIP_STORED (no compression). The engine mmaps entries
    #      directly; ZIP_DEFLATED triggers 'compression not supported'
    #      at load time on at least WoT 2.3.0.0.
    #
    #   2. Files live under a 'res/' prefix inside the archive AND
    #      every intermediate directory must be present as its own
    #      empty entry. paths.xml has
    #         <Path mask="*.wotmod" mode="recursive" root="res">./mods/2.3.0.1</Path>
    #      and the engine's resource manager only finds files inside
    #      a 'res/' tree that it can walk top-down via real directory
    #      entries. Without the directory entries the file is in the
    #      archive but the gui mods loader's ResMgr.openSection() does
    #      not see it - the .wotmod 'loads' but the python module is
    #      never imported. (This is the bug v5.1.1 hit.)
    # v6.0.0 MVP2: our LEGACY custom SWFs (button/menu/battle) are not
    # shipped - they were rejected by WG's IView contract on WoT 2.x.
    # We ship the forked GUIFlash (spotmeter_guiflash.swf) which IS a
    # valid IView, plus its private Python wrapper at gui.mods.spotmeter_gf.
    # The mod's own UI (mod_spotmeter.py) renders into the forked GUIFlash
    # at runtime via g_smGuiFlash.createComponent.
    gf_swf_present = os.path.exists(SRC_SWF_GF)
    gf_py_present  = all(os.path.exists(p) for p in (SRC_GF_INIT, SRC_GF_FLASH, SRC_GF_UTILS))
    if not gf_swf_present:
        print('error: %s missing - run python swf/build.py first' % SRC_SWF_GF, file=sys.stderr)
        return 1
    if not gf_py_present:
        print('error: build/spotmeter_gf/*.pyc missing - compile the wrapper first', file=sys.stderr)
        return 1

    payload_entries = [
        ('res/', None),
        ('res/scripts/', None),
        ('res/scripts/client/', None),
        ('res/scripts/client/gui/', None),
        ('res/scripts/client/gui/mods/', None),
        ('res/scripts/client/gui/mods/mod_spotmeter.pyc', SRC_PYC),
        ('res/scripts/client/gui/mods/spotmeter_gf/', None),
        ('res/scripts/client/gui/mods/spotmeter_gf/__init__.pyc', SRC_GF_INIT),
        ('res/scripts/client/gui/mods/spotmeter_gf/flash.pyc',    SRC_GF_FLASH),
        ('res/scripts/client/gui/mods/spotmeter_gf/utils.pyc',    SRC_GF_UTILS),
        ('res/gui/', None),
        ('res/gui/flash/', None),
        ('res/gui/flash/spotmeter_guiflash.swf', SRC_SWF_GF),
    ]
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_STORED) as z:
        z.write(META_XML, 'meta.xml')
        for arcname, src in payload_entries:
            if src is None:
                # Directory entry: zero-byte stored file with a name
                # ending in '/' is how ZIP encodes a folder.
                info = zipfile.ZipInfo(arcname)
                info.compress_type = zipfile.ZIP_STORED
                z.writestr(info, b'')
            else:
                z.write(src, arcname)

    # Also drop the default config and install instructions next to the
    # .wotmod so the user has everything they need from one folder.
    shipped_config = os.path.join(DIST, 'spotmeter.json')
    shipped_install = os.path.join(DIST, 'INSTALL.txt')
    shutil.copy2(SRC_JSON, shipped_config)
    with open(INSTALL_TXT, 'rb') as fin:
        install_text = fin.read().replace(b'{{VERSION}}', version.encode('utf-8'))
    with open(shipped_install, 'wb') as fout:
        fout.write(install_text)

    # Bundle ZIP for one-link sharing: contains the .wotmod, default
    # config, and INSTALL.txt under a single versioned folder.
    bundle_path = os.path.join(DIST, 'spotmeter-v%s.zip' % version)
    bundle_root = 'spotmeter-v%s' % version
    with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(out_path, '%s/%s' % (bundle_root, os.path.basename(out_path)))
        z.write(shipped_config, '%s/spotmeter.json' % bundle_root)
        z.write(shipped_install, '%s/INSTALL.txt' % bundle_root)

    print('built %s (%d bytes)' % (out_path, os.path.getsize(out_path)))
    print('       %s (%d bytes)' % (bundle_path, os.path.getsize(bundle_path)))
    print('       %s' % shipped_config)
    print('       %s' % shipped_install)

    print('\nwotmod contents:')
    with zipfile.ZipFile(out_path, 'r') as z:
        for info in z.infolist():
            print('  %8d  %s' % (info.file_size, info.filename))
    print('\nbundle contents:')
    with zipfile.ZipFile(bundle_path, 'r') as z:
        for info in z.infolist():
            print('  %8d  %s' % (info.file_size, info.filename))
    return 0


if __name__ == '__main__':
    sys.exit(main())
