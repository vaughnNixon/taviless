"""Round 2 Head-to-Head Benchmark: Taviless v0.1.1 vs Official Tavily API."""

import json
import os
import time
from tavily import TavilyClient as OfficialTavilyClient
from taviless import TavilyClient as TavilessClient

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

tavily = OfficialTavilyClient(api_key=TAVILY_API_KEY)
taviless = TavilessClient()

BENCHMARKS = [
    {
        "name": "1. Obscure Archival Primary Source (1970 NBS Bulletin)",
        "query": "NBS Technical News Bulletin July 1970 Vol 54 No 7 Erlenmeyer flask transducer syringe page 148",
        "search_depth": "basic",
        "include_answer": True,
        "domains": {},
        "ground_truth_keywords": ["archive.org", "technical news", "148"],
    },
    {
        "name": "2. Modern Version-Specific Python 3.13 Free-Threading API",
        "query": "Python 3.13 disable GIL environment variable and sys function",
        "search_depth": "basic",
        "include_answer": True,
        "domains": {},
        "ground_truth_keywords": ["python_gil", "_is_gil_enabled"],
    },
    {
        "name": "3. Security Forensics: CVE-2024-3094 Injected Files (Advanced Depth)",
        "query": "CVE-2024-3094 xz backdoor injected test file names in tarball",
        "search_depth": "advanced",
        "include_answer": False,
        "domains": {},
        "ground_truth_keywords": ["bad-3-corrupt_lzma2", "good-large_compressed"],
    },
    {
        "name": "4. Strict Domain Filtering (python.org whitelisted, docs.python.org blacklisted)",
        "query": "asyncio task group exception handling",
        "search_depth": "basic",
        "include_answer": False,
        "domains": {
            "include_domains": ["python.org"],
            "exclude_domains": ["docs.python.org"],
        },
        "ground_truth_keywords": ["python.org"],
    },
    {
        "name": "5. PEP 703 Technical Internals: Biased Reference Counting and mimalloc",
        "query": "PEP 703 making the global interpreter lock optional mimalloc thread-safe biased reference counting",
        "search_depth": "advanced",
        "include_answer": True,
        "domains": {},
        "ground_truth_keywords": ["biased reference counting", "mimalloc", "pep 703"],
    },
    {
        "name": "6. Specific Technical Artifact Details: SQLite 3.45.0 JSONB",
        "query": "SQLite version 3.45.0 release date jsonb binary json format size savings",
        "search_depth": "basic",
        "include_answer": True,
        "domains": {},
        "ground_truth_keywords": ["jsonb", "sqlite", "2024"],
    },
]


def run_single(name, client, query, search_depth, include_answer, domains):
    t0 = time.time()
    try:
        kwargs = {}
        if "include_domains" in domains:
            kwargs["include_domains"] = domains["include_domains"]
        if "exclude_domains" in domains:
            kwargs["exclude_domains"] = domains["exclude_domains"]

        res = client.search(
            query=query,
            search_depth=search_depth,
            include_answer=include_answer,
            max_results=5,
            **kwargs,
        )
        latency = time.time() - t0
        return {"success": True, "latency": latency, "data": res}
    except Exception as e:
        latency = time.time() - t0
        return {"success": False, "latency": latency, "error": str(e)}


def evaluate():
    results = []
    print("=" * 80)
    print("STARTING ROUND 2 BENCHMARK: UPGRADED TAVILESS vs OFFICIAL TAVILY")
    print("=" * 80)

    for b in BENCHMARKS:
        print(f"\n>>> Running: {b['name']}")
        print(f"    Query: '{b['query']}'")
        print(f"    Depth: {b['search_depth']}")

        # 1. Run Official Tavily
        print("    [1/2] Querying Official Tavily...")
        tavily_res = run_single(
            "Tavily", tavily, b["query"], b["search_depth"], b["include_answer"], b["domains"]
        )
        t_time = tavily_res.get("latency", 0)
        print(f"          Done in {t_time:.2f}s (Success: {tavily_res['success']})")

        time.sleep(1.5)

        # 2. Run Upgraded Taviless
        print("    [2/2] Querying Upgraded Taviless...")
        taviless_res = run_single(
            "Taviless", taviless, b["query"], b["search_depth"], b["include_answer"], b["domains"]
        )
        tl_time = taviless_res.get("latency", 0)
        print(f"          Done in {tl_time:.2f}s (Success: {taviless_res['success']})")

        results.append({
            "benchmark": b,
            "tavily": tavily_res,
            "taviless": taviless_res,
        })

    # Crucial user requirement: WRITE RAW OUTPUT FILE FIRST
    output_path = "benchmark_results_v2.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"ROUND 2 BENCHMARK COMPLETED. Raw results written to {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    evaluate()
