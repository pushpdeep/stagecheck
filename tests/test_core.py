"""Tests for the two fields that are the whole product."""
import json
import pytest
import stagecheck as sc


class R:
    def __init__(self, rid): self.record_id = rid


def test_could_not_run_is_not_a_pass():
    """The distinction a decorator cannot make, and the reason for the API shape."""
    L = sc.Ledger()
    with L.stage("v", bet="b", denominator="offered") as s:
        s.passed(R("a")); s.failed(R("b"), "why"); s.could_not_run(R("c"), "nothing to check")
    smry = L.summaries[0]
    assert smry.offered == 3
    assert smry.judged == 2
    assert smry.could_not_run == 1
    # 1 of 2, not 1 of 3. The denominator is what was JUDGED.
    assert smry.fail_rate == 0.5


def test_a_stage_that_judged_nothing_has_no_rate():
    """Not 0.0. Reporting zero would claim it found no problems."""
    L = sc.Ledger()
    with L.stage("v", bet="b", denominator="offered") as s:
        s.could_not_run(R("a"), "n/a"); s.could_not_run(R("b"), "n/a")
    assert L.summaries[0].fail_rate is None
    assert L.summaries[0].silent


def test_a_row_without_a_denominator_is_refused():
    with pytest.raises(ValueError, match="denominator"):
        sc.Row(stage="v", record_id="a", denominator="", evaluable=sc.PASS)


def test_a_fourth_evaluable_state_is_refused():
    with pytest.raises(ValueError, match="evaluable"):
        sc.Row(stage="v", record_id="a", denominator="d", evaluable="maybe")


def test_a_stage_must_declare_a_bet():
    L = sc.Ledger()
    with pytest.raises(ValueError, match="bet"):
        with L.stage("v", bet="", denominator="offered"):
            pass


def test_inert_is_distinguished_from_silent():
    """Judged plenty and changed nothing — the shape four rungs had."""
    L = sc.Ledger()
    with L.stage("v", bet="b", denominator="offered") as s:
        for i in range(5):
            s.passed(R(str(i)))
    smry = L.summaries[0]
    assert smry.inert and not smry.silent


def test_report_names_the_silent_stage():
    L = sc.Ledger()
    with L.stage("dead", bet="rung 1 gives it something to correct",
                 denominator="rejections") as s:
        s.could_not_run(R("a"), "nothing rejected")
    out = L.report()
    assert "judged NOTHING" in out
    assert "rung 1 gives it something to correct" in out


def test_costs_are_never_fused():
    L = sc.Ledger()
    with L.stage("v", bet="b", denominator="offered") as s:
        s.passed(R("a"), tokens=100)
        s.failed(R("b"), "x", reviews=1)
    out = L.report()
    assert "100 tokens" in out and "1 human reviews" in out
    assert "Never fused" in out


def test_ledger_round_trips(tmp_path):
    L = sc.Ledger()
    with L.stage("v", bet="b", denominator="offered") as s:
        s.passed(R("a")); s.could_not_run(R("b"), "why")
    p = tmp_path / "l.jsonl"
    assert L.write(p) == 2
    rows = [json.loads(x) for x in p.read_text().splitlines()]
    assert {r["evaluable"] for r in rows} == {"pass", "could_not_run"}
    assert all(r["denominator"] == "offered" for r in rows)


def test_ledgers_do_not_share_state():
    a, b = sc.Ledger(), sc.Ledger()
    with a.stage("x", bet="b", denominator="d") as s:
        s.passed(R("1"))
    assert len(a.rows) == 1 and len(b.rows) == 0
