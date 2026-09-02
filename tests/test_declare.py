"""Tests for the three tenses, and for the line watch() must not cross."""
import pytest
import stagecheck as sc


class R:
    def __init__(self, rid, bad=False): self.record_id, self.bad = rid, bad


def _pre(threshold=0.05):
    return sc.Precondition(
        measures="share failing the free check",
        over="gold mentions",
        measure=lambda recs: (sum(1 for r in recs if r.bad), len(recs)),
        holds_if=lambda rate: rate > threshold,
    )


def test_preflight_measures_before_anything_is_built():
    v = sc.declare("v", bet="b", denominator="offered", precondition=_pre())
    m = v.preflight([R("a", True), R("b"), R("c"), R("d")])
    assert m.holds and m.n == 4 and m.value == 0.25
    assert m.over == "gold mentions"


def test_a_precondition_that_does_not_hold_says_so():
    v = sc.declare("v", bet="b", denominator="offered", precondition=_pre(0.5))
    assert not v.preflight([R("a", True), R("b"), R("c"), R("d")]).holds


def test_no_precondition_returns_none_rather_than_inventing_one():
    v = sc.declare("v", bet="b", denominator="offered")
    assert v.preflight([R("a")]) is None
    assert "no testable precondition" in v.report()


def test_watch_halts_on_a_broken_setup():
    v = sc.declare("v", bet="b", denominator="offered", invariants=[
        sc.Invariant("menu size", lambda menu, configured, **_: menu == configured,
                     "the menu is smaller than configured")])
    v.watch(menu=139, configured=139)          # fine
    with pytest.raises(sc.SetupBroken, match="menu size"):
        v.watch(menu=20, configured=139)


def test_a_halted_run_says_it_produced_no_number():
    v = sc.declare("v", bet="b", denominator="offered", invariants=[
        sc.Invariant("model", lambda resolved, requested, **_: resolved == requested,
                     "the resolved model is not the requested one")])
    with pytest.raises(sc.SetupBroken) as e:
        v.watch(resolved="a", requested="b")
    assert "no number" in str(e.value)
    assert "HALTED" in v.report()


def test_an_invariant_that_cannot_see_its_context_has_not_passed():
    """could_not_run is not pass — the rule applied to invariants too."""
    inv = sc.Invariant("menu", lambda menu, configured, **_: menu == configured, "x")
    assert inv.check(something_else=1) is False


def test_all_three_tenses_in_one_report():
    L = sc.Ledger()
    v = sc.declare("v", bet="the output has a decidable invalid state",
                   denominator="offered", precondition=_pre(), ledger=L)
    before = v.preflight([R("a", True), R("b"), R("c"), R("d")])
    with v.run() as s:
        s.failed(R("a"), "bad"); s.passed(R("b")); s.could_not_run(R("c"), "n/a")
    out = v.report(before)
    assert "before:" in out and "after:" in out
    assert "holds" in out


def test_the_divergence_line_names_the_useful_case():
    """A bet that held plus a stage that judged nothing is the signature of an
    input that is not what the precondition was measured on."""
    L = sc.Ledger()
    v = sc.declare("v", bet="b", denominator="offered", precondition=_pre(), ledger=L)
    before = v.preflight([R("a", True), R("b")])
    with v.run() as s:
        s.could_not_run(R("x"), "nothing to check")
    assert "judged NOTHING" in v.report(before)


def test_inert_stage_is_named_as_such():
    L = sc.Ledger()
    v = sc.declare("v", bet="b", denominator="offered", precondition=_pre(), ledger=L)
    before = v.preflight([R("a", True), R("b")])
    with v.run() as s:
        s.passed(R("x")); s.passed(R("y"))
    assert "changed nothing" in v.report(before)


# ── the dashboard ───────────────────────────────────────────────────────
def test_dashboard_names_each_divergence():
    from stagecheck import dashboard
    L = sc.Ledger()
    pre = sc.Precondition(measures="m", over="gold",
                          measure=lambda rs: (1, 4), holds_if=lambda r: r > 0.05)

    inert = sc.declare("inert", bet="b", denominator="d", precondition=pre, ledger=L)
    m = inert.preflight([R("a")])
    with inert.run() as s:
        s.passed(R("x"))

    silent = sc.declare("silent", bet="b", denominator="d", precondition=pre, ledger=L)
    m2 = silent.preflight([R("a")])
    with silent.run() as s:
        s.could_not_run(R("x"), "n/a")

    out = dashboard.render([inert, silent],
                           {"inert": m, "silent": m2})
    assert "changed nothing" in out
    assert "judged nothing" in out
    # every rate must name its set, in the cell
    assert "of 4 gold" in out


def test_dashboard_marks_a_halted_stage_as_no_result():
    from stagecheck import dashboard
    v = sc.declare("v", bet="b", denominator="d", invariants=[
        sc.Invariant("x", lambda a, **_: a == 1, "broke")])
    try:
        v.watch(a=2)
    except sc.SetupBroken:
        pass
    out = dashboard.render([v])
    assert "HALTED" in out and "Nothing here is a result" in out
