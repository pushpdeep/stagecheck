"""stagecheck's command line — the three tenses of one question.

    stagecheck preflight mod:stages   does each stage's bet hold, before you build it?
    stagecheck report   ledger.jsonl  what did each stage buy, and cost?
    stagecheck check    ledger.jsonl  which stages are silent or inert?
    stagecheck evidence               what these checks predicted, and what happened
    stagecheck why                    the reasoning, and where it came from

THERE IS NO `watch` SUBCOMMAND, AND THERE SHOULD NOT BE.

`watch` asserts a stage's declared invariants against live context, inside the
process, while the run happens. A command line cannot attach to that. Shipping a
`watch` that printed something plausible and checked nothing would be exactly the
defect this package exists to find, so it is library-only:

    with my_stage.run(menu=139, configured=139) as s:
        ...

`preflight` CAN be a command, because it needs only your declarations and your
records — so it imports a module you name, the way `gunicorn app:app` does.
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


def _import_stages(spec: str):
    """`mypipeline:STAGES` -> the list of declared stages in your code.

    Your declarations live in your module, not in a config file, because a
    stage's bet belongs next to the stage. That means the CLI has to import
    your code — which is the same bargain gunicorn and pytest make, and is
    stated here rather than hidden.
    """
    import importlib
    if ":" not in spec:
        sys.exit("give it as module:attribute — e.g. mypipeline:STAGES")
    mod_name, attr = spec.rsplit(":", 1)
    sys.path.insert(0, str(pathlib.Path.cwd()))
    try:
        mod = importlib.import_module(mod_name)
    except ImportError as exc:
        sys.exit(f"could not import {mod_name!r}: {exc}")
    stages = getattr(mod, attr, None)
    if stages is None:
        sys.exit(f"{mod_name} has no attribute {attr!r}")
    if not isinstance(stages, (list, tuple)):
        stages = [stages]
    return list(stages)


def cmd_preflight(a) -> int:
    """Does each stage's bet hold on your data, before the stage is built?

    Exits non-zero when a declared bet does NOT hold — which is a statement
    about the data, not about a result, and is therefore safe to gate on. A
    stage whose precondition fails on your dev split will not start paying
    because you built it carefully.
    """
    stages = _import_stages(a.stages)
    records = None
    if a.records:
        p = pathlib.Path(a.records)
        if not p.is_file():
            sys.exit(f"no records at {a.records}")
        records = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

    print()
    failed = untested = 0
    for st in stages:
        if st.precondition is None:
            print(f"  {st.name:20} no testable precondition declared")
            print(f"  {'':20} bet: {st.bet}")
            untested += 1
            continue
        if records is None:
            print(f"  {st.name:20} needs records — pass --records")
            untested += 1
            continue
        m = st.preflight(records)
        mark = "hold" if m.holds else "DO NOT HOLD"
        print(f"  {st.name:20} {mark:12} {m.value:.1%} of {m.n} {m.over}")
        print(f"  {'':20} bet: {st.bet}")
        print(f"  {'':20} measured on {st.precondition.needs}")
        failed += not m.holds
        print()

    if untested:
        print(f"  {untested} stage(s) have no testable precondition. That is a real")
        print("  answer, not an omission: a bet nobody can state in a measurable")
        print("  form is one nobody can check before building it.")
    if failed:
        print(f"\n  {failed} declared bet(s) do not hold on this data.")
        print("  That is a statement about the DATA, not about a result — the layer")
        print("  will not start paying because you build it carefully.")
    print()
    return 1 if failed else 0


def cmd_evidence(a) -> int:
    from . import evidence
    print()
    print(evidence.report())
    print()
    return 0


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

  And there is no `watch` subcommand. watch() asserts a stage's declared
  invariants against live context, inside the process, while the run happens —
  a command line cannot attach to that. A `watch` that printed something
  plausible and checked nothing would be the exact defect this package exists
  to find, so it is library-only.
""")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="stagecheck",
        description="Every stage makes a bet. This one makes you say what it is.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("preflight",
                       help="does each stage's bet hold, before you build it?")
    p.add_argument("stages", help="module:attribute holding your declared stages")
    p.add_argument("--records", help="JSONL of records to measure the bets on")
    p.set_defaults(fn=cmd_preflight)

    p = sub.add_parser("evidence",
                       help="what these checks predicted, and what happened")
    p.set_defaults(fn=cmd_evidence)

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
