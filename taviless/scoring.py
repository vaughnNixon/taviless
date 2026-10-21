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

    Returns None when no sentence meets the minimum relevance threshold, so
    callers can fall back instead of showing an irrelevant 'answer'.
    """
    terms = query_terms(query)
    if not terms:
        return None

    # Calibrated relevance thresholds:
    # Short query (<= 3 terms): sentence must cover >= 50% of terms.
    # Long query (> 3 terms): sentence must hit >= 2 distinct terms or >= 25% coverage.
    min_hits = 1 if len(terms) == 1 else 2
    min_coverage = 0.5 if len(terms) <= 3 else 0.25

    candidates = []  # (-score, -hits, ridx, pos, sent, domain, hit_terms)
    for ridx, r in enumerate(results[:5]):
        domain = urlparse(r.get("url", "")).netloc.lower().removeprefix("www.") if r.get("url") else ""
        content = r.get("content", "") or ""
        for pos, sent in enumerate(_SENT_SPLIT.split(content)):
            sent = sent.strip()
            if not 35 <= len(sent) <= 350:
                continue
            sent_tokens = set(_tokens(sent))
            hit_terms = terms & sent_tokens
            hits = len(hit_terms)
            if hits < min_hits:
                continue
            coverage = hits / len(terms)
            if coverage < min_coverage and hits < 3:
                continue

            density = hits / max(1, len(sent_tokens))
            rank_bonus = 1.0 / (1.0 + ridx * 0.2)
            composite_score = (hits * 2.0 + density * 5.0) * rank_bonus
            candidates.append((-composite_score, -hits, ridx, pos, sent, domain, hit_terms))

    if not candidates:
        return None

    candidates.sort()

    picked, seen, domains = [], set(), []
    covered_terms: Set[str] = set()

    # Pick the top scoring sentence
    best = candidates[0]
    picked.append(best[4])
    seen.add(best[4].lower())
    if best[5] and best[5] not in domains:
        domains.append(best[5])
    covered_terms.update(best[6])

    # If max_sentences > 1, pick the next sentence that maximizes NEW query terms
    if max_sentences > 1:
        best_complement = None
        best_new_hits = 0
        for _, _, _, _, sent, dom, hit_terms in candidates[1:]:
            if sent.lower() in seen:
                continue
            new_terms = hit_terms - covered_terms
            if len(new_terms) > best_new_hits:
                best_new_hits = len(new_terms)
                best_complement = (sent, dom, new_terms)

        if best_complement and best_new_hits > 0:
            picked.append(best_complement[0])
            if best_complement[1] and best_complement[1] not in domains:
                domains.append(best_complement[1])
        elif len(candidates) > 1 and candidates[1][4].lower() not in seen:
            picked.append(candidates[1][4])
            if candidates[1][5] and candidates[1][5] not in domains:
                domains.append(candidates[1][5])

    answer = " ".join(picked)
    return f"{answer} (Sources: {', '.join(domains)})" if domains else answer
