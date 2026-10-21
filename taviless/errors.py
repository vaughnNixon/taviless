"""Exception classes for the Taviless library."""

from __future__ import annotations


class TavilessError(Exception):
    """Base exception for all Taviless errors."""
    pass


class SearchEngineError(TavilessError):
    """Raised when an underlying search engine or gateway encounters an unrecoverable failure."""
    pass


class GatewayUnavailableError(SearchEngineError):
    """Raised when a specific SearXNG or search gateway is unreachable or unresponsive."""
    pass


class ExtractionError(TavilessError):
    """Raised when crawling or extracting content from a webpage fails."""
    pass


class ConfigurationError(TavilessError):
    """Raised when invalid parameters or configurations are passed."""
    pass
