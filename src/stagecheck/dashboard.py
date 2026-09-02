"""The dashboard — three tenses side by side, as one page.

WHY THIS EXISTS, AND WHY IT IS NOT A DASHBOARD IN THE USUAL SENSE

The two monitors in the project this came from show what is happening now, and
neither ever changed a decision. That is not an argument against dashboards; it
is an argument against SINGLE-TENSE ones. A screen showing only the present
cannot surprise you, because there is nothing for the present to disagree with.

Here every row is a stage's declaration, and the columns are the tenses:

    PREDICTED    what the precondition measured, before the stage was built
    OBSERVED     what the stage actually did
    DIVERGENCE   the gap, which is the only column worth looking at

A menu predicted at 87% and delivering 41% is one glance here. It took nine
hours and a purpose-written scoring script to find that in the study.

RULES THAT KEEP IT FROM BECOMING THE OTHER TWO

    · If a cell does not compare a prediction to an observation, or name a
      denominator, it does not go on the page.
    · No token sparklines, no latency histograms, no charts that merely show.
    · Every rate states the set it is over, in the cell, not in a tooltip.

It is a static file. No server, no live connection — the runs it is for are
unattended and nobody watches a six-hour job, so the screen has to work as
something you open afterwards.
"""
from __future__ import annotations

import html
import pathlib
from typing import Iterable

from .declare import Measurement, Stage


def render(stages: Iterable[Stage],
           preflights: dict[str, Measurement] | None = None,
           title: str = "stagecheck") -> str:
    pre = preflights or {}
    rows = []
    for st in stages:
        rows.append(_row(st, pre.get(st.name)))
    body = "\n".join(rows)
    n = len(rows)
    return _PAGE.format(title=html.escape(title), rows=body, n=n)


def _row(st: Stage, m: Measurement | None) -> str:
    s = st.summary()

    # ── predicted ──────────────────────────────────────────────────────
    if m is None:
        predicted = '<span class="none">not measured</span>'
        p_note = ("no testable precondition declared"
                  if st.precondition is None else
                  "call preflight() with your dev split")
    else:
        cls = "ok" if m.holds else "no"
        predicted = f'<span class="{cls}">{m.value:.1%}</span>'
        p_note = f"of {m.n} {html.escape(m.over)}"

    # ── observed ───────────────────────────────────────────────────────
    if st._halts:
        observed = '<span class="halt">HALTED</span>'
        o_note = f"{len(st._halts)} broken invariant(s) · no number produced"
    elif s is None:
        observed = '<span class="none">not run</span>'
        o_note = ""
    elif s.judged == 0:
        observed = '<span class="no">judged nothing</span>'
        o_note = f"could not judge all {s.offered}"
    else:
        cls = "no" if s.failed == 0 else "ok"
        observed = f'<span class="{cls}">{s.fail_rate:.1%}</span>'
        o_note = (f"of {s.judged} judged"
                  + (f" · {s.could_not_run} unjudgeable" if s.could_not_run else ""))

    # ── divergence, the only column that matters ───────────────────────
    div, dcls = _divergence(m, s, bool(st._halts))

    return f"""      <tr>
        <td class="stage">{html.escape(st.name)}
          <span class="bet">{html.escape(st.bet)}</span></td>
        <td class="num">{predicted}<span class="den">{html.escape(p_note)}</span></td>
        <td class="num">{observed}<span class="den">{html.escape(o_note)}</span></td>
        <td class="div {dcls}">{html.escape(div)}</td>
      </tr>"""


def _divergence(m, s, halted) -> tuple[str, str]:
    if halted:
        return ("The setup was not what was declared. Nothing here is a result.",
                "bad")
    if s is None:
        return ("", "")
    if m is None:
        if s.judged == 0:
            return ("Judged nothing, and there was no prediction to check it "
                    "against.", "bad")
        return ("No prediction was recorded, so there is nothing to diverge "
                "from.", "muted")
    if s.judged == 0:
        return ("The bet HELD and the stage judged nothing. Its input is not "
                "what the precondition was measured on.", "bad")
    if m.holds and s.failed == 0:
        return ("The bet held and the stage changed nothing. It is running, "
                "and it is not earning its cost.", "bad")
    if not m.holds and s.failed:
        return ("The bet did not hold and the stage fired anyway. Check what "
                "it is keying on.", "warn")
    return ("Before and after agree.", "ok")


_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  :root{{
    --paper:#FBFAF7; --ink:#1A2332; --rule:#D8D4CC;
    --red:#A4322B; --green:#2F6B4F; --amber:#8A6318; --quiet:#6E6A63;
    --mono:'SF Mono','JetBrains Mono',Menlo,Consolas,monospace;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--paper);color:var(--ink);
       font:16px/1.6 Georgia,'Iowan Old Style',serif}}
  .sheet{{max-width:1100px;margin:0 auto;padding:56px 28px 90px}}
  h1{{font-family:var(--mono);font-size:26px;font-weight:600;margin:0 0 4px;
      letter-spacing:-.02em}}
  .sub{{color:var(--quiet);font-style:italic;margin:0 0 34px}}
  table{{border-collapse:collapse;width:100%}}
  thead th{{font-family:var(--mono);font-size:11.5px;font-weight:600;
    color:var(--quiet);text-align:left;padding:0 16px 9px 0;
    border-bottom:1.5px solid var(--ink)}}
  td{{padding:18px 16px 18px 0;border-bottom:1px solid var(--rule);
     vertical-align:top}}
  .stage{{font-family:var(--mono);font-size:14.5px;font-weight:600;width:23%}}
  .bet{{display:block;font-family:Georgia,serif;font-size:13.5px;
    font-weight:400;color:var(--quiet);font-style:italic;margin-top:5px;
    line-height:1.45}}
  .num{{width:17%;font-family:var(--mono);font-size:23px;font-weight:600;
    letter-spacing:-.02em}}
  .den{{display:block;font-family:Georgia,serif;font-size:12.5px;
    font-weight:400;color:var(--quiet);margin-top:6px;letter-spacing:0}}
  .ok{{color:var(--green)}} .no{{color:var(--red)}}
  .halt{{color:var(--red);font-size:17px}}
  .none{{color:var(--quiet);font-size:16px;font-weight:400}}
  .div{{font-size:14.5px;line-height:1.5}}
  .div.bad{{color:var(--red)}}
  .div.warn{{color:var(--amber)}}
  .div.ok{{color:var(--green)}}
  .div.muted{{color:var(--quiet)}}
  footer{{margin-top:34px;padding-top:18px;border-top:1px solid var(--rule);
    font-size:13.5px;color:var(--quiet);max-width:76ch}}
  @media(max-width:760px){{
    .sheet{{padding:32px 18px 60px}}
    table,thead,tbody,tr,td,th{{display:block}}
    thead{{display:none}}
    td{{border:none;padding:4px 0}}
    tr{{border-bottom:1px solid var(--rule);padding:18px 0;display:block}}
    .stage,.num{{width:auto}}
  }}
</style></head><body><div class="sheet">
  <h1>{title}</h1>
  <p class="sub">{n} stage(s). The third column is the one to read.</p>
  <table>
    <thead><tr>
      <th>stage and its bet</th>
      <th>predicted</th>
      <th>observed</th>
      <th>divergence</th>
    </tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>
  <footer>
    Every rate names the set it is over. A stage that could not judge half its
    input has a rate over the other half, and the cell says so. Nothing here
    compares a number to a target — only a prediction to an observation, which
    is the one comparison that can surprise you.
  </footer>
</div></body></html>
"""


def write(stages, preflights=None, path="stagecheck.html", title="stagecheck") -> str:
    p = pathlib.Path(path)
    p.write_text(render(stages, preflights, title))
    return str(p)
