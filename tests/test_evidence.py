"""The vendored track record, and the staleness that must be a failure not a note."""
import json
import pathlib
from datetime import date, timedelta

import pytest

from stagecheck import evidence as ev

FILE = pathlib.Path(ev.FILE)


def _write(payload, tmp_path, monkeypatch):
    p = tmp_path / "evidence.json"
    p.write_text(json.dumps(payload))
    monkeypatch.setattr(ev, "FILE", p)
    monkeypatch.setattr(ev, "_DATA", ev._load())
    return p


def _payload(days_old=0, preds=None):
    when = (date.today() - timedelta(days=days_old)).isoformat()
    return {"exported": when,
            "study": {"sha": "abc1234", "dirty": False},
            "corpora": ["CADEC v2"],
            "aliases": {"lexical": "accept_lane_fires"},
            "predictions": preds if preds is not None else [
                {"check": "accept_lane_fires", "said": "BUILD",
                 "scope": {"corpus": "CADEC", "split": "dev", "on": "gold", "n": 276},
                 "when": when, "outcome": "right", "what_happened": "", "note": ""}]}


def test_a_missing_record_says_so_rather_than_staying_quiet(tmp_path, monkeypatch):
    """Silence would read as 'no misses'. It is 'no evidence'."""
    monkeypatch.setattr(ev, "FILE", tmp_path / "absent.json")
    monkeypatch.setattr(ev, "_DATA", ev._load())
    assert not ev.available()
    assert "no evidence vendored" in ev.provenance()
    assert "never been tested" in ev.caveat("lexical")


def test_the_alias_maps_registry_names_to_study_names(tmp_path, monkeypatch):
    """The study named its checks before the registry existed. Mapped rather
    than renamed — an entry is a dated claim and editing its subject changes
    what was predicted."""
    _write(_payload(), tmp_path, monkeypatch)
    assert "1 on record" in ev.caveat("lexical")


def test_a_stale_record_is_detectable(tmp_path, monkeypatch):
    _write(_payload(days_old=ev.STALE_DAYS + 1), tmp_path, monkeypatch)
    assert ev.is_stale()
    assert "STALE" in ev.provenance()


def test_a_fresh_record_is_not_stale(tmp_path, monkeypatch):
    _write(_payload(days_old=10), tmp_path, monkeypatch)
    assert not ev.is_stale()


def test_missed_on_is_scoped_to_the_corpus(tmp_path, monkeypatch):
    """A check wrong about GeoWebNews must not be held back on CADEC, and must
    be held back on GeoWebNews."""
    preds = [
        {"check": "accept_lane_fires", "said": "BUILD",
         "scope": {"corpus": "CADEC", "split": "dev", "on": "gold", "n": 276},
         "when": "2026-09-01", "outcome": "right", "what_happened": "", "note": ""},
        {"check": "accept_lane_fires", "said": "BUILD",
         "scope": {"corpus": "GeoWebNews", "split": "dev", "on": "gold", "n": 442},
         "when": "2026-09-01", "outcome": "partly",
         "what_happened": "fired, and scored worse than BAND", "note": ""}]
    _write(_payload(preds=preds), tmp_path, monkeypatch)
    assert ev.missed_on("lexical", "GeoWebNews") is not None
    assert ev.missed_on("lexical", "CADEC") is None


def test_a_dirty_export_is_named_in_the_provenance(tmp_path, monkeypatch):
    """A SHA from a dirty tree does not describe what produced the numbers."""
    p = _payload()
    p["study"]["dirty"] = True
    _write(p, tmp_path, monkeypatch)
    assert "dirty tree" in ev.provenance()


@pytest.mark.skipif(not FILE.is_file(), reason="no evidence vendored in this checkout")
def test_the_vendored_record_is_not_stale():
    """A staleness FAILURE, not a warning.

    This tool decays because its knowledge ages rather than because a
    dependency breaks. A record older than roughly a model generation makes
    every verdict a hypothesis, and a test that merely warns about that is a
    test nobody acts on.

    Re-export from the study:
        PYTHONPATH=. python3 scripts/export_evidence.py
    """
    assert not ev.is_stale(), (
        f"the vendored evidence is {ev.age_days()} days old. "
        "Re-export it from the study, or read every verdict as untested.")
