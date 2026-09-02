"""Lockups that adapt to the reader's theme.

WHY

The first lockups painted the spine and the wordmark in ink (#1A2332). On a
dark README that is near-black on near-black — the mark survived because its
rows carry their own colour, and the name disappeared entirely.

Two ways to fix it, and only one of them is a single file:

  <picture> with media="(prefers-color-scheme: dark)"  — GitHub supports it,
      GitLab's support is inconsistent, and it needs two files kept in step.

  A media query INSIDE the SVG. One file, adapts anywhere the SVG renders,
      and nothing to keep in step. This is that.

The colours do not merely invert. On dark the greens and reds LIFT — #2F6B4F
is legible on paper and muddy on ink — and the hatch shifts to a grey that
reads against a dark ground rather than disappearing into it.
"""
import pathlib
INK,RED,GREEN,GREY = "#1A2332","#A4322B","#2F6B4F","#9A958C"
D_INK,D_RED,D_GREEN,D_GREY = "#E6E9ED","#E27A72","#5FBF88","#7E8895"

STYLE = f'''<style>
    .ink{{fill:{INK}}}
    .judged{{fill:{GREEN}}}
    .failed{{fill:{RED}}}
    .hl{{stroke:{GREY}}}
    .quiet{{fill:#6E6A63}}
    @media (prefers-color-scheme: dark){{
      .ink{{fill:{D_INK}}}
      .judged{{fill:{D_GREEN}}}
      .failed{{fill:{D_RED}}}
      .hl{{stroke:{D_GREY}}}
      .quiet{{fill:#9AA3AF}}
    }}
  </style>'''

HATCH = ('<pattern id="h" width="7" height="7" patternTransform="rotate(45)" '
         'patternUnits="userSpaceOnUse">'
         '<line class="hl" x1="0" y1="0" x2="0" y2="7" stroke-width="3"/></pattern>')

def mark(s, x=0, y=0, animate=None):
    sw, rh, gap, x0 = s*.16, s*.16, s*.10, s*.26
    top = (s-(3*rh+2*gap))/2
    W = (s*.78, s*.48, s*.62)
    cls = ("judged", "failed", None)
    out = [f'<rect class="ink" x="{x}" y="{y}" width="{sw:.2f}" height="{s}" rx="{sw*.18:.2f}"/>']
    for i in range(3):
        ry = y+top+i*(rh+gap)
        fill = ' fill="url(#h)"' if cls[i] is None else ''
        c = f' class="{cls[i]}"' if cls[i] else ''
        if animate:
            steps = ";".join(f"{W[i]*k/6:.1f}" for k in range(7))
            if animate == "loop":
                a = (f'<animate attributeName="width" values="0;{steps};{W[i]:.1f};0;0" '
                     f'keyTimes="0;.03;.06;.09;.12;.15;.18;.2;.78;.85;1" dur="6s" '
                     f'begin="{.1*i:.1f}s" repeatCount="indefinite" calcMode="discrete"/>')
            else:
                a = (f'<animate attributeName="width" values="0;{steps}" dur="1.1s" '
                     f'begin="{.15*i:.2f}s" fill="freeze" calcMode="discrete"/>')
            w0 = 0
        else:
            a, w0 = "", W[i]
        out.append(f'<rect{c} x="{x+x0:.2f}" y="{ry:.2f}" width="{w0:.2f}" '
                   f'height="{rh:.2f}" rx="{rh*.18:.2f}"{fill}>{a}</rect>')
    return "\n  ".join(out)

def write(name, s=44, animate=None, tagline=None):
    fs = s*.66; gx = s*1.55
    W = int(gx + len("stagecheck")*fs*.62 + 4)
    H = int(s + (22 if tagline else 0))
    body = [f'<defs>{HATCH}</defs>', STYLE, mark(s, 0, 0, animate),
            f'<text class="ink" x="{gx:.0f}" y="{s*.72:.0f}" '
            f'font-family="SF Mono,Menlo,Consolas,monospace" font-size="{fs:.0f}" '
            f'font-weight="600" letter-spacing="-.02em">stagecheck</text>']
    if tagline:
        body.append(f'<text class="quiet" x="{gx:.0f}" y="{s+14:.0f}" '
                    f'font-family="Georgia,serif" font-size="{s*.26:.0f}" '
                    f'font-style="italic">{tagline}</text>')
    pathlib.Path(name).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">\n  ' + "\n  ".join(body) + '\n</svg>')
    return name, W, H

def write_mark(name, s=96, animate=None):
    pathlib.Path(name).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}" '
        f'width="{s}" height="{s}">\n  <defs>{HATCH}</defs>\n  {STYLE}\n  '
        + mark(s, 0, 0, animate) + '\n</svg>')
    return name

for n,w,h in (write("lockup-once.svg", 44, "once"),
              write("lockup-loop.svg", 44, "loop"),
              write("lockup.svg", 44, None),
              write("lockup-tagline.svg", 44, None, "Every stage makes a bet."),
              write("lockup-loop-tagline.svg", 44, "loop", "Every stage makes a bet."),
              write("lockup-large.svg", 72, "loop")):
    print(f"  {n:26} {w}x{h}  adaptive")
for n in ("mark.svg","mark-once.svg","mark-loop.svg"):
    write_mark(n, 96, {"mark.svg":None,"mark-once.svg":"once","mark-loop.svg":"loop"}[n])
    print(f"  {n:26} 96x96  adaptive")
for px in (16,32,64):
    write_mark(f"favicon-{px}.svg", px)
    print(f"  favicon-{px}.svg{'':13} adaptive")
