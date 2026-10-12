#!/bin/sh
# Rebuild everything from data/raw: question bank JSON, review list, and the playable page.
#   sh build.sh          -> data/questions.json, data/wr_history.json, data/review.csv, site/index.html
#   sh build.sh --xlsx   -> also data/photo-finish-bank.xlsx (needs: pip install openpyxl)
set -e
cd "$(dirname "$0")"
python3 scripts/build.py
python3 scripts/export_game.py
if [ "$1" = "--xlsx" ]; then python3 scripts/make_xlsx.py; fi
