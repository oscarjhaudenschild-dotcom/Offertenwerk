"""Document chunking pipeline."""

import re
from typing import List, Dict, Tuple
from config import CHUNK_SIZE, CHUNK_OVERLAP


AMOUNT_LINE = re.compile(r"CHF\s*[\d'\u2019]|not applicable|n/a", re.IGNORECASE)

# Matches the greeting line every offer in this archive opens with, right
# after the name/address/date block ("Sehr geehrte A. Beispiel", "Dear B.
# Beispiel"). Used as the cut point for strip_letterhead below - the greeting
# is the one line that reliably marks where the letterhead ends and the
# actual offer begins, across both languages in the corpus.
LETTERHEAD_SALUTATION = re.compile(
    r"^\s*(Dear|Sehr geehrte[rs]?|Liebe[rs]?)\b.*$", re.MULTILINE
)


def strip_letterhead(text: str) -> str:
    """
    Remove the name/address/date block and greeting from the start of a
    document, for the letterhead-comparison run only.

    Every offer opens with the client's own firm name in a name/address block.
    The gold-set questions name that firm too, to keep them unambiguous - so
    the opening lines match a query's firm name almost by definition,
    regardless of what the query actually asks about. That pulled the address
    chunk to the top of the ranking for unrelated questions, which is the
    artifact this function removes. Restricted to a match in the first 500
    characters, so a "Sehr geehrte" appearing later in a document (this
    corpus has none, but a future one might) is left alone.
    """
    match = LETTERHEAD_SALUTATION.search(text[:500])
    if not match:
        return text
    return text[match.end():].lstrip("\n")


def classify_region(text: str) -> str:
    """
    Say whether a chunk is a cost table, running prose, or a mix.

    Measured as the share of non-empty lines carrying an amount. The corpus
    splits cleanly at the extremes - letterheads and service descriptions sit at
    0 to 25 percent, fee tables at 60 percent and above - but a 400-word chunk
    regularly straddles the boundary. A two-way split would file those mixed
    chunks on one side and quietly bias the whole column, so they get their own
    class instead.
    """
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return "fliesstext"
    share = sum(1 for l in lines if AMOUNT_LINE.search(l)) / len(lines)
    if share >= 0.60:
        return "tabelle"
    if share >= 0.25:
        return "gemischt"
    return "fliesstext"


class DocumentChunker:
    """Splits documents into overlapping chunks."""

    def __init__(self, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP,
                 strip_letterhead: bool = False):
        self.chunk_size = chunk_size
        self.overlap = overlap
        # Comparison-run switch only - the practitioner tool never sets this,
        # so app.html keeps indexing the letterhead exactly as before.
        self.strip_letterhead = strip_letterhead

    def _count_words(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())

    def _split_by_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences, hard-splitting any that exceed chunk_size.

        Legal PDFs contain tables and clause lists with no sentence punctuation;
        without this an entire page becomes one unsplittable chunk.
        """
        sentences = re.split(r'(?<=[.!?])\s+', text)
        out = []
        for s in (s.strip() for s in sentences):
            if not s:
                continue
            words = s.split()
            if len(words) <= self.chunk_size:
                out.append(s)
            else:
                for i in range(0, len(words), self.chunk_size):
                    out.append(" ".join(words[i:i + self.chunk_size]))
        return out

    def chunk(self, text: str, doc_id: str, doc_type: str = "unknown") -> List[Dict]:
        """
        Split document into overlapping chunks.

        Returns list of dicts with:
        - chunk_id: unique identifier
        - text: chunk content
        - doc_id: source document
        - doc_type: document type (e.g., "offer", "law", "guideline")
        - position: chunk number within document
        """
        if self.strip_letterhead:
            text = strip_letterhead(text)
        sentences = self._split_by_sentences(text)
        chunks = []
        current_chunk = []
        current_word_count = 0
        position = 0

        for sentence in sentences:
            sentence_words = self._count_words(sentence)

            # Start new chunk if current would exceed size
            if current_word_count + sentence_words > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "chunk_id": f"{doc_id}_chunk_{position}",
                    "text": chunk_text,
                    "doc_id": doc_id,
                    "doc_type": doc_type,
                    "position": position,
                    "word_count": self._count_words(chunk_text),
                    "region": classify_region(chunk_text),
                })
                position += 1

                # Keep overlap sentences for next chunk
                overlap_words = 0
                overlap_sentences = []
                for sent in reversed(current_chunk):
                    sent_words = self._count_words(sent)
                    if overlap_words + sent_words <= self.overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_words += sent_words
                    else:
                        break

                current_chunk = overlap_sentences
                current_word_count = overlap_words

            current_chunk.append(sentence)
            current_word_count += sentence_words

        # Save final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                "chunk_id": f"{doc_id}_chunk_{position}",
                "text": chunk_text,
                "doc_id": doc_id,
                "doc_type": doc_type,
                "position": position,
                "word_count": self._count_words(chunk_text),
                "region": classify_region(chunk_text),
            })

        return chunks

    def chunk_batch(self, documents: List[Tuple[str, str, str]]) -> List[Dict]:
        """
        Chunk multiple documents.

        Args:
            documents: list of (text, doc_id, doc_type) tuples

        Returns:
            flat list of all chunks
        """
        all_chunks = []
        for text, doc_id, doc_type in documents:
            chunks = self.chunk(text, doc_id, doc_type)
            all_chunks.extend(chunks)
        return all_chunks
