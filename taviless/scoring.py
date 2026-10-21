"""Model-free relevance scoring and extractive answers.

Nothing here calls a model. `score` is a transparent heuristic (rank prior +
query-term overlap) and `answer` is the best matching sentence(s) lifted from
the results, not generated text.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set
from urllib.parse import urlparse

from taviless.types import SearchResult

_STOP = frozenset(
    "a an and are as at be by for from how i in is it of on or that the this to was what when where which who why with "
    "do does did can could should would about into than then there their they you your".split()
)
_OPERATORS = re.compile(r"(?:^|\s)-?site:\S+|\bOR\b")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def query_terms(query: str) -> Set[str]:
    """Meaningful lowercase terms of a query (operators and stopwords removed)."""
    cleaned = _OPERATORS.sub(" ", query)
    return {t for t in _tokens(cleaned) if t not in _STOP and (len(t) > 1 or t.isdigit())}


def score_results(query: str, results: List[SearchResult]) -> List[SearchResult]:
    """Assign a heuristic 0.05-0.99 score and sort results by it (stable).

    score = 0.5 * rank_prior + 0.5 * term_overlap, where rank_prior decays with
    the engine's own ordering and term_overlap is the fraction of query terms
    found in the title (weighted) and title/snippet/URL.
    """
    terms = query_terms(query)
    for idx, r in enumerate(results):
        rank_prior = 1.0 / (1.0 + 0.15 * idx)
        if terms:
            title_tokens = set(_tokens(r.get("title", "")))
            body_tokens = title_tokens | set(_tokens(r.get("content", "") + " " + r.get("url", "")))
            overlap = 0.5 * len(terms & title_tokens) / len(terms) + 0.5 * len(terms & body_tokens) / len(terms)
        else:
            overlap = rank_prior
        r["score"] = round(min(0.99, max(0.05, 0.5 * rank_prior + 0.5 * overlap)), 2)
    results.sort(key=lambda r: -r.get("score", 0.0))
    return results


def extractive_answer(query: str, results: List[SearchResult], max_sentences: int = 2) -> Optional[str]:
    """Best matching sentence(s) from the top results, with source domains.

    Returns None when no sentence covers at least half of the query terms, so
    callers can fall back instead of showing an irrelevant "answer".
    """
    terms = query_terms(query)
    if not terms:
        return None
    min_hits = min(2, len(terms))
    candidates = []  # (-coverage, result_idx, position, sentence, domain)
    for ridx, r in enumerate(results[:5]):
        domain = urlparse(r.get("url", "")).netloc.lower().removeprefix("www.") if r.get("url") else ""
        for pos, sent in enumerate(_SENT_SPLIT.split(r.get("content", "") or "")):
            sent = sent.strip()
            if not 40 <= len(sent) <= 300:
                continue
            hits = len(terms & set(_tokens(sent)))
            if hits < min_hits or hits / len(terms) < 0.5:
                continue
            candidates.append((-hits / len(terms), ridx, pos, sent, domain))
    if not candidates:
        return None
    candidates.sort()
    picked, seen, domains = [], set(), []
    for _, _, _, sent, domain in candidates:
        key = sent.lower()
        if key in seen:
            continue
        seen.add(key)
        picked.append(sent)
        if domain and domain not in domains:
            domains.append(domain)
        if len(picked) >= max_sentences:
            break
    answer = " ".join(picked)
    return f"{answer} (Sources: {', '.join(domains)})" if domains else answer
