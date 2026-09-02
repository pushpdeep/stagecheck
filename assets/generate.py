"""O — the spine. Every variation, from one geometry.

THE GEOMETRY, fixed once so nothing drifts between sizes:

  spine   x=0, width 16% of the mark, full height, radius 18% of its width
  rows    three, each 16% of height, gaps of 10%, starting at x=26%
  widths  78% / 48% / 62% of the mark — judged, failed, could-not-judge
  colours ink / green / red / grey-hatch

The hatch is the only thing that does not scale: below about 20px it reads as
noise, so the third row becomes flat grey at 45%. That substitution is declared
rather than fudged — the row still says "counted, not judged".
"""
INK,RED,GREEN,GREY = "#1A2332","#A4322B","#2F6B4F","#9A958C"
LGREEN,LRED,WHITE = "#5FBF88","#E27A72","#FFFFFF"
PAPER,RULE = "#FBFAF7","#D8D4CC"

def mark(size=100, ink=INK, rows=((78,GREEN),(48,RED),(62,"hatch")),
         hatch_col=GREY, flat=False, hatch_id="h", pad=0):
    """One mark, at any size. Returns SVG fragment (no <svg> wrapper)."""
    s = size
    sw = s*0.16                      # spine width
    rh = s*0.16                      # row height
    gap = s*0.10
    x0 = s*0.26
    top = (s - (3*rh + 2*gap))/2
    out = [f'<rect x="{pad}" y="{pad}" width="{sw:.2f}" height="{s:.2f}" '
           f'rx="{sw*0.18:.2f}" fill="{ink}"/>']
    for i,(w,col) in enumerate(rows):
        y = pad + top + i*(rh+gap)
        fill = col if col != "hatch" else (hatch_col if flat else f"url(#{hatch_id})")
        op = ' opacity="0.5"' if (col == "hatch" and flat) else ''
        out.append(f'<rect x="{pad+x0:.2f}" y="{y:.2f}" width="{s*w/100:.2f}" '
                   f'height="{rh:.2f}" rx="{rh*0.18:.2f}" fill="{fill}"{op}/>')
    return "\n".join(out)

def hatch_def(idn="h", col=GREY, w=3):
    return (f'<pattern id="{idn}" width="7" height="7" patternTransform="rotate(45)" '
            f'patternUnits="userSpaceOnUse"><line x1="0" y1="0" x2="0" y2="7" '
            f'stroke="{col}" stroke-width="{w}"/></pattern>')

def wrap(inner, w, h, defs="", bg=None):
    b = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}"><defs>{defs}</defs>{b}{inner}</svg>')

# ── 1 · the mark alone, light ────────────────────────────────────────
open("mark.svg","w").write(wrap(mark(96), 96, 96, hatch_def()))

# ── 2 · the mark, dark background ────────────────────────────────────
open("mark-dark.svg","w").write(wrap(
    mark(96, ink=WHITE, rows=((78,LGREEN),(48,LRED),(62,"hatch"))),
    96, 96, hatch_def("h", WHITE, 2.6), bg=INK))

# ── 3 · avatar tile ──────────────────────────────────────────────────
tile = (f'<rect width="140" height="140" rx="30" fill="{INK}"/>'
        + f'<g transform="translate(30,30)">'
        + mark(80, ink=WHITE, rows=((78,LGREEN),(48,LRED),(62,"hatch")))
        + '</g>')
open("tile.svg","w").write(wrap(tile, 140, 140, hatch_def("h", WHITE, 2.4)))

# ── 4 · favicons ─────────────────────────────────────────────────────
for px in (16, 32, 64):
    flat = px < 24
    open(f"favicon-{px}.svg","w").write(wrap(
        mark(px, flat=flat), px, px, hatch_def("h", GREY, 2)))

# ── 5 · horizontal lockup ────────────────────────────────────────────
lock = (f'<g transform="translate(0,4)">{mark(40)}</g>'
        f'<text x="58" y="34" font-family="SF Mono,Menlo,monospace" '
        f'font-size="30" font-weight="600" letter-spacing="-.02em" fill="{INK}">stagecheck</text>')
open("lockup.svg","w").write(wrap(lock, 260, 48, hatch_def()))

# ── 6 · stacked lockup with tagline ──────────────────────────────────
st = (f'<g transform="translate(0,0)">{mark(52)}</g>'
      f'<text x="70" y="30" font-family="SF Mono,Menlo,monospace" font-size="27" '
      f'font-weight="600" letter-spacing="-.02em" fill="{INK}">stagecheck</text>'
      f'<text x="70" y="50" font-family="Georgia,serif" font-size="13" font-style="italic" '
      f'fill="#6E6A63">Every stage makes a bet.</text>')
open("lockup-tagline.svg","w").write(wrap(st, 330, 56, hatch_def()))

# ── 7 · animated ─────────────────────────────────────────────────────
# The rows do NOT grow at the same rate. Judged and failed slide out from the
# spine; the third arrives last, hesitates, and never fully resolves — it
# pulses, because a record nobody could judge is the one state that does not
# settle. The animation IS the argument, not decoration on it.
A = []
A.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">')
A.append(f'<defs>{hatch_def()}</defs>')
A.append(f'<rect x="0" y="0" width="15.36" height="96" rx="2.77" fill="{INK}">'
         f'<animate attributeName="height" values="0;96" dur=".45s" fill="freeze" '
         f'calcMode="spline" keySplines=".2 .8 .2 1"/></rect>')
rows = [(74.88, GREEN, ".35s"), (46.08, RED, ".5s")]
top = (96 - (3*15.36 + 2*9.6))/2
for i,(w,col,begin) in enumerate(rows):
    y = top + i*(15.36+9.6)
    A.append(f'<rect x="24.96" y="{y:.2f}" width="0" height="15.36" rx="2.77" fill="{col}">'
             f'<animate attributeName="width" values="0;{w:.2f}" dur=".5s" begin="{begin}" '
             f'fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1"/></rect>')
y3 = top + 2*(15.36+9.6)
A.append(f'<rect x="24.96" y="{y3:.2f}" width="0" height="15.36" rx="2.77" fill="url(#h)">'
         f'<animate attributeName="width" values="0;59.52" dur=".55s" begin=".72s" '
         f'fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1"/>'
         f'</rect>')
# NO pulse here. `once` means once — a mark that keeps breathing in a document
# somebody is reading is an irritant, and the looping variants exist for the
# places where motion is the content.
A.append('</svg>')
open("mark-once.svg","w").write("\n".join(A))

# ── 8 · looping: count, hold, clear ──────────────────────────────────
# Six seconds, of which three are perfectly still. A loop is a companion
# rather than a moment, and the hold is what makes it bearable at the
# fortieth repeat. Discrete, never eased — a ledger is tallied.
L = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">',
     f'<defs>{hatch_def()}</defs>',
     f'<rect x="0" y="0" width="15.36" height="96" rx="2.77" fill="{INK}"/>']
_w = (74.88, 46.08, 59.52)
_c = (GREEN, RED, "url(#h)")
_top = (96 - (3*15.36 + 2*9.6))/2
for i in range(3):
    steps = ";".join(f"{_w[i]*k/6:.1f}" for k in range(7))
    L.append(f'<rect x="24.96" y="{_top + i*(15.36+9.6):.2f}" width="0" height="15.36" '
             f'rx="2.77" fill="{_c[i]}">'
             f'<animate attributeName="width" '
             f'values="0;{steps};{_w[i]:.1f};0;0" '
             f'keyTimes="0;.03;.06;.09;.12;.15;.18;.2;.78;.85;1" '
             f'dur="6s" begin="{0.1*i:.1f}s" repeatCount="indefinite" '
             f'calcMode="discrete"/></rect>')
L.append("</svg>")
open("mark-loop.svg","w").write("\n".join(L))

# ── 9 · breath: opacity only, nothing changes shape ──────────────────
# A loop that changes SHAPE pulls the eye every cycle; one that changes only
# opacity does not. This is the variant for a header somebody reads past.
B = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">',
     f'<defs>{hatch_def()}</defs>',
     f'<rect x="0" y="0" width="15.36" height="96" rx="2.77" fill="{INK}"/>']
for i in range(3):
    y = _top + i*(15.36+9.6)
    a = ('<animate attributeName="opacity" values="1;.28;1" dur="3.6s" '
         'repeatCount="indefinite" calcMode="spline" '
         'keySplines=".4 0 .6 1;.4 0 .6 1"/>') if i == 2 else ''
    B.append(f'<rect x="24.96" y="{y:.2f}" width="{_w[i]:.2f}" height="15.36" '
             f'rx="2.77" fill="{_c[i]}">{a}</rect>')
B.append("</svg>")
open("mark-breath.svg","w").write("\n".join(B))

print("written:", ", ".join(sorted(__import__("os").listdir("."))))
