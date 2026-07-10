#!/bin/bash
# update-all.sh — refresh all JS data files from CSVs + live prices
# Run this after updating any CSV file in src/data/
# Usage: ./update-all.sh

set -e
cd "$(dirname "$0")"

PYTHON=".venv/bin/python3"
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi

echo "════════════════════════════════════════"
echo "  Emerytura — full data refresh"
echo "════════════════════════════════════════"

echo ""
echo "▶ Portfolio prices + returns data (update-prices.py)..."
$PYTHON update-prices.py

echo ""
echo "▶ WIG index history (update-wig.py)..."
$PYTHON update-wig.py

echo ""
echo "════════════════════════════════════════"
echo "  ✓ All done — hard-refresh the browser"
echo "════════════════════════════════════════"
