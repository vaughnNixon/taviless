"""Adapters for integrating Taviless into LangChain, CrewAI, and OpenAI tool calling."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from taviless.client import TavilyClient

# ---------------------------------------------------------------------------
# OpenAI Tool Calling Adapter
# ---------------------------------------------------------------------------

OPENAI_TOOL_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "tavily_search",
        "description": (
            "Search the live web for up-to-date information, news, documentation, "
            "and facts. Returns title, url, snippet, and content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string.",
                },
                "search_depth": {
                    "type": "string",
                    "enum": ["basic", "advanced"],
                    "description": (
                        "'basic' returns fast search engine snippets (~300ms). "
                        "'advanced' crawls and extracts token-dense webpage content."
                    ),
                    "default": "basic",
                },
                "max_results": {
                    "type": "integer",
                    "description": "The number of search results to return.",
                    "default": 5,
                },
                "topic": {
                    "type": "string",
                    "enum": ["general", "news"],
                    "description": "Use 'news' for recent events (implies a recency window).",
                    "default": "general",
                },
                "time_range": {
                    "type": "string",
                    "enum": ["day", "week", "month", "year"],
                    "description": "Filter results by freshness (e.g. 'day', 'week', 'month', 'year').",
                },
            },
            "required": ["query"],
        },
    },
}


def get_openai_tool(tool_name: str = "tavily_search") -> Dict[str, Any]:
    """Return a native OpenAI function/tool calling schema definition."""
    schema = dict(OPENAI_TOOL_SCHEMA)
    schema["function"] = dict(OPENAI_TOOL_SCHEMA["function"])
    schema["function"]["name"] = tool_name
    return schema


def execute_openai_tool_call(
    arguments_json: str | Dict[str, Any],
    client: Optional[TavilyClient] = None,
) -> str:
    """Execute an OpenAI tool call directly and return the JSON string response.

    Args:
        arguments_json: Raw arguments JSON string from OpenAI model, or parsed dict.
        client: Optional TavilyClient instance.

    Returns:
        JSON string response matching Tavily's schema.
    """
    if isinstance(arguments_json, str):
        args = json.loads(arguments_json)
    else:
        args = arguments_json

    search_client = client or TavilyClient()
    response = search_client.search(
        query=args.get("query", ""),
        search_depth=args.get("search_depth", "basic"),
        max_results=args.get("max_results", 5),
        time_range=args.get("time_range"),
        topic=args.get("topic", "general"),
    )
    return json.dumps(response, ensure_ascii=False)


# ---------------------------------------------------------------------------
# LangChain Adapter (Drop-in for TavilySearchResults)
# ---------------------------------------------------------------------------


def get_langchain_tool(
    max_results: int = 5,
    search_depth: str = "basic",
    client: Optional[TavilyClient] = None,
    name: str = "tavily_search_results_json",
    description: Optional[str] = None,
) -> Any:
    """Return a drop-in LangChain BaseTool compatible with TavilySearchResults.

    Requires langchain-core to be installed.
    """
    try:
        from langchain_core.tools import tool
    except ImportError:
        try:
            from langchain.tools import tool  # type: ignore
        except ImportError:
            raise ImportError(
                "LangChain is not installed. Run: pip install langchain-core"
            )

    active_client = client or TavilyClient()
    tool_desc = description or (
        "A search engine optimized for comprehensive, accurate, and trusted results. "
        "Useful for when you need to answer questions about current events or documentation."
    )

    @tool(name, description=tool_desc)
    def tavily_search_results_json(query: str) -> List[Dict[str, Any]]:
        """Run search and return results."""
        res = active_client.search(
            query=query,
            search_depth=search_depth,  # type: ignore
            max_results=max_results,
        )
        return res.get("results", [])

    return tavily_search_results_json


# ---------------------------------------------------------------------------
# CrewAI Adapter
# ---------------------------------------------------------------------------


def get_crewai_tool(
    max_results: int = 5,
    search_depth: str = "basic",
    client: Optional[TavilyClient] = None,
    name: str = "Tavily Search Tool",
    description: Optional[str] = None,
) -> Any:
    """Return a CrewAI BaseTool compatible with CrewAI agents.

    Requires crewai or crewai-tools to be installed.
    """
    try:
        from crewai.tools import tool as crewai_tool
    except ImportError:
        try:
            from crewai_tools import tool as crewai_tool  # type: ignore
        except ImportError:
            raise ImportError(
                "CrewAI is not installed. Run: pip install crewai"
            )

    active_client = client or TavilyClient()
    tool_desc = description or (
        "Search the web for up-to-date facts, data, articles, and context."
    )

    @crewai_tool(name)
    def search_web(query: str) -> str:
        """Search the web for information."""
        res = active_client.search(
            query=query,
            search_depth=search_depth,  # type: ignore
            max_results=max_results,
        )
        return json.dumps(res.get("results", []), indent=2, ensure_ascii=False)

    return search_web


__all__ = [
    "OPENAI_TOOL_SCHEMA",
    "execute_openai_tool_call",
    "get_crewai_tool",
    "get_langchain_tool",
    "get_openai_tool",
]
