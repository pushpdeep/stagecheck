# stagecheck

**Every stage makes a bet. This one makes you say what it is.**

A pipeline with several stages — validate, retry, vote, judge, abstain — and no
way to tell which of them earns its cost. stagecheck records the two things
nothing else does, and tells you which stages are doing nothing.

```python
import stagecheck

with stagecheck.stage("validator",
                      bet="the output has a decidable invalid state",
                      denominator="records_offered") as s:
    for rec in records:
        v = check(rec)
        if v is None:  s.could_not_run(rec, "nothing to check")
        elif v:        s.passed(rec)
        else:          s.failed(rec, "code_unknown")

print(stagecheck.report())
```

```
  stage       offered  judged  failed  cannot judge  rate of judged

  validator       704     190      17           514           8.9%
  self-correct     17      17       0             0           0.0%

  worth reading before quoting any rate above:
  validator: could not judge 514 of 704. Its rate is over the minority.
  self-correct: judged 17 and changed none. Its bet was: rung 1 gives it
    something to correct
```

## The two fields

**A denominator on every row.** The named set a rate is over. In the study this
came from, a judge's agreement figure moved **100% → 98% → 49%** across three
record sets with no change in judge behaviour — the number was describing the
composition of the comparison set. That movement is invisible in every LLM
tracing tool, because it is not a property of any call, and calls are what they
model.

**Three outcomes, not two.** `could_not_run` is not `pass`. A check that had
nothing to say is not a check that approved. Collapsing them is how a rate ends
up over a set nobody named.

## What it is not

It does not score your outputs. For that use `ragas`, `deepeval` or
`promptfoo` — they ask *is this answer right?* and they are good at it.

stagecheck asks *is this layer worth its cost?* That is a different question
with a different unit, and it has no other tool.

It never calls a model. No API keys, no dependencies, nothing leaves your
machine.

## Where it came from

A five-month study measuring seven reliability layers over three corpora
(clinical forum posts, SEC filings, news geography) and five model families.

**Four of the seven layers did nothing.** Each passed its own tests. Each wrote
a verdict field that nothing downstream read. One spent 425,355 tokens to move
accuracy by −0.004. A refusal policy withheld 64 correct answers on a threshold
inherited from a different corpus and never reported it.

None of that was visible in any tracing tool, and all of it was visible in a
ledger row with a denominator.

## Install

```
pip install stagecheck
```

## CLI

```
stagecheck report ledger.jsonl    what each stage was offered, judged, changed
stagecheck check  ledger.jsonl    exit non-zero if a stage is silent or inert
stagecheck why                    what this records, and what it caught
```

`check` fails a build only when a stage **judged nothing** or **changed
nothing** — statements about whether the stage ran, never about whether its
answers were good. Halting a run because a result looks unwelcome is optional
stopping, and a tool that encourages it is worse than none.

## One declaration, three tenses

Declare a stage once, and the same object answers all three questions.

```python
validator = stagecheck.declare(
    "validator",
    bet="the output has a decidable invalid state",
    denominator="records_offered",
    precondition=stagecheck.Precondition(
        measures="share of gold whose code fails the free check",
        over="coded gold mentions",
        measure=lambda recs: (sum(1 for r in recs if bad(r)), len(recs)),
        holds_if=lambda rate: rate > 0.05,
    ),
    invariants=[
        stagecheck.Invariant(
            "menu size",
            lambda menu, configured, **_: menu == configured,
            "the menu is smaller than the manifest asked for"),
    ],
)

before = validator.preflight(dev_gold)      # does the bet hold?
with validator.run(menu=139, configured=139) as s:
    ...                                     # is the setup still what I declared?
print(validator.report(before))             # did the bet pay?
```

`watch` halts on the **setup**, never on a result. Halting because a number
looks unwelcome is optional stopping; halting because the resolved model is not
the requested one is a bug report. Every halt is recorded, and a halted run
produces no number.

## The dashboard

```python
from stagecheck import dashboard
dashboard.write([validator, corrector, judge], preflights, "run.html")
```

Three columns — predicted, observed, divergence — and the third is the only one
worth reading. A bet that held beside a stage that judged nothing is a different
problem from a bet that never held, and neither number alone says so.

MIT.
