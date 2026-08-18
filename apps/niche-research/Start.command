#!/bin/bash
# macOS launcher — double-click to open the Niche Research START window.
# (First time, if macOS blocks it: right-click → Open, then confirm.)
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 niche_research_gui.py
else
  echo "Python 3 not found. Install it from https://www.python.org/downloads/"
  read -r -p "Press Enter to close..."
fi
