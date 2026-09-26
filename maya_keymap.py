"""
maya_keymap.py - build a Maya hotkey set from a folder of .ini files.

The .ini files are the source of truth. Every apply() deletes the hotkey set and
rebuilds it from nothing, so what's in the files is exactly what's in Maya.

Usage (Script Editor, Python tab):

    import sys; sys.path.append('/path/to/maya_keymap')
    import importlib, maya_keymap as mk; importlib.reload(mk)

    mk.check('/path/to/maya_keymap/keymap')                    # parse + conflicts, touches nothing
    mk.apply('/path/to/maya_keymap/keymap', 'Enthium',
             export='/path/to/Enthium.mhk')                    # rebuild the set

    mk.reference('/path/to/maya_keymap/reference')             # optional: factory bindings as ini, for browsing

INI format - one section per action, section name = the runTimeCommand it runs:

    [DEFAULT]              ; applies to every section in this file
    enabled = true         ; set false to switch off the whole file

    [MoveTool]
    keys = y               ; space-separated chords: y  shift+y  ctrl+alt+F5
    release =              ; optional runTimeCommand to run on key release
    enabled = true
    note = anything you like

    [mk_MyThing]           ; custom action: give it code and it becomes a runTimeCommand
    keys = alt+y
    python = import maya.cmds as c; print(c.ls(sl=True))
    ; or:  mel = print "hi";
    ; or:  script = scripts/my_thing.py     (path relative to this ini; use this for multi-line code)
    ; command = OtherName  (optional: bind to a different runTimeCommand than the section name)

    [RotateUVTool]         ; editor-only binding, lives in a hotkey context
    keys = a
    context = polyTexturePlacementPanel
    ; context = Editor:graphEditor   (full form; the type defaults to Editor)

Contexts: a binding with no 'context' is global. One with a context only fires
inside that editor, so the same chord can mean different things in the viewport
and in the UV editor without being a conflict. mk.contexts() lists the client
names Maya knows about.

Rules:
  - Files whose name starts with '_' are ignored (handy for parking stuff).
  - Subfolders are read too, in sorted order.
  - An action name may only appear once across all files.
  - Two enabled actions on the same chord in the same context is an error.
  - Modifiers: ctrl, alt (or opt), shift, cmd (macOS only). An uppercase letter means shift.
  - Special keys: Up Down Left Right Home End Page_Up Page_Down Insert Delete
    Backspace Tab Return Space Escape F1..F12 (case-insensitive).
"""
import configparser
import glob
import re
import itertools
import os

import maya.cmds as cmds

__version__ = 7  # bump when editing; check() prints it so you can spot a stale import

# ---------------------------------------------------------------- keys & modifiers

LETTERS = list('abcdefghijklmnopqrstuvwxyz')
DIGITS = list('0123456789')
PUNCT = list("`-=[]\\;',./")
SPECIAL = ['Up', 'Down', 'Left', 'Right', 'Home', 'End', 'Page_Up', 'Page_Down',
           'Insert', 'Delete', 'Backspace', 'Tab', 'Return', 'Space', 'Escape'] + \
          ['F%d' % i for i in range(1, 13)]
SPECIAL_LOOKUP = {s.lower(): s for s in SPECIAL}
SPECIAL_LOOKUP.update({'esc': 'Escape', 'enter': 'Return', 'pgup': 'Page_Up', 'pgdn': 'Page_Down',
                       'del': 'Delete', 'ins': 'Insert', 'bksp': 'Backspace'})
# Maya stores shifted characters literally, e.g. hotkey -keyShortcut "+" ... , so accept them.
SHIFTED = list('~!@#$%^&*()_+{}|:"<>?')
ALL_KEYS = LETTERS + DIGITS + PUNCT + SHIFTED + SPECIAL

IS_MAC = bool(cmds.about(macOS=True))
MOD_NAMES = ['ctrl', 'alt', 'shift'] + (['cmd'] if IS_MAC else [])
MOD_FLAGS = {'ctrl': 'ctrlModifier', 'alt': 'altModifier',
             'shift': 'shiftModifier', 'cmd': 'commandModifier'}
MOD_ALIASES = {'ctrl': 'ctrl', 'control': 'ctrl', 'alt': 'alt', 'opt': 'alt', 'option': 'alt',
               'shift': 'shift', 'cmd': 'cmd', 'command': 'cmd'}
MOD_COMBOS = [list(c) for n in range(len(MOD_NAMES) + 1)
              for c in itertools.combinations(MOD_NAMES, n)]

CUSTOM_CATEGORY = 'Custom Scripts.Keymap'


DEFAULT_CTX_TYPE = 'Editor'


_CTX_MODE = None


def _ctx_mode():
    """How this Maya build addresses hotkey contexts.

    'flag'    cmds.hotkey takes a ctxClient flag
    'current' you set hotkeyCtx -currentClient, then normal hotkey calls land there
    'none'    neither works: context bindings are not supported here
    """
    global _CTX_MODE
    if _CTX_MODE is None:
        try:
            ctx_help = cmds.help('hotkeyCtx') or ''
            hk_help = cmds.help('hotkey') or ''
        except RuntimeError:
            ctx_help = hk_help = ''
        if 'currentClient' in ctx_help:
            # what the Hotkey Editor itself uses, and the only form that queries reliably
            _CTX_MODE = 'current'
        elif 'ctxClient' in hk_help:
            _CTX_MODE = 'flag'
        else:
            _CTX_MODE = 'none'
    return _CTX_MODE


def _ctx_supported():
    return _ctx_mode() != 'none'


def _ctx_flag(ctx):
    """Extra flags for cmds.hotkey when the build supports the ctxClient flag."""
    return {'ctxClient': ctx[1]} if ctx and _ctx_mode() == 'flag' else {}


class _in_context(object):
    """Switch the context's current client for the duration of a block."""

    def __init__(self, ctx):
        self.ctx = ctx if ctx and _ctx_mode() == 'current' else None
        self.prev = ''

    def __enter__(self):
        if self.ctx:
            ctx_type, client = self.ctx
            self.prev = cmds.hotkeyCtx(type=ctx_type, q=True, currentClient=True) or ''
            cmds.hotkeyCtx(type=ctx_type, currentClient=client)
        return self

    def __exit__(self, *exc):
        if self.ctx:
            cmds.hotkeyCtx(type=self.ctx[0], currentClient=self.prev)
        return False


def debug_hotkey_flags():
    """Print what this Maya's hotkey commands actually accept."""
    print('context mode: %s' % _ctx_mode())
    for c in ('hotkey', 'hotkeyCtx'):
        print('\n--- %s ---' % c)
        print(cmds.help(c))


def _ctx_types():
    try:
        return list(cmds.hotkeyCtx(q=True, typeArray=True) or [])
    except (RuntimeError, TypeError):
        return [DEFAULT_CTX_TYPE]


def _ctx_clients(ctx_type=DEFAULT_CTX_TYPE):
    try:
        return list(cmds.hotkeyCtx(type=ctx_type, q=True, clientArray=True) or [])
    except (RuntimeError, TypeError):
        return []


def selftest():
    """Check that querying works at all. If this fails, wipes are silently no-ops."""
    prev = cmds.hotkeySet(q=True, current=True)
    cmds.hotkeySet('Maya_Default', e=True, current=True)
    try:
        hits = [k for k in ('w', 'e', 'r', 'z', 'F8') if any(_query(k, m)[0] for m in MOD_COMBOS)]
    finally:
        cmds.hotkeySet(prev, e=True, current=True)
    print('context mode: %s' % _ctx_mode())
    if hits:
        print('queries OK: found factory bindings on %s' % ', '.join(hits))
        return True
    print('QUERIES BROKEN: Maya_Default looks empty, so wipes will do nothing. '
          'Run mk.debug_hotkey_flags() and send me the output.')
    return False


def contexts():
    """Print the context types and client names this Maya knows about."""
    for t in _ctx_types():
        clients = _ctx_clients(t)
        print('%s: %s' % (t, ', '.join(clients) if clients else '(none)'))
    return {t: _ctx_clients(t) for t in _ctx_types()}


def parse_context(text):
    """'Editor:graphEditor' -> ('Editor', 'graphEditor'); '' -> None.

    A bare name like 'ngst2PaintContext' is looked up across every context type
    Maya reports, so you only need the 'Type:' prefix when it's ambiguous."""
    text = (text or '').strip()
    if not text:
        return None
    if ':' in text:
        ctx_type, client = text.split(':', 1)
        return ctx_type.strip(), client.strip()
    owners = [t for t in _ctx_types() if text in _ctx_clients(t)]
    if len(owners) == 1:
        return owners[0], text
    return DEFAULT_CTX_TYPE, text


def format_context(ctx):
    return 'global' if not ctx else '%s:%s' % ctx


def parse_chord(text):
    """'ctrl+shift+y' -> ('y', ('ctrl', 'shift')). The key may itself be '+'."""
    rest = text.strip()
    mods = set()
    while True:
        m = re.match(r'(?i)^(ctrl|control|alt|opt|option|shift|cmd|command)\+(?=.)', rest)
        if not m:
            break
        mods.add(MOD_ALIASES[m.group(1).lower()])
        rest = rest[m.end():]
    if not rest:
        raise ValueError('bad chord %r' % text)
    if 'cmd' in mods and not IS_MAC:
        raise ValueError('cmd modifier only exists on macOS: %r' % text)
    key = rest
    if len(key) == 1:
        if key.isalpha():
            if key.isupper():
                mods.add('shift')
            key = key.lower()
        elif key not in DIGITS + PUNCT + SHIFTED:
            raise ValueError('unsupported key %r in %r' % (key, text))
    else:
        if key.lower() not in SPECIAL_LOOKUP:
            raise ValueError('unknown key name %r in %r' % (key, text))
        key = SPECIAL_LOOKUP[key.lower()]
    return key, tuple(sorted(mods))


def format_chord(key, mods):
    return '+'.join(list(mods) + [key])

# ---------------------------------------------------------------- loading

def load(folder):
    """Read every .ini under folder. Returns (actions, errors)."""
    actions, errors, seen = [], [], {}
    paths = sorted(glob.glob(os.path.join(folder, '**', '*.ini'), recursive=True))
    for path in paths:
        if os.path.basename(path).startswith('_'):
            continue
        rel = os.path.relpath(path, folder)
        cp = configparser.ConfigParser(interpolation=None, strict=True,
                                       comment_prefixes=('#', ';'))
        cp.optionxform = str  # keep case of option names
        try:
            with open(path, encoding='utf-8') as f:
                cp.read_file(f)
        except configparser.Error as ex:
            errors.append('%s: %s' % (rel, ex))
            continue
        for name in cp.sections():
            s = cp[name]
            if name in seen:
                errors.append('%s: [%s] already defined in %s' % (rel, name, seen[name]))
                continue
            seen[name] = rel
            a = {'name': name, 'file': rel, 'dir': os.path.dirname(path),
                 'enabled': s.getboolean('enabled', fallback=True),
                 'command': s.get('command', name).strip(),
                 'release': s.get('release', '').strip(),
                 'python': s.get('python', '').strip(),
                 'mel': s.get('mel', '').strip(),
                 'script': s.get('script', '').strip(),
                 'note': s.get('note', '').strip(),
                 'context': parse_context(s.get('context', '')),
                 'chords': []}
            if sum(bool(a[k]) for k in ('python', 'mel', 'script')) > 1:
                errors.append('%s: [%s] use only one of python / mel / script' % (rel, name))
            for c in s.get('keys', '').split():
                try:
                    a['chords'].append(parse_chord(c))
                except ValueError as ex:
                    errors.append('%s: [%s] %s' % (rel, name, ex))
            actions.append(a)
    return actions, errors


def _conflicts(actions):
    slots = {}
    for a in actions:
        if a['enabled']:
            for key, mods in a['chords']:
                slots.setdefault((a['context'], key, mods), []).append(a)
    return {c: al for c, al in slots.items() if len(al) > 1}

# ---------------------------------------------------------------- command resolution

def _rtc_exists(name):
    return bool(cmds.runTimeCommand(name, exists=True))


def _name_commands():
    out = {}
    n = cmds.assignCommand(q=True, numElements=True) or 0
    for i in range(1, n + 1):
        out[cmds.assignCommand(i, q=True, name=True)] = i
    return out


def _code_of(a):
    if a['python']:
        return a['python'], 'python'
    if a['mel']:
        return a['mel'], 'mel'
    if a['script']:
        p = os.path.join(a['dir'], a['script'])
        with open(p, encoding='utf-8') as f:
            code = f.read()
        return code, ('mel' if p.lower().endswith('.mel') else 'python')
    return None, None


def _check_commands(actions):
    """Problems that would stop apply(), without changing anything."""
    problems = []
    for a in actions:
        if not a['enabled']:
            continue
        if a['script'] and not os.path.exists(os.path.join(a['dir'], a['script'])):
            problems.append('%s: [%s] script not found: %s' % (a['file'], a['name'], a['script']))
            continue
        code, _ = _code_of(a)
        if code:
            if _rtc_exists(a['command']) and cmds.runTimeCommand(a['command'], q=True, default=True):
                problems.append('%s: [%s] %s is a built-in command, give your action another name'
                                % (a['file'], a['name'], a['command']))
        elif not _rtc_exists(a['command']):
            problems.append('%s: [%s] no runTimeCommand called %s'
                            % (a['file'], a['name'], a['command']))
        if a['release'] and not _rtc_exists(a['release']):
            problems.append('%s: [%s] no runTimeCommand called %s (release)'
                            % (a['file'], a['name'], a['release']))
        if a['context']:
            ctx_type, client = a['context']
            known = _ctx_clients(ctx_type)
            if known and client not in known:
                problems.append('%s: [%s] unknown context %s, known %s clients: %s'
                                % (a['file'], a['name'], client, ctx_type, ', '.join(known)))
            elif not _ctx_supported():
                problems.append('%s: [%s] context bindings unsupported here, '
                                'run mk.debug_hotkey_flags() and send me the output'
                                % (a['file'], a['name']))
    return problems



def _name_command_for(rtc, ncs):
    nc = rtc + 'NameCommand'
    if nc not in ncs:
        ann = cmds.runTimeCommand(rtc, q=True, annotation=True) or rtc
        cmds.nameCommand(nc, annotation=ann, command=rtc, sourceType='mel')
        ncs[nc] = True
    return nc


def _ensure_runtime_command(a):
    code, lang = _code_of(a)
    if not code:
        return a['command']
    rtc = a['command']
    ann = a['note'] or rtc
    if _rtc_exists(rtc):
        cmds.runTimeCommand(rtc, e=True, command=code, commandLanguage=lang, annotation=ann)
    else:
        cmds.runTimeCommand(rtc, command=code, commandLanguage=lang, annotation=ann,
                            category=CUSTOM_CATEGORY)
    return rtc

# ---------------------------------------------------------------- public API

def check(folder):
    """Parse everything, report problems and conflicts. Changes nothing. Returns True if clean."""
    actions, errors = load(folder)
    errors += _check_commands(actions)
    for (ctx, key, mods), al in sorted(_conflicts(actions).items(), key=lambda kv: str(kv[0])):
        errors.append('CONFLICT [%s] %s: %s'
                      % (format_context(ctx), format_chord(key, mods),
                         ', '.join('%s (%s)' % (a['name'], a['file']) for a in al)))
    for e in errors:
        print(e)
    on = [a for a in actions if a['enabled']]
    print('%d actions, %d enabled, %d bindings, %d problems (maya_keymap v%d)'
          % (len(actions), len(on), sum(len(a['chords']) for a in on), len(errors), __version__))
    return not errors


def _query(key, mods, ctx=None):
    """What's bound to a chord. In query mode the key is POSITIONAL: -k is a
    boolean there, so cmds.hotkey(keyShortcut=key, q=True) raises TypeError."""
    flags = {MOD_FLAGS[m]: True for m in mods}
    flags.update(_ctx_flag(ctx))
    try:
        with _in_context(ctx):
            return (cmds.hotkey(key, q=True, name=True, **flags) or '',
                    cmds.hotkey(key, q=True, releaseName=True, **flags) or '')
    except RuntimeError:
        return '', 


def _set_flags(mods):
    return {MOD_FLAGS[m]: (m in mods) for m in MOD_NAMES}


def _wipe_current_set(ctx=None):
  with _in_context(ctx):
    for key in ALL_KEYS:
        variants = [key] + ([key.upper()] if key in LETTERS else [])
        for k in variants:
            for mods in MOD_COMBOS:
                press, rel = _query(k, mods, ctx)
                if press or rel:
                    flags = _set_flags(mods)
                    flags.update(_ctx_flag(ctx))
                    cmds.hotkey(keyShortcut=k, name='', releaseName='', **flags)


def apply(folder, set_name='Enthium', export=None, wipe_contexts='used'):
    """Delete set_name and rebuild it with exactly the enabled bindings in folder.

    wipe_contexts: 'used'  clear only the editor contexts your ini files mention
                   'all'   clear every context Maya reports (slow, very from-scratch)
                   'none'  leave editor contexts at their factory bindings
    """
    if not check(folder):
        raise RuntimeError('keymap has problems, nothing was changed (see above)')
    if set_name == 'Maya_Default':
        raise RuntimeError('pick another set name, Maya_Default is locked')

    actions, _ = load(folder)
    ncs = _name_commands()

    if cmds.hotkeySet(set_name, exists=True):
        cmds.hotkeySet('Maya_Default', e=True, current=True)
        cmds.hotkeySet(set_name, e=True, delete=True)
    cmds.hotkeySet(set_name, source='Maya_Default', current=True)
    _wipe_current_set()

    if wipe_contexts == 'all':
        wipe = [(t, c) for t in _ctx_types() for c in _ctx_clients(t)]
    elif wipe_contexts == 'used':
        wipe = sorted({a['context'] for a in actions if a['enabled'] and a['context']})
    else:
        wipe = []
    for ctx in wipe:
        _wipe_current_set(ctx)

    n = 0
    for a in actions:
        if not a['enabled']:
            continue
        press_nc = _name_command_for(_ensure_runtime_command(a), ncs)
        rel_nc = _name_command_for(a['release'], ncs) if a['release'] else ''
        with _in_context(a['context']):
            for key, mods in a['chords']:
                flags = _set_flags(mods)
                flags.update(_ctx_flag(a['context']))
                cmds.hotkey(keyShortcut=key, name=press_nc, releaseName=rel_nc, **flags)
                n += 1

    cmds.savePrefs(hotkeys=True)
    if export:
        cmds.hotkeySet(set_name, e=True, export=export)
    ctx_n = sum(len(a['chords']) for a in actions if a['enabled'] and a['context'])
    print('applied %d bindings to hotkey set %s (%d of them in editor contexts)'
          % (n, set_name, ctx_n))


def _scan(commands, ctx=None):
    """{action: {'chords': [...], 'release': ''}} for the current set, in one context."""
    found = {}
    for key in ALL_KEYS:
        variants = [(key, False)] + ([(key.upper(), True)] if key in LETTERS else [])
        for k, implied_shift in variants:
            for mods in MOD_COMBOS:
                if implied_shift and 'shift' in mods:
                    continue
                press, rel = _query(k, mods, ctx)
                if not press:
                    continue
                action = commands.get(press, press)
                if not _rtc_exists(action):
                    action = press
                chord = format_chord(key, sorted(set(mods) | ({'shift'} if implied_shift else set())))
                entry = found.setdefault(action, {'chords': [], 'release': ''})
                if chord not in entry['chords']:
                    entry['chords'].append(chord)
                if rel:
                    entry['release'] = commands.get(rel, rel)
    return found


def _write_ref(path, header, items, ctx=None):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('# %s\n\n[DEFAULT]\nenabled = false\n\n' % header)
        for action, entry in sorted(items):
            ann = ''
            if _rtc_exists(action):
                ann = (cmds.runTimeCommand(action, q=True, annotation=True) or '').replace('\n', ' ')
            f.write('[%s]\nkeys = %s\n' % (action, ' '.join(entry['chords'])))
            if entry['release']:
                f.write('release = %s\n' % entry['release'])
            if ctx:
                f.write('context = %s\n' % ('%s:%s' % ctx))
            if ann:
                f.write('note = %s\n' % ann)
            f.write('\n')


def reference(out_folder, set_name='Maya_Default', include_contexts=True):
    """Write a set's bindings as disabled ini files, one per command category.
    Files are prefixed with '_' so load() ignores them even if they end up in your keymap folder.
    Copy sections you want into your own files."""
    prev = cmds.hotkeySet(q=True, current=True)
    cmds.hotkeySet(set_name, e=True, current=True)
    commands = {}
    n = cmds.assignCommand(q=True, numElements=True) or 0
    for i in range(1, n + 1):
        commands[cmds.assignCommand(i, q=True, name=True)] = \
            (cmds.assignCommand(i, q=True, command=True) or '').strip().rstrip(';').strip()

    try:
        found = _scan(commands)
        per_ctx = {}
        if include_contexts:
            for t in _ctx_types():
                for client in _ctx_clients(t):
                    hits = _scan(commands, (t, client))
                    if hits:
                        per_ctx[(t, client)] = hits
    finally:
        cmds.hotkeySet(prev, e=True, current=True)

    by_cat = {}
    for action, entry in found.items():
        cat = 'Other'
        if _rtc_exists(action):
            cat = cmds.runTimeCommand(action, q=True, category=True) or 'Other'
        by_cat.setdefault(cat, []).append((action, entry))

    os.makedirs(out_folder, exist_ok=True)
    for cat, items in sorted(by_cat.items()):
        fname = '_ref_' + ''.join(ch if ch.isalnum() else '_' for ch in cat) + '.ini'
        _write_ref(os.path.join(out_folder, fname),
                   '%d bindings from %s, category: %s' % (len(items), set_name, cat), items)
    for ctx, hits in sorted(per_ctx.items()):
        fname = '_ref_ctx_' + ''.join(ch if ch.isalnum() else '_' for ch in ctx[1]) + '.ini'
        _write_ref(os.path.join(out_folder, fname),
                   '%d bindings from %s, context: %s:%s' % (len(hits), set_name, ctx[0], ctx[1]),
                   list(hits.items()), ctx)
    print('wrote %d categories and %d editor contexts to %s'
          % (len(by_cat), len(per_ctx), out_folder))
