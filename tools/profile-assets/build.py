"""Builds the SVG artwork for profile/README.md.

All text is converted to outlines, so the files render the same everywhere GitHub
shows them (fonts cannot load inside an <img>). Edit the copy below and rerun:

    python3 -m venv .venv && .venv/bin/pip install fonttools brotli uharfbuzz
    .venv/bin/python tools/profile-assets/build.py

Fonts are the brand set (Montserrat, JetBrains Mono, Plus Jakarta Sans), SIL OFL.
Colours come from the brand kit: navy #10233F, orange #FB8220, cream #FBF7F2.
"""

import io
import re
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "profile" / "assets"

NAVY, ORANGE, CREAM = "#10233F", "#FB8220", "#FBF7F2"


def rgba(hex_, a):
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


THEMES = {
    "light": dict(
        bg=CREAM, ink=NAVY, muted=rgba(NAVY, 0.66), faint=rgba(NAVY, 0.055),
        line=rgba(NAVY, 0.14), card="#FFFFFF", stroke=rgba(NAVY, 0.13),
        accent=ORANGE, accent_text="#C2610F", track_off=rgba(NAVY, 0.13),
        track_on=NAVY, knob_off="#FFFFFF", ai_fill=rgba(ORANGE, 0.09),
        ai_stroke=rgba(ORANGE, 0.55), frame=rgba(NAVY, 0.3),
    ),
    "dark": dict(
        bg=NAVY, ink=CREAM, muted=rgba(CREAM, 0.68), faint=rgba(CREAM, 0.05),
        line=rgba(CREAM, 0.16), card=rgba(CREAM, 0.045), stroke=rgba(CREAM, 0.15),
        accent=ORANGE, accent_text=ORANGE, track_off=rgba(CREAM, 0.15),
        track_on=CREAM, knob_off=rgba(CREAM, 0.6), ai_fill=rgba(ORANGE, 0.1),
        ai_stroke=rgba(ORANGE, 0.5), frame=rgba(CREAM, 0.3),
    ),
}


# --- Type -----------------------------------------------------------------------------------

class Face:
    def __init__(self, file, wght=None):
        font = TTFont(HERE / "fonts" / file)
        if "fvar" in font:
            font = instancer.instantiateVariableFont(font, {"wght": wght})
        font.flavor = None
        buf = io.BytesIO()
        font.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(data))
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(data))

    def shape(self, text, size, tracking=0.0):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        s = size / self.upem
        out, x = [], 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            if info.codepoint == 0:
                raise ValueError(f"missing glyph in {text!r}")
            out.append((self.order[info.codepoint], x + pos.x_offset * s, pos.y_offset * s))
            x += pos.x_advance * s + tracking * size
        return out, (x - tracking * size if out else 0.0)

    def width(self, text, size, tracking=0.0):
        return self.shape(text, size, tracking)[1]

    def d(self, text, size, x, y, anchor="start", tracking=0.0):
        glyphs, w = self.shape(text, size, tracking)
        x -= {"start": 0, "middle": w / 2, "end": w}[anchor]
        s = size / self.upem
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        for name, gx, gy in glyphs:
            self.glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, x + gx, y - gy)))
        return pen.getCommands(), w


LIGHT = Face("Montserrat-Variable-latin.woff2", 300)
REGULAR = Face("Montserrat-Variable-latin.woff2", 400)
MEDIUM = Face("Montserrat-Variable-latin.woff2", 500)
SEMI = Face("Montserrat-Variable-latin.woff2", 600)
BOLD = Face("Montserrat-Variable-latin.woff2", 700)
MONO = Face("JetBrainsMono-Variable-latin.woff2", 500)


def text(face, s, size, x, y, fill, anchor="start", tracking=0.0, attrs="", maxw=None):
    d, w = face.d(s, size, x, y, anchor, tracking)
    if maxw is not None and w > maxw:
        raise ValueError(f"{s!r} is {w:.0f} wide, limit {maxw}")
    return f'<path d="{d}" fill="{fill}"{attrs}/>'


def mono(s, size, x, y, fill, anchor="start", attrs="", maxw=None):
    return text(MONO, s.upper(), size, x, y, fill, anchor, 0.12, attrs, maxw)


def wrap(face, s, size, maxw):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and face.width(trial, size) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def paragraph(face, s, size, x, y, leading, fill, maxw, attrs=""):
    return "".join(
        text(face, line, size, x, y + i * leading, fill, attrs=attrs)
        for i, line in enumerate(wrap(face, s, size, maxw))
    )


# --- Shared pieces --------------------------------------------------------------------------

def logo(variant, x, y, height):
    src = (HERE / f"consenteo-logo{'-on-dark' if variant == 'dark' else ''}.svg").read_text()
    inner = re.search(r"<svg[^>]*>(.*)</svg>", src, re.S).group(1)
    scale = height / 192.2
    return f'<g transform="translate({x} {y}) scale({scale:.4f})">{inner}</g>'


REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"


def svg(w, h, title, body, style=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-labelledby="t"><title id="t">{title}</title>'
        f"<style>{style}{REDUCED}</style>{body}</svg>"
    )


def panel(w, h, t, grid=True, rule=False):
    out = [
        f'<clipPath id="clip"><rect width="{w}" height="{h}" rx="24"/></clipPath>',
        f'<rect width="{w}" height="{h}" rx="24" fill="{t["bg"]}"/>',
    ]
    if grid:
        out.append(
            f'<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">'
            f'<path d="M40 0H0V40" fill="none" stroke="{t["faint"]}" stroke-width="1"/></pattern>'
            f'<rect width="{w}" height="{h}" rx="24" fill="url(#grid)"/>'
        )
    if rule:
        out.append(f'<rect width="{w}" height="6" fill="{ORANGE}" clip-path="url(#clip)"/>')
    out.append(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="23.5" fill="none" stroke="{t["line"]}"/>')
    return "".join(out)


def toggle_css(t, travel, name="sw"):
    """Keyframes for a toggle switching on: the track fills, the knob slides and turns orange."""
    return (
        f"@keyframes {name}-track{{from{{fill:{t['track_off']}}}}}"
        f"@keyframes {name}-knob{{from{{transform:translateX(-{travel}px);fill:{t['knob_off']}}}}}"
        f".{name}-t{{animation:{name}-track .45s ease both}}"
        f".{name}-k{{animation:{name}-knob .55s cubic-bezier(.3,1.5,.55,1) both}}"
    )


def toggle(t, x, y, w, h, delay, name="sw"):
    r = h / 2
    knob_r = h * 0.32
    cx = x + w - r
    style = f' style="animation-delay:{delay:.2f}s"'
    return (
        f'<rect class="{name}-t" x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{t["track_on"]}"{style}/>'
        f'<circle class="{name}-k" cx="{cx}" cy="{y + r}" r="{knob_r:.2f}" fill="{ORANGE}"{style}/>'
    )


def fade_css():
    return (
        "@keyframes rise{from{opacity:0;transform:translateY(10px)}}"
        ".rise{animation:rise .6s cubic-bezier(.2,.8,.2,1) both}"
    )


# --- Hero -----------------------------------------------------------------------------------

LINES = [
    ("Build", "Websites and platforms"),
    ("Build", "Mobile apps"),
    ("Build", "Custom systems"),
    ("Connect", "System integration"),
    ("Grow", "Digital marketing"),
    ("Automate", "AI and custom agents"),
    ("Comply", "Consent and privacy"),
    ("Sustain", "Support and evolution"),
]


def hero():
    W, H = 1280, 600
    t = THEMES["dark"]
    b = [panel(W, H, t, rule=True)]
    b.append(
        '<radialGradient id="glow" cx="1040" cy="90" r="560" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{ORANGE}" stop-opacity=".2"/>'
        f'<stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/></radialGradient>'
        f'<rect width="{W}" height="{H}" rx="24" fill="url(#glow)"/>'
    )
    b.append(logo("dark", 46, 46, 92))
    left = 72
    b.append(mono("Digital products · AI · Privacy", 15, left, 214, ORANGE, maxw=620))
    b.append(text(LIGHT, "Digital products and AI,", 50, left, 284, CREAM, tracking=-0.02, maxw=640))
    b.append(text(BOLD, "built as one system.", 50, left, 346, CREAM, tracking=-0.02, maxw=640))
    b.append(paragraph(
        REGULAR,
        "Built by engineers with 200+ consent implementations across 20+ jurisdictions, "
        "now delivering the full digital stack.",
        20, left, 408, 31, t["muted"], 600,
    ))
    verbs = ["Build", "Connect", "Automate", "Comply", "Grow", "Sustain"]
    x = left
    for i, v in enumerate(verbs):
        if i:
            b.append(f'<circle cx="{x + 11}" cy="{524 - 5}" r="2.5" fill="{ORANGE}"/>')
            x += 22
        d, w = MONO.d(v.upper(), 13.5, x, 524, tracking=0.14)
        b.append(f'<path d="{d}" fill="{rgba(CREAM, 0.55)}"/>')
        x += w

    # Service-line console: every line switches on in turn.
    px, py, pw, ph = 748, 64, 468, 472
    b.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="18" fill="{rgba(CREAM, 0.045)}" stroke="{rgba(CREAM, 0.14)}"/>')
    b.append(mono("Service lines", 13, px + 26, py + 42, rgba(CREAM, 0.55)))
    last = 0.7 + 0.32 * (len(LINES) - 1)
    b.append(mono("All on", 13, px + pw - 26, py + 42, ORANGE, anchor="end",
                  attrs=f' class="rise" style="animation-delay:{last + 0.4:.2f}s"'))
    b.append(f'<path d="M{px} {py + 64}H{px + pw}" stroke="{rgba(CREAM, 0.1)}"/>')
    row = (ph - 64) / len(LINES)
    for i, (verb, title) in enumerate(LINES):
        cy = py + 64 + row * i + row / 2
        if i:
            b.append(f'<path d="M{px + 26} {py + 64 + row * i:.1f}H{px + pw - 26}" stroke="{rgba(CREAM, 0.07)}"/>')
        b.append(mono(verb, 12, px + 26, cy + 4.5, rgba(ORANGE, 0.9)))
        b.append(text(MEDIUM, title, 18.5, px + 132, cy + 6.5, CREAM, maxw=250))
        b.append(toggle(t, px + pw - 26 - 50, cy - 13, 50, 26, 0.7 + 0.32 * i))
    style = toggle_css(t, 24) + fade_css()
    return svg(W, H, "Consenteo. Digital products and AI, built as one system.", "".join(b), style)


# --- System map -----------------------------------------------------------------------------

def system_map(mode):
    W, H = 1280, 600
    t = THEMES[mode]
    b = [panel(W, H, t)]
    # Support surrounds the whole system.
    b.append(f'<rect x="40" y="52" width="1200" height="508" rx="18" fill="none" stroke="{t["frame"]}" stroke-dasharray="7 7" class="flow-slow"/>')
    label = "Sustain · Support and evolution"
    lw = MONO.width(label.upper(), 13, 0.12)
    b.append(f'<rect x="64" y="40" width="{lw + 28:.0f}" height="24" fill="{t["bg"]}"/>')
    b.append(mono(label, 13, 78, 57, t["accent_text"]))

    def box(x, y, w, h, verb, title, delay):
        return (
            f'<g class="rise" style="animation-delay:{delay}s">'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{t["card"]}" stroke="{t["stroke"]}"/>'
            + mono(verb, 12.5, x + 22, y + 32, t["accent_text"])
            + text(SEMI, title, 21, x + 22, y + h - 22, t["ink"], maxw=w - 44)
            + "</g>"
        )

    # Connectors first so boxes sit on top.
    paths = [
        "M330 148 C 400 148, 400 182, 470 182",
        "M330 244 C 400 244, 400 206, 470 206",
        "M790 194 H 900",
    ]
    for p in paths:
        b.append(f'<path d="{p}" fill="none" stroke="{t["line"]}" stroke-width="2"/>')
        b.append(f'<path d="{p}" fill="none" stroke="{ORANGE}" stroke-width="2" stroke-dasharray="4 14" class="flow"/>')
        b.append(f'<circle r="4.5" fill="{ORANGE}"><animateMotion dur="2.4s" repeatCount="indefinite" path="{p}"/></circle>')
    b.append(f'<path d="M893 187 L901 194 L893 201" fill="none" stroke="{t["muted"]}" stroke-width="2"/>')

    # Drops from each surface into the layers beneath.
    for x in (205, 630, 1050):
        b.append(f'<path d="M{x} {286 if x == 205 else 246}V530" stroke="{t["line"]}" stroke-width="2" stroke-dasharray="2 6"/>')
        b.append(f'<circle cx="{x}" r="4" fill="{ORANGE}"><animate attributeName="cy" from="{290 if x == 205 else 250}" to="528" dur="2.8s" begin="{(x % 7) * 0.2:.1f}s" repeatCount="indefinite"/>'
                 f'<animate attributeName="opacity" values="0;1;1;0" dur="2.8s" begin="{(x % 7) * 0.2:.1f}s" repeatCount="indefinite"/></circle>')

    b.append(box(80, 104, 250, 88, "Build", "Websites", 0.1))
    b.append(box(80, 200, 250, 88, "Build", "Mobile apps", 0.25))
    b.append(box(470, 140, 320, 108, "Build · Core", "Custom systems", 0.4))
    b.append(box(908, 140, 292, 108, "Grow", "Digital marketing", 0.55))

    layers = [
        ("Connect", "System integration", "APIs and middleware between every platform", t["card"], t["stroke"]),
        ("Automate", "AI and custom agents", "Agents that act inside each system", t["ai_fill"], t["ai_stroke"]),
        ("Comply", "Consent and privacy", "Consent state governs the whole stack", t["card"], t["stroke"]),
    ]
    for i, (verb, title, note, fill, stroke) in enumerate(layers):
        y = 318 + i * 76
        b.append(f'<g class="rise" style="animation-delay:{0.75 + i * 0.15:.2f}s">')
        # Opaque base so the drops only show between layers.
        b.append(f'<rect x="80" y="{y}" width="1120" height="60" rx="12" fill="{t["bg"]}"/>')
        b.append(f'<rect x="80" y="{y}" width="1120" height="60" rx="12" fill="{fill}" stroke="{stroke}"/>')
        if verb == "Automate":
            b.append(f'<rect x="80" y="{y}" width="1120" height="60" rx="12" fill="url(#sheen)"/>')
        b.append(mono(verb, 12.5, 104, y + 35, t["accent_text"]))
        b.append(text(SEMI, title, 19, 228, y + 37, t["ink"]))
        b.append(text(REGULAR, note, 17, 1176, y + 36, t["muted"], anchor="end"))
        b.append("</g>")
    b.insert(1, (
        '<linearGradient id="sheen" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0" stop-color="{ORANGE}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{ORANGE}" stop-opacity=".16"/>'
        f'<stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/>'
        '<animate attributeName="x1" values="-1;1" dur="5s" repeatCount="indefinite"/>'
        '<animate attributeName="x2" values="0;2" dur="5s" repeatCount="indefinite"/>'
        "</linearGradient>"
    ))
    style = (
        "@keyframes flow{to{stroke-dashoffset:-36}}.flow{animation:flow 1.4s linear infinite}"
        "@keyframes flow-slow{to{stroke-dashoffset:-28}}.flow-slow{animation:flow-slow 4s linear infinite}"
        + fade_css()
    )
    return svg(W, H, "Consenteo service lines as one system: websites and mobile apps feed custom systems, "
               "which feed digital marketing; integration, AI agents and consent run beneath them; "
               "support surrounds the whole.", "".join(b), style)


# --- AI agent demo --------------------------------------------------------------------------

def agent(mode):
    W, H = 1280, 520
    t = THEMES[mode]
    b = [panel(W, H, t)]
    b.append(mono("Illustrative example", 12, W - 40, 40, t["muted"], anchor="end"))

    # Voice note.
    x, y, w, h = 40, 64, 500, 416
    b.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{t["card"]}" stroke="{t["stroke"]}"/>')
    b.append(mono("Voice note · Sales", 13, x + 28, y + 44, t["accent_text"]))
    b.append(f'<circle cx="{x + 52}" cy="{y + 104}" r="24" fill="{t["track_on"]}"/>')
    b.append(f'<path d="M{x + 46} {y + 94}L{x + 60} {y + 104}L{x + 46} {y + 114}Z" fill="{ORANGE}"/>')
    heights = [10, 22, 34, 18, 40, 28, 14, 36, 24, 44, 30, 16, 26, 38, 20, 12, 30, 22, 34, 14, 26, 18, 10]
    for i, bh in enumerate(heights):
        bx = x + 96 + i * 13
        b.append(f'<rect class="wave" x="{bx}" y="{y + 104 - bh / 2}" width="6" height="{bh}" rx="3" fill="{t["muted"]}" style="animation-delay:{(i % 6) * 0.12:.2f}s"/>')
    b.append(mono("0:14", 13, x + w - 28, y + 109, t["muted"], anchor="end"))
    quote = "“Met the facilities manager at the Marina site. They want a quote for 40 units. Follow up on Thursday.”"
    b.append(paragraph(MEDIUM, quote, 23, x + 28, y + 190, 36, t["ink"], w - 56))
    b.append(f'<path d="M{x + 28} {y + h - 70}H{x + w - 28}" stroke="{t["line"]}"/>')
    b.append(mono("Spoken in English or Arabic", 12.5, x + 28, y + h - 36, t["muted"]))

    # Hand-off arrow.
    b.append(f'<path d="M552 272H604" stroke="{t["line"]}" stroke-width="2"/>')
    b.append(f'<path d="M552 272H604" stroke="{ORANGE}" stroke-width="2" stroke-dasharray="4 10" class="flow"/>')
    b.append(f'<path d="M598 265L606 272L598 279" fill="none" stroke="{ORANGE}" stroke-width="2"/>')

    # Agent actions.
    x, y, w, h = 618, 64, 622, 416
    b.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{t["card"]}" stroke="{t["stroke"]}"/>')
    b.append(mono("Agent actions", 13, x + 28, y + 44, t["accent_text"]))
    b.append(mono("Logged", 13, x + w - 28, y + 44, t["muted"], anchor="end"))
    actions = [
        ("Visit logged against the account", "CRM"),
        ("Deal moved to the proposal stage", "CRM"),
        ("Quote drafted for 40 units", "Documents"),
        ("Follow-up booked for Thursday", "Calendar"),
    ]
    row = 56
    for i, (label, system) in enumerate(actions):
        cy = y + 92 + i * row
        delay = 0.9 + i * 0.55
        b.append(f'<g class="rise" style="animation-delay:{delay:.2f}s">')
        b.append(toggle(t, x + 28, cy - 12, 44, 24, delay + 0.15))
        b.append(text(MEDIUM, label, 19.5, x + 92, cy + 7, t["ink"], maxw=390))
        b.append(mono(system, 12, x + w - 28, cy + 5, t["muted"], anchor="end"))
        b.append("</g>")
    # The one step that waits for a person.
    cy = y + 92 + len(actions) * row + 10
    delay = 0.9 + len(actions) * 0.55
    b.append(f'<g class="rise" style="animation-delay:{delay:.2f}s">')
    b.append(f'<rect x="{x + 16}" y="{cy - 30}" width="{w - 32}" height="60" rx="12" fill="{t["ai_fill"]}" stroke="{t["ai_stroke"]}"/>')
    b.append(f'<rect x="{x + 28}" y="{cy - 12}" width="44" height="24" rx="12" fill="none" stroke="{ORANGE}" stroke-width="2"/>')
    b.append(f'<circle class="wait" cx="{x + 40}" cy="{cy}" r="7" fill="{ORANGE}"/>')
    b.append(text(SEMI, "Quote held for your approval", 19.5, x + 92, cy + 7, t["ink"]))
    b.append(mono("Confirm", 12, x + w - 28, cy + 5, t["accent_text"], anchor="end"))
    b.append("</g>")
    b.append(mono("Role permissions · Every action logged", 12.5, x + 28, y + h - 30, t["muted"]))

    style = (
        toggle_css(t, 20) + fade_css()
        + "@keyframes wave{50%{transform:scaleY(.35)}}.wave{transform-box:fill-box;transform-origin:center;animation:wave 1.1s ease-in-out infinite}"
        + "@keyframes wait{50%{opacity:.35}}.wait{animation:wait 1.6s ease-in-out infinite}"
        + "@keyframes flow{to{stroke-dashoffset:-28}}.flow{animation:flow 1.2s linear infinite}"
    )
    return svg(W, H, "Illustrative example: a sales voice note becomes four logged actions in the CRM, "
               "documents and calendar, with the quote held for approval.", "".join(b), style)


# --- Consent propagation --------------------------------------------------------------------

def consent(mode):
    W, H = 1280, 470
    t = THEMES[mode]
    b = [panel(W, H, t)]

    # The choice.
    x, y, w, h = 40, 40, 300, 340
    b.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{t["card"]}" stroke="{t["stroke"]}"/>')
    b.append(mono("Consent choice", 13, x + 26, y + 42, t["accent_text"]))
    b.append(toggle(t, x + 26, y + 120, 132, 72, 0.5, name="big"))
    b.append(text(SEMI, "One choice,", 24, x + 26, y + 262, t["ink"]))
    b.append(text(LIGHT, "enforced everywhere.", 24, x + 26, y + 294, t["ink"]))

    # Trunk.
    trunk_y = 210
    b.append(f'<path d="M{x + w} {trunk_y}H1214" stroke="{t["line"]}" stroke-width="2"/>')
    b.append(f'<path class="trunk" d="M{x + w} {trunk_y}H1214" stroke="{ORANGE}" stroke-width="2" pathLength="1" stroke-dasharray="1 1"/>')

    nodes = [
        ("Tags", "Tag management"),
        ("Analytics", "Consent Mode v2"),
        ("Ads", "Ad platforms"),
        ("Mobile", "App SDKs"),
        ("Server", "Server-side tracking"),
        ("CRM", "CRM and automation"),
    ]
    cols = [392, 674, 956]
    cw, ch = 258, 104
    for i, (tag, title) in enumerate(nodes):
        col, top_row = i % 3, i < 3
        nx = cols[col]
        ny = 64 if top_row else 252
        delay = 1.0 + (nx - 340) / 900 * 1.2 + (0 if top_row else 0.12)
        sy, ey = (ny + ch, trunk_y) if top_row else (trunk_y, ny)
        b.append(f'<path d="M{nx + 30} {sy}V{ey}" stroke="{t["line"]}" stroke-width="2"/>')
        b.append(f'<path class="drop" d="M{nx + 30} {sy}V{ey}" stroke="{ORANGE}" stroke-width="2" style="animation-delay:{delay:.2f}s"/>')
        b.append(f'<rect x="{nx}" y="{ny}" width="{cw}" height="{ch}" rx="14" fill="{t["card"]}" stroke="{t["stroke"]}"/>')
        b.append(mono(tag, 12, nx + 22, ny + 34, t["muted"]))
        b.append(f'<circle class="dot" cx="{nx + cw - 26}" cy="{ny + 30}" r="6" fill="{ORANGE}" style="animation-delay:{delay + 0.2:.2f}s"/>')
        b.append(text(SEMI, title, 19.5, nx + 22, ny + 76, t["ink"], maxw=cw - 40))

    regs = "UAE PDPL · DIFC · ADGM · GDPR · UK GDPR · US state laws"
    b.append(f'<path d="M40 412H1240" stroke="{t["line"]}"/>')
    b.append(mono("Covered", 12.5, 40, 446, t["accent_text"]))
    b.append(mono(regs, 12.5, 1240, 446, t["muted"], anchor="end"))

    style = (
        toggle_css(t, 60, "big")
        + "@keyframes trunk{from{stroke-dashoffset:1}}.trunk{animation:trunk 1.6s ease-in-out 1s both}"
        + f"@keyframes drop{{from{{stroke:{t['line']}}}}}.drop{{animation:drop .4s ease both}}"
        + f"@keyframes dot{{from{{fill:{t['track_off']};transform:scale(.6)}}}}"
        + ".dot{transform-box:fill-box;transform-origin:center;animation:dot .4s cubic-bezier(.3,1.6,.5,1) both}"
    )
    return svg(W, H, "One consent choice propagates to tag management, Consent Mode v2, ad platforms, "
               "app SDKs, server-side tracking and the CRM.", "".join(b), style)


# --- Engagement path ------------------------------------------------------------------------

def engage(mode):
    W, H = 1280, 400
    t = THEMES[mode]
    b = [panel(W, H, t)]
    stages = [
        ("Discovery", "Map processes, systems and bottlenecks.", "Findings and a prioritised roadmap"),
        ("Pilot", "Prove one agent or integration in live use.", "A working solution for one team"),
        ("Full build", "Deliver the complete platform or programme.", "Production system, documentation, training"),
        ("Retained support", "Maintain, monitor and extend after launch.", "Agreed hours and response commitments"),
    ]
    x0, step, ty = 56, 296, 84
    b.append(f'<path d="M{x0 + 60} {ty}H{x0 + step * 3 + 30}" stroke="{t["line"]}" stroke-width="2"/>')
    b.append(f'<path class="trunk" d="M{x0 + 60} {ty}H{x0 + step * 3 + 30}" stroke="{ORANGE}" stroke-width="2" pathLength="1" stroke-dasharray="1 1"/>')
    for i, (title, purpose, output) in enumerate(stages):
        x = x0 + i * step
        delay = 0.5 + i * 0.7
        b.append(f'<rect x="{x - 8}" y="{ty - 22}" width="76" height="44" fill="{t["bg"]}"/>')
        b.append(toggle(t, x, ty - 16, 60, 32, delay))
        b.append(f'<g class="rise" style="animation-delay:{delay:.2f}s">')
        b.append(mono(f"0{i + 1}", 13, x, ty + 64, t["accent_text"]))
        b.append(text(BOLD, title, 25, x, ty + 102, t["ink"], tracking=-0.01, maxw=step - 30))
        b.append(paragraph(REGULAR, purpose, 17, x, ty + 140, 26, t["muted"], step - 40))
        b.append(f'<path d="M{x} {ty + 206}H{x + step - 40}" stroke="{t["line"]}"/>')
        b.append(mono("Output", 11.5, x, ty + 234, t["accent_text"]))
        b.append(paragraph(MEDIUM, output, 16.5, x, ty + 262, 24, t["ink"], step - 40))
        b.append("</g>")
    style = (
        toggle_css(t, 28) + fade_css()
        + "@keyframes trunk{from{stroke-dashoffset:1}}.trunk{animation:trunk 2.4s cubic-bezier(.4,0,.2,1) .5s both}"
    )
    return svg(W, H, "How we engage: discovery, pilot, full build and retained support. "
               "Each stage can be commissioned on its own.", "".join(b), style)


# --- Footer ---------------------------------------------------------------------------------

def footer():
    W, H = 1280, 300
    t = THEMES["dark"]
    b = [panel(W, H, t, rule=True)]
    b.append(
        '<radialGradient id="glow" cx="1120" cy="300" r="480" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{ORANGE}" stop-opacity=".18"/>'
        f'<stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/></radialGradient>'
        f'<rect width="{W}" height="{H}" rx="24" fill="url(#glow)"/>'
    )
    b.append(text(LIGHT, "Consent is where we started.", 40, 72, 120, CREAM, tracking=-0.02))
    b.append(text(BOLD, "Now we build the whole system.", 40, 72, 172, CREAM, tracking=-0.02))
    b.append(mono("consenteo.com", 14, 72, 236, ORANGE))
    # The mark, large, switching on.
    b.append(toggle(t, 940, 96, 248, 136, 0.4, name="big"))
    style = toggle_css(t, 112, "big")
    return svg(W, H, "Consent is where we started. Now we build the whole system. consenteo.com", "".join(b), style)


# --- Heading marker and buttons --------------------------------------------------------------

def marker():
    # The mark as an orange outline, readable on light and dark GitHub themes.
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 46 26" width="46" height="26" aria-hidden="true">'
        f'<rect x="1.5" y="1.5" width="43" height="23" rx="11.5" fill="none" stroke="{ORANGE}" stroke-width="3"/>'
        f'<circle cx="33" cy="13" r="6.5" fill="{ORANGE}"/></svg>'
    )


def button(label, fill, ink, stroke=None, arrow=True):
    size, h, pad = 15, 52, 26
    lw = MONO.width(label.upper(), size, 0.12)
    w = round(lw + pad * 2 + (26 if arrow else 0))
    b = [f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{(h - 2) / 2}" fill="{fill}"'
         + (f' stroke="{stroke}" stroke-width="2"' if stroke else "") + "/>"]
    b.append(mono(label, size, pad, h / 2 + 5.5, ink))
    if arrow:
        ax = pad + lw + 12
        b.append(f'<path d="M{ax} {h / 2}H{ax + 14}M{ax + 8} {h / 2 - 6}L{ax + 14} {h / 2}L{ax + 8} {h / 2 + 6}" '
                 f'fill="none" stroke="{ink}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{label}"><title>{label}</title>{"".join(b)}</svg>')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "hero.svg": hero(),
        "footer.svg": footer(),
        "marker.svg": marker(),
        "button-site.svg": button("Visit consenteo.com", ORANGE, NAVY),
        "button-talk.svg": button("Book a discovery session", NAVY, CREAM, stroke=rgba(CREAM, 0.35)),
    }
    for mode in ("light", "dark"):
        files[f"system-map-{mode}.svg"] = system_map(mode)
        files[f"agent-{mode}.svg"] = agent(mode)
        files[f"consent-{mode}.svg"] = consent(mode)
        files[f"engage-{mode}.svg"] = engage(mode)
    for name, content in files.items():
        (OUT / name).write_text(content)
        print(f"{name:24} {len(content) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
