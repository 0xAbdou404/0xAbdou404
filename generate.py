#!/usr/bin/env python3
"""
generate.py  -  Neofetch-style GitHub profile card generator (Andrew6rant style)

Reads config.json + a themed ASCII portrait and renders a self-contained card as:
  assets/dark_mode.svg   assets/light_mode.svg     (glyphs baked as vector paths,
  assets/preview_dark.png assets/preview_light.png   so GitHub needs no fonts)

The SVG and the PNG preview come from the SAME cairo drawing code, so what you
verify in the PNG is exactly what GitHub will display.
"""
import cairo, json, os

HERE = os.path.dirname(os.path.abspath(__file__))

# ----- typography / layout knobs -------------------------------------------
FONT      = "DejaVu Sans Mono"
SIZE      = 16.0     # font size in px
LINE      = 21.0     # line advance in px
TOP       = 40       # top padding
BOTTOM    = 34       # bottom padding
PADX      = 38       # left / right padding
GAP       = 44       # gap between portrait and panel
RADIUS    = 14       # card corner radius

THEMES = {
    "dark": {
        "bg": "#0D1117", "border": "#30363D", "fg": "#C9D1D9", "dim": "#6E7681",
        "dots": "#39414A", "label": "#E3A857", "value": "#79C0FF",
        "user": "#7EE787", "green": "#3FB950", "red": "#FF7B72",
        "portrait": "assets/portrait_dark.png",
    },
    "light": {
        "bg": "#FFFFFF", "border": "#D0D7DE", "fg": "#1F2328", "dim": "#8C959F",
        "dots": "#D8DEE4", "label": "#BC4C00", "value": "#0969DA",
        "user": "#1A7F37", "green": "#1A7F37", "red": "#CF222E",
        "portrait": "assets/portrait_light.png",
    },
}


def hexrgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255


# --------------------------------------------------------------------------
# line builders: each returns a list of (text, color_key) "runs"
# --------------------------------------------------------------------------
def field(label, value, cols):
    core = f"- {label}: "
    dots = max(2, cols - len(core) - len(value))
    return [("- ", "dim"), (label, "label"), (": ", "fg"),
            ("." * dots, "dots"), (value, "value")]


def section(label, cols):
    used = 3 + len(label) + 1            # "- " + label + " "
    dashes = max(3, cols - used)
    return [("- ", "dim"), (label, "label"), (" ", "fg"), ("-" * dashes, "dim")]


def userhost(user, host, cols):
    used = len(user) + 1 + len(host) + 1
    dashes = max(3, cols - used)
    return [(user, "user"), ("@", "dim"), (host, "user"),
            (" ", "fg"), ("-" * dashes, "dim")]


def _half(label, value, width, prefix):
    p = "- " if prefix else ""
    core = f"{p}{label}: "
    dots = max(2, width - len(core) - len(value))
    return [(p, "dim"), (label, "label"), (": ", "fg"),
            ("." * dots, "dots"), (value, "value")]


def stat_two(l_label, l_value, r_label, r_value, cols):
    half = (cols - 3) // 2
    left = _half(l_label, l_value, half, True)
    right = _half(r_label, r_value, cols - 3 - half, False)
    return left + [(" | ", "dim")] + right


def stat_loc(loc, added, deleted, cols):
    return [("- ", "dim"), ("Lines of Code on GitHub", "label"), (": ", "fg"),
            (loc, "value"), (" ( ", "dim"),
            (f"{added}++", "green"), (",  ", "dim"),
            (f"{deleted}--", "red"), (" )", "dim")]


def build_lines(cfg, cols):
    """Return list of lines; each line is a list of runs (or None for blank)."""
    lines = [userhost(cfg["user"], cfg["host"], cols), None]
    for grp in cfg["groups"]:
        for label, value in grp:
            lines.append(field(label, value, cols))
        lines.append(None)
    lines.append(section("Contact", cols))
    for label, value in cfg["contact"]:
        lines.append(field(label, value, cols))
    lines.append(None)
    lines.append(section("GitHub Stats", cols))
    s = cfg["stats"]
    lines.append(stat_two("Repos", s["repos"], "Stars", s["stars"], cols))
    lines.append(stat_two("Commits", s["commits"], "Followers", s["followers"], cols))
    lines.append(stat_loc(s["loc"], s["added"], s["deleted"], cols))
    return lines


def natural_cols(cfg):
    """Widest line (in chars) so values right-align with no overflow."""
    c = [70]
    for grp in cfg["groups"]:
        for label, value in grp:
            c.append(len(f"- {label}: ") + 2 + len(value))
    for label, value in cfg["contact"]:
        c.append(len(f"- {label}: ") + 2 + len(value))
    s = cfg["stats"]
    for a, b in [("Repos", s["repos"]), ("Commits", s["commits"])]:
        c.append((len(f"- {a}: ") + 2 + len(b)) * 2 + 3)
    for a, b in [("Stars", s["stars"]), ("Followers", s["followers"])]:
        c.append((len(f"{a}: ") + 2 + len(b)) * 2 + 3)
    c.append(len("- Lines of Code on GitHub: ") + len(s["loc"]) +
             len(f" ( {s['added']}++,  {s['deleted']}-- )"))
    return max(c)


# --------------------------------------------------------------------------
def measure():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10)
    ctx = cairo.Context(surf)
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(SIZE)
    char_w = ctx.text_extents("0").x_advance
    fasc, fdesc = ctx.font_extents()[0], ctx.font_extents()[1]
    return char_w, fasc, fdesc


def draw(ctx, theme, cfg, cols, lines, char_w, fasc, portrait_geom):
    T = THEMES[theme]
    # runs
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(SIZE)
    px, py, pw, ph = portrait_geom
    panel_x = PADX + pw + GAP

    # portrait (themed PNG) painted as scaled image
    img = cairo.ImageSurface.create_from_png(os.path.join(HERE, T["portrait"]))
    iw, ih = img.get_width(), img.get_height()
    ctx.save()
    ctx.translate(px, py)
    ctx.scale(pw / iw, ph / ih)
    ctx.set_source_surface(img, 0, 0)
    ctx.paint()
    ctx.restore()

    for r, runs in enumerate(lines):
        if not runs:
            continue
        baseline = TOP + r * LINE + fasc
        col = 0
        for text, key in runs:
            if text:
                ctx.set_source_rgb(*hexrgb(T[key]))
                ctx.move_to(panel_x + col * char_w, baseline)
                ctx.text_path(text)   # glyphs -> vector paths (font-free SVG)
                ctx.fill()
            col += len(text)


def render(theme, cfg, cols, lines, char_w, fasc, fdesc):
    T = THEMES[theme]
    nrows = len(lines)
    panel_block = nrows * LINE
    ph = max(240, min(430, panel_block * 0.96))
    # portrait native aspect
    img = cairo.ImageSurface.create_from_png(os.path.join(HERE, T["portrait"]))
    pw = ph * img.get_width() / img.get_height()
    panel_x = PADX + pw + GAP
    W = int(panel_x + cols * char_w + PADX)
    H = int(TOP + panel_block + BOTTOM)
    px = PADX
    py = TOP + (panel_block - ph) / 2
    geom = (px, py, pw, ph)

    def paint_all(ctx):
        # card background + border
        ctx.set_source_rgb(*hexrgb(T["bg"]))
        ctx.paint()
        _round_rect(ctx, 6, 6, W - 12, H - 12, RADIUS)
        ctx.set_source_rgb(*hexrgb(T["border"]))
        ctx.set_line_width(1.4)
        ctx.stroke()
        draw(ctx, theme, cfg, cols, lines, char_w, fasc, geom)

    # ---- SVG (vector, glyphs as paths) ----
    svg_path = os.path.join(HERE, f"assets/{theme}_mode.svg")
    svg = cairo.SVGSurface(svg_path, W, H)
    paint_all(cairo.Context(svg))
    svg.finish()

    # ---- PNG preview @2x (identical layout) ----
    scale = 2
    png = cairo.ImageSurface(cairo.FORMAT_ARGB32, W * scale, H * scale)
    pctx = cairo.Context(png)
    pctx.scale(scale, scale)
    paint_all(pctx)
    png.write_to_png(os.path.join(HERE, f"assets/preview_{theme}.png"))
    return W, H


def _round_rect(ctx, x, y, w, h, r):
    import math
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def main():
    with open(os.path.join(HERE, "config.json")) as f:
        cfg = json.load(f)
    cols = natural_cols(cfg)
    lines = build_lines(cfg, cols)
    char_w, fasc, fdesc = measure()
    for theme in ("dark", "light"):
        W, H = render(theme, cfg, cols, lines, char_w, fasc, fdesc)
        print(f"{theme}: {W}x{H}  cols={cols}")
    print("done ->", os.path.join(HERE, "assets"))


if __name__ == "__main__":
    main()