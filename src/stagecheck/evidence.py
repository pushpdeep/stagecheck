"""The vendored track record — what these checks have predicted, and what happened.

WHERE THIS COMES FROM

`evidence.json` is exported from the study that produced these checks, by
`scripts/export_evidence.py` in that repository. It is DATA and it is vendored,
not fetched.

Vendored because a tool that phones home for its calibration behaves differently
depending on the network, and this one's whole argument is that a measurement
must state the conditions it was taken under. Data rather than code because the
dependency points one way: the study imports stagecheck, and stagecheck knows
nothing about the study. The reverse would make anyone installing a measurement
library inherit a corpora problem and a non-transferable licence.

WHY IT HAS AN AGE, AND WHY THAT AGE IS PRINTED

This tool decays in an unusual way. Most tools rot because a dependency breaks;
this one has none — it reads a file and does arithmetic and never calls a model,
so it cannot break when a provider changes a response shape.

It rots because its KNOWLEDGE ages. "Self-correction rescues nothing" was
measured on 2026 open-weight models. If a later generation corrects itself
reliably, the code still runs perfectly and the advice is wrong — and a tool
giving confident stale advice is worse than no tool, because it is trusted.

So every verdict prints the age of the evidence behind it, and a stale record is
a test failure rather than a footnote.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date
from typing import Any

HERE = pathlib.Path(__file__).parent
FILE = HERE / "evidence.json"

#: A record older than this is reported as stale. Twelve months is roughly a
#: model generation, which is the interval over which these findings could
#: plausibly stop holding. Deliberately not configurable: a staleness threshold
#: a user can raise is one they will raise.
STALE_DAYS = 365


def _load() -> dict:
    if not FILE.is_file():
        return {}
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return {}


_DATA = _load()


def available() -> bool:
    return bool(_DATA.get("predictions"))


def age_days() -> int | None:
    stamp = _DATA.get("exported")
    if not stamp:
        return None
    try:
        y, m, d = (int(x) for x in stamp.split("-"))
        return (date.today() - date(y, m, d)).days
    except Exception:
        return None


def provenance() -> str:
    """One line naming what this evidence is, and how old."""
    if not available():
        return "no evidence vendored — every verdict here is untested"
    st = _DATA.get("study", {})
    n = len(_DATA["predictions"])
    days = age_days()
    age = "age unknown" if days is None else (
        f"{days} days old" if days < STALE_DAYS
        else f"**{days} days old — STALE**")
    corpora = ", ".join(_DATA.get("corpora", [])) or "unnamed corpora"
    dirty = " (from a dirty tree)" if st.get("dirty") else ""
    return (f"{n} prediction(s) from {corpora}, "
            f"study {st.get('sha', '?')}{dirty}, {age}")


def is_stale() -> bool:
    days = age_days()
    return days is not None and days > STALE_DAYS


def _canonical(check: str) -> str:
    return _DATA.get("aliases", {}).get(check, check)


def summary(check: str | None = None) -> str:
    if not available():
        return ""
    name = _canonical(check) if check else None
    rows = [p for p in _DATA["predictions"]
            if name is None or p.get("check") == name]
    if not rows:
        return ""
    counts: dict[str, int] = {}
    for p in rows:
        counts[p.get("outcome", "unknown")] = counts.get(p.get("outcome", "unknown"), 0) + 1
    order = ("right", "partly", "wrong", "unknown")
    parts = [f"{counts[k]} {k}" for k in order if k in counts]
    return f"{len(rows)} on record · " + ", ".join(parts)


def missed_on(check: str, corpus: str) -> dict[str, Any] | None:
    """Has this check been wrong ON THIS CORPUS?

    The distinction that stops a report contradicting itself: recommending a
    check on the very corpus it misled us about, with the summary of that miss
    four lines below. Measured — that happened.
    """
    if not available():
        return None
    name = _canonical(check)
    for p in _DATA["predictions"]:
        if (p.get("check") == name
                and (p.get("scope") or {}).get("corpus") == corpus
                and p.get("outcome") in ("wrong", "partly")):
            return p
    return None


def caveat(check: str) -> str:
    """The line printed beside a verdict."""
    if not available():
        return "no track record — this check has never been tested against an outcome"
    s = summary(check)
    if not s:
        return "no track record — this check has never been tested against an outcome"
    name = _canonical(check)
    misses = [p for p in _DATA["predictions"]
              if p.get("check") == name and p.get("outcome") in ("wrong", "partly")]
    if not misses:
        return s
    corpus = (misses[0].get("scope") or {}).get("corpus", "a corpus")
    return f"{s}  ·  MISSED on {corpus}"


def report() -> str:
    if not available():
        return ("  No evidence is vendored. Every verdict this tool prints is a\n"
                "  hypothesis with no track record, and should be read as one.")
    lines = ["  what these checks have predicted, and what happened", "",
             f"  {provenance()}", ""]
    mark = {"right": "\u2713", "wrong": "\u2717", "partly": "~", "unknown": "?"}
    for p in _DATA["predictions"]:
        sc = p.get("scope") or {}
        lines.append(f"  {mark.get(p.get('outcome'), '?')} {p.get('check', '?'):22} "
                     f"{p.get('said', '')}")
        lines.append(f"    {sc.get('corpus','?')}/{sc.get('split','?')} on "
                     f"{sc.get('on','?')}, n={sc.get('n','?')} · {p.get('when','?')}")
        if p.get("what_happened"):
            lines.append(f"    \u2192 {p['what_happened']}")
        if p.get("note"):
            lines.append(f"    ! {p['note']}")
        lines.append("")
    lines.append(f"  {summary()}")
    if is_stale():
        lines += ["", "  THIS RECORD IS STALE. Every finding in it was measured on the",
                  "  models and corpora named above. Read each verdict as a hypothesis",
                  "  until it has been re-measured."]
    return "\n".join(lines)
