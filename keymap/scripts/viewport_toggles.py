"""Popup showing the viewport's Show-menu state. Drag across the boxes to toggle several."""
import maya.cmds as cmds
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

# (modelEditor flag, label) in the order they appear
TYPES = [
    ('polymeshes', 'Polygons'), ('nurbsSurfaces', 'NURBS Surfaces'), ('nurbsCurves', 'NURBS Curves'),
    ('subdivSurfaces', 'Subdivs'), ('planes', 'Planes'),
    ('lights', 'Lights'), ('cameras', 'Cameras'), ('imagePlane', 'Image Planes'),
    ('joints', 'Joints'), ('ikHandles', 'IK Handles'), ('deformers', 'Deformers'),
    ('dynamics', 'Dynamics'), ('fluids', 'Fluids'), ('hairSystems', 'Hair'), ('follicles', 'Follicles'),
    ('nCloths', 'nCloth'), ('nParticles', 'nParticles'), ('nRigids', 'nRigids'),
    ('dynamicConstraints', 'Dyn. Constraints'),
    ('locators', 'Locators'), ('dimensions', 'Dimensions'), ('pivots', 'Pivots'), ('handles', 'Handles'),
    ('textures', 'Textures'), ('strokes', 'Strokes'), ('motionTrails', 'Motion Trails'),
    ('pluginShapes', 'Plugin Shapes'), ('controlVertices', 'CVs'), ('hulls', 'Hulls'),
    ('grid', 'Grid'), ('hud', 'HUD'), ('manipulators', 'Manipulators'),
]
COLS = 2
_win = None


def _panel():
    for p in (cmds.getPanel(underPointer=True), cmds.getPanel(withFocus=True)):
        if p and cmds.getPanel(typeOf=p) == 'modelPanel':
            return p
    return None


class ShowPopup(QtWidgets.QFrame):
    def __init__(self, panel):
        super().__init__(None, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.panel = panel
        self.paint_value = None          # value being "painted" during a drag
        self.setStyleSheet('QFrame{background:#2b2b2b;border:1px solid #555;} QCheckBox{color:#ddd;padding:2px 8px;}')
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(6, 6, 6, 6); grid.setSpacing(0)
        title = QtWidgets.QLabel('Show  -  %s' % panel); title.setStyleSheet('color:#999;padding:2px 8px 6px;')
        grid.addWidget(title, 0, 0, 1, COLS)
        self.boxes = {}
        for i, (flag, label) in enumerate(TYPES):
            cb = QtWidgets.QCheckBox(label)
            cb.setChecked(bool(cmds.modelEditor(panel, q=True, **{flag: True})))
            cb.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)   # the frame handles the mouse
            self.boxes[cb] = flag
            grid.addWidget(cb, 1 + i // COLS, i % COLS)
        self.adjustSize()

    def _box_at(self, pos):
        for cb in self.boxes:
            if cb.geometry().contains(pos):
                return cb
        return None

    def _apply(self, cb, value):
        if cb.isChecked() == value:
            return
        cb.setChecked(value)
        cmds.modelEditor(self.panel, e=True, **{self.boxes[cb]: value})

    def mousePressEvent(self, e):
        cb = self._box_at(e.pos())
        if cb is None:
            return super().mousePressEvent(e)
        self.paint_value = not cb.isChecked()       # first box decides the direction
        self._apply(cb, self.paint_value)

    def mouseMoveEvent(self, e):
        if self.paint_value is None:
            return
        cb = self._box_at(e.pos())
        if cb is not None:
            self._apply(cb, self.paint_value)

    def mouseReleaseEvent(self, e):
        self.paint_value = None

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()


def toggle():
    global _win
    if _win is not None and _win.isVisible():
        _win.close(); _win = None
        return
    panel = _panel()
    if not panel:
        cmds.inViewMessage(amg='No viewport under the cursor', pos='midCenterBot', fade=True)
        return
    _win = ShowPopup(panel)
    _win.move(QtGui.QCursor.pos() + QtCore.QPoint(12, 12))
    _win.show()


toggle()
