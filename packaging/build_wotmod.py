"""Build the SpotMeter v7 .wotmod package (Gameface panel).

A .wotmod is a ZIP archive World of Tanks reads from mods/<version>/. It
contains meta.xml at the root plus game-relative resources under res/.

v7.0.0: the panel is a Gameface (HTML/CSS/JS) overlay driven by
spotmeter_gfpanel + net.openwg.gameface. The old GUIFlash SWF + the private
spotmeter_gf fork are GONE (no more net.gambiter.* class collision). The mod
now ships:
  - mod_spotmeter.pyc              (the mod)
  - spotmeter_gfpanel.pyc          (the Gameface render layer)
  - gui/gameface/mods/spotmeter/SpotMeterPanel.html  (the panel UI)
  - mods/configs/res_map/net.spotmeter.panel.json    (layout registration)

Requires net.openwg.gameface installed at runtime (a shared dependency).

Run (after compiling the .pyc to build/ - preflight.py does this):
    python packaging/build_wotmod.py
Output goes to dist/.
"""
from __future__ import print_function
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PYC     = os.path.join(ROOT, 'build', 'mod_spotmeter.pyc')
SRC_GFPANEL = os.path.join(ROOT, 'build', 'spotmeter_gfpanel.pyc')
SRC_HTML    = os.path.join(ROOT, 'src', 'gameface', 'SpotMeterPanel.html')
SRC_RESMAP  = os.path.join(ROOT, 'src', 'res_map', 'net.spotmeter.panel.json')
SRC_JSON    = os.path.join(ROOT, 'src', 'spotmeter.json')
META_XML    = os.path.join(ROOT, 'packaging', 'meta.xml')
INSTALL_TXT = os.path.join(ROOT, 'packaging', 'INSTALL.txt')
DIST        = os.path.join(ROOT, 'dist')


def read_version():
    with open(META_XML, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('<version>') and line.endswith('</version>'):
                return line[len('<version>'):-len('</version>')]
    raise RuntimeError('version not found in meta.xml')


def main():
    for p in (SRC_PYC, SRC_GFPANEL, SRC_HTML, SRC_RESMAP, META_XML):
        if not os.path.exists(p):
            print('error: missing %s (compile the .pyc to build/ first)' % p,
                  file=sys.stderr)
            return 1
    if not os.path.exists(DIST):
        os.makedirs(DIST)

    version = read_version()
    out_path = os.path.join(DIST, 'spotmeter-v%s.wotmod' % version)

    # ZIP_STORED (the engine mmaps entries; DEFLATE fails to load on 2.x) and
    # EVERY intermediate directory must be present as its own empty entry (the
    # resource manager walks real dir entries top-down). res/ maps to VFS root:
    #   res/scripts/client/gui/mods/*.pyc          -> auto-loaded Python
    #   res/gui/gameface/mods/spotmeter/*.html      -> coui:// panel asset
    #   res/mods/configs/res_map/*.json             -> OpenWG res_map config
    payload_entries = [
        ('res/', None),
        ('res/scripts/', None),
        ('res/scripts/client/', None),
        ('res/scripts/client/gui/', None),
        ('res/scripts/client/gui/mods/', None),
        ('res/scripts/client/gui/mods/mod_spotmeter.pyc', SRC_PYC),
        ('res/scripts/client/gui/mods/spotmeter_gfpanel.pyc', SRC_GFPANEL),
        ('res/gui/', None),
        ('res/gui/gameface/', None),
        ('res/gui/gameface/mods/', None),
        ('res/gui/gameface/mods/spotmeter/', None),
        ('res/gui/gameface/mods/spotmeter/SpotMeterPanel.html', SRC_HTML),
        ('res/mods/', None),
        ('res/mods/configs/', None),
        ('res/mods/configs/res_map/', None),
        ('res/mods/configs/res_map/net.spotmeter.panel.json', SRC_RESMAP),
    ]
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_STORED) as z:
        z.write(META_XML, 'meta.xml')
        for arcname, src in payload_entries:
            if src is None:
                info = zipfile.ZipInfo(arcname)
                info.compress_type = zipfile.ZIP_STORED
                z.writestr(info, b'')
            else:
                z.write(src, arcname)

    # default config + INSTALL next to the .wotmod, plus a one-link bundle zip
    shipped_config = os.path.join(DIST, 'spotmeter.json')
    shipped_install = os.path.join(DIST, 'INSTALL.txt')
    shutil.copy2(SRC_JSON, shipped_config)
    with open(INSTALL_TXT, 'rb') as fin:
        install_text = fin.read().replace(b'{{VERSION}}', version.encode('utf-8'))
    with open(shipped_install, 'wb') as fout:
        fout.write(install_text)

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
    return 0


if __name__ == '__main__':
    sys.exit(main())
