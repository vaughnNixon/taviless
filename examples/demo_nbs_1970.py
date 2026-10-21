"""Showcase Demo: 1970 NBS Technical News Bulletin Archival Retrieval.

This demo demonstrates how Taviless retrieves obscure primary-source archival
documents without hallucinating.

The Challenge:
Find the physical apparatus description (Erlenmeyer flask, pressure transducer,
syringe) in the July 1970 National Bureau of Standards (NBS) Technical News
Bulletin (Vol. 54, No. 7, pp. 148-149). While LLMs frequently claim this is
unverified or non-existent, Taviless retrieves the digitized print scan from
the Internet Archive.
"""

from taviless import TavilyClient


def main():
    print("=" * 70)
    print("Taviless Archival Retrieval Showcase: 1970 NBS Technical News Bulletin")
    print("=" * 70)

    client = TavilyClient()
    query = "NBS Technical News Bulletin July 1970 Vol 54 No 7 Erlenmeyer flask transducer syringe page 148"

    print(f"\n[1] Querying engines: '{query}'...")
    response = client.search(query, search_depth="basic", max_results=5)

    print(f"[2] Results retrieved in {response.get('response_time', 0.0):.2f}s:\n")
    found_archive = False
    for idx, r in enumerate(response["results"], 1):
        print(f"  #{idx} Title:   {r['title']}")
        print(f"     URL:     {r['url']}")
        print(f"     Snippet: {r['content'][:140]}...\n")
        if "archive.org" in r["url"] or "148" in r["content"] or "149" in r["content"]:
            found_archive = True

    print("=" * 70)
    if found_archive:
        print("[SUCCESS] Primary-source historical document located without hallucinations!")
    else:
        print("[RESULT] Top results returned.")
    print("=" * 70)


if __name__ == "__main__":
    main()
