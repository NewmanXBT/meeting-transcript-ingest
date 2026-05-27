#!/usr/bin/env zsh
set -euo pipefail

LABEL="${LABEL:-com.zerodrift.meeting-transcript-ingest}"
launchctl print "gui/$(id -u)/$LABEL"
