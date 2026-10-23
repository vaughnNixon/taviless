# Taviless 🔍

> **Free, model-free web retrieval for LLMs. Search across engines, deduplicate results, extract useful content, and return evidence to your AI agent.**
> 
> A free, zero-dependency, open-source library compatible with the Tavily search API.

[![PyPI version](https://img.shields.io/pypi/v/taviless.svg)](https://pypi.org/project/taviless/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-brightgreen.svg)]()
[![Tests](https://github.com/vaughnNixon/taviless/actions/workflows/tests.yml/badge.svg)](https://github.com/vaughnNixon/taviless/actions/workflows/tests.yml)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(Pure%20Stdlib)-blueviolet)]()

Taviless gives your AI agents, LangChain workflows, CrewAI teams, and local LLMs real-time web search with clean, token-dense markdown content extraction—**without API keys, subscriptions, credit cards, or Docker containers required**.

---

## ⚡ The Origin Story

Taviless was **vibe-coded in about 20 minutes, taking roughly two hours from a random whiteboard idea to a fully tested, production-packaged Python library**. 

### Why We Built It
Most search APIs for AI agents (like Tavily) charge monthly subscriptions, gate basic capabilities behind credit cards, and throttle agent exploration. When building autonomous agents, you shouldn't need a paid API key just to verify facts or read a webpage. 

Furthermore, many proprietary search engines bias heavily toward commercial SEO pages or hallucinate when asked for long-tail historical records. Taviless was built to provide:
1. **Absolute Freedom:** Pure Python standard library (`urllib.request`, `concurrent.futures`, `html.parser`). `pip install taviless` and you're immediately running.
2. **Search API Compatibility:** Compatible with Tavily's search response schema so existing agent pipelines can switch with a single-line import change.
3. **Speculative Multi-Engine Racing (v0.1.1):** Queries DuckDuckGo and SearXNG simultaneously with a 250ms fast cutoff, giving you sub-1.5s search speeds and multi-engine deduplicated results.
4. **Deep Archival Retrieval:** Grounded evidence from primary sources (including Internet Archive scans and academic repositories) where standard LLMs hallucinate.
5. **Reverse-Chronological Temporal Grounding:** Prevents agents from falling into the "Static Homepage Trap" on fast-moving tech queries.

---

## 🏛️ Featured Showcase: The 1970 NBS Archival Challenge

To see why model-free, primary-source web retrieval matters, consider this query:

> *"NBS Technical News Bulletin July 1970 Vol 54 No 7 Erlenmeyer flask transducer syringe page 148"*

When asked about this obscure physical laboratory apparatus from 1970, commercial LLMs frequently claim the citation is "unverified", "non-existent", or completely hallucinate the contents. 

Taviless runs multi-engine discovery with deep archival traversal and retrieves the exact digitized print scan from the **Internet Archive** in seconds:

```bash
python examples/demo_nbs_1970.py
```

```text
======================================================================
Taviless Archival Retrieval Showcase: 1970 NBS Technical News Bulletin
======================================================================
[1] Querying engines: 'NBS Technical News Bulletin July 1970 Vol 54 No 7...'
[2] Results retrieved in 8.19s:

  #1 Title:   Technical News Bulletin - volume 54 no. 7 - Archive.org
     URL:     https://archive.org/details/technicalnewsbul547nati
     Snippet: T1 .U45 v.54 no.7 1970 Camera Sony Alpha-A6300 (Control)... The NBS Technical News Bulletin is a publication of the U.S. Government...

  #2 Title:   PDF United States. National Bureau of Standards. Technical News Bulletin...
     URL:     https://ia601803.us.archive.org/34/items/sim_dimensions-national-bureau-of-standards_1970-07_54_7/...
     Snippet: Technical News Bulletin JULY 1970 / VOL. 54, NO. 7 / ISSUED MONTHLY...

======================================================================
[SUCCESS] Primary-source historical document located without hallucinations!
======================================================================
```

No hallucinations. Just verifiable, primary-source evidence returned directly to the agent.

---

## 📦 Installation

**Zero Docker required.** Works out of the box on Windows, macOS, and Linux:

```bash
# Pure Python standard library install (zero 3rd-party dependencies!)
pip install taviless

# Optional: with high-density trafilatura article extractor
pip install "taviless[extract]"
```

---

## 🚀 Quickstart: Drop-in Tavily Search Replacement

Simply change your import:

```python
# Before: from tavily import TavilyClient
from taviless import TavilyClient

# Initialize client (api_key is accepted for compatibility, but optional)
client = TavilyClient()

# 1. Basic fast search (~300ms)
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

### 2. Direct URL Content Extraction (`client.extract`)

Extract clean, token-dense markdown from target URLs in parallel (compatible with Tavily's extract API):

```python
data = client.extract(urls=["https://peps.python.org/pep-3156/"])
for item in data["results"]:
    print(f"URL: {item['url']}")
    print(f"Content: {item['raw_content'][:300]}...")
```

---

## 🤖 Example: LLM Tool Calling with Grounded Citations

Here is a complete, working example showing how an LLM (e.g., OpenAI `gpt-4o`) calls Taviless, receives structured source evidence, and synthesizes a grounded answer with citations:

```python
import json
from openai import OpenAI
from taviless.adapters import get_openai_tool, execute_openai_tool_call

client = OpenAI()

messages = [
    {"role": "system", "content": "You are a research assistant. Always back up claims with search evidence."},
    {"role": "user", "content": "What are the latest updates on Python 3.14?"}
]

# 1. Send query to LLM with Taviless tool definition
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=[get_openai_tool()],
)

message = response.choices[0].message

# 2. Check if the LLM invoked Taviless search
if message.tool_calls:
    messages.append(message)
    for tool_call in message.tool_calls:
        print(f"-> Agent invoked tool: {tool_call.function.name}")
        print(f"-> Arguments: {tool_call.function.arguments}")
        
        # Execute Taviless tool call
        tool_result = execute_openai_tool_call(tool_call.function.arguments)
        
        # Feed retrieved sources back into conversation
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.function.name,
            "content": tool_result,
        })

    # 3. Model synthesizes final grounded answer with sources
    final_response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
    )
    print("\nFinal Grounded Answer:\n")
    print(final_response.choices[0].message.content)
```

---

## 🧠 Advanced Parallel RAG Search

When building RAG agents, search snippets are often too brief. Switch to `search_depth="advanced"` to crawl the top URLs in parallel and extract ad-free, token-dense markdown:

```python
client = TavilyClient()

response = client.search(
    "latest discoveries in solid state battery commercialization",
    search_depth="advanced",
    max_results=3,
    include_raw_content=False,
)

for result in response["results"]:
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Body Content:\n{result['content'][:500]}...\n")
```

---

## ⏱️ Reverse-Chronological Temporal Grounding

Most web scrapers fall into the **Static Homepage Trap**: when you search for "latest model", they crawl the vendor's root homepage and grab whatever marketing banner was written months ago.

Taviless uses **Reverse-Chronological Temporal Grounding**:
1. Checks the current calendar date (`datetime.date.today()`).
2. Engages fresh date-filtering (`time_range="month"` or `"week"`).
3. Scans extracted content for timestamps $\le \text{Today}$ and orders paragraphs from newest to oldest.

```python
# Automatically detects temporal intent and surfaces the freshest sub-releases
results = client.search("latest AI model releases", search_depth="advanced")
```

---

## 🧩 Framework Adapters

### 1. LangChain
```python
from taviless.adapters import get_langchain_tool

# Drop-in replacement for TavilySearchResults
tavily_tool = get_langchain_tool(max_results=5, search_depth="basic")

# Bind directly to your model or agent
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

---

---

## 🔬 Head-to-Head Benchmark: Taviless vs. Official Tavily API

We executed a real-world, 6-challenge raw retrieval benchmark pitting **Taviless** directly against the **Official Tavily Search API** (using live API credits). 

The full, unabridged raw JSON responses and test harness are included in the repository:
- **Test Runner:** [`benchmarks/run_benchmark.py`](benchmarks/run_benchmark.py)
- **Raw Benchmark Data:** [`benchmarks/raw_results.json`](benchmarks/raw_results.json) (121 KB of unfiltered network payloads)

### Benchmark Results Table

| Challenge | Official Tavily API | Taviless (v0.1.1) | Ground Truth & Behavior Analysis |
| :--- | :--- | :--- | :--- |
| **1. Archival Primary Source** *(1970 NBS Bulletin)* | 1.69s | **3.74s** | 🏆 **Taviless won ground truth.** Tavily drifted into commercial lab vendor SEO; its LLM admitted failure (*"Sources do not provide specific details..."*). Taviless extracted **10,000+ characters of raw OCR text** directly from `archive.org`. |
| **2. Python 3.13 Free-Threading API** | **0.27s** *(cached)* | 5.44s | 🏅 **Tavily won depth.** Tavily surfaced both `PYTHON_GIL=0` and `sys._is_gil_enabled()`. Taviless extracted `PYTHON_GIL=1`, but missed `_is_gil_enabled` in the StackOverflow question snippet. |
| **3. Security Forensics: CVE-2024-3094** *(Advanced)* | **0.27s** *(cached)* | 2.18s | 🏅 **Tavily won depth.** Tavily extracted both injected files (`bad-3-corrupt_lzma2` & `good-large_compressed`). Taviless extracted `bad-3-corrupt_lzma2`, but top slots went to institutional registries (NVD / CVE.org). |
| **4. Strict Domain Filtering** *(python.org)* | **0.28s** | 0.49s | 🏅 **Tavily won uptime.** Tavily returned 5 discussion threads. Taviless hit DuckDuckGo's HTTP 202 bot challenge due to rapid-fire test bursts from a single IP. |
| **5. PEP 703 Internals** *(mimalloc & BRC)* | 3.99s | **1.18s** | 🏅 **Tavily won uptime.** Tavily synthesized Biased Reference Counting details. Taviless hit DuckDuckGo HTTP 202 bot challenge during the burst. |
| **6. SQLite 3.45.0 JSONB Release** | 2.78s | **2.12s** | 🏆 **Taviless won speed & precision.** Taviless extracted the exact release date (`2024-01-15`) and official binary JSON specification directly from `sqlite.org`, beating Tavily's latency. |

---

## ⚖️ Real Technical Limits & Trade-Offs (No Sugarcoating)

We believe in radical technical transparency. Here are the exact limitations of Taviless compared to paid search APIs:

### 1. The Rate-Limiting Reality: Public Gateways vs. Paid Cloud Proxies
* **Official Tavily ($29 – $100+/month):** Tavily maintains a multi-million-request pool of rotating residential proxies. You can hammer 50 queries in 5 seconds without ever seeing a CAPTCHA.
* **Taviless ($0.00 / Free):** Uses open public SearXNG gateways and DuckDuckGo endpoints. If you send **20+ queries in rapid succession within seconds from a single residential IP**, DuckDuckGo will temporarily return an `HTTP 202 Bot Challenge`.
* **The Solution:** For standard AI agents (LangChain, AutoGen, CrewAI), the model naturally pauses for 3–6 seconds between thoughts, so rate limits are rarely triggered. For high-throughput scraper swarms, spin up a local 1-line Docker node: `TavilyClient(searxng_url="http://localhost:8080")`.

### 2. Extractive Quotes vs. Generative LLM Summaries
* **Official Tavily:** Includes a server-side generative LLM that writes 2–3 cohesive English paragraphs summarizing the sources.
* **Taviless:** **100% model-free**. Its `answer` field extracts the highest-density factual sentences directly from the source pages with citations. If no sentences cross the density threshold, it cleanly returns `null` rather than hallucinating.
* **Why this matters for agents:** If you are feeding search results into an AI agent (GPT-4o, Claude 3.5, Gemini), **your agent is already doing the answering**. Paying Tavily extra just to generate an answer you throw away is redundant.

### 3. Snippets vs. Deep Web Crawling
* In `search_depth="basic"`, Taviless uses fast search engine snippets (~0.7s) to protect your latency and context window. If a question is buried deep in a StackOverflow answer, basic snippets might miss it.
* In `search_depth="advanced"`, Taviless concurrently crawls and parses up to **20,000 characters per page**. For explicit page reading, call `client.extract(urls=[...])` which supports up to 25,000+ characters per URL.

---

## 🔎 Response Fields: What's Real

Taviless has no model in the loop, so a few fields differ from Tavily's:

- **`score`**: a transparent heuristic, **not** a model relevance score. It's `0.5 × rank prior + 0.5 × query-term overlap` (title weighted), clamped to 0.05-0.99, and results are sorted by it. Good for ordering and thresholding sanity checks, not for comparing across queries.
- **`answer`** (with `include_answer=True`): **extractive**, not generated. It's the best-matching sentence(s) from the top results, with source domains appended, e.g. `"... (Sources: docs.python.org)"`. When nothing matches at least half the query terms it is `null`, so check for that.
- **`warnings`** (extra field, only present when something went wrong): why a search came back thin or empty, e.g. a DuckDuckGo bot challenge, a SearXNG `403` (JSON format disabled), or pages that couldn't be crawled. Empty results with no warnings means the engines really found nothing.

---

## ⚠️ Limitations & Best Practices

While Taviless provides a robust multi-engine gateway out of the box, keep the following real-world characteristics in mind:

1. **Upstream Interface Changes:** Public search engines (DuckDuckGo, SearXNG public instances) do not provide SLA-backed APIs; their HTML markup, headers, and anti-bot challenges can change periodically. Taviless employs a multi-tiered fallback (SearXNG JSON $\rightarrow$ DuckDuckGo POST $\rightarrow$ DuckDuckGo GET $\rightarrow$ DuckDuckGo Lite HTML table) to maintain resilience.
2. **Rate Limiting & Throttling:** If you run heavy parallel agent swarms sending dozens of queries per second, public gateways will temporarily throttle or rate-limit automated IP requests.
3. **Private SearXNG Node (recommended for production):** SearXNG is Taviless's primary engine. A private instance gives you multi-engine aggregation, no shared rate limits, and keeps your queries private:
   ```bash
   docker run -d -p 8080:8080 -e "SEARXNG_BASE_URL=http://localhost:8080/" searxng/searxng
   export TAVILESS_SEARXNG_URL="http://localhost:8080"
   ```
   > SearXNG ships with JSON output disabled. Add `json` to `search.formats` in its `settings.yml` (`formats: [html, json]`) or Taviless will get `403`s.

   When a private URL is set, Taviless **never** falls back to public SearXNG gateways (your queries stay on your node); in `auto` mode it can still fall back to DuckDuckGo.

   **Public gateways (best-effort):** with no private URL, Taviless races a built-in list of public SearXNG instances in parallel and uses the first that answers. Many public instances disable JSON output or rate-limit bots, and your queries go to third-party servers, so don't send anything sensitive through them.
   Or pass it in code: `TavilyClient(searxng_url="http://localhost:8080")`.

4. **HTTP Request Compatibility & Bot Protection:** Taviless uses standard HTTP headers with a Safari-style User-Agent for clean request compatibility across technical documentation, news, academic archives, and public web pages without sending contradictory Chromium Client Hints. However, website responses vary, and destinations protected by active bot detection systems (e.g., Cloudflare Turnstile, DataDome, or interactive CAPTCHAs) may restrict automated requests. When an automated fetch is restricted or fails, Taviless handles it gracefully: it logs a notice in the `warnings` field, retains the original search engine snippet, and continues execution so your AI agent loop never crashes.

---

## 🧪 Testing

```bash
# Run unit test suite (41 passing tests)
python -m unittest discover tests

# Run live verification
python test_run.py

# Run the 1970 NBS archival demonstration
python examples/demo_nbs_1970.py
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details. Free for commercial, personal, and research use.
