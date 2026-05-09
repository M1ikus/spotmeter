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

    # WoT's .wotmod loader expects ZIP_STORED (no compression) so the
    # engine can mmap entries directly; ZIP_DEFLATED triggers
    # 'Mod package not loaded' on at least WoT 2.2.1.2.
    #
    # Path layout: paths.xml has
    #     <Path mask="*.wotmod" mode="recursive" root="res">./mods/2.2.1.2</Path>
    # so the archive content is mounted at the engine's resource root
    # (the same level as the game's res/ directory). Files therefore
    # go in directly without a 'res/' prefix.
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_STORED) as z:
        z.write(META_XML, 'meta.xml')
        z.write(SRC_PYC, 'scripts/client/gui/mods/mod_spotmeter.pyc')

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
