"""stagecheck — every stage makes a bet; this makes you say what it is.

WHAT THIS IS FOR

A pipeline with several stages — validate, retry, vote, judge, abstain — and no
way to tell which of them is worth its cost. That is not a hypothetical: the
study this came from measured seven such stages and found four did nothing,
each of them passing its own tests, each writing a field nothing downstream
read.

The two things nothing else records, and which are the entire product:

    denominator   the NAMED SET a rate is over. A judge's agreement figure in
                  that study moved 100% -> 98% -> 49% across three record sets
                  with NO change in judge behaviour, because the number was
                  describing the composition of the comparison set. That
                  movement is invisible to every LLM tracing tool, because it
                  is not a property of any call, and calls are what they model.

    evaluable     THREE values, not two. `could_not_run` is not `pass`. In one
                  arm 514 of 704 records had a check with nothing to say about
                  them; folding those into agreement would have produced a rate
                  over a set nobody named.

WHY A CONTEXT MANAGER AND NOT A DECORATOR

Both were written and compared on the same pipeline. A decorator sees records
in and records out, so a record a stage APPROVED and a record it COULD NOT
JUDGE both come back unchanged — indistinguishable from outside. Measured on
five records: the decorator reported 5 judged and a 20% failure rate; the
context manager reported 3 judged, 1 failed, 2 could-not-run, a 33% rate over a
set it can name. Same data.

The decorator cannot express the third state, which means it cannot produce the
claim this tool exists to make. The extra two lines are the feature.
"""
from __future__ import annotations

import json
import pathlib
import time
from dataclasses import asdict, dataclass, field
from contextlib import contextmanager

__version__ = "0.1.0"

PASS, FAIL, COULD_NOT_RUN = "pass", "fail", "could_not_run"
EVALUABLE = (PASS, FAIL, COULD_NOT_RUN)


@dataclass
class Row:
    """One record's passage through one stage."""

    stage: str
    record_id: str
    denominator: str
    evaluable: str = COULD_NOT_RUN
    outcome: str | None = None
    tokens: int = 0
    latency_ms: float = 0.0
    reviews: int = 0
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.evaluable not in EVALUABLE:
            raise ValueError(
                f"evaluable must be one of {EVALUABLE}, not {self.evaluable!r}. "
                "The third state is the point — two states is what every other "
                "tool does, and it is how a rate ends up over a set nobody named."
            )
        if not self.denominator:
            raise ValueError(
                f"stage {self.stage!r} produced a row with no denominator. "
                "A rate without a named set is not a number."
            )


@dataclass
class Summary:
    stage: str
    bet: str
    denominator: str
    offered: int
    judged: int
    failed: int
    could_not_run: int
    tokens: int
    reviews: int
    seconds: float

    @property
    def fail_rate(self) -> float | None:
        """Over JUDGED, never over OFFERED.

        Returns None rather than 0.0 when nothing could be judged. A stage that
        ran on nothing has no rate, and reporting 0% would say it found no
        problems — which is a claim it has not earned.
        """
        return self.failed / self.judged if self.judged else None

    @property
    def silent(self) -> bool:
        """Judged nothing. Not the same as found nothing wrong."""
        return self.judged == 0

    @property
    def inert(self) -> bool:
        """Judged plenty and changed nothing.

        The shape four stages had in the source study: running, costing,
        passing their tests, and altering no outcome.
        """
        return self.judged > 0 and self.failed == 0


class Stage:
    """The handle a stage reports through. Nothing is inferred."""

    __slots__ = ("name", "bet", "denominator", "number", "rows", "_t0", "_ledger")

    def __init__(self, name, bet, denominator, number, ledger):
        if not bet:
            raise ValueError(
                f"stage {name!r} has no declared bet. A stage nobody can state "
                "a claim for is a stage nobody has justified — and this tool "
                "exists because four such stages ran for five months."
            )
        self.name, self.bet = name, bet
        self.denominator, self.number = denominator, number
        self.rows: list[Row] = []
        self._t0 = time.perf_counter()
        self._ledger = ledger

    def passed(self, rec, **kw):
        """Judged, and fine."""
        self._row(rec, PASS, **kw)

    def failed(self, rec, outcome: str, **kw):
        """Judged, and wrong. `outcome` must be a reason a later stage can act on."""
        self._row(rec, FAIL, outcome=outcome, **kw)

    def could_not_run(self, rec, why: str, **kw):
        """Had nothing to say about this record.

        NOT a pass. The field was missing, the vocabulary could not type it,
        the span was ungrounded. Recorded as its own state so every rate above
        knows what it is over.
        """
        self._row(rec, COULD_NOT_RUN, outcome=why, **kw)

    def _row(self, rec, evaluable, outcome=None, tokens=0, reviews=0, **detail):
        self.rows.append(Row(
            stage=self.name, record_id=_id(rec), denominator=self.denominator,
            evaluable=evaluable, outcome=outcome, tokens=int(tokens),
            reviews=int(reviews), detail=detail,
            latency_ms=(time.perf_counter() - self._t0) * 1000,
        ))

    def summary(self) -> Summary:
        n = len(self.rows)
        ran = sum(1 for r in self.rows if r.evaluable != COULD_NOT_RUN)
        return Summary(
            stage=self.name, bet=self.bet, denominator=self.denominator,
            offered=n, judged=ran,
            failed=sum(1 for r in self.rows if r.evaluable == FAIL),
            could_not_run=n - ran,
            tokens=sum(r.tokens for r in self.rows),
            reviews=sum(r.reviews for r in self.rows),
            seconds=time.perf_counter() - self._t0,
        )


class Ledger:
    """Rows and summaries for one run. Explicit, so tests do not share state."""

    def __init__(self):
        self.rows: list[Row] = []
        self.summaries: list[Summary] = []

    @contextmanager
    def stage(self, name: str, *, bet: str, denominator: str, number: str = ""):
        s = Stage(name, bet, denominator, number, self)
        try:
            yield s
        finally:
            self.rows.extend(s.rows)
            self.summaries.append(s.summary())

    def write(self, path="stagecheck.jsonl") -> int:
        p = pathlib.Path(path)
        with p.open("w") as fh:
            for r in self.rows:
                fh.write(json.dumps(asdict(r)) + "\n")
        return len(self.rows)

    def report(self) -> str:
        return report(self.summaries)


#: The default ledger, for the common case of one pipeline in one process.
_default = Ledger()


def stage(name: str, *, bet: str, denominator: str, number: str = ""):
    """Declare a stage and report each record through it.

        with stagecheck.stage("validator",
                              bet="the output has a decidable invalid state",
                              denominator="records_offered") as s:
            for rec in records:
                v = check(rec)
                if v is None:  s.could_not_run(rec, "nothing to check")
                elif v:        s.passed(rec)
                else:          s.failed(rec, "code_unknown")
    """
    return _default.stage(name, bet=bet, denominator=denominator, number=number)


def rows():
    return list(_default.rows)


def summaries():
    return list(_default.summaries)


def write(path="stagecheck.jsonl") -> int:
    return _default.write(path)


def reset() -> None:
    _default.rows.clear()
    _default.summaries.clear()


def report(sums=None) -> str:
    """What each stage was offered, judged, and changed.

    Ordered as declared rather than by any score: the sequence a reader needs
    is the pipeline's own, because a stage that judges nothing is usually
    starved by the one before it.
    """
    sums = summaries() if sums is None else sums
    if not sums:
        return "  no stages recorded"
    w = max(len(s.stage) for s in sums)
    out = [f"  {'stage':<{w}} {'offered':>8} {'judged':>7} {'failed':>7} "
           f"{'cannot judge':>13} {'rate of judged':>15}", ""]
    for s in sums:
        rate = "—" if s.fail_rate is None else f"{s.fail_rate:.1%}"
        out.append(f"  {s.stage:<{w}} {s.offered:8} {s.judged:7} {s.failed:7} "
                   f"{s.could_not_run:13} {rate:>15}")
    flags = []
    for s in sums:
        if s.silent:
            flags.append(f"  {s.stage}: judged NOTHING. It is not finding no problems — "
                         f"it is not running. Its bet was: {s.bet}")
        elif s.inert:
            flags.append(f"  {s.stage}: judged {s.judged} and changed none. "
                         f"Its bet was: {s.bet}")
        elif s.could_not_run > s.judged:
            flags.append(f"  {s.stage}: could not judge {s.could_not_run} of "
                         f"{s.offered}. Its rate is over the minority.")
    if flags:
        out += ["", "  worth reading before quoting any rate above:"] + flags
    total_tokens = sum(s.tokens for s in sums)
    total_reviews = sum(s.reviews for s in sums)
    if total_tokens or total_reviews:
        out += ["", f"  cost: {total_tokens:,} tokens · {total_reviews} human reviews",
                "  Never fused. A token and a review are not exchangeable, and any",
                "  single number combining them has picked an exchange rate for you."]
    return "\n".join(out)


def _id(rec) -> str:
    for attr in ("record_id", "id", "doc_id", "uid"):
        v = getattr(rec, attr, None)
        if v:
            return str(v)
    if isinstance(rec, dict):
        for k in ("record_id", "id", "doc_id"):
            if rec.get(k):
                return str(rec[k])
    return str(id(rec))
