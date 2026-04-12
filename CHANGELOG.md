# Changelog

## [0.3.0] - 2026-04-11

### Changed
- **Renamed the package from `neuromem` / `neuromem-core` to `truememory`.** The import path, PyPI dist name, console scripts (`truememory-mcp`, `truememory-ingest`), environment variables (`TRUEMEMORY_*`), runtime data directory (`~/.truememory/`), MCP server slug (`truememory`), and wire-format tags (`<truememory-context>`) all moved to the new name. See MIGRATION notes below if you're upgrading from 0.2.x.
- Moved `mcp[cli]` and `httpx` from the `[mcp]` optional extra into the core `dependencies` list so `pip install truememory && truememory-mcp --setup` works on the first run. The `[mcp]` extra is kept as a no-op alias for backwards compatibility.

### Fixed
- Aligned version string across `pyproject.toml`, `truememory/__init__.py`, `truememory/ingest/__init__.py`, `CITATION.cff`, and the README bibtex. Previously four of these were stuck at 0.2.0 while the code was tagged 0.2.2.
- Rebranded the `_SAURON_BANNER` ASCII splash in `truememory/ingest/cli.py` that was missed by the initial sed pass (its letters were separated by spaces, which evaded the contiguous `neuromem` regex).
- Rebranded all 10 chart PNGs in `assets/charts/` (hero-banner, leaderboard, accuracy-vs-cost, category-radar, category-heatmap, category-grouped-bars, cost-per-answer, latency-comparison, hardware-matrix, eval-pipeline). Re-rendered from the original design HTML sources with TrueMemory branding; coloring, typography, grid, grain, and layout preserved exactly.
- Fixed two label overlaps in the parallel-category-coordinates chart (Temporal axis EverMemOS label was colliding with TrueMemory Pro's dot; Single-hop axis Mem0 label was sitting on the descending line toward Multi-hop).

### Migration from 0.2.x (`neuromem-core`)
- Uninstall the old package: `pip uninstall neuromem-core`
- Install the new one: `pip install truememory`
- Update imports: `from neuromem import Memory` → `from truememory import Memory`
- Update class references: `NeuromemEngine` → `TrueMemoryEngine`
- Update environment variables: `NEUROMEM_*` → `TRUEMEMORY_*`
- Your existing data at `~/.neuromem/` is not automatically migrated — either move it manually to `~/.truememory/` or start fresh
- Re-register the MCP server in Claude Code: `claude mcp remove neuromem && truememory-mcp --setup`

## [0.2.0] - 2026-04-03

### Added
- 9 data visualizations (hero banner, leaderboard bar chart, accuracy vs cost scatter, cost per answer, category radar, latency, hardware matrix, eval pipeline diagram, per-category grouped bars)
- `assets/charts/` directory with chart HTML sources and rendered PNGs
- `benchmarks/` directory with full LoCoMo evaluation against 8 memory systems
- Independent benchmark scripts for each competitor (self-contained, reproducible on Modal)
- Complete result JSONs with per-question answers, judge votes, and latency data
- BENCHMARK_RESULTS.md with cost analysis, latency comparison, and hardware requirements
- LICENSE file (Apache 2.0)
- CHANGELOG.md

### Changed
- Visual README overhaul: hero banner, emoji section headers, highlight badges, embedded charts
- License changed from MIT to Apache 2.0
- Updated README benchmark section: 8 competitors (was 4), best scores across runs
- TrueMemory Pro: 91.5% on LoCoMo
- TrueMemory Base: 88.2% on LoCoMo

### Benchmark Results
- 8 systems evaluated on LoCoMo (1,540 questions each, 12,320 total) with identical answer model, judge, scoring, top-k, and prompt
- TrueMemory Pro: 91.5%, TrueMemory Base: 88.2%
- All runs completed with zero API errors

## [0.1.3] - 2026-03-28

### Added
- TRUEMEMORY_EMBED_MODEL environment variable for tier selection
- GPU optional dependency (`pip install truememory[gpu]`)

## [0.1.2] - 2026-03-27

### Added
- Incremental entity profile building for MCP/add() workflow

## [0.1.1] - 2026-03-26

### Added
- Initial release of truememory
- 6-layer memory pipeline: FTS5, vector search, temporal, salience, personality, consolidation
- Base tier (Model2Vec) and Pro tier (Qwen3) embedding support
- MCP server for Claude integration
- Simple Memory API (Mem0-compatible interface)
