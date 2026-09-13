"""Tests for the three provenance gaps — the stamp, the refusal, and confirm().

Each test is written from the failure that put the gap in
`docs/TODO-provenance.md`, and made to exercise the refusal rather than only
the happy path. A guard that has only ever been shown to allow things has not
been shown to guard anything.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import stagecheck
from stagecheck import Invariant, Ledger, Precondition, declare


# ── the stamp ────────────────────────────────────────────────────────
def test_a_ledger_without_a_stamp_still_works():
    """The stamp is additive. Every existing caller passes nothing and is
    unaffected — a provenance feature that breaks the runs it was built to
    describe has not helped anyone."""
    led = Ledger()
    assert led.run == {}
    with led.stage("s", bet="b", denominator="records") as s:
        s.passed("r1")
    assert len(led.rows) == 1


def test_the_stamp_is_carried_verbatim_and_never_interpreted():
    """stagecheck does not know what a model is. `{"kettle": "boiled"}` is
    carried exactly as `{"model": "gpt-oss:20b"}` would be."""
    led = Ledger(run={"model": "gpt-oss:20b", "kettle": "boiled"})
    assert led.run["model"] == "gpt-oss:20b"
    assert led.run["kettle"] == "boiled"


def test_stamp_chains_and_adds():
    led = Ledger(run={"commit": "abc123"}).stamp(host="ladder-gpu", gpu="RTX 6000 Ada")
    assert led.run == {"commit": "abc123", "host": "ladder-gpu", "gpu": "RTX 6000 Ada"}


def test_a_stamp_cannot_be_rewritten_mid_run():
    """A stamp that changes describes neither half of the run."""
    led = Ledger(run={"model": "gpt-oss:20b"})
    with pytest.raises(ValueError, match="already"):
        led.stamp(model="llama3.1:8b")


def test_setting_a_key_to_the_same_value_is_not_a_change():
    led = Ledger(run={"model": "gpt-oss:20b"})
    led.stamp(model="gpt-oss:20b")
    assert led.run["model"] == "gpt-oss:20b"


# ── the stamp reaches the file ───────────────────────────────────────
def test_every_written_row_carries_the_stamp(tmp_path):
    """On the ROW and not in a header: rows get filtered, concatenated and
    pasted between files, and a header survives none of that."""
    led = Ledger(run={"model": "m", "host": "h"})
    with led.stage("s", bet="b", denominator="records") as s:
        s.passed("r1")
        s.failed("r2", outcome="wrong")
    p = tmp_path / "led.jsonl"
    led.write(p)
    rows = [json.loads(l) for l in p.read_text().splitlines()]
    assert len(rows) == 2
    for r in rows:
        assert r["run"] == {"model": "m", "host": "h"}


def test_an_unstamped_ledger_writes_rows_without_a_run_key(tmp_path):
    led = Ledger()
    with led.stage("s", bet="b", denominator="records") as s:
        s.passed("r1")
    p = tmp_path / "led.jsonl"
    led.write(p)
    assert "run" not in json.loads(p.read_text().splitlines()[0])


# ── the refusal, which is the point ──────────────────────────────────
def _one(run, rid):
    led = Ledger(run=run)
    with led.stage("s", bet="b", denominator="records") as s:
        s.passed(rid)
    return led


def test_two_runs_with_the_same_stamp_merge():
    a = _one({"model": "m", "host": "h"}, "r1")
    b = _one({"model": "m", "host": "h"}, "r2")
    assert len(a.merge(b).rows) == 2


def test_merging_across_different_hardware_is_refused():
    """The measurement behind gap 2: identical manifest, corpus and seed gave
    23 records on a CPU-split model and 22 on a GPU-resident one. Two machines
    are two experiments."""
    a = _one({"model": "m", "host": "laptop"}, "r1")
    b = _one({"model": "m", "host": "ladder-gpu"}, "r2")
    with pytest.raises(ValueError) as e:
        a.merge(b)
    assert "host" in str(e.value)
    assert "laptop" in str(e.value) and "ladder-gpu" in str(e.value)


def test_the_refusal_names_every_key_that_differs():
    a = _one({"model": "m1", "host": "h1", "commit": "c"}, "r1")
    b = _one({"model": "m2", "host": "h2", "commit": "c"}, "r2")
    with pytest.raises(ValueError) as e:
        a.merge(b)
    msg = str(e.value)
    assert "model" in msg and "host" in msg
    assert "commit" not in msg          # it agrees, so it is not the problem


def test_a_key_present_on_one_side_only_is_a_difference():
    """Absence is not agreement. A ledger that did not record its GPU has not
    said it ran on the same one."""
    a = _one({"model": "m", "gpu": "RTX 6000"}, "r1")
    b = _one({"model": "m"}, "r2")
    with pytest.raises(ValueError, match="gpu"):
        a.merge(b)


def test_merging_an_unstamped_ledger_is_refused():
    """No stamp is not a wildcard. It is the case where nobody can tell, which
    is the stronger reason to refuse."""
    a = _one({"model": "m"}, "r1")
    b = _one({}, "r2")
    with pytest.raises(ValueError, match="no run stamp"):
        a.merge(b)
    with pytest.raises(ValueError, match="no run stamp"):
        b.merge(a)


def test_the_merged_ledger_keeps_the_stamp():
    a = _one({"model": "m", "host": "h"}, "r1")
    b = _one({"model": "m", "host": "h"}, "r2")
    assert a.merge(b).run == {"model": "m", "host": "h"}


# ── confirm(): the configuration, before the spend ───────────────────
def _stage():
    return declare(
        "extract",
        bet="the output has a decidable invalid state",
        denominator="records_offered",
        invariants=[
            Invariant("menu size", lambda menu, configured, **_: menu == configured,
                      "the menu is smaller than the manifest asked for"),
            Invariant("entity", lambda prompt, entity, **_: entity in prompt,
                      "the prompt does not name this corpus's entity"),
        ],
    )


def test_confirm_reports_every_invariant_rather_than_raising_on_the_first():
    """Several can be wrong at once, and seeing one of five is how a
    misconfiguration gets fixed five times."""
    got = _stage().confirm(menu=20, configured=139,
                           prompt="find every adverse reaction", entity="organism")
    assert len(got) == 2
    assert [holds for _, holds, _ in got] == [False, False]


def test_confirm_passes_on_a_correct_configuration():
    st = _stage()
    got = st.confirm(menu=139, configured=139,
                     prompt="find every organism the paper mentions",
                     entity="organism")
    assert [holds for _, holds, _ in got] == [True, True]
    assert st.confirmed(menu=139, configured=139,
                        prompt="every organism mentioned", entity="organism")


def test_the_wrong_prompt_is_what_this_was_written_from():
    """Twelve cells of a study ran with another corpus's task description.
    Every PRECONDITION held — there really were mentions to find — and the
    instruction was wrong. A precondition asks whether the stage has work; this
    asks whether the stage is the one declared."""
    st = _stage()
    assert not st.confirmed(menu=139, configured=139,
                            prompt="find every adverse reaction the writer describes",
                            entity="organism")


def test_an_invariant_that_cannot_see_what_it_needs_does_not_pass():
    """Same rule as `watch`: it could not run, and counting that as a pass is
    the two-state accounting refused everywhere else in this tool."""
    got = _stage().confirm(menu=139, configured=139)   # no prompt, no entity
    assert ("entity", False, "the prompt does not name this corpus's entity") in got


def test_a_stage_with_no_invariants_confirms_vacuously_and_says_so():
    st = declare("s", bet="b", denominator="records")
    assert st.confirm() == []
    assert st.confirmed() is True       # nothing declared, nothing broken


def test_confirm_does_not_replace_watch():
    """They are different tenses of the same statement, and both exist. The
    config can be right at the start and broken by the third call."""
    st = _stage()
    assert st.confirmed(menu=139, configured=139,
                        prompt="every organism", entity="organism")
    with pytest.raises(stagecheck.SetupBroken):
        with st.run(menu=20, configured=139,
                    prompt="every organism", entity="organism"):
            pass
