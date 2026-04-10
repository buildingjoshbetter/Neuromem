#!/bin/sh
# Neuromem installer — https://github.com/buildingjoshbetter/neuromem
#
# One-line install:
#   curl -LsSf https://raw.githubusercontent.com/buildingjoshbetter/neuromem/main/install.sh | sh
#
# What this does:
#   1. Installs uv (Astral's Python tool manager) if missing — uv brings its own
#      Python runtime, so your system Python is never touched.
#   2. Fetches a managed Python 3.12 into ~/.local/share/uv/python/.
#   3. Installs neuromem-core as an isolated uv tool.
#   4. Runs `neuromem-mcp --setup` (code from PyPI) to auto-configure
#      Claude Code and/or Claude Desktop. Set NEUROMEM_SKIP_SETUP=1 to skip.
#
# Environment overrides:
#   NEUROMEM_PY=3.12         # pin a specific Python (default: 3.12)
#   NEUROMEM_EXTRAS=mcp      # pip extras (default: mcp; use "gpu,mcp" for Pro)
#   NEUROMEM_SOURCE=...      # install from a local path or git URL instead of PyPI
#                            # (useful for testing: NEUROMEM_SOURCE=/path/to/neuromem)
#   NEUROMEM_SKIP_SETUP=1    # skip the Claude auto-config step
#
# Safety:
#   - No sudo required. Everything lands under $HOME.
#   - The script body is wrapped in a main() function, so a mid-download
#     network drop cannot execute partial logic — the file must parse
#     completely before anything runs.
#   - Source: https://github.com/buildingjoshbetter/neuromem/blob/main/install.sh
#     Read it first if you want: curl -LsSf <URL> -o install.sh && less install.sh

# ---------- pretty output helpers ----------
if [ -t 1 ]; then
  BLUE='\033[1;36m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'
  RED='\033[1;31m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'
else
  BLUE=''; GREEN=''; YELLOW=''; RED=''; BOLD=''; DIM=''; RESET=''
fi
say()  { printf '%b[neuromem]%b %s\n' "$BLUE"  "$RESET" "$*"; }
ok()   { printf '%b[neuromem]%b %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '%b[neuromem]%b %s\n' "$RED"   "$RESET" "$*" >&2; }
die()  { warn "error: $*"; exit 1; }

# ---------- main ----------
main() {
  set -eu

  NEUROMEM_PY="${NEUROMEM_PY:-3.12}"
  NEUROMEM_EXTRAS="${NEUROMEM_EXTRAS:-mcp}"
  NEUROMEM_SOURCE="${NEUROMEM_SOURCE:-}"

  # Defend against hostile env vars (e.g. a malicious "paste this" blog post).
  case "$NEUROMEM_PY" in
    ''|*[!0-9.]*)
      die "invalid NEUROMEM_PY: '$NEUROMEM_PY' (expected digits and dots, e.g. 3.12)" ;;
  esac
  case "$NEUROMEM_EXTRAS" in
    *[!a-zA-Z0-9,_-]*)
      die "invalid NEUROMEM_EXTRAS: '$NEUROMEM_EXTRAS' (expected names like 'mcp' or 'gpu,mcp')" ;;
  esac

  if [ -n "$NEUROMEM_SOURCE" ]; then
    PKG_SPEC="${NEUROMEM_SOURCE}[${NEUROMEM_EXTRAS}]"
    say "using custom source: $NEUROMEM_SOURCE"
  else
    PKG_SPEC="neuromem-core[${NEUROMEM_EXTRAS}]"
  fi

  # ---------- preflight ----------
  command -v curl >/dev/null 2>&1 || die "curl is required but not found on PATH"

  case "$(uname -s)" in
    Darwin|Linux) ;;
    *) die "unsupported OS: $(uname -s) — installer supports Mac and Linux. See README for Windows." ;;
  esac

  # Make sure common install dirs are on PATH for THIS shell so we can find
  # uv even if the user already has it but hasn't restarted their terminal.
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

  # ---------- step 1: install uv if missing ----------
  if command -v uv >/dev/null 2>&1; then
    say "uv already installed ($(uv --version 2>/dev/null || echo unknown))"
  else
    say "installing uv (Astral) — https://docs.astral.sh/uv/"
    # Astral's official installer — trusted source, same curl|sh pattern.
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || \
      die "uv install failed — try: curl -LsSf https://astral.sh/uv/install.sh | sh"
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    command -v uv >/dev/null 2>&1 || \
      die "uv installed but not on PATH — restart your shell and re-run this script"
  fi

  # ---------- step 2: ensure Python NEUROMEM_PY is available ----------
  say "fetching managed Python $NEUROMEM_PY (system Python untouched, ~30s on first run)..."
  # stderr is NOT suppressed — you see uv's progress output so a slow download
  # doesn't look like a frozen terminal.
  uv python install "$NEUROMEM_PY" >/dev/null || \
    die "failed to install managed Python $NEUROMEM_PY (see error above)"

  # ---------- step 3: install neuromem-core as a uv tool ----------
  say "installing $PKG_SPEC (~1-2 min on first run)..."
  # --force makes re-runs idempotent. --python pins the interpreter to avoid
  # astral-sh/uv#14110. stderr stays visible so you see real progress and errors.
  uv tool install --python "$NEUROMEM_PY" --force "$PKG_SPEC" >/dev/null || \
    die "neuromem-core install failed (see error above)"

  # Future shells should see ~/.local/bin. Reversible via 'uv tool update-shell --uninstall'.
  say "adding uv's tool dir to your shell rc (reversible)..."
  uv tool update-shell >/dev/null 2>&1 || true

  # ---------- step 4: auto-configure Claude ----------
  if [ "${NEUROMEM_SKIP_SETUP:-}" = "1" ]; then
    say "skipping Claude setup (NEUROMEM_SKIP_SETUP=1)"
  else
    say "configuring Claude Code / Claude Desktop..."
    # neuromem-mcp lives at ~/.local/bin/neuromem-mcp. Its sys.executable
    # resolves to the isolated tool venv, so Claude gets a stable absolute path.
    neuromem-mcp --setup || \
      warn "auto-setup returned non-zero (you can re-run it with: neuromem-mcp --setup)"
  fi

  # ---------- done ----------
  printf '\n'
  ok "neuromem-core installed."
  printf '\n'
  printf '  %b%bIMPORTANT — if Claude Desktop was already open:%b\n' "$YELLOW" "$BOLD" "$RESET"
  printf '    Quit it completely with %bCmd+Q%b and reopen it.\n' "$BOLD" "$RESET"
  printf '    A new chat window is NOT enough — the config only loads at launch.\n'
  printf '\n'
  printf '  %bNext:%b start a new Claude session and try:\n' "$GREEN" "$RESET"
  printf '    %b"remember that I prefer dark mode"%b\n' "$DIM" "$RESET"
  printf '    %b"what do you remember about me?"%b\n' "$DIM" "$RESET"
  printf '\n'
  printf '  %bCommands:%b\n' "$GREEN" "$RESET"
  printf '    neuromem-mcp --setup              %b# re-run Claude auto-config%b\n' "$DIM" "$RESET"
  printf '    uv tool upgrade neuromem-core     %b# update to latest%b\n' "$DIM" "$RESET"
  printf '    uv tool uninstall neuromem-core   %b# uninstall%b\n' "$DIM" "$RESET"
  printf '\n'
}

main "$@"
