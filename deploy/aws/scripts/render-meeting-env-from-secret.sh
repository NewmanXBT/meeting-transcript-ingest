#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
ZERODRIFT_MEETING_SECRET_ID="${ZERODRIFT_MEETING_SECRET_ID:-zerodrift/notify/lark}"
ZERODRIFT_MEETING_ENV_FILE="${ZERODRIFT_MEETING_ENV_FILE:-/etc/zerodrift-meetings/env}"
ZERODRIFT_OBSIDIAN_ROOT="${ZERODRIFT_OBSIDIAN_ROOT:-/var/lib/zerodrift-publisher/ObsidianVault}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required" >&2
  exit 1
fi

secret_string="$(
  aws secretsmanager get-secret-value \
    --region "$AWS_REGION" \
    --secret-id "$ZERODRIFT_MEETING_SECRET_ID" \
    --query SecretString \
    --output text
)"

env_body="$(
  SECRET_STRING="$secret_string" python3 - <<'PY'
import json
import os
import sys

try:
    parsed = json.loads(os.environ.get("SECRET_STRING", "{}"))
except json.JSONDecodeError:
    print("Meeting secret must be a JSON object", file=sys.stderr)
    raise SystemExit(2)

allowed = [
    "LARK_API_BASE",
    "LARK_APP_ID",
    "LARK_APP_SECRET",
    "LARK_ACCESS_TOKEN",
    "FEISHU_APP_ID",
    "FEISHU_APP_SECRET",
    "FEISHU_ACCESS_TOKEN",
]

lines = []
for key in allowed:
    value = parsed.get(key) or parsed.get(key.lower())
    if value is None or str(value).strip() == "":
        continue
    text = str(value).strip()
    if "\n" in text or "\r" in text:
        print(f"{key} contains a newline, refusing to write EnvironmentFile", file=sys.stderr)
        raise SystemExit(3)
    lines.append(f"{key}={text}")

has_app = any(line.startswith("LARK_APP_ID=") for line in lines) and any(
    line.startswith("LARK_APP_SECRET=") for line in lines
)
has_token = any(line.startswith("LARK_ACCESS_TOKEN=") or line.startswith("FEISHU_ACCESS_TOKEN=") for line in lines)
if not has_app and not has_token:
    print("No Lark app credentials or access token found in meeting secret", file=sys.stderr)
    raise SystemExit(4)

print("\n".join(sorted(lines)))
PY
)"

install -d -m 0750 -o root -g root "$(dirname "$ZERODRIFT_MEETING_ENV_FILE")"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

{
  printf '%s\n' "$env_body"
  printf 'MEETING_AUTO_SUMMARIZE=1\n'
  printf 'MEETING_SUMMARY_BACKEND=bedrock\n'
  printf 'MEETING_NOTES_MODEL=deepseek.v3.2\n'
  printf 'MEETING_BEDROCK_REGION=%s\n' "$AWS_REGION"
  printf 'MEETING_SUMMARY_MAX_CHARS=120000\n'
  printf 'MEETING_SUMMARY_MAX_OUTPUT_TOKENS=2400\n'
  printf 'LARK_BACKEND=api\n'
  printf 'LARK_REGION=lark\n'
  printf 'LARK_API_BASE=https://open.larksuite.com\n'
  printf 'LOOKBACK_HOURS=72\n'
  printf 'LARK_PAGE_SIZE=20\n'
  printf 'GOOGLE_AUTO=0\n'
  printf 'MEETING_INBOX_DIR=/var/lib/zerodrift-meetings/inbox\n'
  printf 'OBSIDIAN_SOURCES_DIR=%s/ZeroDrift Material Library/sources/meetings\n' "$ZERODRIFT_OBSIDIAN_ROOT"
  printf 'OBSIDIAN_INTERNAL_DIR=%s/ZeroDrift Wiki/raw/internal\n' "$ZERODRIFT_OBSIDIAN_ROOT"
} > "$tmp"

install -m 0600 -o root -g root "$tmp" "$ZERODRIFT_MEETING_ENV_FILE"
echo "Rendered $ZERODRIFT_MEETING_ENV_FILE from Secrets Manager secret $ZERODRIFT_MEETING_SECRET_ID"
