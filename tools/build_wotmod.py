"""Build a .wotmod package for any mod under ``mods/``.

A .wotmod file is a regular ZIP archive that World of Tanks reads from
its mods/<version>/ directory. It must contain a meta.xml at the root
plus any game-relative resources (e.g. scripts/client/...). This
script also bundles a default config alongside the .wotmod for the
user to optionally drop into mods/configs/.

Repo layout (monorepo for multiple WoT mods):

    <repo>/
        tools/build_wotmod.py    (this file)
        mods/<modname>/
            meta.xml             (id, version, name, description)
            INSTALL.txt          (shipped to user, optional)
            src/
                mod_<modname>.py     (main module, source)
                <modname>.json       (default config, optional)
            build/
                mod_<modname>.pyc    (compiled by py27, must exist)
            dist/
                <modname>-v<version>.wotmod   (this script's output)
                <modname>-v<version>.zip      (idem)

Convention:
    - Mod folder name == short name used in artefact filenames
      (e.g. ``mods/spotmeter`` -> ``spotmeter-v<version>.wotmod``).
    - Main module file is ``src/mod_<modname>.py`` (and .pyc in build/).
    - Optional config file is ``src/<modname>.json``; if missing,
      the bundle simply omits it.

Run:
    python tools/build_wotmod.py <modname>

Example:
    python tools/build_wotmod.py spotmeter
"""
from __future__ import print_function
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_version(meta_xml_path):
    with open(meta_xml_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('<version>') and line.endswith('</version>'):
                return line[len('<version>'):-len('</version>')]
    raise RuntimeError('version not found in %s' % meta_xml_path)


def build_mod(modname):
    mod_dir = os.path.join(ROOT, 'mods', modname)
    src_pyc = os.path.join(mod_dir, 'build', 'mod_%s.pyc' % modname)
    src_json = os.path.join(mod_dir, 'src', '%s.json' % modname)
    meta_xml = os.path.join(mod_dir, 'meta.xml')
    install_txt = os.path.join(mod_dir, 'INSTALL.txt')
    dist = os.path.join(mod_dir, 'dist')

    if not os.path.isdir(mod_dir):
        print('error: %s does not exist' % mod_dir, file=sys.stderr)
        return 1
    if not os.path.exists(src_pyc):
        print('error: %s does not exist - compile the mod first' % src_pyc, file=sys.stderr)
        return 1
    if not os.path.exists(meta_xml):
        print('error: %s does not exist' % meta_xml, file=sys.stderr)
        return 1
    if not os.path.exists(dist):
        os.makedirs(dist)

    version = read_version(meta_xml)
    out_path = os.path.join(dist, '%s-v%s.wotmod' % (modname, version))

    # Two requirements for WoT 2.x .wotmod files (verified against
    # working community mods like wot-public-mods/replays-manager):
    #
    #   1. ZIP_STORED (no compression). The engine mmaps entries
    #      directly; ZIP_DEFLATED triggers 'compression not supported'
    #      at load time on at least WoT 2.2.1.2.
    #
    #   2. Files live under a 'res/' prefix inside the archive AND
    #      every intermediate directory must be present as its own
    #      empty entry. paths.xml has
    #         <Path mask="*.wotmod" mode="recursive" root="res">./mods/2.2.1.2</Path>
    #      and the engine's resource manager only finds files inside
    #      a 'res/' tree that it can walk top-down via real directory
    #      entries. Without the directory entries the file is in the
    #      archive but the gui mods loader's ResMgr.openSection() does
    #      not see it - the .wotmod 'loads' but the python module is
    #      never imported. (This is the bug v5.1.1 hit.)
    payload_entries = [
        ('res/', None),
        ('res/scripts/', None),
        ('res/scripts/client/', None),
        ('res/scripts/client/gui/', None),
        ('res/scripts/client/gui/mods/', None),
        ('res/scripts/client/gui/mods/mod_%s.pyc' % modname, src_pyc),
    ]
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_STORED) as z:
        z.write(meta_xml, 'meta.xml')
        for arcname, src in payload_entries:
            if src is None:
                # Directory entry: zero-byte stored file with a name
                # ending in '/' is how ZIP encodes a folder.
                info = zipfile.ZipInfo(arcname)
                info.compress_type = zipfile.ZIP_STORED
                z.writestr(info, b'')
            else:
                z.write(src, arcname)

    # Drop default config and install instructions next to the .wotmod
    # so the user has everything they need from one folder.
    shipped_config = os.path.join(dist, '%s.json' % modname)
    shipped_install = os.path.join(dist, 'INSTALL.txt')
    has_config = os.path.exists(src_json)
    if has_config:
        shutil.copy2(src_json, shipped_config)
    has_install = os.path.exists(install_txt)
    if has_install:
        with open(install_txt, 'rb') as fin:
            install_text = fin.read().replace(b'{{VERSION}}', version.encode('utf-8'))
        with open(shipped_install, 'wb') as fout:
            fout.write(install_text)

    # Bundle ZIP for one-link sharing: contains the .wotmod, default
    # config (if any), and INSTALL.txt under a single versioned folder.
    bundle_path = os.path.join(dist, '%s-v%s.zip' % (modname, version))
    bundle_root = '%s-v%s' % (modname, version)
    with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(out_path, '%s/%s' % (bundle_root, os.path.basename(out_path)))
        if has_config:
            z.write(shipped_config, '%s/%s.json' % (bundle_root, modname))
        if has_install:
            z.write(shipped_install, '%s/INSTALL.txt' % bundle_root)

    print('built %s (%d bytes)' % (out_path, os.path.getsize(out_path)))
    print('       %s (%d bytes)' % (bundle_path, os.path.getsize(bundle_path)))
    if has_config:
        print('       %s' % shipped_config)
    if has_install:
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


def main(argv):
    if len(argv) != 2:
        print('usage: %s <modname>' % argv[0], file=sys.stderr)
        print('example: %s spotmeter' % argv[0], file=sys.stderr)
        return 2
    return build_mod(argv[1])


if __name__ == '__main__':
    sys.exit(main(sys.argv))
