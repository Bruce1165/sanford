#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$SCRIPT_DIR/com.neotrade2.cpolar_watchdog.plist"
SERVICE_NAME="com.neotrade2.cpolar_watchdog"

mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$LAUNCHD_DIR"

if launchctl list | grep -q "$SERVICE_NAME"; then
  launchctl bootout "gui/$(id -u)" "$SERVICE_NAME" 2>/dev/null || true
  sleep 1
fi

cp "$PLIST_FILE" "$LAUNCHD_DIR/$SERVICE_NAME.plist"
launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_DIR/$SERVICE_NAME.plist"
launchctl kickstart -k "gui/$(id -u)/$SERVICE_NAME"

launchctl list | grep "$SERVICE_NAME" || true

