"""
drag_drop_install.py - drag this file from Finder/Explorer into the Maya viewport.

It puts this folder on Maya's Python path and makes a "Keymap" shelf tab with
three buttons: Check, Apply, Draw. Run it once; the shelf is saved with your prefs.

Expects the layout it ships with:
    maya_keymap/
        drag_drop_install.py   <- this file
        maya_keymap.py
        keymap_draw.py
        glove80_enthium.py
        keymap/                <- your .ini files
        img/                   <- images get written here
"""
import os
import sys

import maya.cmds as cmds
import maya.mel as mel

SHELF = 'Keymap'
SET_NAME = 'Enthium'

try:
    ROOT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    ROOT = ''

# Every button reloads the modules first: Maya caches imports for the whole session,
# so without this you keep running whatever version you first imported.
_RELOAD = ('import importlib, maya_keymap, glove80_enthium, keymap_draw\n'
           'for _m in (maya_keymap, glove80_enthium, keymap_draw): importlib.reload(_m)\n'
           'import maya_keymap as mk, keymap_draw as kd\n')

_BUTTONS = [
    ('Check', 'chk', 'Parse the ini files: problems and key conflicts. Changes nothing.',
     _RELOAD + 'mk.check(r"{keymap}")'),
    ('Apply', 'app', 'Rebuild the {set_name} hotkey set from the ini files.',
     _RELOAD + 'mk.apply(r"{keymap}", "{set_name}", export=r"{root}/{set_name}.mhk")'),
    ('Draw', 'img', 'Render one image per modifier layer into the img folder.',
     _RELOAD + 'kd.draw(r"{keymap}", r"{img}")'),
]


def install(root=None):
    root = root or ROOT
    if not root or not os.path.exists(os.path.join(root, 'maya_keymap.py')):
        cmds.error('could not find maya_keymap.py next to the installer')

    # path, now and for future sessions
    if root not in sys.path:
        sys.path.append(root)
    _persist_path(root)

    fmt = {'root': root.replace('\\', '/'),
           'keymap': os.path.join(root, 'keymap').replace('\\', '/'),
           'img': os.path.join(root, 'img').replace('\\', '/'),
           'set_name': SET_NAME}

    mel.eval('global string $gShelfTopLevel')
    if not cmds.shelfLayout(SHELF, exists=True):
        mel.eval('addNewShelfTab "%s"' % SHELF)
    for child in cmds.shelfLayout(SHELF, q=True, childArray=True) or []:
        if cmds.shelfButton(child, q=True, label=True) in [b[0] for b in _BUTTONS]:
            cmds.deleteUI(child)
    for label, overlay, annotation, command in _BUTTONS:
        cmds.shelfButton(parent=SHELF, label=label, imageOverlayLabel=overlay,
                         annotation=annotation.format(**fmt), image='pythonFamily.png',
                         sourceType='python', command=command.format(**fmt))
    cmds.saveAllShelves(mel.eval('$tmp = $gShelfTopLevel'))
    print('Keymap shelf installed, using %s' % root)


def _persist_path(root):
    """Append a sys.path line to userSetup.py so imports work next launch."""
    scripts = os.path.join(cmds.internalVar(userAppDir=True), 'scripts')
    if not os.path.isdir(scripts):
        os.makedirs(scripts)
    setup = os.path.join(scripts, 'userSetup.py')
    line = 'sys.path.append(r"%s")  # maya_keymap' % root
    existing = ''
    if os.path.exists(setup):
        with open(setup, encoding='utf-8') as f:
            existing = f.read()
    if line in existing:
        return
    with open(setup, 'a', encoding='utf-8') as f:
        f.write('\nimport sys\n%s\n' % line)
    print('added maya_keymap to %s' % setup)


def onMayaDroppedPythonFile(*args):
    install()


if __name__ == '__main__':
    install()
