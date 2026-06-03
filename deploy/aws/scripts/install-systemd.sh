#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if ! id zerodrift >/dev/null 2>&1; then
  useradd --system --home /var/lib/zerodrift-meetings --create-home --shell /usr/sbin/nologin zerodrift
fi

install -d -m 0755 /etc/systemd/system
install -m 0644 "$repo_root/deploy/aws/systemd/zdmeeting-ingest.service" /etc/systemd/system/zdmeeting-ingest.service
install -m 0644 "$repo_root/deploy/aws/systemd/zdmeeting-ingest.timer" /etc/systemd/system/zdmeeting-ingest.timer

install -d -m 0750 -o zerodrift -g zerodrift /var/lib/zerodrift-meetings
install -d -m 0750 -o zerodrift -g zerodrift /var/lib/zerodrift-meetings/inbox
install -d -m 0750 -o zerodrift -g zerodrift /var/lib/zerodrift-publisher/ObsidianVault
install -d -m 0750 -o zerodrift -g zerodrift "/var/lib/zerodrift-publisher/ObsidianVault/ZeroDrift Material Library/sources/meetings"
install -d -m 0750 -o zerodrift -g zerodrift "/var/lib/zerodrift-publisher/ObsidianVault/ZeroDrift Wiki/raw/internal"
install -d -m 0750 -o root -g root /etc/zerodrift-meetings

systemctl daemon-reload
echo "Installed ZeroDrift meeting transcript systemd units."
