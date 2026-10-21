"""Webpage crawling and content extraction tools."""

from __future__ import annotations

import gzip
import ipaddress
import logging
import socket
from typing import Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

from taviless.extractor.stdlib import extract_text_stdlib, reorder_reverse_chronological
from taviless.extractor.trafilatura_ext import HAS_TRAFILATURA, extract_with_trafilatura

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip",
}

MAX_RESPONSE_BYTES = 2_000_000


def _is_public_url(url: str) -> bool:
    """True only for http(s) URLs whose host resolves exclusively to public IPs (SSRF guard)."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        for info in socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                return False
        return True
    except Exception:
        return False


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_public_url(newurl):
            raise urllib.error.URLError(f"blocked redirect to non-public URL: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SafeRedirectHandler)


def fetch_url(url: str, timeout: float = 4.0) -> Tuple[str, str]:
    """Fetch raw HTML content from a URL safely using urllib.

    Args:
        url: The target URL to fetch.
        timeout: Network timeout in seconds.

    Returns:
        A tuple of (decoded_html_string, final_resolved_url).
    """
    if not _is_public_url(url):
        raise ValueError(f"refusing to fetch non-public URL: {url}")
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with _OPENER.open(req, timeout=timeout) as response:
        raw_bytes = response.read(MAX_RESPONSE_BYTES)
        final_url = response.geturl()

        # Handle gzip compression if present
        encoding = response.headers.get("Content-Encoding", "").lower()
        if "gzip" in encoding:
            try:
                raw_bytes = gzip.decompress(raw_bytes)
            except Exception:
                pass

        # Detect charset or fallback to utf-8
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            html_text = raw_bytes.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            html_text = raw_bytes.decode("utf-8", errors="replace")

        return html_text, final_url


def extract_content(
    html_content: str,
    max_chars: int = 5000,
    use_trafilatura: bool = True,
    reverse_chronological: bool = False,
) -> str:
    """Extract clean, ad-free text/markdown from HTML.

    Args:
        html_content: The raw HTML content string.
        max_chars: Character limit for extracted content.
        use_trafilatura: Whether to use trafilatura if installed.
        reverse_chronological: Whether to reorder paragraphs so newest calendar dates appear first.

    Returns:
        Structured clean text or markdown.
    """
    if use_trafilatura and HAS_TRAFILATURA:
        text = extract_with_trafilatura(html_content, max_chars=max_chars)
    else:
        text = extract_text_stdlib(html_content, max_chars=max_chars)

    if reverse_chronological and text:
        text = reorder_reverse_chronological(text)

    return text


def fetch_and_extract(
    url: str,
    timeout: float = 4.0,
    max_chars: int = 5000,
    use_trafilatura: bool = True,
    reverse_chronological: bool = False,
) -> Tuple[str, Optional[str]]:
    """Download a webpage and extract clean body content.

    Args:
        url: Target web address.
        timeout: Fetch timeout in seconds.
        max_chars: Character limit for extracted text.
        use_trafilatura: Whether to use trafilatura if available.
        reverse_chronological: Whether to sort sections with newest dates first.

    Returns:
        Tuple of (clean_extracted_text, raw_html_string).
        If fetching fails, returns empty string and None.
    """
    try:
        raw_html, _ = fetch_url(url, timeout=timeout)
        clean_text = extract_content(
            raw_html,
            max_chars=max_chars,
            use_trafilatura=use_trafilatura,
            reverse_chronological=reverse_chronological,
        )
        return clean_text, raw_html
    except Exception as exc:
        logger.debug("Failed to fetch and extract %s: %s", url, exc)
        return "", None


__all__ = [
    "HAS_TRAFILATURA",
    "extract_content",
    "extract_text_stdlib",
    "extract_with_trafilatura",
    "fetch_and_extract",
    "fetch_url",
    "reorder_reverse_chronological",
]
