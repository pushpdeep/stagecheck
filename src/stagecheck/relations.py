"""The relation registry — what a free check can ask about a value and a code.

WHY A REGISTRY AND NOT A CHECK

A validation stage usually implements one relation and, when that relation finds
nothing, reports that the stage is dead. Measured in the study behind this
package: a lexical-overlap check had **zero** signal on a corpus of numerals —
`47.6` shares no token with `EffectiveIncomeTaxRateContinuingOperations`, by
construction, on any run — and a type-compatibility check on the *same data*
reached 87.7% coverage.

The signal was there. The tool could not see it, because it only knew one way to
look.

So a relation is a first-class thing here, and the report says which relations
have signal on YOUR data rather than whether yours does. That changes the output
from a diagnosis to a recommendation, and nobody's work gets called broken.

THE THREE ANSWERS, AND THE THIRD IS THE POINT

    AGREE       consistent on this relation
    CONTRADICT  VIOLATED — a proof of wrongness, which is the only thing a free
                check can ever establish
    SILENT      this relation cannot speak about this record

SILENT is not AGREE. Collapsing them computes a rate over a set nobody named,
which is the failure this whole package exists to refuse.

HOW A RELATION IS JUDGED, in this order and not another

    1. FALSE CONTRADICTIONS ON KNOWN-GOOD RECORDS, first and before anything.
       Every contradiction of a record you know is right is false by
       construction. A check that rejects a correct answer set is worse than no
       check. In the study, one such rate went from 9.3% to 0.13% by being
       measured this way, and the measurement cost nothing.
    2. COVERAGE. A relation speaking about 3% of records is not worth wiring in
       however precise it is.
    3. DISCRIMINATION. A relation that agrees with everything has no power, and
       calling that "endorsing" is how a check ends up vouching hardest where it
       knows least.

THE WARNING THAT COST THE STUDY A DAY

A relation validated only on KNOWN-GOOD records can be far worse on real model
output. Measured: 1.22% false contradictions on gold, **35.7% on the model's own
output**, because gold spans sit exactly where an annotator put them and model
spans drift, so the context window is read wrongly and the relation contradicts
confidently on a misreading.

`measure()` therefore takes either, and the report says which. A relation is not
validated until it has been measured on both.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

AGREE, CONTRADICT, SILENT = "agree", "contradict", "silent"

_PUNCT = re.compile(r"[^a-z0-9 ]")
_MONTHS = (r"january|february|march|april|may|june|july|august|september"
           r"|october|november|december")


def tokens(s: str) -> set[str]:
    return set(_PUNCT.sub(" ", (s or "").lower()).split())


@runtime_checkable
class Vocabulary(Protocol):
    """What a relation may ask of your vocabulary.

    Only `exists` is required. Every other method is optional, and a relation
    that needs a method you have not implemented reports **not applicable**
    once, rather than SILENT on every record — those are different states and
    reporting them the same way hides which one you are in.
    """

    def exists(self, code: Any) -> bool: ...

    # Optional. Implement what you have.
    #   terms(code)          -> the names this code is known by
    #   code_type(code)      -> "money" | "percent" | ... , or None
    #   codes_for_term(term) -> every code that name belongs to
    #   is_kind(code)        -> True if the code is the right KIND of thing


@dataclass
class Relation:
    """One deterministic question a free check can ask."""

    name: str
    asks: str
    judge: Callable[..., str]
    needs: tuple[str, ...] = ()
    needs_context: bool = False
    note: str = ""

    def applies(self, vocab) -> bool:
        return all(callable(getattr(vocab, m, None)) for m in self.needs)


# ── the relations ───────────────────────────────────────────────────────

def _exists(value, before, after, code, vocab) -> str:
    """Is the code in the vocabulary at all?

    The cheapest relation, and it went quiet in the study for an instructive
    reason: once the model picked from a retrieved menu of real codes it could
    no longer invent one. A relation can be perfectly sound and have nothing to
    do. Note that it is INVISIBLE on known-good records — a gold code exists by
    definition — and useful on model output, which is the inverse of the trap in
    `type` below, and the reason both views are needed.
    """
    if code in (None, ""):
        return SILENT
    try:
        return AGREE if vocab.exists(code) else CONTRADICT
    except Exception:
        return SILENT


def _lexical(value, before, after, code, vocab) -> str:
    """Do the value's words appear among the code's own names?

    Where it applies it is the strongest relation known here: in the study the
    records it endorsed were 80–89% correct across five model families whose
    headline scores spanned a factor of 2.8.

    It can only ENDORSE. A miss is not a contradiction — a person writing "bit
    drowsy" for a concept named "Drowsy" is not proof of wrongness, and treating
    it as one would reject a large share of correct answers.
    """
    try:
        names = vocab.terms(code) or []
    except Exception:
        return SILENT
    want = tokens(value)
    if not names or not want:
        return SILENT
    return AGREE if any(want == tokens(t) for t in names) else SILENT


def _kind(value, before, after, code, vocab) -> str:
    """Is the code the right KIND of thing?

    Needs a vocabulary with categories. Flat vocabularies do not have them, and
    `applies` says so once.
    """
    try:
        ok = vocab.is_kind(code)
    except Exception:
        return SILENT
    return SILENT if ok is None else (AGREE if ok else CONTRADICT)


def _type_compat(value, before, after, code, vocab) -> str:
    """Does the value's SHAPE agree with the type its code claims?

    Built for the case where lexical overlap is a structural zero: a numeric
    value and an English concept name share no token, yet BOTH carry a type —
    the code's name says `...Percentage` or `...Amount`, and the value sits next
    to `%`, `$`, "million", "shares".

    MEASURED, and the two numbers must be read together:
        on known-good records   87.7% coverage, 1.22% false
        on model output         35.7% false

    The gap is the finding, not a caveat. It is kept here as the worked example
    of a relation that must be validated on both.
    """
    try:
        ct = vocab.code_type(code)
    except Exception:
        return SILENT
    if ct is None:
        return SILENT
    vt = value_shape(value, before, after)
    return SILENT if vt is None else (AGREE if vt == ct else CONTRADICT)


def value_shape(value: str, before: str = "", after: str = "") -> str | None:
    """A value's type, from its own form and the characters either side.

    Conservative by design: returns None rather than guessing, because an
    unconfident relation that abstains is usable and one that guesses
    manufactures false contradictions. Each rule below was added because a
    measured disagreement demanded it — a first draft contradicted 8.54% of a
    known-good set and three rules took it to 1.22%.
    """
    t = (value or "").strip()
    a = (after or "")[:24].lower()
    if re.match(rf"^({_MONTHS})\b", t.lower()) or re.match(r"^(19|20)\d{2}$", t):
        return "date"
    if re.match(r"^\s*%", after or "") or a[:12].lstrip().startswith("percent"):
        return "percent"
    if re.search(r"\byears?\b|\bmonths?\b|\bdays?\b", a[:14]):
        return "duration"
    # A currency symbol immediately before outranks a quantity word after:
    # "$ 6.1 billion in share repurchases" is money, and "share" three tokens
    # later does not make it a count.
    if re.search(r"[$€£]\s*$", (before or "")[-4:]):
        return "money"
    # "per share" is a UNIT, not a quantity of shares.
    if re.search(r"\bper\s+(share|unit)\b", a[:18]):
        return "money"
    if re.search(r"\bshares?\b|\bunits?\b|\bitems?\b|\bpeople\b|\bemployees\b", a[:22]):
        return "count"
    if re.search(r"\b(million|billion|thousand)\b", a[:16]):
        return "money"
    return None


def _unique(value, before, after, code, vocab) -> str:
    """Does a matching name IDENTIFY one thing, or merely match?

    Not really a check on a record — a name shared by two hundred places is
    still the right name. It is a property of the VOCABULARY that WEAKENS the
    lexical relation, and it exists because of a miss: a lexical check fired on
    39.8% of records and the lane it produced scored WORSE than the records it
    could not vouch for, on three models, because matching "London" to an entry
    named "London" says nothing about which London.

    Reported as AGREE or SILENT, never CONTRADICT. Implementing it as a
    per-record contradiction made it reject 126 correct records before that was
    noticed.
    """
    try:
        name = (vocab.terms(code) or [None])[0]
        holders = set(vocab.codes_for_term(name) or []) if name else set()
    except Exception:
        return SILENT
    return AGREE if holders else SILENT


REGISTRY: list[Relation] = [
    Relation("exists", "is the code in the vocabulary at all?", _exists,
             needs=("exists",),
             note="Invisible on known-good records and useful on model output."),
    Relation("lexical", "do the value's words appear in the code's own names?",
             _lexical, needs=("terms",),
             note="Endorses only. A miss is not proof of wrongness."),
    Relation("kind", "is the code the right KIND of thing?", _kind,
             needs=("is_kind",),
             note="Needs categories. Vacuous on a flat vocabulary."),
    Relation("type", "does the value's shape agree with the code's type?",
             _type_compat, needs=("code_type",), needs_context=True,
             note="1.22% false on known-good records, 35.7% on model output."),
    Relation("unique", "does a matching name identify one thing?", _unique,
             needs=("terms", "codes_for_term"),
             note="Qualifies `lexical` rather than standing alone."),
]


def register(relation: Relation) -> None:
    """Add your own. The four above are the ones this study needed; yours will
    differ, and a registry nobody can extend is a list."""
    if any(r.name == relation.name for r in REGISTRY):
        raise ValueError(f"a relation named {relation.name!r} is already registered")
    REGISTRY.append(relation)


# ── measurement ─────────────────────────────────────────────────────────

@dataclass
class Result:
    name: str
    asks: str
    applicable: bool = True
    agree: int = 0
    contradict: int = 0
    silent: int = 0
    false_contradictions: int = 0
    examples: list = field(default_factory=list)
    note: str = ""

    @property
    def spoke(self) -> int:
        return self.agree + self.contradict

    @property
    def coverage(self) -> float:
        n = self.spoke + self.silent
        return self.spoke / n if n else 0.0

    @property
    def false_rate(self) -> float:
        return self.false_contradictions / self.contradict if self.contradict else 0.0

    def verdict(self, min_coverage: float = 0.10, max_false: float = 0.02) -> str:
        """Four states, because two cannot describe a relation.

        An ENDORSING relation can only vouch; a REJECTING one can prove
        wrongness. A first version of this scale treated "endorses only" as
        failure and so reported that the study's best corpus had no usable
        signal — the tool contradicting the work that produced it.
        """
        if not self.applicable:
            return "n/a"
        if self.coverage < min_coverage:
            return "no signal"
        if self.contradict and self.false_rate > max_false:
            return "BROKEN"
        if self.contradict == 0:
            # Agreeing with EVERYTHING is not endorsement, it is absence of
            # discrimination — the ACCEPT-lane-on-a-gazetteer failure.
            if self.agree and self.silent:
                return "endorses"
            return "vacuous" if self.agree else "silent"
        return "rejects"


def measure(records, vocab, *, value_of=None, code_of=None, context_of=None,
            known_good=None, relations=None) -> list[Result]:
    """Run every applicable relation over a record set. No model calls.

    `records` may be known-good or model output — the caller says which, and the
    difference is not cosmetic.

    `known_good(record)` marks a record you know is right. On an answer key it
    is `lambda _: True`, which makes every contradiction false BY CONSTRUCTION
    and is the cheapest validation available.
    """
    value_of = value_of or (lambda r: getattr(r, "text", "") or "")
    code_of = code_of or (lambda r: getattr(r, "code", None) or getattr(r, "sct", None))
    context_of = context_of or (lambda r: ("", ""))
    out = []
    for rel in (relations or REGISTRY):
        res = Result(rel.name, rel.asks, note=rel.note)
        res.applicable = rel.applies(vocab)
        if not res.applicable:
            out.append(res)
            continue
        for rec in records:
            code = code_of(rec)
            if isinstance(code, (list, tuple)):
                code = code[0] if code else None
            before, after = context_of(rec) if rel.needs_context else ("", "")
            try:
                v = rel.judge(value_of(rec), before, after, code, vocab)
            except Exception:
                v = SILENT
            if v == AGREE:
                res.agree += 1
            elif v == CONTRADICT:
                res.contradict += 1
                if known_good is not None and known_good(rec):
                    res.false_contradictions += 1
                    if len(res.examples) < 4:
                        res.examples.append((value_of(rec), code))
            else:
                res.silent += 1
        out.append(res)
    return out


def report(results, on: str = "known-good records", corpus: str = "") -> str:
    """The recommendation, not the diagnosis.

    Usable relations first. A report that opens with what is broken tells
    somebody their work is bad; one that opens with what works on their data
    hands them a check.
    """
    order = {"rejects": 0, "endorses": 1, "BROKEN": 2, "no signal": 3,
             "vacuous": 4, "silent": 5, "n/a": 6}
    rows = sorted(results, key=lambda r: order.get(r.verdict(), 9))
    if not rows:
        return "  no relations were measured"
    w = max(len(r.name) for r in rows)
    lines = [f"  relations available on this data  ·  measured on {on.upper()}, "
             f"no model calls", ""]
    for r in rows:
        v = r.verdict()
        if v == "n/a":
            lines.append(f"  {r.name:<{w}}  —{'':<12} your vocabulary cannot support it")
            continue
        detail = f"speaks about {r.coverage:5.1%}"
        if r.contradict:
            detail += f" · {r.contradict} contradictions, {r.false_rate:.2%} false"
        lines.append(f"  {r.name:<{w}}  {v:<11} {detail}")
        if r.examples:
            val, code = r.examples[0]
            lines.append(f"  {'':<{w}}  e.g. it rejects {val!r} against "
                         f"{str(code)[:38]} — and that was RIGHT")

    try:
        from . import evidence
    except Exception:
        evidence = None

    usable, caution = [], []
    for r in rows:
        if r.verdict() not in ("rejects", "endorses"):
            continue
        miss = evidence.missed_on(r.name, corpus) if (evidence and corpus) else None
        (caution if miss else usable).append((r, miss))

    if evidence and evidence.available():
        lines.append("")
        for r in rows:
            if r.verdict() in ("n/a", "no signal"):
                continue
            lines.append(f"  {r.name:<{w}}  {evidence.caveat(r.name)}")

    lines.append("")
    if usable:
        lines.append(f"  → build on {', '.join(r.name for r, _ in usable)}.")
    for r, miss in caution:
        lines.append(f"  → {r.name} has signal here, but this tool was WRONG about it")
        lines.append(f"    on {corpus} before: {miss.get('what_happened','')}")
        lines.append("    Measure it against the alternative before trusting it.")
    if not usable and not caution:
        lines.append("  → no relation on this list has usable signal here. That is a real")
        lines.append("    answer: the free check has nothing to work with, and any paid")
        lines.append("    layer built on top of it inherits that.")
    if on.startswith("known"):
        lines.append("  Measured on KNOWN-GOOD records. A relation can be far worse on model")
        lines.append("  output — measured once at 1.22% here and 35.7% there.")
    return "\n".join(lines)
