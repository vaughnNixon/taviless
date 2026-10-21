"""Unit tests for adapters (OpenAI tool, LangChain, CrewAI)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from taviless.adapters import (
    execute_openai_tool_call,
    get_crewai_tool,
    get_langchain_tool,
    get_openai_tool,
)


class TestAdapters(unittest.TestCase):
    def test_openai_tool_schema(self) -> None:
        schema = get_openai_tool(tool_name="custom_search")
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "custom_search")
        params = schema["function"]["parameters"]
        self.assertEqual(params["type"], "object")
        self.assertIn("query", params["properties"])
        self.assertIn("search_depth", params["properties"])
        self.assertIn("query", params["required"])

    @patch("taviless.client.TavilyClient.search")
    def test_execute_openai_tool_call(self, mock_search) -> None:
        mock_search.return_value = {
            "query": "hello world",
            "results": [{"title": "Hello", "url": "https://example.com", "content": "World", "score": 0.9}],
            "response_time": 0.2,
        }

        args_str = json.dumps({"query": "hello world", "max_results": 1})
        res_json = execute_openai_tool_call(args_str)
        data = json.loads(res_json)

        self.assertEqual(data["query"], "hello world")
        self.assertEqual(len(data["results"]), 1)

    def test_langchain_tool_instantiation_if_installed(self) -> None:
        try:
            import langchain_core
        except ImportError:
            self.skipTest("langchain_core not installed")

        tool = get_langchain_tool(max_results=3)
        self.assertEqual(tool.name, "tavily_search_results_json")
        self.assertTrue(callable(tool.invoke) or callable(tool))



if __name__ == "__main__":
    unittest.main()
