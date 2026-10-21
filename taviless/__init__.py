"""Taviless: 100% free, zero-dependency, open-source drop-in replacement for Tavily Search API."""

from __future__ import annotations

from taviless.client import Client, TavilyClient, search
from taviless.errors import (
    ConfigurationError,
    ExtractionError,
    GatewayUnavailableError,
    SearchEngineError,
    TavilessError,
)
from taviless.types import SearchDepth, SearchResponse, SearchResult

__version__ = "0.1.0"

__all__ = [
    "Client",
    "ConfigurationError",
    "ExtractionError",
    "GatewayUnavailableError",
    "SearchDepth",
    "SearchEngineError",
    "SearchResponse",
    "SearchResult",
    "TavilessError",
    "TavilyClient",
    "__version__",
    "search",
]
