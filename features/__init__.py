"""Feature extraction — enrich paragraph blocks with computed features.

This stage runs AFTER normalization and BEFORE classification.
It recomputes text-based features from normalized text and merges
them with features already set during parsing.
"""

from docstructure.core.document import Document
from docstructure.core.nodes import BlockFeatures, ParagraphBlock


def extract_features(doc: Document) -> None:
    """Extract and attach BlockFeatures to every ParagraphBlock."""
    for block in doc.paragraphs:
        text = block.text
        word_count = len(text.split()) if text.strip() else 0
        sentence_count = max(0, text.count(".") + text.count("!") + text.count("?"))
        if sentence_count == 0 and word_count > 0:
            sentence_count = 1

        existing = block.features
        if existing:
            existing.word_count = word_count
            existing.sentence_count = sentence_count
        else:
            block.features = BlockFeatures(
                word_count=word_count,
                sentence_count=sentence_count,
            )
