"""Unit tests for the abstention detector (SP-0)."""

from phi3geom.dataset.abstention import detect_abstention, is_abstention_rule


def test_rule_detects_explicit_abstentions():
    assert is_abstention_rule("I don't know.") is True
    assert is_abstention_rule("The answer is not in the context.") is True
    assert is_abstention_rule("This question is unanswerable.") is True
    assert is_abstention_rule("There is no answer in the passage.") is True
    assert is_abstention_rule("Cannot be determined from the text.") is True


def test_rule_empty_is_abstention():
    assert is_abstention_rule("") is True
    assert is_abstention_rule("   \n ") is True


def test_rule_does_not_flag_real_answers():
    assert is_abstention_rule("Paris") is False
    assert is_abstention_rule("The capital of France is Paris.") is False


def test_detect_abstention_evidence_source():
    assert detect_abstention("I don't know") == (True, "rule")
    assert detect_abstention("Paris") == (False, "none")
    # backstop recovers a paraphrase the rules miss
    assert detect_abstention(
        "That isn't something the passage tells us.", backstop=lambda _t: True
    ) == (True, "classifier")
    # backstop says no -> not abstention
    assert detect_abstention("Paris", backstop=lambda _t: False) == (False, "none")
