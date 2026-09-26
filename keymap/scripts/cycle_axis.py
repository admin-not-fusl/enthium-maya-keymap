"""Cycle the active transform tool's axis orientation: object -> world -> component.

Works on whichever of Move / Rotate / Scale is the current tool. Modes that a tool
does not support are skipped, so the cycle is shorter for Rotate if it turns out
to have no component mode in this build.
"""
import maya.cmds as cmds

# (label, mode number) in cycle order, per manipulator class
_CYCLE = {
    'manipMove':   [('object', 0), ('world', 2), ('component', 10)],
    'manipRotate': [('object', 0), ('world', 1), ('component', 4)],
    'manipScale':  [('object', 0), ('world', 2), ('component', 10)],
}
_CMD = {
    'manipMove': cmds.manipMoveContext,
    'manipRotate': cmds.manipRotateContext,
    'manipScale': cmds.manipScaleContext,
}
_CTX = {'manipMove': 'Move', 'manipRotate': 'Rotate', 'manipScale': 'Scale'}


def _active_manip():
    ctx = cmds.currentCtx()
    try:
        cls = cmds.contextInfo(ctx, c=True)
    except RuntimeError:
        cls = ''
    if cls in _CYCLE:
        return cls
    # super contexts (the default W/E/R tools) report their own class, so fall back on name
    low = ctx.lower()
    for cls in _CYCLE:
        if cls[5:].lower() in low:
            return cls
    return None


def cycle_axis():
    cls = _active_manip()
    if not cls:
        cmds.inViewMessage(amg='No transform tool active', pos='midCenterBot', fade=True)
        return
    cmd, name, cycle = _CMD[cls], _CTX[cls], _CYCLE[cls]
    current = cmd(name, q=True, mode=True)
    order = [m for _, m in cycle]
    start = order.index(current) if current in order else -1
    for step in range(1, len(cycle) + 1):
        label, mode = cycle[(start + step) % len(cycle)]
        try:
            cmd(name, e=True, mode=mode)
        except RuntimeError:
            continue  # this build doesn't have that mode for this tool
        if cmd(name, q=True, mode=True) == mode:
            cmds.inViewMessage(amg='%s axis: <hl>%s</hl>' % (name, label),
                               pos='midCenterBot', fade=True, fadeStayTime=600)
            return
    cmds.inViewMessage(amg='Could not change axis mode', pos='midCenterBot', fade=True)


cycle_axis()
