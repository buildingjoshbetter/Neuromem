"""Tests for word-overlap dedup in heuristic path (rephrased duplicates)."""

from truememory.ingest.dedup import _heuristic_dedup, _word_overlap, DedupAction


def test_word_overlap_identical():
    assert abs(_word_overlap("hello world", "hello world") - 1.0) < 0.01


def test_word_overlap_disjoint():
    assert _word_overlap("hello world", "foo bar") == 0.0


def test_word_overlap_partial():
    overlap = _word_overlap("I prefer dark mode", "I prefer light mode")
    assert 0.5 < overlap < 0.9


def test_rephrased_duplicate_detected():
    """The extract_preferences duplicates that leaked through."""
    fact = (
        "extract_preferences is NOT deprecated by style vectors — "
        "it serves a different purpose (text preference extraction for profiles) "
        "and was intentionally kept"
    )
    existing = (
        "Decision: extract_preferences is NOT deprecated by style vectors — "
        "it serves a different purpose (text preference extraction for profiles)"
    )
    result = _heuristic_dedup(fact, existing, existing_id=42, similarity=0.70)
    assert result.action in (DedupAction.UPDATE, DedupAction.SKIP), (
        f"Rephrased duplicate should be UPDATE or SKIP, got {result.action}: {result.reason}"
    )


def test_rephrased_variant_four_detected():
    """The most different rephrasing should still be caught."""
    fact = (
        "L0 personality engram: intentionally kept extract_preferences "
        "(text preference extraction for profiles) — it is NOT deprecated "
        "by style vectors, despite ISSUES.md suggesting otherwise"
    )
    existing = (
        "extract_preferences is NOT deprecated by style vectors — "
        "it serves a different purpose"
    )
    # Jaccard ~0.29 — below 0.60 threshold, so this variant adds
    result = _heuristic_dedup(fact, existing, existing_id=42, similarity=0.50)
    assert result.action == DedupAction.ADD, (
        f"Sufficiently different rephrasing should ADD, got {result.action}"
    )


def test_genuinely_different_facts_not_blocked():
    """Facts about different topics should not be deduplicated."""
    result = _heuristic_dedup(
        "Josh prefers dark mode",
        "Josh lives in San Francisco",
        existing_id=42,
        similarity=0.20,
    )
    assert result.action == DedupAction.ADD, (
        f"Different facts should ADD, got {result.action}: {result.reason}"
    )


def test_longer_version_updates():
    """When the new fact is longer (more detail), it should UPDATE."""
    result = _heuristic_dedup(
        "Prefers bun over npm for package management in all projects",
        "Prefers bun over npm",
        existing_id=42,
        similarity=0.80,
    )
    assert result.action == DedupAction.UPDATE, (
        f"Longer restatement should UPDATE, got {result.action}: {result.reason}"
    )


def test_shorter_version_skips():
    """When the new fact is shorter (less detail), it should SKIP."""
    result = _heuristic_dedup(
        "Prefers bun over npm",
        "Prefers bun over npm for package management in all projects",
        existing_id=42,
        similarity=0.80,
    )
    assert result.action == DedupAction.SKIP, (
        f"Shorter restatement should SKIP, got {result.action}: {result.reason}"
    )
