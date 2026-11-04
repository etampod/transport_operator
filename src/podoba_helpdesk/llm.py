"""Model interface.

The default model may only return a sentence that already appears in the graded
passage. Routing does not call the model, so a different backend cannot change
which tool runs.
"""

from __future__ import annotations

import os
from typing import Protocol

from podoba_helpdesk.textutil import content_tokens, overlap_count, split_sentences


class LLM(Protocol):
    name: str

    def answer(self, question: str, passage: str) -> str:
        """Return an answer grounded in `passage`."""


class ExtractiveLLM:
    """Copy the passage sentence that covers the question best."""

    name = "dummy-extractive-v1"

    def answer(self, question: str, passage: str) -> str:
        sentences = split_sentences(passage)
        if not sentences:
            return ""
        query_tokens = content_tokens(question)
        best = max(
            sentences,
            key=lambda sentence: (overlap_count(query_tokens, sentence), -len(sentence)),
        )
        if query_tokens and overlap_count(query_tokens, best) == 0:
            return sentences[0]
        return best


class TransformersLLM:
    """Optional local generator. Not installed by requirements.txt."""

    name = "google/flan-t5-small"

    def __init__(self) -> None:
        from transformers import pipeline

        self._pipe = pipeline("text2text-generation", model=self.name)

    def answer(self, question: str, passage: str) -> str:
        prompt = (
            "Answer the question using only the passage. "
            f"Passage: {passage} Question: {question}"
        )
        result = self._pipe(prompt, max_new_tokens=96, do_sample=False)
        text = result[0].get("generated_text", "") if result else ""
        return str(text).strip()


def build_llm() -> LLM:
    backend = os.environ.get("LLM_BACKEND", "extractive").strip().casefold()
    if backend == "transformers":
        return TransformersLLM()
    if backend not in {"extractive", "dummy", ""}:
        raise ValueError(f"Unknown LLM_BACKEND {backend!r}. Use extractive or transformers.")
    return ExtractiveLLM()
