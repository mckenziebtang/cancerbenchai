from __future__ import annotations

import re


SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def chunk_abstract(title: str, abstract: str, max_chars: int = 1200) -> list[str]:
    """Create readable, sentence-aligned chunks with the title as context."""
    sentences = [sentence.strip() for sentence in SENTENCE_BOUNDARY.split(abstract) if sentence.strip()]
    if not sentences:
        return [f"{title}. {abstract}".strip()]

    chunks: list[str] = []
    current = title.strip()
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars or current == title.strip():
            current = candidate
            continue
        chunks.append(current)
        # Repeat the title to keep every retrieved passage independently useful.
        current = f"{title.strip()} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks

