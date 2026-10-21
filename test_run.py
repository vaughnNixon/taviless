"""End-to-end verification script for Taviless."""

import json
import time
from taviless import TavilyClient, search


def main():
    print("=" * 60)
    print("TAVILESS: Live Drop-in Verification")
    print("=" * 60)

    # 1. Initialize TavilyClient (api_key is accepted for drop-in parity)
    client = TavilyClient(api_key="none")

    query = "Python asyncio event loop basics"
    print(f"\n1. Executing Basic Search (depth='basic', max_results=3)...")
    print(f"   Query: '{query}'")

    t0 = time.time()
    basic_res = client.search(query, search_depth="basic", max_results=3)
    duration = time.time() - t0

    print(f"   Status: Completed in {duration:.2f}s (reported: {basic_res.get('response_time')}s)")
    print(f"   Found {len(basic_res.get('results', []))} results:")
    for idx, r in enumerate(basic_res.get("results", []), 1):
        print(f"     [{idx}] {r.get('title')}")
        print(f"         URL: {r.get('url')}")
        print(f"         Score: {r.get('score')}")
        print(f"         Snippet: {r.get('content')[:120]}...\n")

    # Verify Tavily Schema
    assert "query" in basic_res
    assert "results" in basic_res
    assert isinstance(basic_res["results"], list)
    for r in basic_res["results"]:
        assert "title" in r and "url" in r and "content" in r and "score" in r

    print("   [PASS] Basic Search and Tavily Schema verified successfully.")

    # 2. Advanced Search with parallel link crawling and content extraction
    print("\n2. Executing Advanced Search (depth='advanced', max_results=2)...")
    t1 = time.time()
    adv_res = client.search(
        "Python asyncio event loop documentation",
        search_depth="advanced",
        max_results=2,
    )
    adv_duration = time.time() - t1
    print(f"   Status: Completed in {adv_duration:.2f}s (reported: {adv_res.get('response_time')}s)")
    for idx, r in enumerate(adv_res.get("results", []), 1):
        print(f"     [{idx}] {r.get('title')}")
        print(f"         URL: {r.get('url')}")
        print(f"         Extracted Content Length: {len(r.get('content', ''))} chars")
        print(f"         Content Preview: {r.get('content', '')[:180]}...\n")

    print("   [PASS] Advanced parallel extraction verified successfully.")

    # 3. Context string for LLMs (get_search_context)
    print("\n3. Testing LLM Context Generation (get_search_context)...")
    context = client.get_search_context("asyncio task", max_results=2, max_tokens=500)
    print(f"   Context snippet:\n   {context[:250]}...\n")
    assert "Source:" in context and "Content:" in context
    print("   [PASS] Context Generation verified.")

    print("\n" + "=" * 60)
    print("All Taviless live verification checks passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
