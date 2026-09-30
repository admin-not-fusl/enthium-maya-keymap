"""
glove80_enthium.py - physical layout of the Glove80 with your Enthium legends.

This is the table the drawing code uses. Positions are in pixels, taken from the
MoErgo layout editor view, so the picture comes out looking like the editor.

Each key is a dict:
    x, y    centre of the key
    rot     rotation in degrees (thumb clusters only)
    legend  what's printed on the key
    char    what Maya sees when you press it, or None if Maya can never see it
            (Magic, mouse keys, ZMK macros...). None keys are drawn greyed out.
    mod     'ctrl' / 'alt' / 'shift' / 'cmd' if this key IS that modifier,
            so it can be highlighted on the layer it triggers.

Edit freely: if you move a key on the board, move it here.
"""

KEY_W = 88.0
KEY_H = 88.0
PITCH = 98.0
BOARD_W = 1930.0
BOARD_H = 810.0

# Home row mods, pinky -> index. This is the usual GUI / Alt / Ctrl / Shift order;
# if your Glove80 config differs, fix it here.
HOME_ROW_MODS = {'c': 'cmd', 'i': 'alt', 'a': 'ctrl', 'e': 'shift',
                 's': 'cmd', 'n': 'alt', 't': 'ctrl', 'h': 'shift'}

CTRL_FLIPS = {'Down': 'Up', 'Right': 'Left'}

# (x, y_of_first_key, [(legend, char), ...] top to bottom)
_COLUMNS = [
    (128, 111, [('F1', 'F1'), ('↑ scroll', None), ('↓ scroll', None),
                ('B', 'b'), ('Esc', 'Escape'), ('Magic', None)]),
    (225, 111, [('F2', 'F2'), ('1', '1'), ('Q', 'q'), ('C', 'c'), ("'", "'"), ('¥', '\\')]),
    (323, 62, [('F3', 'F3'), ('2', '2'), ('Y', 'y'), ('I', 'i'), (',', ','), ('↕', 'Down')]),
    (420, 62, [('F4', 'F4'), ('3', '3'), ('O', 'o'), ('A', 'a'), ('.', '.'), ('↔', 'Right')]),
    (518, 62, [('F5', 'F5'), ('4', '4'), ('U', 'u'), ('E', 'e'), (';', ';'), ('(', '(')]),
    (616, 160, [('5', '5'), ('=', '='), ('-', '-'), ('/', '/')]),
    (1301, 160, [('6', '6'), ('X', 'x'), ('K', 'k'), ('J', 'j')]),
    (1398, 62, [('F6', 'F6'), ('7', '7'), ('L', 'l'), ('H', 'h'), ('M', 'm'), ('&paranq_r', None)]),
    (1496, 62, [('F7', 'F7'), ('8', '8'), ('D', 'd'), ('T', 't'), ('G', 'g'), ('[', '[')]),
    (1594, 62, [('F8', 'F8'), ('9', '9'), ('P', 'p'), ('N', 'n'), ('F', 'f'), (']', ']')]),
    (1691, 111, [('F9', 'F9'), ('0', '0'), ('Z', 'z'), ('S', 's'), ('V', 'v'), ('`', '`')]),
    (1789, 111, [('F10', 'F10'), ('F11', 'F11'), ('F12', 'F12'),
                 ('W', 'w'), ('Insert', 'Insert'), ('Magic', None)]),
]

# (x, y, rotation, legend, char, mod)
_THUMBS = [
    (717, 550, 10, 'Ctrl', None, 'ctrl'),
    (810, 592, 20, 'Shift', None, 'shift'),
    (899, 650, 30, '&thumb_L', None, None),
    (625, 636, 10, 'R', 'r', None),
    (722, 678, 20, 'Alt', None, 'alt'),
    (818, 740, 30, 'Delete', 'Delete', None),
    (1213, 550, -10, '&thumb_LA', None, None),
    (1120, 592, -20, '&thumb_U', None, None),
    (1031, 650, -30, 'MousUp', None, None),
    (1305, 636, -10, '&space_LA', 'Space', None),
    (1208, 678, -20, 'Shift', None, 'shift'),
    (1112, 740, -30, 'MousDn', None, None),
]


# x ranges that each half occupies, thumb clusters included
HALVES = {'left': (60.0, 990.0), 'right': (1000.0, 1880.0)}


def board_size(half=None):
    if half:
        x0, x1 = HALVES[half]
        return x1 - x0, BOARD_H
    return BOARD_W, BOARD_H


def origin(half=None):
    return HALVES[half][0] if half else 0.0


def keys(half=None):
    """The 80 keys, or just the ones on one half."""
    out = _all_keys()
    if half:
        x0, x1 = HALVES[half]
        out = [k for k in out if x0 <= k['x'] <= x1]
    return out


def _all_keys():
    out = []
    for x, y0, entries in _COLUMNS:
        for i, (legend, char) in enumerate(entries):
            out.append({'x': x, 'y': y0 + i * PITCH, 'rot': 0, 'legend': legend,
                        'char': char, 'mod': HOME_ROW_MODS.get(char)})

    for x, y, rot, legend, char, mod in _THUMBS:
        out.append({'x': x, 'y': y, 'rot': rot, 'legend': legend, 'char': char, 'mod': mod})
    return out
