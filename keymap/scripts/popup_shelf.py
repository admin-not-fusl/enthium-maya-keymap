"""Tool palette at the cursor. Reads keymap/_palette.ini; sections are groups.
Each line is  Label = value, where value is one of:
    RunTimeCommandName        runs it
    py:python code            runs it
    cam:top                   look through that camera in the viewport you opened it over
    pop:                      maximise / restore that viewport (like tapping space)
    layout:Four View          switch the panel layout by name
"""
import os, configparser
import maya.cmds as cmds, maya.mel as mel
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

INI = os.path.join(os.path.dirname(__file__), '..', '_palette.ini')

ICON_SIZE = 40      # icon edge in px
TILE_W    = 52      # tile width; the short name is clipped to fit this
TILE_COLS = 2       # tiles per row inside each group
LABEL_PT  = 8       # font size of the name under the icon

# Icons for the view commands, which aren't runtime commands.
DEFAULT_ICONS = {'cam:': 'Camera.png', 'pop:': 'singlePerspLayout.png', 'layout:': 'fourViewLayout.png'}


def _icon(cmd, override):
    names = [override] if override else []
    if not cmd.startswith(('py:', 'cam:', 'pop:', 'layout:')):
        try:
            names.append(cmds.runTimeCommand(cmd, q=True, image=True) or '')
        except RuntimeError:
            pass
        names.append(cmd[:1].lower() + cmd[1:] + '.png')       # shelf naming guess: PolyBevel -> polyBevel.png
    names.append(DEFAULT_ICONS.get(cmd.split(':')[0] + ':', ''))
    for name in filter(None, names):
        for path in (':/' + name, name, os.path.join(os.path.dirname(INI), name)):
            pm = QtGui.QPixmap(path)
            if not pm.isNull():
                return QtGui.QIcon(pm)
    return None
_win = None


def _model_panel():
    for p in (cmds.getPanel(underPointer=True), cmds.getPanel(withFocus=True)):
        if p and cmds.getPanel(typeOf=p) == 'modelPanel':
            return p
    return None


def _load():
    cp = configparser.ConfigParser(interpolation=None, comment_prefixes=('#', ';'))
    cp.optionxform = str
    cp.read(INI, encoding='utf-8')
    return [(g, list(cp[g].items())) for g in cp.sections()]


def _run(cmd, panel):
    if cmd.startswith('py:'):
        exec(cmd[3:], {'cmds': cmds, 'mel': mel, 'panel': panel})
    elif cmd.startswith('cam:'):
        if panel:
            cmds.lookThru(panel, cmd[4:].strip())
    elif cmd.startswith('pop:'):
        if panel:
            cmds.setFocus(panel)
            mel.eval('panePop')
    elif cmd.startswith('layout:'):
        mel.eval('setNamedPanelLayout "%s"' % cmd[7:].strip())
    else:
        mel.eval(cmd)


class Palette(QtWidgets.QFrame):
    def __init__(self, groups, panel):
        super().__init__(None, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.panel = panel
        self.setStyleSheet('QFrame{background:#2b2b2b;border:1px solid #555;}'
                           'QLabel{color:#8a8;font-weight:bold;padding:4px 6px 0;}'
                           'QPushButton{color:#ddd;background:#3a3a3a;border:none;padding:5px 10px;text-align:left;}'
                           'QPushButton:hover{background:#4a5a7a;}'
                           'QLineEdit{color:#eee;background:#1e1e1e;border:1px solid #555;padding:3px;}'
                            'QToolButton{color:#ddd;background:#3a3a3a;border:none;padding:3px;}'
                            'QToolButton:hover{background:#4a5a7a;}')
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(2)
        self.search = QtWidgets.QLineEdit(placeholderText='filter...  (%s)' % (panel or 'no viewport'))
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._run_first)
        lay.addWidget(self.search)
        cols = QtWidgets.QHBoxLayout(); cols.setSpacing(8); lay.addLayout(cols)
        self.buttons = []
        for group, items in groups:
            col = QtWidgets.QVBoxLayout(); col.setSpacing(2); col.setAlignment(QtCore.Qt.AlignTop)
            col.addWidget(QtWidgets.QLabel(group))
            grid = QtWidgets.QGridLayout(); grid.setSpacing(3); col.addLayout(grid)
            for i, (label, value) in enumerate(items):
                cmd, override, short = (list(map(str.strip, value.split('|'))) + ['', ''])[:3]
                b = QtWidgets.QToolButton()
                b.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
                b.setFixedSize(TILE_W, ICON_SIZE + 24)
                b.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
                f = b.font(); f.setPointSizeF(LABEL_PT); b.setFont(f)
                b.setText(QtGui.QFontMetrics(f).elidedText(short or label, QtCore.Qt.ElideRight, TILE_W - 6))
                b.setToolTip(label)
                b.setProperty('match', ('%s %s' % (label, short)).lower())
                icon = _icon(cmd, override)
                if icon:
                    b.setIcon(icon)
                else:
                    b.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
                b.clicked.connect(lambda _=False, c=cmd: self._fire(c))
                grid.addWidget(b, i // TILE_COLS, i % TILE_COLS)
                self.buttons.append(b)
            cols.addLayout(col)
        self.adjustSize()

    def _fire(self, cmd):
        self.close(); _run(cmd, self.panel)

    def _filter(self, text):
        t = text.lower()
        for b in self.buttons:
            b.setVisible(t in b.property('match'))
        self.adjustSize()

    def _run_first(self):
        for b in self.buttons:
            if b.isVisible():
                b.click(); return

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        else:
            self.search.setFocus(); self.search.event(e)


def toggle():
    global _win
    if _win is not None and _win.isVisible():
        _win.close(); _win = None; return
    panel = _model_panel()                      # grab it before the popup covers it
    _win = Palette(_load(), panel)
    _win.adjustSize()
    cur = QtGui.QCursor.pos()
    pos = cur - QtCore.QPoint(_win.width() // 2, _win.height() // 2)
    screen = QtGui.QGuiApplication.screenAt(cur).availableGeometry()
    pos.setX(max(screen.left(), min(pos.x(), screen.right() - _win.width())))
    pos.setY(max(screen.top(), min(pos.y(), screen.bottom() - _win.height())))
    _win.move(pos)
    _win.show(); _win.search.setFocus()


toggle()
