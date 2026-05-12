#!/bin/bash

set -e

SERVICE_NAME="com.neotrade2.cpolar_watchdog"
PLIST_PATH="$HOME/Library/LaunchAgents/$SERVICE_NAME.plist"

launchctl bootout "gui/$(id -u)" "$SERVICE_NAME" 2>/dev/null || true
rm -f "$PLIST_PATH"
launchctl list | grep "$SERVICE_NAME" || true

