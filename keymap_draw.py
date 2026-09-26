"""
keymap_draw.py - draw your keymap as one image per modifier layer.

    import sys; sys.path.append('/path/to/maya_keymap')
    import importlib, keymap_draw as kd; importlib.reload(kd)
    kd.draw('/path/to/maya_keymap/keymap', '/path/to/maya_keymap/img')

Writes, into the output folder:
    01_native.svg/.png, 02_shift.svg/.png, ... one per layer in LAYERS
    all_layers.svg/.png - every layer stacked as sections in one tall image

PNG needs Qt, which Maya already has. Outside Maya you get the SVGs and can
convert them with anything (rsvg-convert, Inkscape, resvg...).

Colours: keys are tinted by which .ini file the binding came from, unbound keys
stay dark, keys Maya can never see are greyed out, and the modifier keys that
make up the current layer are outlined in blue. Double-bound keys go red.
"""
import os
import re

import glove80_enthium as board

# label, modifiers held. Rename or reorder freely.
LAYERS = [
    ('native', []),
    ('shift', ['shift']),
    ('ctrl', ['ctrl']),
    ('alt', ['alt']),
    ('backspace', ['ctrl', 'shift']),
    ('escape', ['alt', 'shift']),
    ('R', ['alt', 'ctrl']),
    ('super', ['alt', 'ctrl', 'shift']),
]

BG = '#232b36'
KEY_BG = '#2f3945'
KEY_DEAD = '#272e38'
TEXT = '#e6ebf2'
DIM = '#6b7784'
MOD_OUTLINE = '#4ea3ff'
CONFLICT = '#7a2230'
TITLE_H = 96.0

# tint per .ini file, in sorted file order
PALETTE = ['#3c5a3f', '#3d4a66', '#5c4433', '#4a3a5c', '#33565c', '#5c3344', '#4f4a2e']


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _words(name):
    name = re.sub(r'^(mk_|ek_)', '', name)
    name = name.replace('_', ' ')
    name = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', name)
    return name.split()


def _wrap(name, max_chars=13, max_lines=3):
    lines, cur = [], ''
    for w in _words(name):
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
        if len(lines) == max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return [l[:max_chars + 3] for l in lines] or ['']


def _bindings(folder, context=None):
    """{(key, mods_tuple): [action, ...]} for one context, plus file colours.

    context=None draws the global bindings; pass a client name like 'graphEditor'
    to draw that editor's context instead."""
    from maya_keymap import load, parse_context
    actions, errors = load(folder)
    for e in errors:
        print(e)
    want = parse_context(context) if context else None
    files = sorted({a['file'] for a in actions})
    colours = {f: PALETTE[i % len(PALETTE)] for i, f in enumerate(files)}
    slots = {}
    for a in actions:
        if not a['enabled'] or a['context'] != want:
            continue
        for chord in a['chords']:
            slots.setdefault(chord, []).append(a)
    return slots, colours


def used_contexts(folder):
    """Client names that appear in the ini files."""
    from maya_keymap import load
    actions, _ = load(folder)
    return sorted({a['context'][1] for a in actions if a['enabled'] and a['context']})


def _key_svg(k, slots, colours, mods):
    parts = []
    cx, cy = k['x'], k['y']
    w, h = board.KEY_W, board.KEY_H
    x, y = cx - w / 2.0, cy - h / 2.0
    transform = ' transform="rotate(%g %g %g)"' % (k['rot'], cx, cy) if k['rot'] else ''
    parts.append('<g%s>' % transform)

    hits = slots.get((k['char'], tuple(sorted(mods))), []) if k['char'] else []
    is_layer_mod = k['mod'] in mods

    if len(hits) > 1:
        fill = CONFLICT
    elif hits:
        fill = colours.get(hits[0]['file'], KEY_BG)
    elif k['char'] is None:
        fill = KEY_DEAD
    else:
        fill = KEY_BG
    stroke = MOD_OUTLINE if is_layer_mod else 'none'
    parts.append('<rect x="%g" y="%g" width="%g" height="%g" rx="9" fill="%s" stroke="%s" '
                 'stroke-width="3"/>' % (x, y, w, h, fill, stroke))

    legend_colour = TEXT if (hits or is_layer_mod) else DIM
    parts.append('<text x="%g" y="%g" font-family="Helvetica, Arial, sans-serif" font-size="15" '
                 'fill="%s">%s</text>'
                 % (x + 8, y + 20, legend_colour, _esc(k['legend'][:9])))

    if hits:
        name = hits[0]['name'] if len(hits) == 1 else 'CONFLICT'
        lines = _wrap(name)
        size = 14 if len(lines) < 3 else 12
        top = cy + 8 - (len(lines) - 1) * (size + 1) / 2.0
        for i, line in enumerate(lines):
            parts.append('<text x="%g" y="%g" text-anchor="middle" font-family="Helvetica, Arial, '
                         'sans-serif" font-size="%d" fill="%s">%s</text>'
                         % (cx, top + i * (size + 1), size, TEXT, _esc(line)))
    parts.append('</g>')
    return ''.join(parts)


def _board_svg(label, mods, slots, colours, half=None):
    """One section: title plus the board (or one half of it), origin at 0,0."""
    title = label if not mods else '%s   (%s)' % (label, '+'.join(mods))
    want = tuple(sorted(mods))
    keys = board.keys(half)
    on_board = {k['char'] for k in keys if k['char']}
    n = sum(len(hits) for (key, m), hits in slots.items() if m == want and key in on_board)
    w, h = board.board_size(half)
    parts = ['<rect x="0" y="0" width="%g" height="%g" fill="%s"/>' % (w, h + TITLE_H, BG),
             '<text x="40" y="60" font-family="Helvetica, Arial, sans-serif" font-size="40" '
             'font-weight="bold" fill="%s">%s</text>' % (TEXT, _esc(title)),
             '<text x="%g" y="60" text-anchor="end" font-family="Helvetica, Arial, sans-serif" '
             'font-size="22" fill="%s">%d bound</text>' % (w - 40, DIM, n),
             '<g transform="translate(%g %g)">' % (-board.origin(half), TITLE_H)]
    for k in keys:
        parts.append(_key_svg(k, slots, colours, mods))
    parts.append('</g>')
    return ''.join(parts)


def _document(body, width, height):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="%g" height="%g" viewBox="0 0 %g %g">'
            '<rect width="%g" height="%g" fill="%s"/>%s</svg>'
            % (width, height, width, height, width, height, BG, body))


def _rasterize(svg_path, png_path, scale=1.0):
    try:
        try:
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtGui import QImage, QPainter, QColor
        except ImportError:
            from PySide2.QtSvg import QSvgRenderer
            from PySide2.QtGui import QImage, QPainter, QColor
    except ImportError:
        return False
    renderer = QSvgRenderer(svg_path)
    size = renderer.defaultSize()
    img = QImage(int(size.width() * scale), int(size.height() * scale), QImage.Format_ARGB32)
    img.fill(QColor(BG))
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    return bool(img.save(png_path, 'PNG'))


def draw(folder, out_dir, layers=None, png=True, scale=1.0, sheet=True, sheet_scale=1.0,
         context=None, all_contexts=True, half=None, sheet_half='left', sheet_columns=2):
    """Render one image per layer, plus one combined sheet of every layer.

    all_contexts  True (default) also draws each editor context used in the ini
                  files: its layers go in a subfolder, and any layer of it that
                  has bindings is appended as a section of the combined sheet.
    context       draw only this one context instead of the global bindings.
    half          per-layer images: None for the whole board, 'left' / 'right'.
    sheet_half    which half the combined sheet shows (default 'left').
    sheet_columns how many sections sit side by side on the sheet (default 2).
    """
    layers = layers or LAYERS
    targets = [context] if context or not all_contexts else [None] + used_contexts(folder)
    own_w, own_h = board.board_size(half)
    sheet_w, sheet_h = board.board_size(sheet_half)
    on_sheet_half = {k['char'] for k in board.keys(sheet_half) if k['char']}
    written, cells, gap = [], [], 40.0

    for target in targets:
        slots, colours = _bindings(folder, target)
        folder_out = out_dir if target is None else os.path.join(out_dir, target)
        os.makedirs(folder_out, exist_ok=True)
        for i, (label, mods) in enumerate(layers, start=1):
            title = label if target is None else '%s  -  %s' % (label, target)
            stem = os.path.join(folder_out, '%02d_%s' % (i, re.sub(r'\W+', '_', label)))
            svg_path = stem + '.svg'
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(_document(_board_svg(title, sorted(mods), slots, colours, half),
                                  own_w, own_h + TITLE_H))
            written.append(svg_path)
            if png and _rasterize(svg_path, stem + '.png', scale):
                written.append(stem + '.png')

            # global layers always get a section; a context only when it has something
            want = tuple(sorted(mods))
            n = sum(len(h) for (key, m), h in slots.items()
                    if m == want and key in on_sheet_half)
            if target is None or n:
                cells.append(_board_svg(title, sorted(mods), slots, colours, sheet_half))

    if sheet and cells:
        rows = (len(cells) + sheet_columns - 1) // sheet_columns
        body = ''.join('<g transform="translate(%g %g)">%s</g>'
                       % (gap + (i % sheet_columns) * (sheet_w + gap),
                          gap + (i // sheet_columns) * (sheet_h + TITLE_H + gap), cell)
                       for i, cell in enumerate(cells))
        svg_path = os.path.join(out_dir, 'all_layers.svg')
        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(_document(body, gap + sheet_columns * (sheet_w + gap),
                              gap + rows * (sheet_h + TITLE_H + gap)))
        written.append(svg_path)
        if png and _rasterize(svg_path, os.path.join(out_dir, 'all_layers.png'), sheet_scale):
            written.append(os.path.join(out_dir, 'all_layers.png'))

    print('wrote %d files to %s (%d sections on the sheet)' % (len(written), out_dir, len(cells)))
    if png and not any(p.endswith('.png') for p in written):
        print('no PNGs: Qt SVG module not available, SVGs were written instead')
    return written
