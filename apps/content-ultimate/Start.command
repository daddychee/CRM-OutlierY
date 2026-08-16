#!/bin/bash
# ============================================================
# CONTENT ULTIMATE — nut Start: mo giao dien web (trong trinh duyet).
# Double-click file nay trong Finder (hoac chay ./Start.command).
#
# Trang chu co 2 khoi:
#   1. Outline Board  — dan URL video cung song → tick chon → outline.txt
#   2. Author Extract — Extractor (ban thao → ho so giong)
#                       + Writer (nap outline tu board → kich ban theo giong)
# ============================================================
cd "$(dirname "$0")"

if [ ! -x .venv/bin/content-ultimate ]; then
  echo "Chua cai tool. Dang cai (co fastembed — hoi lau lan dau)..."
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/pip install -q -e ".[dev,llm,embed]" || {
    echo "LOI cai dat."; read -r -p "Nhan Enter de dong..." _; exit 1; }
fi

exec .venv/bin/content-ultimate
