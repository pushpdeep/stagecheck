"""The relation registry, and the four states that two cannot describe."""
import pytest
from stagecheck import relations as R


class Vocab:
    def exists(self, c): return c != "MISSING"
    def terms(self, c): return {"271782001": ["Drowsy"]}.get(c, [str(c)])
    def code_type(self, c): return "percent" if "Rate" in str(c) else "money"


class Bare:
    """Only the required method. Everything else must report n/a, once."""
    def exists(self, c): return True


class Rec:
    def __init__(self, text, code, before="", after=""):
        self.text, self.code, self._b, self._a = text, code, before, after


CTX = lambda r: (r._b, r._a)


def test_a_relation_needing_a_missing_method_is_not_applicable():
    """n/a ONCE, not SILENT on every record. Those are different states and
    reporting them the same way hides which one you are in."""
    res = {r.name: r for r in R.measure([Rec("x", "c")], Bare())}
    assert res["lexical"].applicable is False
    assert res["lexical"].verdict() == "n/a"
    assert res["exists"].applicable is True


def test_lexical_endorses_and_never_contradicts():
    """A person writing 'bit drowsy' for a concept named 'Drowsy' is not proof
    of wrongness."""
    recs = [Rec("drowsy", "271782001"), Rec("bit drowsy", "271782001")]
    res = {r.name: r for r in R.measure(recs, Vocab())}
    assert res["lexical"].contradict == 0
    assert res["lexical"].agree == 1 and res["lexical"].silent == 1


def test_exists_contradicts_a_missing_code():
    res = {r.name: r for r in R.measure([Rec("x", "MISSING")], Vocab())}
    assert res["exists"].contradict == 1


def test_type_reads_the_context_either_side():
    recs = [Rec("47.6", "EffectiveIncomeTaxRate", " was ", " % and"),
            Rec("19.4", "DebtFaceAmount", "$ ", " million")]
    res = {r.name: r for r in R.measure(recs, Vocab(), context_of=CTX)}
    assert res["type"].agree == 2 and res["type"].contradict == 0


def test_type_contradicts_a_shape_that_disagrees():
    recs = [Rec("47.6", "DebtFaceAmount", " was ", " % and")]
    res = {r.name: r for r in R.measure(recs, Vocab(), context_of=CTX)}
    assert res["type"].contradict == 1


def test_a_currency_symbol_outranks_a_quantity_word_after_it():
    """'$ 6.1 billion in share repurchases' is money. Three of eight measured
    disagreements were this rule."""
    assert R.value_shape("6.1", "authorized $ ", " billion in share") == "money"


def test_per_share_is_a_unit_not_a_count():
    assert R.value_shape("90.07", "price of $ ", " per share , excl") == "money"


def test_value_shape_abstains_rather_than_guessing():
    assert R.value_shape("42", "the number ", " appears here") is None


def test_a_false_contradiction_on_known_good_records_makes_it_BROKEN():
    """Every contradiction of a record you know is right is false by
    construction. That is the cheapest validation there is."""
    recs = [Rec("47.6", "DebtFaceAmount", " was ", " % and")] * 10
    res = {r.name: r for r in
           R.measure(recs, Vocab(), context_of=CTX, known_good=lambda _: True)}
    assert res["type"].false_rate == 1.0
    assert res["type"].verdict() == "BROKEN"


def test_agreeing_with_everything_is_vacuous_not_endorsing():
    """The ACCEPT-lane-on-a-gazetteer failure: vouching hardest where it knows
    least."""
    class Always:
        def exists(self, c): return True
    res = {r.name: r for r in R.measure([Rec("a", "1"), Rec("b", "2")], Always())}
    assert res["exists"].verdict() == "vacuous"


def test_report_leads_with_what_to_build():
    recs = [Rec("drowsy", "271782001"), Rec("x", "MISSING")]
    out = R.report(R.measure(recs, Vocab()))
    assert "build on" in out
    assert out.index("build on") > out.index("relations available")


def test_a_registered_relation_is_measured():
    """A registry nobody can extend is a list."""
    R.register(R.Relation("shouty", "is the value shouty?",
                          lambda v, b, a, c, voc: R.AGREE if v.isupper() else R.SILENT))
    try:
        res = {r.name: r for r in R.measure([Rec("LOUD", "1"), Rec("quiet", "1")], Vocab())}
        assert res["shouty"].agree == 1
    finally:
        R.REGISTRY[:] = [r for r in R.REGISTRY if r.name != "shouty"]


def test_registering_a_duplicate_name_is_refused():
    with pytest.raises(ValueError, match="already registered"):
        R.register(R.Relation("lexical", "x", lambda *a: R.SILENT))
