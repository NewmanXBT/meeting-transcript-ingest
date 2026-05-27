#!/usr/bin/env zsh
set -euo pipefail

LABEL="${LABEL:-com.zerodrift.meeting-transcript-ingest}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"

echo "Uninstalled $LABEL"
