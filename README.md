# Taviless 🔍

> **100% Free, Zero-Dependency, Open-Source Drop-in Replacement for the Tavily Search API.**

[![PyPI](https://img.shields.io/pypi/v/taviless.svg)](https://pypi.org/project/taviless/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-brightgreen.svg)]()

Taviless gives your AI agents, LangChain workflows, and CrewAI teams real-time web search with clean, token-dense markdown content extraction—**without API keys, subscriptions, or credit card requirements**.

---

## ⚡ Highlights

* **100% Tavily-Compatible Schema:** Outputs exact schema match (`query`, `results[{"title", "url", "content", "score", "raw_content"}]`, `response_time`).
* **Zero Dependencies by Default:** Core library runs exclusively on the Python standard library (`urllib.request`, `concurrent.futures`, `html.parser`).
* **Dual Search Depths:**
  * `search_depth="basic"`: Blazing fast search engine snippets (~300ms).
  * `search_depth="advanced"`: Parallel link crawling via `ThreadPoolExecutor` and clean markdown extraction.
* **Resilient Multi-Engine Gateway:** Queries SearXNG instances with automatic failover and circuit breakers, backed by DuckDuckGo fallback.
* **Private SearXNG Support:** Point to your private Docker instance via `TAVILESS_SEARXNG_URL` for unlimited throughput.
* **1-Line Integrations:** Ready-to-use adapters for LangChain, CrewAI, and native OpenAI tool definitions.
* **Opt-in Extraction:** Supports `pip install "taviless[extract]"` for `trafilatura`-powered content extraction.

---

## 📦 Installation

```bash
# Minimal zero-dependency install (pure Python standard library)
pip install taviless

# Optional: with high-density trafilatura article extractor
pip install "taviless[extract]"
```

---

## 🚀 Quickstart: Drop-in Tavily Replacement

Simply change your import:

```python
# Before: from tavily import TavilyClient
from taviless import TavilyClient

# Initialize client (api_key is accepted for compatibility, but optional)
client = TavilyClient()

# 1. Basic fast search
response = client.search("python asyncio event loop", search_depth="basic", max_results=3)
print(response)
```

### Tavily-Compatible Output:

```json
{
  "query": "python asyncio event loop",
  "results": [
    {
      "title": "Event loop — Python 3.14.0 documentation",
      "url": "https://docs.python.org/3/library/asyncio-eventloop.html",
      "content": "The event loop is the core of every asyncio application...",
      "score": 0.98,
      "raw_content": null
    }
  ],
  "response_time": 0.32,
  "answer": null,
  "images": []
}
```

---

## 🧠 Advanced Parallel RAG Search

When building RAG agents, search snippets are often too brief. Switch to `search_depth="advanced"` to crawl the top URLs in parallel and extract ad-free, token-dense markdown:

```python
client = TavilyClient()

response = client.search(
    "latest discoveries in exoplanet atmospheres",
    search_depth="advanced",
    max_results=3,
    include_raw_content=False,
)

for result in response["results"]:
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Body Content:\n{result['content']}\n")
```

---

## 🤖 Framework Adapters

### 1. LangChain

```python
from taviless.adapters import get_langchain_tool

# Drop-in replacement for TavilySearchResults
tavily_tool = get_langchain_tool(max_results=5, search_depth="basic")

# Bind to your model or agent
llm_with_tools = model.bind_tools([tavily_tool])
```

### 2. CrewAI

```python
from crewai import Agent
from taviless.adapters import get_crewai_tool

search_tool = get_crewai_tool(max_results=3, search_depth="advanced")

researcher = Agent(
    role="Senior Market Researcher",
    goal="Gather up-to-date market data",
    tools=[search_tool],
    verbose=True,
)
```

### 3. OpenAI Function / Tool Calling

```python
from openai import OpenAI
from taviless.adapters import get_openai_tool, execute_openai_tool_call

client = OpenAI()

# Provide schema in chat completion
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What are the latest updates on Python 3.14?"}],
    tools=[get_openai_tool()],
)

# Execute model tool calls in one line
tool_call = response.choices[0].message.tool_calls[0]
tool_result_json = execute_openai_tool_call(tool_call.function.arguments)
```

---

## 🛠️ Configuration & Custom Instances

### Self-Hosted SearXNG
If you run SearXNG locally in Docker:
```bash
docker run -d -p 8080:8080 -e "SEARXNG_BASE_URL=http://localhost:8080/" searxng/searxng
```

Configure Taviless to use it automatically:

```bash
export TAVILESS_SEARXNG_URL="http://localhost:8080"
```

Or pass it programmatically:

```python
client = TavilyClient(searxng_url="http://localhost:8080")
```

---

## 🧪 Testing

```bash
# Run test suite
python -m unittest discover tests

# Run live end-to-end verification
python test_run.py
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
