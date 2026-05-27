#!/usr/bin/env zsh
set -euo pipefail

LABEL="${LABEL:-com.zerodrift.meeting-transcript-ingest}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-3600}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNNER="$REPO_ROOT/scripts/run_daemon_once.sh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$REPO_ROOT/logs"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR" "$REPO_ROOT/inbox" "$REPO_ROOT/state"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$RUNNER</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO_ROOT</string>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>$INTERVAL_SECONDS</integer>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/daemon.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/daemon.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$HOME/.npm-global/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>LARK_CLI_NO_PROXY</key>
    <string>1</string>
  </dict>
</dict>
</plist>
PLIST

chmod +x "$RUNNER"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"
launchctl kickstart -k "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true

echo "Installed $LABEL"
echo "Plist: $PLIST"
echo "Logs: $LOG_DIR/daemon.out.log and $LOG_DIR/daemon.err.log"
