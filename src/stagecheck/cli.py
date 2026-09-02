"""stagecheck's command line — the three tenses of one question.

    stagecheck report   ledger.jsonl    what did each stage buy, and cost?
    stagecheck check    ledger.jsonl    which stages are silent or inert?
    stagecheck why                      the reasoning, and where it came from

`preflight` and `watch` are not here yet. Shipping a command that does not
work would be the exact defect this tool exists to find, so they are absent
rather than stubbed — a missing stage honestly labelled is a result; a stage
that runs and does nothing is not.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

from . import COULD_NOT_RUN, FAIL, PASS, Summary, report


def _load(path: str) -> list[dict]:
    p = pathlib.Path(path)
    if not p.is_file():
        sys.exit(f"no ledger at {path}")
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _summarise(rows: list[dict]) -> list[Summary]:
    by_stage: dict[str, list[dict]] = collections.OrderedDict()
    for r in rows:
        by_stage.setdefault(r["stage"], []).append(r)
    out = []
    for name, rs in by_stage.items():
        ran = sum(1 for r in rs if r["evaluable"] != COULD_NOT_RUN)
        dens = {r.get("denominator") for r in rs}
        out.append(Summary(
            stage=name,
            bet=rs[0].get("detail", {}).get("bet", "(not recorded in the ledger)"),
            # A stage whose rows disagree about their denominator is a stage
            # whose rate is over an ambiguous set. Said rather than resolved.
            denominator=next(iter(dens)) if len(dens) == 1 else f"AMBIGUOUS {sorted(dens)}",
            offered=len(rs), judged=ran,
            failed=sum(1 for r in rs if r["evaluable"] == FAIL),
            could_not_run=len(rs) - ran,
            tokens=sum(r.get("tokens", 0) for r in rs),
            reviews=sum(r.get("reviews", 0) for r in rs),
            seconds=sum(r.get("latency_ms", 0) for r in rs) / 1000,
        ))
    return out


def cmd_report(a) -> int:
    print()
    print(report(_summarise(_load(a.ledger))))
    print()
    return 0


def cmd_check(a) -> int:
    """Exit non-zero if any stage is silent or inert.

    For CI. The threshold for failing a build is deliberately narrow: a stage
    that judged NOTHING, or judged plenty and changed nothing. Both are
    statements about whether the stage ran, not about whether its answers were
    good — halting on a result would be optional stopping, and a tool that
    encourages that is worse than none.
    """
    sums = _summarise(_load(a.ledger))
    bad = []
    for s in sums:
        if s.silent:
            bad.append((s.stage, "judged nothing — it is not running"))
        elif s.inert:
            bad.append((s.stage, f"judged {s.judged} and changed none"))
        elif "AMBIGUOUS" in s.denominator:
            bad.append((s.stage, f"rows disagree about the denominator: {s.denominator}"))
    print()
    if not bad:
        print(f"  {len(sums)} stage(s), all judging and all changing something.")
        print()
        return 0
    for name, why in bad:
        print(f"  {name}: {why}")
    print()
    print("  These are statements about whether a stage RAN, never about whether")
    print("  its answers were good. Halting a run on a result would be optional")
    print("  stopping; halting on a stage that is not running is a bug report.")
    print()
    return 1


def cmd_why(a) -> int:
    print("""
  stagecheck records two things nothing else does.

  A DENOMINATOR on every row — the named set a rate is over. In the study this
  came from, a judge's agreement figure moved 100% -> 98% -> 49% across three
  record sets with NO change in judge behaviour. The number was describing the
  composition of the comparison set. That movement is invisible in every LLM
  tracing tool, because it is not a property of any call.

  THREE OUTCOMES, not two. `could_not_run` is not `pass`. In one arm, 514 of
  704 records had a check with nothing to say about them; folding those into
  agreement would have produced a rate over a set nobody named.

  What it caught, in the pipeline it came from:

    four of seven stages did nothing — each passing its own tests, each
    writing a verdict field nothing downstream read

    one stage spent 425,355 tokens to change accuracy by -0.004

    one refusal policy withheld 64 correct answers on a threshold inherited
    from a different corpus, and never reported it

  What it does NOT do: score your outputs. Use ragas or deepeval for that.
  This asks whether your LAYERS are worth their cost, which is a different
  question and has no other tool.
""")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="stagecheck",
        description="Every stage makes a bet. This one makes you say what it is.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("report", help="what each stage was offered, judged and changed")
    p.add_argument("ledger", nargs="?", default="stagecheck.jsonl")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("check", help="fail if a stage is silent or inert (for CI)")
    p.add_argument("ledger", nargs="?", default="stagecheck.jsonl")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("why", help="what this records and why")
    p.set_defaults(fn=cmd_why)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
