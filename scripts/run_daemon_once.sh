#!/usr/bin/env zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export LARK_CLI_NO_PROXY="${LARK_CLI_NO_PROXY:-1}"

if [[ -z "${OPENAI_API_KEY:-}" ]] && command -v security >/dev/null 2>&1; then
  account="${USER:-$(id -un)}"
  for service in openai_api_key openai-OPENAI_API_KEY OPENAI_API_KEY; do
    key="$(security find-generic-password -a "$account" -s "$service" -w 2>/dev/null || true)"
    if [[ -n "$key" ]]; then
      export OPENAI_API_KEY="$key"
      break
    fi
  done
fi

if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON:-python3}"
fi

cd "$REPO_ROOT"
exec "$PYTHON_BIN" "$REPO_ROOT/scripts/meeting_ingest.py" \
  --env-file "$REPO_ROOT/.env" \
  daemon-run \
  --once \
  "$@"
