"""Cycle the viewport's shading mode on one key.

    shaded  ->  shaded + textures  ->  shaded + textures + lights  ->  shaded ...

Coming from wireframe or wireframe-on-shaded (or anything else that isn't one of
the three states) always lands on shaded + textures, with the wire overlay off.
Acts on the viewport under the pointer, falling back to the focused one.
"""
import maya.cmds as cmds

# label, displayTextures, displayLights
STATES = [
    ('shaded', False, 'default'),
    ('shaded + textured', True, 'default'),
    ('shaded + textured + lights', True, 'all'),
]
FROM_ELSEWHERE = 1  # index landed on when coming from wireframe etc.


def _model_panel():
    for panel in (cmds.getPanel(underPointer=True), cmds.getPanel(withFocus=True)):
        if panel and cmds.getPanel(typeOf=panel) == 'modelPanel':
            return panel
    return None


def cycle_shading():
    panel = _model_panel()
    if not panel:
        return
    appearance = cmds.modelEditor(panel, q=True, displayAppearance=True)
    textures = bool(cmds.modelEditor(panel, q=True, displayTextures=True))
    lights = cmds.modelEditor(panel, q=True, displayLights=True)
    wos = bool(cmds.modelEditor(panel, q=True, wireframeOnShaded=True))

    if appearance != 'smoothShaded' or wos:
        target = FROM_ELSEWHERE
    else:
        current = next((i for i, (_, t, l) in enumerate(STATES)
                        if t == textures and l == lights), None)
        target = FROM_ELSEWHERE if current is None else (current + 1) % len(STATES)

    label, textures, lights = STATES[target]
    cmds.modelEditor(panel, e=True, displayAppearance='smoothShaded', wireframeOnShaded=False,
                     displayTextures=textures, displayLights=lights)
    cmds.inViewMessage(amg='<hl>%s</hl>' % label, pos='midCenterBot', fade=True,
                       fadeStayTime=500)


cycle_shading()
