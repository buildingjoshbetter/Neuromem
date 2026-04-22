"""CLI flag handling for `truememory-mcp`.

Regression tests for the v0.4.1 fix to the --help hang bug: without this
handling, any unknown argument (including --help) fell through to
mcp.run(transport="stdio") which blocks on stdin forever, making
`pip install truememory && truememory-mcp --help` hang.
"""
from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

from truememory import __version__


def _truememory_mcp_bin() -> str | None:
    """Locate the installed truememory-mcp console script, or None.

    Prefer the script installed by pip. Fall back to invoking via
    `python -m truememory.mcp_server` — slower because it re-runs all
    module-level imports, but works in any environment where truememory
    is importable.
    """
    return shutil.which("truememory-mcp")


def _run_cli(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    bin_path = _truememory_mcp_bin()
    if bin_path:
        cmd = [bin_path] + args
    else:
        cmd = [sys.executable, "-m", "truememory.mcp_server"] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def test_help_long_flag_exits_cleanly():
    """`truememory-mcp --help` must exit 0 with usage text, not hang."""
    result = _run_cli(["--help"])
    assert result.returncode == 0, f"non-zero exit: {result.returncode}\nstderr: {result.stderr}"
    assert "Usage: truememory-mcp" in result.stdout, f"stdout missing usage line:\n{result.stdout}"
    assert "--setup" in result.stdout
    assert "--version" in result.stdout


def test_help_short_flag_exits_cleanly():
    """`truememory-mcp -h` must behave identically to --help."""
    result = _run_cli(["-h"])
    assert result.returncode == 0, f"non-zero exit: {result.returncode}\nstderr: {result.stderr}"
    assert "Usage: truememory-mcp" in result.stdout


def test_version_flag_prints_current_version():
    """`truememory-mcp --version` must print the exact package version and exit 0."""
    result = _run_cli(["--version"])
    assert result.returncode == 0, f"non-zero exit: {result.returncode}\nstderr: {result.stderr}"
    assert __version__ in result.stdout, f"stdout missing version {__version__}:\n{result.stdout}"


def test_version_short_flag_prints_current_version():
    """`truememory-mcp -V` must behave identically to --version."""
    result = _run_cli(["-V"])
    assert result.returncode == 0, f"non-zero exit: {result.returncode}\nstderr: {result.stderr}"
    assert __version__ in result.stdout


@pytest.mark.skipif(not shutil.which("truememory-mcp"), reason="console script not on PATH")
def test_help_via_console_script_does_not_hang():
    """Explicit end-to-end test via the installed console script.

    This is the exact invocation a user would type after `pip install truememory`.
    Uses a tight 15s timeout because the fix should return in milliseconds;
    a hang would mean the --help handling regressed back into the mcp.run() path.
    """
    result = subprocess.run(
        ["truememory-mcp", "--help"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    assert "Usage:" in result.stdout
