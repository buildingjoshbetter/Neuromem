# Contributing to TrueMemory

Thanks for your interest in contributing.

## Architecture Overview

TrueMemory uses a 6-layer memory pipeline. Each layer is implemented as a
standalone module in `truememory/`:

| Layer | Name | Module(s) |
|-------|------|-----------|
| L0 | Personality Engram | `personality.py` — entity profiles, communication patterns, preferences |
| L1 | Working Memory | Deferred (not yet implemented) |
| L2 | Episodic | `fts_search.py` — FTS5 keyword search + temporal filtering |
| L3 | Semantic | `vector_search.py`, `hybrid.py` — dense vectors (Model2Vec or Qwen3 by tier) + RRF fusion |
| L4 | Salience Guard | `salience.py` — noise filtering + entity boosting |
| L5 | Consolidation | `consolidation.py`, `predictive.py` — summaries, contradiction resolution, predictive coding |

The orchestrator (`engine.py`) ties all layers together with graceful
degradation — if any module is missing or fails, the engine falls back to
whatever layers are available.

### Ingest Subpackage

The `truememory/ingest/` subpackage provides automatic memory capture via
Claude Code hooks. It includes:

- `extractor.py` — LLM-based memory extraction from conversation transcripts
- `encoding_gate.py` — biomimetic filtering that decides what is worth storing
- `dedup.py` — deduplication against existing memories
- `pipeline.py` — end-to-end ingestion orchestrator
- `hooks/` — Claude Code hook scripts for automatic capture

Ingest depends on `truememory` core for storage and search but can be
installed and run independently.

## Getting Started

1. Fork the repo and clone locally.
2. Create a virtualenv: `python -m venv .venv && source .venv/bin/activate`
3. Install in dev mode: `pip install -e ".[all,dev]"`
4. Run tests: `pytest tests/ -v`
5. Run linter: `ruff check truememory/`

## Code Style

- Add type hints to all public function signatures.
- Use `logging` instead of `print` for diagnostic output.
- Keep modules focused — one layer per file.
- Docstrings on public classes and functions (Google style preferred).
- No star imports (`from module import *`).

## Pull Requests

- One feature/fix per PR.
- Include a clear description of what changed and why.
- Run `ruff check truememory/` and `pytest tests/ -v` before submitting.

## Reporting Issues

Use [GitHub Issues](https://github.com/buildingjoshbetter/TrueMemory/issues).
Include your Python version, OS, and steps to reproduce.

## License

By contributing, you agree that your contributions will be licensed under
the [AGPL-3.0 License](LICENSE).
