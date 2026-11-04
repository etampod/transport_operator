"""Load Markdown policies into section chunks.

A new policy is a new file. The loader reads YAML-style front matter and splits
the body on level-2 headings, so each chunk is one rule a passenger can cite.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from podoba_helpdesk.config import CORPUS_DIR
from podoba_helpdesk.textutil import content_tokens, normalize_ws


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    title: str
    section: str
    text: str
    tokens: list[str]

    @property
    def citation(self) -> str:
        return f"{self.doc_id} — {self.section}"


@dataclass(frozen=True)
class Corpus:
    chunks: list[Chunk]

    @property
    def document_ids(self) -> list[str]:
        seen: list[str] = []
        for chunk in self.chunks:
            if chunk.doc_id not in seen:
                seen.append(chunk.doc_id)
        return seen


def _split_front_matter(raw: str) -> tuple[dict[str, str], str]:
    text = raw.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    meta: dict[str, str] = {}
    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    if end is None:
        return {}, text
    body = "\n".join(lines[end + 1 :])
    return meta, body


def load_policy(path: Path) -> list[Chunk]:
    meta, body = _split_front_matter(path.read_text(encoding="utf-8"))
    doc_id = meta.get("doc_id") or path.stem
    title = meta.get("title") or doc_id
    chunks: list[Chunk] = []
    section = ""
    buffer: list[str] = []

    def flush() -> None:
        text = normalize_ws(" ".join(buffer))
        if section and text:
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    title=title,
                    section=section,
                    text=text,
                    tokens=content_tokens(text),
                )
            )

    for line in body.splitlines():
        if line.startswith("## "):
            flush()
            section = line[3:].strip()
            buffer = []
        else:
            buffer.append(line)
    flush()
    return chunks


def load_corpus(directory: Path | None = None) -> Corpus:
    folder = directory or CORPUS_DIR
    paths = sorted(folder.glob("*.md"))
    chunks: list[Chunk] = []
    for path in paths:
        chunks.extend(load_policy(path))
    if not chunks:
        raise FileNotFoundError(f"No policy markdown found in {folder}")
    return Corpus(chunks=chunks)
