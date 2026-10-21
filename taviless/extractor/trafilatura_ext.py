"""Optional trafilatura-powered high-density article extraction with fallback."""

from __future__ import annotations

import logging
from typing import Optional

from taviless.extractor.stdlib import extract_text_stdlib

logger = logging.getLogger(__name__)

try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    trafilatura = None  # type: ignore
    HAS_TRAFILATURA = False


def extract_with_trafilatura(html_content: str, max_chars: int = 5000) -> str:
    """Extract token-dense markdown content using trafilatura if available, falling back to stdlib.

    Args:
        html_content: Raw HTML string.
        max_chars: Maximum characters to retain.

    Returns:
        Extracted main body text/markdown.
    """
    if not html_content or not html_content.strip():
        return ""

    if HAS_TRAFILATURA and trafilatura is not None:
        try:
            extracted: Optional[str] = trafilatura.extract(
                html_content,
                include_links=False,
                include_images=False,
                include_tables=True,
                output_format="txt",
                favor_recall=True,
            )
            if extracted and extracted.strip():
                text = extracted.strip()
                if max_chars and len(text) > max_chars:
                    return text[:max_chars].rstrip() + "..."
                return text
        except Exception as e:
            logger.debug("trafilatura extraction failed, falling back to stdlib: %s", e)

    # Fallback to stdlib
    return extract_text_stdlib(html_content, max_chars=max_chars)
