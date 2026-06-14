"""SpotMeter pre-send preflight - run before every wgmods / Aslain submission.

The mod ships inside Aslain's modpack (alongside XVM and dozens of mods) and the
author can't live-test in a full pack, so this automates every DETERMINISTIC
gate. Green here + the manual items in PRESEND_CHECKLIST.md = safe to send.

Run from the repo root with Python 3:
    python packaging/preflight.py
Exit code 0 = all hard checks pass (warnings allowed); non-zero = fix before sending.

The py27 interpreter (for the real bytecode compile) is found via the PY27 env
var, else a sensible default; override if yours lives elsewhere.
"""
from __future__ import print_function
import ast
import io
import json
import os
import re
import subprocess
import sys
import tokenize
import warnings
import zipfile

# ast.Str is deprecated (py3.12+) but still the type on older interpreters;
# we already prefer ast.Constant, the fallback is just for compat.
warnings.filterwarnings('ignore', category=DeprecationWarning, module=__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY27 = os.environ.get('PY27', r'C:\Users\23120\miniforge3\envs\py27\python.exe')

SRC_MAIN = os.path.join(ROOT, 'src', 'mod_spotmeter.py')
SRC_FORK = [os.path.join(ROOT, 'src', 'spotmeter_gf', f)
            for f in ('__init__.py', 'flash.py', 'utils.py')]
CONFIG_JSON = os.path.join(ROOT, 'src', 'spotmeter.json')
META_XML = os.path.join(ROOT, 'packaging', 'meta.xml')
BUILD_PYC = os.path.join(ROOT, 'build', 'mod_spotmeter.pyc')
BUILD_FORK_DIR = os.path.join(ROOT, 'build', 'spotmeter_gf')

# Symbols deleted in v6.1.0 (garage panel + lobby window-watch). A LIVE code
# reference to any of these is a NameError at runtime -> hard fail.
DEAD_SYMBOLS = {
    '_show_garage_panel', '_hide_garage_panel', '_garage_panel_tick',
    '_schedule_garage_refresh', '_refresh_garage_state', '_maybe_update_garage_label',
    '_fmt_garage_defaults', '_fmt_garage_battle_panel', '_fmt_garage_hotkeys',
    'SPOTMETER_GARAGE_ROOT', '_GARAGE_PANEL_ACTIVE', '_GARAGE_PANEL_REFRESH_CB',
    '_GARAGE_PANEL_LAST', 'SPOTMETER_GARAGE_REFRESH_SEC',
    '_ww_is_real_window', '_ww_window_alias', '_ww_window_layer',
    '_ww_windows_manager', '_ww_lobby_sm', '_ww_on_window_status',
    '_ww_on_route_changed', '_WW_ROUTE_BUSY', '_WW_IGNORE_ALIASES',
}

PORTAL_LIMITS = (1000, 3000, 1000)  # version changes / mod description / installation

_results = []  # (level 'FAIL'|'WARN'|'OK', name, detail)


def ok(name, detail=''):
    _results.append(('OK', name, detail))


def warn(name, detail):
    _results.append(('WARN', name, detail))


def fail(name, detail):
    _results.append(('FAIL', name, detail))


def _str_value(node):
    """String value of an ast str literal (py3.8 Constant or older Str)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):
        return node.s
    return None


def _read(path):
    with io.open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_py27_compile():
    if not os.path.exists(PY27):
        warn('py27-compile', 'py27 interpreter not found at %s (set PY27 env) - '
             'SKIPPED the authoritative py2 syntax/compile check!' % PY27)
        return
    targets = [(SRC_MAIN, BUILD_PYC, 'mod_spotmeter.py')]
    for src in SRC_FORK:
        targets.append((src, os.path.join(BUILD_FORK_DIR, os.path.basename(src) + 'c'),
                        'spotmeter_gf/' + os.path.basename(src)))
    if not os.path.isdir(BUILD_FORK_DIR):
        os.makedirs(BUILD_FORK_DIR)
    for src, cfile, dfile in targets:
        code = ("import py_compile,sys\n"
                "try:\n"
                "  py_compile.compile(r'%s', cfile=r'%s', dfile='%s', doraise=True)\n"
                "except Exception as e:\n"
                "  sys.stderr.write(str(e)); sys.exit(1)\n" % (src, cfile, dfile))
        p = subprocess.Popen([PY27, '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, err = p.communicate()
        if p.returncode != 0:
            fail('py27-compile', '%s did not compile under py2.7: %s'
                 % (dfile, err.decode('utf-8', 'replace').strip()))
            return
    ok('py27-compile', 'mod + fork compile under py2.7 (fresh bytecode written to build/)')


def check_ast_and_json():
    try:
        ast.parse(_read(SRC_MAIN))
        ok('ast-parse', 'mod_spotmeter.py parses')
    except SyntaxError as e:
        fail('ast-parse', 'mod_spotmeter.py: %s' % e)
    try:
        data = json.loads(_read(CONFIG_JSON))
        if not isinstance(data, dict):
            fail('json-load', 'spotmeter.json is not a dict')
        else:
            ok('json-load', 'spotmeter.json loads (%d keys)' % len(data))
    except ValueError as e:
        fail('json-load', 'spotmeter.json invalid: %s' % e)


def check_dead_symbols():
    """Tokenise (so comments/strings are excluded) and look for any NAME token
    in the removed-symbol set."""
    found = {}
    with io.open(SRC_MAIN, 'rb') as fh:
        try:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type == tokenize.NAME and tok.string in DEAD_SYMBOLS:
                    found.setdefault(tok.string, tok.start[0])
        except tokenize.TokenError:
            pass
    if found:
        fail('dead-symbols', 'live references to removed v6.1.0 symbols: '
             + ', '.join('%s (line %d)' % (k, v) for k, v in sorted(found.items())))
    else:
        ok('dead-symbols', 'no live references to removed garage/window-watch symbols')


def _module_assignments(tree):
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = node.value
    return out


def check_config_parity():
    tree = ast.parse(_read(SRC_MAIN))
    assigns = _module_assignments(tree)
    dc = assigns.get('DEFAULT_CONFIG')
    if not isinstance(dc, ast.Dict):
        fail('config-parity', 'DEFAULT_CONFIG dict not found in source')
        return
    code_keys = set(filter(None, (_str_value(k) for k in dc.keys)))
    json_keys = set(k for k in json.loads(_read(CONFIG_JSON))
                    if not k.startswith('_comment'))
    only_code = code_keys - json_keys
    only_json = json_keys - code_keys
    if only_code or only_json:
        fail('config-parity', 'DEFAULT_CONFIG vs spotmeter.json mismatch - '
             'only in code: %s ; only in json: %s'
             % (sorted(only_code) or 'none', sorted(only_json) or 'none'))
    else:
        ok('config-parity', 'DEFAULT_CONFIG and spotmeter.json keys match (%d)' % len(code_keys))


def check_i18n():
    tree = ast.parse(_read(SRC_MAIN))
    assigns = _module_assignments(tree)
    strings = assigns.get('_STRINGS')
    if not isinstance(strings, ast.Dict):
        fail('i18n-parity', '_STRINGS dict not found')
        return
    langs = {}
    for k, v in zip(strings.keys, strings.values):
        lang = _str_value(k)
        if lang in ('en', 'pl') and isinstance(v, ast.Dict):
            langs[lang] = set(filter(None, (_str_value(kk) for kk in v.keys)))
    if 'en' not in langs or 'pl' not in langs:
        fail('i18n-parity', 'could not extract en/pl from _STRINGS')
        return
    miss_pl = langs['en'] - langs['pl']
    miss_en = langs['pl'] - langs['en']
    if miss_pl or miss_en:
        fail('i18n-parity', 'EN/PL key mismatch - missing in pl: %s ; missing in en: %s'
             % (sorted(miss_pl) or 'none', sorted(miss_en) or 'none'))
    else:
        ok('i18n-parity', 'EN/PL string keys match (%d each)' % len(langs['en']))
    # every _t('literal') must exist in EN
    used = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == '_t' and node.args):
            lit = _str_value(node.args[0])
            if lit is not None:
                used.add(lit)
    undefined = sorted(k for k in used if k not in langs.get('en', set()))
    if undefined:
        fail('i18n-keys', "_t() keys not defined in _STRINGS['en']: %s" % undefined)
    else:
        ok('i18n-keys', 'all %d _t() literal keys are defined' % len(used))


def _version_from_source():
    tree = ast.parse(_read(SRC_MAIN))
    for name, node in _module_assignments(tree).items():
        if name == 'MOD_VERSION':
            return _str_value(node)
    return None


def _version_from_meta():
    m = re.search(r'<version>\s*([\d.]+)\s*</version>', _read(META_XML))
    return m.group(1) if m else None


def check_versions():
    v_src = _version_from_source()
    v_meta = _version_from_meta()
    if not v_src or not v_meta:
        fail('version-consistency', 'could not read MOD_VERSION (%s) or meta.xml (%s)'
             % (v_src, v_meta))
        return None
    if v_src != v_meta:
        fail('version-consistency', 'MOD_VERSION=%s != meta.xml=%s' % (v_src, v_meta))
        return None
    ok('version-consistency', 'MOD_VERSION == meta.xml == %s' % v_src)
    # version present in the public docs
    docs = {
        'README.md': os.path.join(ROOT, 'README.md'),
        'CHANGELOG.md': os.path.join(ROOT, 'CHANGELOG.md'),
        'PORTAL_LISTING.md': os.path.join(ROOT, 'packaging', 'PORTAL_LISTING.md'),
        'INSTALL.txt': os.path.join(ROOT, 'packaging', 'INSTALL.txt'),
    }
    for label, path in docs.items():
        text = _read(path)
        if v_src in text or (label == 'INSTALL.txt' and '{{VERSION}}' in text):
            ok('version-in-%s' % label, 'mentions %s' % v_src)
        else:
            warn('version-in-%s' % label, 'does not mention current version %s' % v_src)
    # stale "current" 6.0.x in headline docs (changelog history is allowed)
    for label in ('README.md', 'PORTAL_LISTING.md'):
        for m in re.findall(r'6\.0\.\d', _read(docs[label])):
            warn('stale-version-%s' % label, 'found older version token %s (check it is not a current/headline ref)' % m)
            break
    return v_src


def check_portal_limits():
    text = _read(os.path.join(ROOT, 'packaging', 'PORTAL_LISTING.md'))
    # take the 3 fenced blocks after the WG portal heading
    idx = text.find('WG Mods portal')
    blocks = re.findall(r'```\n(.*?)\n```', text[idx:] if idx >= 0 else text, re.S)
    labels = ('version-changes', 'mod-description', 'installation')
    for i, (lab, lim) in enumerate(zip(labels, PORTAL_LIMITS)):
        if i >= len(blocks):
            warn('portal-%s' % lab, 'block not found')
            continue
        n = len(blocks[i])
        if n > lim:
            fail('portal-%s' % lab, '%d > %d chars' % (n, lim))
        else:
            ok('portal-%s' % lab, '%d / %d chars' % (n, lim))


def check_msa_settings_version():
    tree = ast.parse(_read(SRC_MAIN))
    for name, node in _module_assignments(tree).items():
        if name == '_MSA_SETTINGS_VERSION':
            val = getattr(node, 'value', None) if isinstance(node, ast.Constant) else None
            ok('msa-settings-version', '_MSA_SETTINGS_VERSION = %s (bump on any template change!)' % val)
            return
    warn('msa-settings-version', '_MSA_SETTINGS_VERSION not found')


def check_build_and_wotmod(version):
    p = subprocess.Popen([sys.executable, os.path.join(ROOT, 'packaging', 'build_wotmod.py')],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT)
    out, err = p.communicate()
    if p.returncode != 0:
        fail('build', 'build_wotmod.py failed: %s'
             % (err.decode('utf-8', 'replace').strip() or out.decode('utf-8', 'replace').strip()))
        return
    wotmod = os.path.join(ROOT, 'dist', 'spotmeter-v%s.wotmod' % (version or ''))
    if not version or not os.path.exists(wotmod):
        fail('build', 'expected artifact not produced: %s' % wotmod)
        return
    ok('build', 'built %s (%d B)' % (os.path.basename(wotmod), os.path.getsize(wotmod)))
    expected = {
        'meta.xml',
        'res/scripts/client/gui/mods/mod_spotmeter.pyc',
        'res/scripts/client/gui/mods/spotmeter_gf/__init__.pyc',
        'res/scripts/client/gui/mods/spotmeter_gf/flash.pyc',
        'res/scripts/client/gui/mods/spotmeter_gf/utils.pyc',
        'res/gui/flash/spotmeter_guiflash.swf',
    }
    with zipfile.ZipFile(wotmod) as z:
        if z.testzip() is not None:
            fail('wotmod-crc', 'zip CRC check failed')
        infos = z.infolist()
        names = [i.filename for i in infos]
        deflated = [i.filename for i in infos if i.compress_type != zipfile.ZIP_STORED]
        if deflated:
            fail('wotmod-stored', 'entries not ZIP_STORED (engine will reject): %s' % deflated)
        else:
            ok('wotmod-stored', 'all entries ZIP_STORED')
        if names and names[0] != 'meta.xml':
            warn('wotmod-meta-first', "meta.xml is not the first entry (it's %s)" % names[0])
        files = set(n for n in names if not n.endswith('/'))
        missing = expected - files
        extra = files - expected
        if missing:
            fail('wotmod-payload', 'missing files: %s' % sorted(missing))
        elif extra:
            fail('wotmod-payload', 'unexpected extra files: %s' % sorted(extra))
        else:
            ok('wotmod-payload', 'exact expected 6-file payload')
        # every intermediate directory present as its own entry
        needed_dirs = set()
        for f in expected:
            parts = f.split('/')[:-1]
            for i in range(1, len(parts) + 1):
                needed_dirs.add('/'.join(parts[:i]) + '/')
        dir_entries = set(n for n in names if n.endswith('/'))
        missing_dirs = needed_dirs - dir_entries
        if missing_dirs:
            fail('wotmod-dirs', 'missing directory entries (engine walk fails): %s' % sorted(missing_dirs))
        else:
            ok('wotmod-dirs', 'all intermediate directory entries present')


def check_git_clean():
    try:
        out = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).decode('utf-8')
    except Exception as e:
        warn('git-clean', 'could not run git: %s' % e)
        return
    if out.strip():
        warn('git-clean', 'working tree has uncommitted changes (commit before tagging):\n' + out.rstrip())
    else:
        ok('git-clean', 'working tree clean')


def _run(fn, *a):
    """Run a check; a crash inside it becomes a FAIL, never aborts the gate."""
    try:
        return fn(*a)
    except Exception as e:
        fail(fn.__name__, 'check crashed: %s: %s' % (type(e).__name__, e))
        return None


def main():
    print('SpotMeter preflight  (root: %s)\n' % ROOT)
    _run(check_py27_compile)
    _run(check_ast_and_json)
    _run(check_dead_symbols)
    _run(check_config_parity)
    _run(check_i18n)
    version = _run(check_versions)
    _run(check_portal_limits)
    _run(check_msa_settings_version)
    _run(check_build_and_wotmod, version)
    _run(check_git_clean)

    fails = [r for r in _results if r[0] == 'FAIL']
    warns = [r for r in _results if r[0] == 'WARN']
    glyph = {'OK': '[ok]  ', 'WARN': '[WARN]', 'FAIL': '[FAIL]'}
    for level, name, detail in _results:
        print('%s %-22s %s' % (glyph[level], name, detail))
    print('\n%d ok, %d warning(s), %d failure(s)'
          % (len(_results) - len(fails) - len(warns), len(warns), len(fails)))
    if fails:
        print('\nNOT READY - fix the failures above before sending.')
        return 1
    print('\nAutomated gate PASSED. Now do the manual items in packaging/PRESEND_CHECKLIST.md.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
