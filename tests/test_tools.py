from pathlib import Path

from podoba_helpdesk.config import CORPUS_DIR
from podoba_helpdesk.corpus import load_corpus
from podoba_helpdesk.tools import assess_delay_compensation, calculate_fare, delay_schedule, fare_schedule

ROOT = Path(__file__).resolve().parents[1]


def test_adult_and_child_fares_are_computed() -> None:
    adult = calculate_fare("How much is an adult single ticket for 3 zones?")
    assert "4.80 EUR" in adult["answer"]
    assert adult["citations"] == ["POL-FARE — Adult single tickets"]

    child = calculate_fare("How much is a child single ticket for 4 zones?")
    assert "3.00 EUR" in child["answer"]
    assert "6.00 EUR" in child["answer"]
    assert "POL-FARE — Child fares" in child["citations"]

    two_zones = calculate_fare("How much is an adult single ticket for 2 zones?")
    assert "3.60 EUR" in two_zones["answer"]


def test_delay_bands_and_strike_exclusion() -> None:
    half = assess_delay_compensation(
        "The train was 45 minutes late and the ticket cost 8.00 EUR."
    )
    assert "4.00 EUR" in half["answer"]
    assert "50 percent" in half["answer"]

    none = assess_delay_compensation(
        "The train was 12 minutes late and the ticket cost 6.40 EUR."
    )
    assert "does not qualify" in none["answer"]
    assert "0.00 EUR" in none["answer"]

    full = assess_delay_compensation(
        "The train was 75 minutes late and the ticket cost 9.60 EUR."
    )
    assert "9.60 EUR" in full["answer"]
    assert "100 percent" in full["answer"]

    strike = assess_delay_compensation(
        "The train was 70 minutes late because of a strike announced 48 hours in advance. "
        "The ticket cost 10.00 EUR."
    )
    assert "0.00 EUR" in strike["answer"]
    assert "Announced strikes" in strike["citations"][0]


def test_short_notice_strike_stays_on_the_minute_band() -> None:
    short = assess_delay_compensation(
        "The train was 70 minutes late because of a strike announced 2 hours in advance. "
        "The ticket cost 10.00 EUR."
    )
    assert "10.00 EUR" in short["answer"]
    assert "100 percent" in short["answer"]
    assert "Announced strikes" not in " ".join(short["citations"])

    unannounced = assess_delay_compensation(
        "The train was 70 minutes late because of a strike. The ticket cost 10.00 EUR."
    )
    assert "10.00 EUR" in unannounced["answer"]
    assert "100 percent" in unannounced["answer"]


def test_rules_are_quoted_from_the_policy() -> None:
    chunks = {(chunk.doc_id, chunk.section): chunk.text for chunk in load_corpus().chunks}
    fare = fare_schedule()
    delay = delay_schedule()
    assert fare.adult_rule == chunks[("POL-FARE", "Adult single tickets")]
    assert fare.child_rule in chunks[("POL-FARE", "Child fares")]
    assert fare.adult_rule in calculate_fare("How much is an adult single ticket for 3 zones?")["answer"]
    assert delay.partial_rule in chunks[("POL-DELAY", "Compensation thresholds")]
    assert delay.strike_rule in chunks[("POL-DELAY", "Announced strikes")]
    paid = assess_delay_compensation(
        "The train was 45 minutes late and the ticket cost 8.00 EUR."
    )
    assert delay.partial_rule in paid["answer"]


def test_for_zone_phrasing_and_a_child_synonym() -> None:
    adult = calculate_fare("How much is an adult single for zone 3?")
    assert "4.80 EUR" in adult["answer"]
    child = calculate_fare("How much is a kids single for 4 zones?")
    assert "3.00 EUR" in child["answer"]
    assert "6.00 EUR" in child["answer"]


def test_computed_amounts_are_not_stored_in_the_corpus() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in CORPUS_DIR.glob("*.md"))
    for amount in ("3.60 EUR", "4.80 EUR", "3.00 EUR", "4.00 EUR", "6.00 EUR"):
        assert amount not in text
    assert ROOT.joinpath("corpus", "policies").is_dir()
