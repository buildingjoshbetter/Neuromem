"""MEMORIST-L4 regression tests.

Ensures the `build_entity_summary_sheets` function is disabled by default
in `TrueMemoryEngine.consolidate()`, that legacy `period='entity_profile'`
rows are purged on `open()`, and that the escape-hatch env var
`TRUEMEMORY_ENTITY_SHEETS=1` re-enables the function.

Context: MEMORIST-L4 research session (2026-04-23) found that the function
produces fat profile rows that saturate top-1 retrieval by keyword match
and leak superseded facts into contradiction scoring. Disabling produced
+5.3 pts on the composite L4 probe metric. See
``_working/memorist/l4_consolidation/REPORT.md`` §3, §10.7.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import warnings
from pathlib import Path

import pytest


def _seed_messages(tmp_path):
    """Build a convo JSON with enough per-sender messages (>=5) to
    trigger build_entity_summary_sheets when enabled."""
    tmp_json = tmp_path / "convo.json"
    messages = [
        {"content": "I live in Boston and work at Stripe.",
         "sender": "alice", "recipient": "bob",
         "timestamp": "2026-01-05T10:00:00Z", "category": "session_1",
         "modality": "conversation"},
        {"content": "Boston winters are tough.",
         "sender": "alice", "recipient": "bob",
         "timestamp": "2026-01-06T10:00:00Z", "category": "session_1",
         "modality": "conversation"},
        {"content": "Thinking about leaving Stripe soon.",
         "sender": "alice", "recipient": "bob",
         "timestamp": "2026-01-10T10:00:00Z", "category": "session_1",
         "modality": "conversation"},
        {"content": "Got an offer from a new startup.",
         "sender": "alice", "recipient": "bob",
         "timestamp": "2026-02-01T10:00:00Z", "category": "session_2",
         "modality": "conversation"},
        {"content": "I accepted the offer. Moving to Austin.",
         "sender": "alice", "recipient": "bob",
         "timestamp": "2026-02-15T10:00:00Z", "category": "session_2",
         "modality": "conversation"},
        {"content": "Austin is hot but I love it here.",
         "sender": "alice", "recipient": "bob",
         "timestamp": "2026-03-01T10:00:00Z", "category": "session_3",
         "modality": "conversation"},
    ]
    tmp_json.write_text(json.dumps(messages))
    return tmp_json


@pytest.fixture
def seeded_engine(tmp_path, monkeypatch):
    """Fresh DB ingested via TrueMemoryEngine.ingest() — which runs the
    full consolidation pipeline including (default) the L4-disable path."""
    from truememory.engine import TrueMemoryEngine

    monkeypatch.delenv("TRUEMEMORY_ENTITY_SHEETS", raising=False)
    tmp_json = _seed_messages(tmp_path)
    db_path = tmp_path / "l4_test.db"

    eng = TrueMemoryEngine(db_path)
    stats = eng.ingest(str(tmp_json))
    eng.close()
    return db_path, stats


def test_disabled_by_default_no_entity_profile_rows(seeded_engine):
    """Default v0.5.1 behavior: ingest() must NOT write any summaries
    rows with period='entity_profile'."""
    db_path, _stats = seeded_engine
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT COUNT(*) FROM summaries WHERE period = 'entity_profile'"
    ).fetchone()[0]
    conn.close()
    assert rows == 0, (
        f"Expected 0 entity_profile rows after default ingest(), got {rows}. "
        "build_entity_summary_sheets should be disabled by default; see "
        "MEMORIST-L4 REPORT.md."
    )


def test_stats_reports_disabled_string(seeded_engine):
    """The ingest() stats dict must explicitly flag the feature as
    DISABLED so observability tools can surface the state."""
    _db_path, stats = seeded_engine
    assert "entity_summary_sheets" in stats
    assert "DISABLED" in stats["entity_summary_sheets"]
    assert "TRUEMEMORY_ENTITY_SHEETS" in stats["entity_summary_sheets"]


def test_env_var_re_enables(tmp_path, monkeypatch):
    """TRUEMEMORY_ENTITY_SHEETS=1 re-enables the (deprecated) function."""
    monkeypatch.setenv("TRUEMEMORY_ENTITY_SHEETS", "1")

    from truememory.engine import TrueMemoryEngine

    tmp_json = _seed_messages(tmp_path)
    db_path = tmp_path / "reenabled_test.db"

    # Suppress the deprecation warning during intentional re-enable.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        eng = TrueMemoryEngine(db_path)
        stats = eng.ingest(str(tmp_json))
        eng.close()

    assert "re-enabled via TRUEMEMORY_ENTITY_SHEETS=1" in stats["entity_summary_sheets"]

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT COUNT(*) FROM summaries WHERE period = 'entity_profile'"
    ).fetchone()[0]
    conn.close()
    assert rows > 0, (
        "With TRUEMEMORY_ENTITY_SHEETS=1, entity_profile summary rows "
        "should be written."
    )


def test_startup_migration_purges_legacy_rows(tmp_path, monkeypatch):
    """Upgraders arriving with an existing DB that has
    period='entity_profile' rows (produced by v0.5.0) must have those
    rows purged on open() so the MEMORIST-L4 benefit is immediate."""
    from truememory.engine import TrueMemoryEngine
    from truememory.storage import create_db

    # Simulate a v0.5.0 database with legacy rows.
    db_path = tmp_path / "legacy.db"
    conn = create_db(db_path)
    # Ensure summaries table exists with schema.
    conn.execute(
        "INSERT INTO summaries (entity, period, start_date, end_date, summary, message_ids) "
        "VALUES ('alice', 'entity_profile', '2026-01-01', '2026-03-01', "
        "'Entity Profile: alice. Lives in Boston, moved to Austin.', '[1,2,3,4,5]')"
    )
    conn.commit()
    conn.close()

    # Confirm the legacy row exists before open().
    conn2 = sqlite3.connect(str(db_path))
    pre = conn2.execute(
        "SELECT COUNT(*) FROM summaries WHERE period='entity_profile'"
    ).fetchone()[0]
    conn2.close()
    assert pre == 1, "Test setup: legacy row should exist before open()"

    # Open and let the migration run. Default = env not set.
    monkeypatch.delenv("TRUEMEMORY_ENTITY_SHEETS", raising=False)
    eng = TrueMemoryEngine(db_path).open(rebuild_vectors=False)
    eng.close()

    # Legacy row should be gone.
    conn3 = sqlite3.connect(str(db_path))
    post = conn3.execute(
        "SELECT COUNT(*) FROM summaries WHERE period='entity_profile'"
    ).fetchone()[0]
    conn3.close()
    assert post == 0, (
        f"MEMORIST-L4 migration should have purged legacy entity_profile "
        f"rows on open(); got {post} remaining."
    )


def test_startup_migration_skipped_when_re_enabled(tmp_path, monkeypatch):
    """If the user explicitly re-enables the feature, the purge should
    NOT run — their next consolidate() will rewrite the rows anyway."""
    from truememory.engine import TrueMemoryEngine
    from truememory.storage import create_db

    db_path = tmp_path / "reenabled.db"
    conn = create_db(db_path)
    conn.execute(
        "INSERT INTO summaries (entity, period, start_date, end_date, summary, message_ids) "
        "VALUES ('alice', 'entity_profile', '2026-01-01', '2026-03-01', "
        "'Entity Profile: alice.', '[1,2,3]')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("TRUEMEMORY_ENTITY_SHEETS", "1")
    eng = TrueMemoryEngine(db_path).open(rebuild_vectors=False)
    eng.close()

    conn2 = sqlite3.connect(str(db_path))
    rows = conn2.execute(
        "SELECT COUNT(*) FROM summaries WHERE period='entity_profile'"
    ).fetchone()[0]
    conn2.close()
    assert rows == 1, (
        "With TRUEMEMORY_ENTITY_SHEETS=1, migration should not purge; "
        "got %d rows (expected 1 preserved)." % rows
    )


def test_deprecation_warning_on_direct_call():
    """Calling build_entity_summary_sheets directly must emit a
    DeprecationWarning so future developers see the MEMORIST-L4 context
    without having to read the REPORT."""
    from truememory.consolidation import build_entity_summary_sheets
    from truememory.storage import create_db

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "warn.db"
        conn = create_db(db_path)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                build_entity_summary_sheets(conn)
            except Exception:
                # The function may raise on empty DB, but the warning
                # must already have been emitted at the top of the body.
                pass

        conn.close()

    dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert dep_warnings, (
        "build_entity_summary_sheets must emit DeprecationWarning when "
        "called directly (MEMORIST-L4)."
    )
    msg = str(dep_warnings[0].message)
    assert "MEMORIST-L4" in msg
    assert "TRUEMEMORY_ENTITY_SHEETS" in msg
