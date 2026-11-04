"""BM25 search over policy sections.

The corpus is small and the useful answers are exact phrases ("90 minutes",
"5 working days"). BM25 over those sections is enough, and a dense retriever
can replace `BM25Retriever.search` without changing the graph.
"""

from __future__ import annotations

from rank_bm25 import BM25Okapi

from podoba_helpdesk.corpus import Chunk, Corpus
from podoba_helpdesk.textutil import content_tokens


class BM25Retriever:
    def __init__(self, corpus: Corpus) -> None:
        self.chunks: list[Chunk] = list(corpus.chunks)
        tokenized = [chunk.tokens or ["empty"] for chunk in self.chunks]
        self._bm25 = BM25Okapi(tokenized)

    def search(self, query: str, k: int = 6) -> list[dict]:
        tokens = content_tokens(query)
        if not tokens or not self.chunks:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda index: float(scores[index]), reverse=True)
        hits: list[dict] = []
        for index in ranked[:k]:
            chunk = self.chunks[index]
            hits.append(
                {
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "section": chunk.section,
                    "text": chunk.text,
                    "citation": chunk.citation,
                    "bm25": round(float(scores[index]), 6),
                }
            )
        return hits
