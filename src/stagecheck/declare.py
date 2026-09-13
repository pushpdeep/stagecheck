"""One declaration, read in three tenses.

THE PROBLEM THIS SOLVES

`stage()` takes a `bet` and stores it, and the bet is prose — *"the output has a
decidable invalid state"*. Prose cannot be tested, so the declaration was only
ever readable in the past tense: after the run, in a report.

That leaves the tool as three ideas sharing a package rather than one tool.
Worse, it leaves the gap that produced the most expensive defect in the study
this came from: a menu declared at 139 entries and delivered at 20, with
nothing checking that the declaration still described the run.

WHAT CHANGES

A stage is declared ONCE, with a bet that has a testable form, and the same
object answers all three questions:

    BEFORE   does this bet hold on my data?          .preflight(records)
    DURING   is the setup still what I declared?     .watch(**context)
    AFTER    did the bet pay?                        .report()

The three tenses cannot disagree, because there is only one declaration.

WHAT `watch` WILL AND WILL NOT HALT ON

This is the design's sharpest line and it was nearly got wrong. A watcher that
halts on RESULTS is optional stopping: kill enough runs that look bad and the
survivors are a biased sample. So the invariants a stage declares must be
statements about its SETUP, never about its output.

    HALT ON                          DO NOT HALT ON
    resolved model != requested      accuracy looks low
    menu smaller than configured     a stage is changing nothing
    retrieval fell back silently     cost per record is high
    output unparseable above ~80%    the delta is negative
    a required resource is absent    the spread between draws is wide

Every halt is recorded with its reason, and a halted run produces NO number —
it is a bug report, not a result. That is what keeps the left column from
becoming a thumb on the scale.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable

from . import COULD_NOT_RUN, FAIL, PASS, Ledger, Summary, _default


class SetupBroken(RuntimeError):
    """A declared invariant about the SETUP was violated mid-run.

    Not an assertion about results. Raised so the run stops before spending
    more on a configuration that is not the one declared — the case that cost
    this project 133 minutes when a model name resolved to something absent,
    and an entire arm when a 139-entry menu was silently delivered as 20.
    """


@dataclass
class Measurement:
    """What a precondition found. Carries its own denominator, always."""

    holds: bool
    value: float
    over: str                       # the named set, never optional
    n: int
    detail: str = ""

    def __str__(self) -> str:
        verdict = "holds" if self.holds else "DOES NOT HOLD"
        s = f"{verdict} — {self.value:.1%} of {self.n} {self.over}"
        return f"{s}. {self.detail}" if self.detail else s


@dataclass
class Precondition:
    """The bet, in a form that can be measured before the stage exists.

    `measure` returns (numerator, denominator_count) over whatever records it
    is handed. `holds_if` turns that rate into a verdict. Both are the user's,
    because only they know what their stage is betting on.

    `needs` is stated so a preflight run on the wrong input says so rather than
    producing a number: a precondition measured on gold can be wildly wrong
    about model output. Measured here at 1.22% on gold and 35.7% on the same
    check's own live output, which is why the field exists.
    """

    measures: str
    over: str
    measure: Callable[[Any], tuple[int, int]]
    holds_if: Callable[[float], bool] = lambda rate: rate > 0.0
    needs: str = "gold"             # "gold" | "model output" | "either"

    def run(self, records) -> Measurement:
        hits, n = self.measure(records)
        rate = hits / n if n else 0.0
        return Measurement(holds=bool(n) and self.holds_if(rate),
                           value=rate, over=self.over, n=n)


@dataclass
class Invariant:
    """A statement about the SETUP that must stay true while the run happens.

    Never about the output. See the module docstring for the line and why it
    is not negotiable.
    """

    name: str
    holds: Callable[..., bool]
    says: str

    def check(self, **context) -> bool:
        try:
            return bool(self.holds(**context))
        except TypeError:
            # An invariant that cannot see what it needs has NOT passed. It
            # could not run, and silently treating that as a pass is the
            # two-state accounting this whole tool exists to refuse.
            return False


@dataclass
class Stage:
    """A stage, declared once and read in three tenses."""

    name: str
    bet: str
    denominator: str
    precondition: Precondition | None = None
    invariants: list[Invariant] = field(default_factory=list)
    number: str = ""
    ledger: Ledger | None = None

    _halts: list = field(default_factory=list, repr=False)

    # ── tense zero ─────────────────────────────────────────────────────
    def confirm(self, **context) -> list[tuple[str, bool, str]]:
        """Check the declared invariants BEFORE the stage runs.

        `watch` checks the same statements DURING a run and raises
        `SetupBroken` when one breaks. `confirm` asks them first, when the
        answer can still stop the spend, and REPORTS rather than raising —
        because several may be wrong at once and seeing one of five is how a
        misconfiguration gets fixed five times.

        Returns (name, holds, says) per invariant. An invariant that cannot
        see what it needs reads False, exactly as in `watch`: it could not
        run, and counting that as a pass is the two-state accounting this
        tool refuses everywhere else.

        The case it was written from: twelve cells of a study ran with another
        corpus's task description. Every precondition held — there really were
        mentions to find — and the INSTRUCTION was wrong. A precondition
        asks whether the stage has work to do; this asks whether the stage is
        the one that was declared.
        """
        return [(inv.name, inv.check(**context), inv.says)
                for inv in self.invariants]

    def confirmed(self, **context) -> bool:
        """True when every declared invariant holds on this configuration."""
        return all(holds for _, holds, _ in self.confirm(**context))

    # ── tense one ──────────────────────────────────────────────────────
    def preflight(self, records) -> Measurement | None:
        """Does the bet hold on this data, before the stage is built?

        Returns None when no precondition was declared — which is a real
        answer, not an omission. A stage whose bet cannot be stated in a
        testable form is a stage nobody can check in advance, and saying so is
        more useful than inventing a check.
        """
        if self.precondition is None:
            return None
        return self.precondition.run(records)

    # ── tense two ──────────────────────────────────────────────────────
    def watch(self, **context) -> None:
        """Assert the declared setup invariants. Raises SetupBroken.

        Call it once when the run starts and, for anything that can change
        mid-run, again as it changes. A declaration checked only at startup is
        how a menu configured at 139 was delivered as 20 for an entire arm.
        """
        broken = [inv for inv in self.invariants if not inv.check(**context)]
        if not broken:
            return
        self._halts.extend(broken)
        lines = [f"  {i.name}: {i.says}" for i in broken]
        raise SetupBroken(
            f"stage {self.name!r} — the setup is not what was declared:\n"
            + "\n".join(lines)
            + "\n\n  This is a bug report, not a result. Fix the configuration and"
              "\n  re-run; the partial run produces no number."
        )

    @contextmanager
    def run(self, **context):
        """Record this stage. Checks invariants first, if any were declared."""
        if self.invariants and context:
            self.watch(**context)
        led = self.ledger or _default
        with led.stage(self.name, bet=self.bet,
                       denominator=self.denominator, number=self.number) as s:
            yield s

    # ── tense three ────────────────────────────────────────────────────
    def summary(self) -> Summary | None:
        led = self.ledger or _default
        for s in reversed(led.summaries):
            if s.stage == self.name:
                return s
        return None

    def report(self, preflight: Measurement | None = None) -> str:
        """The three tenses side by side, which is the point of the object.

        Printing them together is what makes a divergence visible. A
        precondition that held on gold and a stage that judged nothing is the
        signature of a check whose input is not what it was measured on — and
        neither number alone says so.
        """
        out = [f"  {self.name}", f"    bet: {self.bet}"]
        if preflight is not None:
            out.append(f"    before: {preflight}")
        elif self.precondition is not None:
            out.append("    before: not measured — call preflight() with your dev split")
        else:
            out.append("    before: no testable precondition declared")

        if self._halts:
            out.append(f"    during: HALTED on {len(self._halts)} broken invariant(s) "
                       f"— no number was produced")
        elif self.invariants:
            out.append(f"    during: {len(self.invariants)} invariant(s) held")

        s = self.summary()
        if s is None:
            out.append("    after: this stage has not run")
        else:
            rate = "no rate — it judged nothing" if s.fail_rate is None \
                else f"{s.fail_rate:.1%} of {s.judged} judged"
            out.append(f"    after: offered {s.offered}, judged {s.judged}, "
                       f"could not judge {s.could_not_run} · {rate}")
            if preflight is not None:
                out.append(f"    {_divergence(preflight, s)}")
        return "\n".join(out)


def _divergence(before: Measurement, after: Summary) -> str:
    """The line worth having. A bet that held and a stage that does nothing is
    a different problem from a bet that never held."""
    if after.judged == 0:
        return ("→ the bet HELD and the stage judged NOTHING. Its input is not "
                "what the precondition was measured on.")
    if before.holds and after.failed == 0:
        return ("→ the bet held and the stage changed nothing. It is running, "
                "and it is not earning its cost.")
    if not before.holds and after.failed:
        return ("→ the bet did NOT hold and the stage fired anyway. Check what "
                "it is actually keying on.")
    return "→ before and after agree."


def declare(name: str, *, bet: str, denominator: str,
            precondition: Precondition | None = None,
            invariants: list[Invariant] | None = None,
            number: str = "", ledger: Ledger | None = None) -> Stage:
    """Declare a stage once.

        validator = stagecheck.declare(
            "validator",
            bet="the output has a decidable invalid state",
            denominator="records_offered",
            precondition=Precondition(
                measures="share of gold whose code fails the free check",
                over="coded gold mentions",
                measure=lambda recs: (sum(1 for r in recs if bad(r)), len(recs)),
                holds_if=lambda rate: rate > 0.05,
            ),
            invariants=[
                Invariant("menu size",
                          lambda menu, configured, **_: menu == configured,
                          "the menu is smaller than the manifest asked for"),
            ],
        )

        before = validator.preflight(dev_gold)
        with validator.run(menu=139, configured=139) as s:
            ...
        print(validator.report(before))
    """
    if not bet:
        raise ValueError(
            f"stage {name!r} has no declared bet. A stage nobody can state a "
            "claim for is a stage nobody has justified.")
    return Stage(name=name, bet=bet, denominator=denominator,
                 precondition=precondition, invariants=invariants or [],
                 number=number, ledger=ledger)
