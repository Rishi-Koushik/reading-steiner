#!/usr/bin/env bash
# HTML Notepad Launcher
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
exec python3 "$DIR/html_notepad.py" "$@"
