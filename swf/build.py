"""Build all SpotMeter SWFs (currently: button + menu).

For each target:
  1. Construct a minimal stub SWF in pure Python. The stub contains a
     single empty class declaration (e.g. spotmeter.SpotMeterButton)
     extending Object. We hand-build the ABC bytecode rather than rely
     on an external AS3 compiler (Apache Flex / Adobe AIR SDK) - this
     stub never runs, it only gives FFDec something to *replace*.
  2. Run FFDec CLI -importScript, which compiles our real AS3 source
     using FFDec's internal AS3 compiler and replaces the empty class's
     methods/traits with the full implementation.

Requires:
  - Python 2.7 or 3.x (stdlib only)
  - FFDec at C:\\Program Files (x86)\\FFDec\\ffdec-cli.exe (override via
    FFDEC_CLI env var).
"""
from __future__ import print_function

import os
import struct
import subprocess
import sys

HERE     = os.path.dirname(os.path.abspath(__file__))
SRC_ROOT = os.path.join(HERE, 'src')

FFDEC_CLI = os.environ.get(
    'FFDEC_CLI',
    r'C:\Program Files (x86)\FFDec\ffdec-cli.exe',
)

# Per-SWF build targets.
TARGETS = [
    {
        'src_dir':    os.path.join(SRC_ROOT, 'button'),
        'package':    'spotmeter',
        'class_name': 'SpotMeterButton',
        'stub_name':  'stub_button.swf',
        'out_name':   'spotmeter_button.swf',
    },
    {
        'src_dir':    os.path.join(SRC_ROOT, 'menu'),
        'package':    'spotmeter',
        'class_name': 'SpotMeterMenu',
        'stub_name':  'stub_menu.swf',
        'out_name':   'spotmeter_menu.swf',
    },
    {
        'src_dir':    os.path.join(SRC_ROOT, 'battle'),
        'package':    'spotmeter',
        'class_name': 'SpotMeterBattlePanel',
        'stub_name':  'stub_battle.swf',
        'out_name':   'spotmeter_battle.swf',
    },
    # v6.0.0 MVP1 ship: we copy the upstream GUIFlash.swf (GambitER /
    # CH4MPi, MIT) byte-identical to spotmeter_guiflash.swf. NO patching
    # via FFDec - we tried adding a MouseEvent.CLICK listener to
    # UIComponentEx but FFDec's AS3 recompile emits bytecode that fails
    # WG's AVM2 verifier on load, crashing WoT. The byte-identical copy
    # works because we ship it under a different alias / Python wrapper
    # namespace (gui.mods.spotmeter_gf with VIEW_ALIAS
    # 'SpotMeterGuiFlashView'). The flip side: no click events on
    # components, so the in-battle panel stays display-only; the user
    # controls everything via Numpad hotkeys. Clickable UI is deferred
    # until we have a working SDK or P-code editing pipeline.
    {
        'src_dir':       os.path.join(SRC_ROOT, 'guiflash'),
        'base_swf':      os.path.join(HERE, '..', 'research',
                                      'gambiter_unpack', 'res', 'gui',
                                      'flash', 'GUIFlash.swf'),
        'pass_through':  True,
        'package':       'net.gambiter',
        'class_name':    'FlashUI',
        'stub_name':     'stub_guiflash.swf',
        'out_name':      'spotmeter_guiflash.swf',
    },
]

# SWF stage (in pixels). Twips = px * 20.
SWF_VERSION = 13
STAGE_W_PX  = 100
STAGE_H_PX  = 40
FRAME_RATE  = 30


# ============================================================================
# Encoding helpers
# ============================================================================

def u30(value):
    """AVM2 u30: variable-length, 7 bits per byte, high bit is continuation."""
    if value < 0:
        raise ValueError('u30 cannot encode negative value')
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def u8(v):  return struct.pack('<B', v)
def u16(v): return struct.pack('<H', v)
def u32(v): return struct.pack('<I', v)


def _bits_for_signed(v):
    if v == 0:
        return 1
    if v > 0:
        return v.bit_length() + 1
    return ((-v) - 1).bit_length() + 1


def swf_rect(xmin_t, xmax_t, ymin_t, ymax_t):
    nbits = max(_bits_for_signed(v) for v in (xmin_t, xmax_t, ymin_t, ymax_t))
    nbits = max(nbits, 1)
    bits = []

    def _push(value, width):
        if value < 0:
            value = (1 << width) + value
        for i in range(width - 1, -1, -1):
            bits.append((value >> i) & 1)

    _push(nbits, 5)
    _push(xmin_t, nbits)
    _push(xmax_t, nbits)
    _push(ymin_t, nbits)
    _push(ymax_t, nbits)
    while len(bits) % 8:
        bits.append(0)
    out = bytearray()
    for i in range(0, len(bits), 8):
        b = 0
        for j in range(8):
            b = (b << 1) | bits[i + j]
        out.append(b)
    return bytes(out)


def swf_tag(tag_type, payload):
    return struct.pack('<H', (tag_type << 6) | 0x3F) + struct.pack('<I', len(payload)) + payload


# ============================================================================
# AVM2 ABC: minimal class skeleton for `<package>.<ClassName>` extending Object
# ============================================================================

OP_GETLOCAL_0       = 0xD0
OP_PUSHSCOPE        = 0x30
OP_CONSTRUCTSUPER   = 0x49
OP_RETURNVOID       = 0x47

NS_KIND_PACKAGE     = 0x16
MN_KIND_QNAME       = 0x07
TRAIT_CLASS         = 0x04
CLASS_FLAG_SEALED   = 0x01


def _encode_string(s):
    data = s.encode('utf-8')
    return u30(len(data)) + data


def build_abc(package, class_name, super_name='Object'):
    """Build the minimal ABC blob for one class. FFDec's -importScript will
    find this class by package+name and replace its body with the compiled
    AS3 source."""

    # ---- cpool ----
    # Strings indexed from 1 (index 0 is implicit empty/any).
    strings = ['', package, class_name, super_name]
    str_blob = u30(len(strings))
    for s in strings[1:]:
        str_blob += _encode_string(s)

    # Namespaces: ns[1] = PackageNamespace(package), ns[2] = PackageNamespace("")
    ns_blob = u30(3)
    ns_blob += u8(NS_KIND_PACKAGE) + u30(1)
    ns_blob += u8(NS_KIND_PACKAGE) + u30(0)

    nss_blob = u30(1)  # ns_sets: implicit only

    # Multinames: mn[1] = QName(ns1, class_name string), mn[2] = QName(ns2, super)
    mn_blob = u30(3)
    mn_blob += u8(MN_KIND_QNAME) + u30(1) + u30(2)
    mn_blob += u8(MN_KIND_QNAME) + u30(2) + u30(3)

    cpool = b''
    cpool += u30(1)  # ints: implicit only
    cpool += u30(1)  # uints
    cpool += u30(1)  # doubles
    cpool += str_blob
    cpool += ns_blob
    cpool += nss_blob
    cpool += mn_blob

    # ---- methods (3 empty signatures: iinit, cinit, script init) ----
    def _empty_method():
        return u30(0) + u30(0) + u30(0) + u8(0)
    methods_blob = u30(3) + _empty_method() * 3

    metadata_blob = u30(0)

    # ---- instance + class ----
    instance_blob = b''
    instance_blob += u30(1)                    # name = mn[1] (our class)
    instance_blob += u30(2)                    # super = mn[2] (Object)
    instance_blob += u8(CLASS_FLAG_SEALED)
    instance_blob += u30(0)                    # interface_count
    instance_blob += u30(0)                    # iinit = method 0
    instance_blob += u30(0)                    # trait_count

    class_blob = u30(1) + u30(0)               # cinit=1, no traits

    classes_blob = u30(1) + instance_blob + class_blob

    # ---- script with class trait ----
    script_trait = b''
    script_trait += u30(1)                     # trait name = mn[1]
    script_trait += u8(TRAIT_CLASS)
    script_trait += u30(0) + u30(0)            # slot_id=0, class_index=0
    script_blob = u30(1) + u30(2) + u30(1) + script_trait  # 1 script, init=method 2, 1 trait

    # ---- method bodies (minimum valid AVM2 bytecode) ----
    iinit_code = bytes(bytearray([
        OP_GETLOCAL_0, OP_PUSHSCOPE, OP_GETLOCAL_0,
        OP_CONSTRUCTSUPER, 0x00, OP_RETURNVOID,
    ]))
    body_iinit = (u30(0) + u30(2) + u30(1) + u30(0) + u30(1)
                  + u30(len(iinit_code)) + iinit_code + u30(0) + u30(0))

    cinit_code = bytes(bytearray([OP_RETURNVOID]))
    body_cinit = (u30(1) + u30(0) + u30(1) + u30(0) + u30(0)
                  + u30(len(cinit_code)) + cinit_code + u30(0) + u30(0))

    script_code = bytes(bytearray([OP_RETURNVOID]))
    body_script = (u30(2) + u30(0) + u30(1) + u30(0) + u30(0)
                   + u30(len(script_code)) + script_code + u30(0) + u30(0))

    bodies_blob = u30(3) + body_iinit + body_cinit + body_script

    # ---- assemble ----
    abc = b''
    abc += u16(16)     # minor_version
    abc += u16(46)     # major_version
    abc += cpool
    abc += methods_blob
    abc += metadata_blob
    abc += classes_blob
    abc += script_blob
    abc += bodies_blob
    return abc


def build_doabc_tag(abc_bytes, name):
    return swf_tag(82, u32(1) + name.encode('utf-8') + b'\x00' + abc_bytes)


def build_symbol_class_tag(package, class_name):
    fqcn = (package + '.' + class_name).encode('utf-8')
    return swf_tag(76, u16(1) + u16(0) + fqcn + b'\x00')


def build_stub_swf(package, class_name):
    rect = swf_rect(0, STAGE_W_PX * 20, 0, STAGE_H_PX * 20)
    frame_rate = u16(FRAME_RATE << 8)
    frame_count = u16(1)

    body = b''
    body += rect + frame_rate + frame_count
    body += swf_tag(69, u32(0x08))   # FileAttributes: has AS3
    body += build_doabc_tag(build_abc(package, class_name), package)
    body += build_symbol_class_tag(package, class_name)
    body += swf_tag(1, b'')          # ShowFrame
    body += swf_tag(0, b'')          # End

    file_length = 8 + len(body)
    header = struct.pack('<BBBBI', ord('F'), ord('W'), ord('S'),
                         SWF_VERSION, file_length)
    return header + body


# ============================================================================
# Build driver
# ============================================================================

def build_target(target):
    stub_path = os.path.join(HERE, target['stub_name'])
    out_path  = os.path.join(HERE, target['out_name'])
    src_dir   = target['src_dir']

    if not os.path.isdir(src_dir):
        print('error: source dir missing: %s' % src_dir, file=sys.stderr)
        return False

    # pass_through: skip FFDec entirely and just copy base_swf to the
    # output path verbatim. Used for spotmeter_guiflash where any FFDec
    # recompile breaks WG's AVM2 verifier on load - we want a byte-
    # identical copy of the upstream library.
    if target.get('pass_through'):
        base_swf = target.get('base_swf')
        if not base_swf or not os.path.isfile(base_swf):
            print('error: pass_through target missing base_swf: %s' % base_swf, file=sys.stderr)
            return False
        import shutil
        shutil.copyfile(base_swf, out_path)
        print('  [%s] pass_through copy -> %s (%d bytes)'
              % (target['class_name'], out_path, os.path.getsize(out_path)))
        return True

    # If the target specifies a `base_swf` (path to a pre-existing SWF
    # to patch), copy that as our starting point instead of generating a
    # 1-class stub. Needed for targets like spotmeter_guiflash where we
    # patch a complex library SWF and want FFDec to keep the unchanged
    # classes intact - it only replaces the classes that have matching
    # source files in src_dir.
    base_swf = target.get('base_swf')
    if base_swf:
        if not os.path.isfile(base_swf):
            print('error: base_swf missing: %s' % base_swf, file=sys.stderr)
            return False
        print('  [%s] base -> %s' % (target['class_name'], stub_path))
        import shutil
        shutil.copyfile(base_swf, stub_path)
    else:
        print('  [%s] stub -> %s' % (target['class_name'], stub_path))
        stub = build_stub_swf(target['package'], target['class_name'])
        with open(stub_path, 'wb') as f:
            f.write(stub)

    cmd = [FFDEC_CLI, '-importScript', stub_path, out_path, src_dir]
    print('  [%s] ffdec importScript -> %s' % (target['class_name'], out_path))
    rc = subprocess.call(cmd)
    if rc != 0:
        print('  error: FFDec exit %d for %s' % (rc, target['class_name']), file=sys.stderr)
        return False
    if not os.path.exists(out_path):
        print('  error: output not created: %s' % out_path, file=sys.stderr)
        return False
    print('  [%s] done: %s (%d bytes)' % (target['class_name'], out_path, os.path.getsize(out_path)))
    return True


def main():
    if not os.path.exists(FFDEC_CLI):
        print('error: FFDec CLI not found at:', FFDEC_CLI, file=sys.stderr)
        print('       set FFDEC_CLI env var to override.', file=sys.stderr)
        return 1

    for i, t in enumerate(TARGETS, 1):
        print('[%d/%d] building %s' % (i, len(TARGETS), t['out_name']))
        if not build_target(t):
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
