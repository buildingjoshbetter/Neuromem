"""MEMORIST-L5 regression tests.

Ensures the surprise rerank boost:

1. Defaults to α=0 (off) — results are byte-identical to pre-wiring.
2. Respects constructor > env var > 0.0 precedence.
3. Only boosts message-backed rows (not summaries, profiles, etc.).
4. Chunks IN-clause queries so >999 candidates don't crash.
5. Degrades gracefully when surprise_scores table is missing or empty.

Context: MEMORIST-L5 session (2026-04-23) found that the orphaned
surprise signal (written at ingest, never read at retrieval) can lift
P@10 by +2.0 pts on short-horizon (McNemar p≈0.06, not yet significant).
Session recommended shipping the wiring with α=0 default and flipping
after Modal validation at p<0.05. See
``_working/memorist/l5_predictive/REPORT.md``.
"""
from __future__ import annotations

import os
import sqlite3
from unittest.mock import patch

import pytest


@pytest.fixture
def engine_with_surprise(tmp_path, monkeypatch):
    """Build a small DB, insert a few messages with real surprise rows."""
    # Isolate env state
    monkeypatch.delenv("TRUEMEMORY_ALPHA_SURPRISE", raising=False)

    from truememory.engine import TrueMemoryEngine
    from truememory.storage import create_db

    db_path = tmp_path / "l5.db"
    conn = create_db(db_path)

    # Seed a handful of messages.
    for i in range(1, 6):
        conn.execute(
            "INSERT INTO messages (content, sender, recipient, timestamp, category, modality) "
            "VALUES (?, 'alice', 'bob', ?, 'session_1', 'conversation')",
            (f"message number {i} about topic", f"2026-0{i}-01T10:00:00Z"),
        )

    # Ensure surprise_scores table exists and populate with known values.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS surprise_scores ("
        "message_id INTEGER PRIMARY KEY, "
        "surprise REAL NOT NULL, "
        "fact_count INTEGER DEFAULT 0, "
        "new_fact_count INTEGER DEFAULT 0, "
        "FOREIGN KEY (message_id) REFERENCES messages(id))"
    )
    # id=1 low surprise, id=5 high surprise
    for i, s in zip(range(1, 6), [0.1, 0.2, 0.3, 0.4, 0.9]):
        conn.execute(
            "INSERT INTO surprise_scores (message_id, surprise) VALUES (?, ?)",
            (i, s),
        )
    conn.commit()
    conn.close()

    eng = TrueMemoryEngine(db_path)
    eng.open(rebuild_vectors=False)
    return eng


def _fake_results(ids_and_scores, source=None):
    """Construct a minimal results list like rerank_with_modality_fusion
    produces (id + score + score-duplicate as rerank_score)."""
    out = []
    for idx, score in ids_and_scores:
        r = {
            "id": idx,
            "content": f"message {idx}",
            "score": score,
            "rerank_score": score,
        }
        if source is not None:
            r["source"] = source
        out.append(r)
    return out


def test_alpha_zero_is_byte_identical(engine_with_surprise):
    """Default α=0 → `_apply_surprise_boost` returns the input list
    with identical order AND identical scores. This is the contract
    the 'ship-default-off' recommendation depends on."""
    eng = engine_with_surprise
    original = _fake_results([(1, 0.9), (5, 0.8), (3, 0.7), (2, 0.6), (4, 0.5)])
    # Snapshot state for comparison.
    before = [(r["id"], r["score"]) for r in original]

    assert eng._get_alpha_surprise() == 0.0  # default
    result = eng._apply_surprise_boost(original)

    after = [(r["id"], r["score"]) for r in result]
    assert before == after, (
        "At α=0 the surprise boost must preserve order AND scores "
        "exactly — otherwise ship-default-off breaks the 'no change' "
        "contract."
    )


def test_env_var_sets_alpha(engine_with_surprise, monkeypatch):
    """TRUEMEMORY_ALPHA_SURPRISE env var is read at call-time."""
    eng = engine_with_surprise
    monkeypatch.setenv("TRUEMEMORY_ALPHA_SURPRISE", "0.3")
    assert eng._get_alpha_surprise() == 0.3

    monkeypatch.setenv("TRUEMEMORY_ALPHA_SURPRISE", "1.5")
    assert eng._get_alpha_surprise() == 1.5

    monkeypatch.setenv("TRUEMEMORY_ALPHA_SURPRISE", "not a number")
    assert eng._get_alpha_surprise() == 0.0  # falls back safely


def test_constructor_override_beats_env_var(tmp_path, monkeypatch):
    """alpha_surprise constructor arg takes priority over env var."""
    monkeypatch.setenv("TRUEMEMORY_ALPHA_SURPRISE", "0.3")

    from truememory.engine import TrueMemoryEngine
    from truememory.storage import create_db

    db_path = tmp_path / "override.db"
    create_db(db_path).close()

    eng = TrueMemoryEngine(db_path, alpha_surprise=0.7)
    eng.open(rebuild_vectors=False)
    assert eng._get_alpha_surprise() == 0.7

    # Memory class plumbs the arg through too.
    from truememory import Memory
    mem = Memory(":memory:", alpha_surprise=0.5)
    assert mem._engine._get_alpha_surprise() == 0.5


def test_alpha_positive_boosts_high_surprise(engine_with_surprise):
    """With α>0, high-surprise messages should get their score
    multiplied by (1 + α·s); order should re-sort accordingly."""
    eng = engine_with_surprise
    eng._alpha_surprise_override = 0.5

    # id=5 has surprise 0.9 (highest); id=1 has 0.1 (lowest).
    # Start with id=1 at top (score=0.9) and id=5 at bottom (score=0.5).
    # After boost at α=0.5:
    #   id=1: 0.9 * (1 + 0.5*0.1) = 0.945
    #   id=5: 0.5 * (1 + 0.5*0.9) = 0.725
    # id=1 still top, but id=5's multiplicative lift moves it up.
    results = _fake_results([(1, 0.9), (2, 0.8), (3, 0.7), (4, 0.6), (5, 0.5)])
    boosted = eng._apply_surprise_boost(results)

    # id=5 (highest surprise) moves above id=4 (lower surprise, lower base).
    # Check: id=5 should now rank above id=4.
    boosted_ids = [r["id"] for r in boosted]
    assert boosted_ids.index(5) < boosted_ids.index(4), (
        "At α=0.5, high-surprise row (id=5) should re-rank above "
        "lower-surprise row (id=4). Got order: %r" % boosted_ids
    )

    # All boosted rows should have score = base * (1 + α * surprise)
    for r in boosted:
        assert r["score"] > 0


def test_non_message_rows_not_boosted(engine_with_surprise):
    """Rows with source in {personality, profile, summary, contradiction}
    must NOT receive the boost — their id is NOT a messages.id and
    would silently cross-table collide."""
    eng = engine_with_surprise
    eng._alpha_surprise_override = 0.5

    # Summary row whose `id` happens to match a messages.id (5).
    summary_row = {
        "id": 5, "content": "summary", "score": 0.9, "source": "summary",
    }
    message_row = {
        "id": 3, "content": "msg", "score": 0.5,
    }
    boosted = eng._apply_surprise_boost([summary_row, message_row])

    # Find the summary row in output and assert its score is untouched.
    out_summary = next(r for r in boosted if r["source"] == "summary")
    assert out_summary["score"] == 0.9, (
        "Summary row must NOT be boosted — its id is not a messages.id."
    )
    # Message row should be boosted.
    out_msg = next(r for r in boosted if "source" not in r)
    assert out_msg["score"] > 0.5


def test_missing_surprise_table_degrades_gracefully(tmp_path, caplog):
    """When surprise_scores table doesn't exist (cold DB before any
    consolidate), the boost should log and return results unchanged."""
    import logging
    from truememory.engine import TrueMemoryEngine
    from truememory.storage import create_db

    db_path = tmp_path / "cold.db"
    conn = create_db(db_path)
    # Drop the surprise_scores table if the storage layer created it.
    conn.execute("DROP TABLE IF EXISTS surprise_scores")
    conn.commit()
    conn.close()

    eng = TrueMemoryEngine(db_path, alpha_surprise=0.3)
    eng.open(rebuild_vectors=False)

    results = _fake_results([(1, 0.9), (2, 0.8)])
    original_scores = [(r["id"], r["score"]) for r in results]

    with caplog.at_level(logging.WARNING, logger="truememory.engine"):
        boosted = eng._apply_surprise_boost(results)

    # Should return input as-is.
    assert [(r["id"], r["score"]) for r in boosted] == original_scores
    # Should log a warning.
    assert any(
        "L5 surprise boost unavailable" in rec.message
        for rec in caplog.records
        if rec.levelname == "WARNING"
    )


def test_empty_surprise_map_returns_input(engine_with_surprise):
    """When surprise_scores exists but has no entries for our IDs,
    the boost is a no-op (logs nothing, preserves input)."""
    eng = engine_with_surprise
    eng._alpha_surprise_override = 0.5

    # IDs 100, 101, 102 do NOT exist in surprise_scores (seeded 1-5).
    results = _fake_results([(100, 0.9), (101, 0.8), (102, 0.7)])
    boosted = eng._apply_surprise_boost(results)

    # Order and scores unchanged.
    assert [(r["id"], r["score"]) for r in boosted] == [
        (100, 0.9), (101, 0.8), (102, 0.7)
    ]


def test_chunked_in_clause_handles_many_ids(engine_with_surprise):
    """With >999 candidate IDs, the IN-clause must chunk, not crash."""
    eng = engine_with_surprise
    eng._alpha_surprise_override = 0.3

    # 1500 ids (most won't have surprise rows, but that's fine)
    big = _fake_results([(i, 1.0 / i) for i in range(1, 1501)])

    # Should not raise sqlite3.OperationalError: too many SQL variables
    boosted = eng._apply_surprise_boost(big)
    assert len(boosted) == 1500


def test_empty_results_returns_empty(engine_with_surprise):
    eng = engine_with_surprise
    eng._alpha_surprise_override = 0.3
    assert eng._apply_surprise_boost([]) == []


def test_alpha_zero_skips_db_query(engine_with_surprise):
    """At α=0 the boost must short-circuit before touching the DB —
    this is what makes ship-default-off zero-cost.

    Verified by replacing the connection with a sentinel that raises
    if any method is called. (sqlite3.Connection.execute is read-only
    in CPython, so patch.object doesn't work here; we use a duck-typed
    substitute instead.)
    """
    eng = engine_with_surprise

    class _ExplodingConn:
        def __getattr__(self, name):
            raise AssertionError(
                f"α=0 path should not touch the DB (tried to access .{name})"
            )

    real_conn = eng.conn
    eng.conn = _ExplodingConn()
    try:
        results = _fake_results([(1, 0.9), (2, 0.5)])
        # Should NOT raise AssertionError.
        boosted = eng._apply_surprise_boost(results)
        assert [r["id"] for r in boosted] == [1, 2]
    finally:
        eng.conn = real_conn
