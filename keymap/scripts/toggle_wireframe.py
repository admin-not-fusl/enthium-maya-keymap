"""Toggle the viewport between wireframe and wireframe-on-shaded.

    wireframe  <->  wireframe on shaded

Coming from anything else (plain shaded, textured...) lands on wireframe first.
Textures and lights are left as they are, so wireframe-on-shaded keeps whatever
shading you had. Acts on the viewport under the pointer, else the focused one.
"""
import maya.cmds as cmds


def _model_panel():
    for panel in (cmds.getPanel(underPointer=True), cmds.getPanel(withFocus=True)):
        if panel and cmds.getPanel(typeOf=panel) == 'modelPanel':
            return panel
    return None


def toggle_wireframe():
    panel = _model_panel()
    if not panel:
        return
    appearance = cmds.modelEditor(panel, q=True, displayAppearance=True)
    wos = bool(cmds.modelEditor(panel, q=True, wireframeOnShaded=True))

    if appearance == 'wireframe':
        cmds.modelEditor(panel, e=True, displayAppearance='smoothShaded', wireframeOnShaded=True)
        label = 'wireframe on shaded'
    else:
        cmds.modelEditor(panel, e=True, displayAppearance='wireframe', wireframeOnShaded=False)
        label = 'wireframe'
    cmds.inViewMessage(amg='<hl>%s</hl>' % label, pos='midCenterBot', fade=True, fadeStayTime=500)


toggle_wireframe()
