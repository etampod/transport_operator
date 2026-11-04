"""Shared constants for the Podoba Transit helpdesk."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "corpus" / "policies"

DISCLAIMER = (
    "This assistant summarizes Podoba Transit customer rules for information only. "
    "It does not create a refund, a compensation decision, or a penalty notice. "
    "Station staff confirm claims and exceptions."
)

CHITCHAT_ANSWER = (
    "I am the Podoba Transit customer service assistant. I answer questions about "
    "fares, tickets, refunds, delay compensation, accessibility, complaints, lost "
    "property, and onboard safety, and I cite the rule I use."
)

OUT_OF_SCOPE_ANSWER = (
    "That question is outside Podoba Transit customer service. I can help with "
    "fares, tickets, refunds, delay compensation, accessibility, complaints, lost "
    "property, and onboard safety."
)

NOT_FOUND_ANSWER = "I could not find a Podoba Transit rule that answers this question."

EXAMPLE_QUESTIONS = [
    "How long is a single ticket valid?",
    "What does an adult single ticket cost in zone 1?",
    "How much is an adult single ticket for 3 zones?",
    "The train was 45 minutes late and the ticket cost 8.00 EUR. How much compensation do I get?",
    "How long is a single ticket valid, and how long is lost property kept?",
    "Hello, who are you?",
]
