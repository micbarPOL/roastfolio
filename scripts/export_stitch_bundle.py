#!/usr/bin/env python3
"""
scripts/export_stitch_bundle.py — Export Roastfolio UI Screens & CSS for Google Stitch

Generates modular, screen-specific HTML components, clean design tokens,
dedicated screen CSS, and full-page high-resolution PNG screenshots with
fully populated component data (no loaders or empty states) ready to upload or
paste into Google Stitch (stitch.withgoogle.com).
"""

from __future__ import annotations

import datetime
import http.server
import json
import math
import os
import re
import socketserver
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "exports" / "stitch"
SCREENSHOTS_DIR = EXPORT_DIR / "screenshots"


def extract_design_tokens() -> str:
    """Extract core design tokens and variables from src/styles/main.css."""
    main_css_path = ROOT / "src" / "styles" / "main.css"
    content = main_css_path.read_text(encoding="utf-8")

    # Extract :root variables and base styles
    root_match = re.search(r"(:root\s*\{[^}]+\})", content)
    light_match = re.search(r"(:root\[data-theme=\"light\"\]\s*\{[^}]+\})", content)

    tokens = [
        "/* ═════════════════════════════════════════════════════════════════",
        "   Roastfolio Core Design Tokens for Google Stitch",
        "   ═════════════════════════════════════════════════════════════════ */",
        "",
        root_match.group(1) if root_match else "",
        "",
        light_match.group(1) if light_match else "",
        "",
        "/* Core Card & Typography Foundations */",
        "body {",
        "    font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;",
        "    background: #050e18;",
        "    color: #eef7ff;",
        "}",
        "",
        ".dash-card, .wallet-card, .fintech-card, .mini-chart-section, .table-container {",
        "    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);",
        "    border: 1px solid rgba(0, 242, 254, 0.2);",
        "    border-radius: 20px;",
        "    padding: 24px;",
        "    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);",
        "}",
        "",
        ".brand-logo {",
        "    width: 48px;",
        "    height: 48px;",
        "    border-radius: 12px;",
        "    border: 1px solid rgba(0, 242, 254, 0.3);",
        "    box-shadow: 0 2px 8px rgba(0, 242, 254, 0.15);",
        "}",
        "",
        ".accent-cyan { color: #00f2fe; }",
        ".accent-green { color: #4ade80; }",
        ".accent-red { color: #f87171; }",
        ".accent-purple { color: #a855f7; }",
    ]
    return "\n".join(tokens)


def extract_portfolio_css() -> str:
    """Extract clean, dedicated styles for the Portfolio screen."""
    return """/* ═════════════════════════════════════════════════════════════════
   Roastfolio — Portfolio Screen CSS (Breakdown & Holdings)
   ═════════════════════════════════════════════════════════════════ */

/* ── Mini Charts Grid (Donut Breakdown) ── */
.mini-charts-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    padding: 0 0 24px;
}

#portfolio-composition-container {
    grid-column: 1 / -1;
}

.mini-chart-section {
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);
    border: 1px solid rgba(0, 242, 254, 0.2);
    border-radius: 20px;
    padding: 24px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

.mini-chart-section h3 {
    margin: 0 0 16px;
    color: #eef7ff;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 700;
}

.pie-wrapper-mini {
    position: relative;
    width: 100%;
    height: 220px;
}

#portfolio-composition-container .pie-wrapper-mini {
    height: 320px;
}

#portfolio-composition-container .pie-with-legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 30px;
}

/* ── Interactive Pie Legends ── */
.pie-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    justify-content: center;
    max-width: 600px;
}

.legend-item {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: rgba(14, 165, 233, 0.06);
    border: 1px solid rgba(14, 165, 233, 0.18);
    border-radius: 8px;
    font-size: 12px;
    color: #cbd5e1;
    font-family: 'SF Mono', 'Fira Code', monospace;
    cursor: pointer;
    transition: background 0.2s, border-color 0.2s;
}

.legend-item:hover {
    background: rgba(14, 165, 233, 0.15);
    border-color: rgba(0, 242, 254, 0.4);
}

.legend-color-bar {
    width: 4px;
    height: 14px;
    border-radius: 2px;
}

.legend-text {
    font-weight: 500;
}

.legend-pct {
    font-weight: 700;
    color: #00f2fe;
}

/* ── Holdings Section & Tabs ── */
.table-container {
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);
    border: 1px solid rgba(0, 242, 254, 0.2);
    border-radius: 20px;
    padding: 24px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

.tx-section-title {
    font-size: 18px;
    font-weight: 700;
    color: #eef7ff;
    letter-spacing: 0.5px;
    margin-bottom: 16px;
}

.holdings-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}

.holdings-tab-btn {
    padding: 8px 16px;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(14, 165, 233, 0.2);
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    color: #94a3b8;
    transition: all 0.2s;
    font-family: 'SF Mono', 'Fira Code', monospace;
}

.holdings-tab-btn:hover {
    background: rgba(14, 165, 233, 0.12);
    color: #00f2fe;
    border-color: rgba(0, 242, 254, 0.4);
}

.holdings-tab-btn.active {
    background: rgba(0, 242, 254, 0.15);
    color: #eef7ff;
    border-color: #00f2fe;
    box-shadow: 0 0 12px rgba(0, 242, 254, 0.25);
}

.holdings-content {
    display: none;
    overflow-x: auto;
    width: 100%;
}

.holdings-content.active {
    display: block;
}

/* ── Holdings Table ── */
.holdings-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    table-layout: auto;
}

.holdings-table thead th {
    position: sticky;
    top: 0;
    z-index: 2;
    background: rgba(8, 21, 38, 0.95);
    color: #94a3b8;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-family: 'SF Mono', 'Fira Code', monospace;
    padding: 12px 14px;
    border-bottom: 1px solid rgba(0, 242, 254, 0.2);
    text-align: right;
}

.holdings-table thead th:first-child {
    text-align: left;
}

.holdings-table tbody td {
    padding: 12px 14px;
    font-size: 13px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    color: #e2e8f0;
    text-align: right;
    vertical-align: middle;
}

.holdings-table tbody td:first-child {
    text-align: left;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-weight: 600;
}

.holdings-table tbody tr:hover {
    background: rgba(0, 242, 254, 0.05);
}

.accent-green { color: #34d399 !important; }
.accent-red   { color: #f87171 !important; }
.text-muted   { color: #94a3b8 !important; }

/* ── Responsive Mobile ── */
@media (max-width: 900px) {
    .mini-charts-grid {
        grid-template-columns: 1fr;
    }
    .hide-on-mobile {
        display: none;
    }
}
"""


def extract_statistics_css() -> str:
    """Extract clean, dedicated styles for the Statistics screen."""
    return """/* ═════════════════════════════════════════════════════════════════
   Roastfolio — Statistics Screen CSS
   ═════════════════════════════════════════════════════════════════ */

/* ── Statistics Sections & Cards ── */
.stats-section {
    background: linear-gradient(145deg, #0f172a 0%, #020617 100%);
    border: 1px solid rgba(14, 165, 233, 0.2);
    border-radius: 16px;
    box-shadow: 
        inset 0 0 20px rgba(14, 165, 233, 0.05),
        0 8px 32px rgba(0, 0, 0, 0.5),
        0 0 10px rgba(14, 165, 233, 0.1);
    position: relative;
    overflow: hidden;
    padding: 24px 28px;
    margin: 20px 0;
}

.stats-section h2 {
    margin: 0 0 18px;
    font-size: 1.1rem;
    color: #00f0ff;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid rgba(14, 165, 233, 0.2);
    padding-bottom: 10px;
    text-shadow: 0 0 8px rgba(0, 240, 255, 0.3);
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
}

.stat-card {
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border-radius: 12px;
    padding: 16px 18px;
    border-left: 4px solid #00f0ff;
    box-shadow: inset 0 0 10px rgba(14, 165, 233, 0.05);
}

.stat-label {
    font-size: 0.75rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
}

.stat-value {
    font-size: 1.25rem;
    font-weight: 700;
    color: #e2e8f0;
}

.stat-sub {
    font-size: 0.8rem;
    color: #94a3b8;
    margin-top: 4px;
}

/* ── Stats Accordions ── */
.stats-acc-section {
    padding: 0;
    overflow: hidden;
}

.stats-acc-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 28px;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 1.1rem;
    font-weight: 600;
    color: #e2e8f0;
    text-align: left;
    border-bottom: 1px solid rgba(14, 165, 233, 0.2);
}

.stats-acc-btn:hover {
    background: rgba(14, 165, 233, 0.05);
}

.stats-acc-preview {
    font-size: 0.85rem;
    font-weight: normal;
    color: #94a3b8;
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
    padding-right: 12px;
}

.stats-acc-preview-badge {
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: bold;
}

.stats-acc-preview-badge.bm-score-good { background-color: rgba(39, 174, 96, 0.15); color: #27ae60; }
.stats-acc-preview-badge.bm-score-mid  { background-color: rgba(212, 172, 42, 0.15); color: #d4ac2a; }
.stats-acc-preview-badge.bm-score-bad  { background-color: rgba(192, 57, 43, 0.15); color: #c0392b; }

.stats-acc-arrow {
    flex-shrink: 0;
    color: #888;
    transition: transform 0.22s ease;
    transform: rotate(0deg);
}

.stats-acc-body {
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.28s ease, padding 0.22s ease;
    padding: 0 28px;
}

.stats-acc-body--open {
    max-height: 9999px;
    padding: 16px 28px 24px;
}

/* ── Benchmark Comparison Table ── */
.bm-scroll {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin-top: 4px;
}

.bm-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    white-space: nowrap;
    color: #e2e8f0;
}

.bm-th {
    padding: 7px 10px;
    background: #0f172a;
    color: #e2e8f0;
    font-weight: 600;
    text-align: right;
    letter-spacing: 0.3px;
    position: sticky;
    top: 0;
    z-index: 2;
}

.bm-th-month  { text-align: left; position: sticky; left: 0; z-index: 3; }
.bm-th-port   { text-align: right; position: sticky; left: 110px; z-index: 3; }
.bm-th-score  { background: #020617; }

.bm-td {
    padding: 5px 10px;
    text-align: right;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-variant-numeric: tabular-nums;
}

.bm-td.bm-month {
    text-align: left;
    font-weight: 500;
    position: sticky;
    left: 0;
    background: #0f172a;
    z-index: 1;
    min-width: 108px;
    color: #e2e8f0;
}

.bm-td.bm-port {
    position: sticky;
    left: 110px;
    background: #0f172a;
    z-index: 1;
    font-weight: 700;
    border-right: 2px solid rgba(255,255,255,0.1);
    min-width: 80px;
    color: #e2e8f0;
}

.bm-td.bm-win  { background: rgba(52, 211, 153, 0.10); }
.bm-td.bm-loss { background: rgba(248, 113, 113, 0.10); }
.bm-td.bm-na   { color: #64748b; background: rgba(255,255,255,0.02); }
.bm-icon       { font-size: 10px; margin-right: 2px; }
.bm-td.bm-win  .bm-icon { color: #34d399; }
.bm-td.bm-loss .bm-icon { color: #f87171; }

.bm-diff {
    display: block;
    font-size: 10px;
    color: #94a3b8;
    margin-top: 1px;
}

.bm-score { font-weight: 700; min-width: 48px; }
.bm-score-good { color: #34d399; }
.bm-score-mid  { color: #fbbf24; }
.bm-score-bad  { color: #f87171; }

/* ── Underwater Lakes ── */
.uwl-controls-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
    margin-bottom: 18px;
}

.uwl-stat-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}

.uwl-stat-card {
    position: relative;
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.85) 0%, rgba(5, 14, 24, 0.95) 100%);
    border: 1px solid rgba(0, 242, 254, 0.18);
    border-radius: 16px;
    padding: 16px 20px;
    overflow: hidden;
}

.uwl-stat-card-depth::after { border-color: rgba(248, 113, 113, 0.4); }
.uwl-stat-card-width::after { border-color: rgba(56, 189, 248, 0.4); }

.uwl-stat-eyebrow {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #94a3b8;
    font-family: 'SF Mono', 'Fira Code', monospace;
    margin-bottom: 6px;
}

.uwl-stat-value {
    font-size: 24px;
    font-weight: 700;
    color: #eef7ff;
    letter-spacing: -0.02em;
}

.uwl-stat-meta {
    font-size: 12px;
    color: #64748b;
    margin-top: 4px;
}

.uwl-chart-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
}

.uwl-chart-panel {
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);
    border: 1px solid rgba(0, 242, 254, 0.16);
    border-radius: 16px;
    padding: 16px;
    display: flex;
    flex-direction: column;
}

.uwl-chart-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
}

.uwl-chart-title {
    font-size: 13px;
    font-weight: 600;
    color: #cbd5e1;
    margin: 0;
}

.uwl-lake-pill {
    font-size: 11px;
    color: #00f2fe;
    background: rgba(0, 242, 254, 0.08);
    border: 1px solid rgba(0, 242, 254, 0.2);
    border-radius: 999px;
    padding: 3px 10px;
}

.uwl-chart-wrap {
    position: relative;
    height: 220px;
    width: 100%;
}

/* ── Monthly Performance Heatmap ── */
.heatmap-scroll-wrap {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}

.heatmap-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 12px;
}

.heatmap-table th {
    padding: 8px 12px;
    background: rgba(15, 23, 42, 0.95);
    color: #94a3b8;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.06em;
    border-bottom: 1px solid rgba(0, 242, 254, 0.2);
    text-align: center;
}

.heatmap-th-month, .heatmap-td-month {
    text-align: left !important;
    font-weight: 600;
    color: #e2e8f0;
}

.heatmap-cell {
    padding: 8px 12px;
    text-align: center;
    border-radius: 6px;
    transition: transform 0.15s, box-shadow 0.15s;
    font-weight: 600;
}

.heatmap-cell:hover {
    transform: scale(1.05);
    z-index: 2;
    box-shadow: 0 0 12px rgba(0, 242, 254, 0.35);
}

.history-wallet-btns {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.history-wallet-btn {
    padding: 6px 14px;
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(14, 165, 233, 0.2);
    color: #94a3b8;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
    font-family: 'SF Mono', 'Fira Code', monospace;
}

.history-wallet-btn.is-active {
    background: rgba(0, 242, 254, 0.15);
    border-color: #00f2fe;
    color: #eef7ff;
    box-shadow: 0 0 10px rgba(0, 242, 254, 0.25);
}

@media (max-width: 900px) {
    .uwl-chart-grid,
    .uwl-stat-grid {
        grid-template-columns: 1fr;
    }
}
"""


def extract_retirement_css() -> str:
    """Extract clean, dedicated styles for the Retirement Forecast & FIRE screen."""
    return """/* ═════════════════════════════════════════════════════════════════
   Roastfolio — Retirement Screen CSS (Forecast & FIRE Simulation)
   ═════════════════════════════════════════════════════════════════ */

.retirement-screen {
    display: grid;
    gap: 16px;
    padding: 12px 12px 28px;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

.retirement-layout {
    display: grid;
    gap: 16px;
    grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.9fr);
    align-items: start;
}

.retirement-card {
    background: linear-gradient(180deg, rgba(15, 28, 42, 0.98), rgba(8, 18, 28, 0.98));
    color: #eef7ff;
    border: 1px solid rgba(0, 242, 254, 0.2);
    border-radius: 24px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    padding: 24px;
    overflow: hidden;
}

.retirement-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 16px;
}

.retirement-hero-card {
    display: grid;
    gap: 16px;
}

.retirement-hero-copy .mgmt-section-title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #00f2fe;
    font-weight: 700;
    margin-bottom: 6px;
}

.retirement-hero-copy .wallet-panel-title {
    font-size: 22px;
    font-weight: 700;
    color: #eef7ff;
    margin: 0 0 8px;
}

.retirement-hero-subtitle {
    margin: 0;
    font-size: 13px;
    color: #94a3b8;
    line-height: 1.5;
}

.retirement-hero-meta {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
}

.retirement-insight-pill {
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(0, 242, 254, 0.08);
    border: 1px solid rgba(0, 242, 254, 0.25);
    color: #00f2fe;
    font-size: 12px;
    font-family: 'SF Mono', 'Fira Code', monospace;
}

.retirement-action-bar {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.mgmt-btn {
    padding: 8px 18px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
    border: 1px solid transparent;
}

.mgmt-btn-primary {
    background: #00f2fe;
    color: #050e18;
    box-shadow: 0 0 16px rgba(0, 242, 254, 0.4);
}

.mgmt-btn-primary:hover {
    background: #4ef6ff;
    box-shadow: 0 0 22px rgba(0, 242, 254, 0.6);
}

.mgmt-btn-secondary {
    background: rgba(15, 23, 42, 0.8);
    border-color: rgba(14, 165, 233, 0.3);
    color: #cbd5e1;
}

.mgmt-btn-secondary:hover {
    border-color: #00f2fe;
    color: #eef7ff;
}

/* ── Warning & Notice Banners ── */
.retirement-warning-banner {
    padding: 14px 18px;
    border-radius: 14px;
    background: rgba(248, 113, 113, 0.12);
    border: 1px solid rgba(248, 113, 113, 0.35);
    color: #fca5a5;
    font-size: 13px;
    display: flex;
    gap: 8px;
    align-items: center;
}

/* ── Projection Chart Panel ── */
.retirement-chart-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.retirement-range-btns {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.retirement-range-btn {
    padding: 6px 14px;
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(14, 165, 233, 0.2);
    color: #94a3b8;
    font-size: 12px;
    cursor: pointer;
    font-family: 'SF Mono', 'Fira Code', monospace;
}

.retirement-range-btn.is-active {
    background: rgba(0, 242, 254, 0.15);
    border-color: #00f2fe;
    color: #eef7ff;
    box-shadow: 0 0 10px rgba(0, 242, 254, 0.25);
}

.retirement-chart-controls {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    background: rgba(8, 18, 30, 0.6);
    border: 1px solid rgba(14, 165, 233, 0.15);
    border-radius: 12px;
    padding: 12px 16px;
}

.retirement-chart-control-label {
    font-size: 11px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-family: 'SF Mono', 'Fira Code', monospace;
}

.retirement-chart-meta {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
}

.retirement-mini-stat {
    background: rgba(10, 22, 38, 0.6);
    border: 1px solid rgba(0, 242, 254, 0.15);
    border-radius: 12px;
    padding: 12px 14px;
}

.retirement-mini-stat-label {
    font-size: 11px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    display: block;
    margin-bottom: 4px;
}

.retirement-mini-stat strong {
    font-size: 16px;
    color: #eef7ff;
    font-family: 'SF Mono', 'Fira Code', monospace;
}

.retirement-chart-wrapper {
    position: relative;
    height: 420px;
    width: 100%;
}

.retirement-chart-footnote {
    font-size: 11px;
    color: #64748b;
    line-height: 1.5;
}

/* ── Summary & Form Grid ── */
.retirement-summary-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
}

.retirement-stat-card {
    background: rgba(10, 22, 38, 0.7);
    border: 1px solid rgba(0, 242, 254, 0.15);
    border-radius: 14px;
    padding: 14px 16px;
}

.mgmt-input {
    width: 100%;
    padding: 8px 12px;
    background: rgba(8, 18, 30, 0.85);
    border: 1px solid rgba(14, 165, 233, 0.25);
    border-radius: 8px;
    color: #eef7ff;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 13px;
    box-sizing: border-box;
}

.mgmt-input:focus {
    outline: none;
    border-color: #00f2fe;
    box-shadow: 0 0 10px rgba(0, 242, 254, 0.3);
}

@media (max-width: 1100px) {
    .retirement-layout {
        grid-template-columns: 1fr;
    }
}
"""


def extract_transactions_css() -> str:
    """Extract clean, dedicated styles for the Transactions screen."""
    return """/* ═════════════════════════════════════════════════════════════════
   Roastfolio — Transactions Screen CSS
   ═════════════════════════════════════════════════════════════════ */

/* ── Summary Bar & Turnover Cards ── */
.tx-summary-bar {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin: 0 0 20px;
}

.tx-stat-card {
    flex: 1;
    min-width: 220px;
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);
    border: 1px solid rgba(0, 242, 254, 0.2);
    border-radius: 16px;
    padding: 18px 22px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

.tx-section-title {
    font-size: 13px;
    font-weight: 700;
    color: #00f2fe;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    margin: 0 0 16px;
    text-shadow: 0 0 8px rgba(0, 242, 254, 0.3);
}

/* ── Activity Calendar & Legend ── */
.tx-activity-card {
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);
    border: 1px solid rgba(0, 242, 254, 0.2);
    border-radius: 20px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

.cal-legend-swatch {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 3px;
    vertical-align: middle;
}

.cal-i1 { background-color: rgba(14, 165, 233, 0.2); }
.cal-i2 { background-color: rgba(14, 165, 233, 0.4); }
.cal-i3 { background-color: rgba(14, 165, 233, 0.6); }
.cal-i4 { background-color: rgba(14, 165, 233, 0.8); }
.cal-i5 { background-color: #00f2fe; box-shadow: 0 0 6px rgba(0, 242, 254, 0.8); }

.cal-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 20px 24px;
}

.cal-month {
    font-size: 12px;
}

.cal-month-name {
    font-weight: 700;
    color: #94a3b8;
    margin-bottom: 6px;
    font-size: 13px;
    font-family: 'SF Mono', 'Fira Code', monospace;
}

.cal-dow-row {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    margin-bottom: 4px;
}

.cal-dow {
    text-align: center;
    font-size: 10px;
    color: #64748b;
    font-weight: 600;
}

.cal-days {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 3px;
}

.cal-day {
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    font-size: 10px;
    color: #64748b;
    background: rgba(14, 165, 233, 0.05);
    cursor: default;
}

.cal-day.empty {
    background: transparent;
}

.cal-day.cal-active {
    font-weight: 700;
    color: #050e18;
    cursor: pointer;
}

/* ── Turnover Chart ── */
.tx-chart-section {
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);
    border: 1px solid rgba(0, 242, 254, 0.2);
    border-radius: 20px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

/* ── History Table & Filters ── */
.tx-history-card {
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);
    border: 1px solid rgba(0, 242, 254, 0.2);
    border-radius: 20px;
    padding: 24px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    overflow-x: auto;
}

.col-filter {
    display: block;
    width: 100%;
    margin-top: 4px;
    padding: 4px 8px;
    font-size: 11px;
    border: 1px solid rgba(14, 165, 233, 0.4);
    border-radius: 6px;
    background: #0f172a;
    color: #e2e8f0;
    box-sizing: border-box;
}

.filter-btn {
    display: inline-block;
    margin-top: 4px;
    padding: 4px 8px;
    font-size: 11px;
    border: 1px solid rgba(14, 165, 233, 0.4);
    border-radius: 6px;
    background: #0f172a;
    color: #e2e8f0;
    cursor: pointer;
}

/* ── Operation Badges ── */
.tx-op-badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    font-family: 'SF Mono', 'Fira Code', monospace;
    background: color-mix(in srgb, var(--tx-op-color, #94a3b8) 16%, transparent);
    color: var(--tx-op-color, #94a3b8);
    border: 1px solid color-mix(in srgb, var(--tx-op-color, #94a3b8) 35%, transparent);
}
"""


def extract_coping_diary_css() -> str:
    """Extract clean, dedicated styles for the Coping Diary screen."""
    return """/* ═════════════════════════════════════════════════════════════════
   Roastfolio — Coping Diary Screen CSS (Conviction & Emotional Ledger)
   ═════════════════════════════════════════════════════════════════ */

.diary-split {
    display: grid;
    grid-template-columns: minmax(320px, 36%) minmax(0, 64%);
    gap: 16px;
    min-height: 560px;
}

.diary-pane {
    border: 1px solid rgba(127, 143, 164, 0.25);
    border-radius: 20px;
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    overflow: hidden;
}

.diary-pane-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(127, 143, 164, 0.2);
}

.diary-pane-head strong {
    font-size: 15px;
    font-weight: 700;
    color: #eef7ff;
}

.diary-ledger-list {
    padding: 12px;
    display: grid;
    gap: 10px;
    max-height: 72vh;
    overflow-y: auto;
}

.diary-ledger-card {
    border: 1px solid rgba(127, 143, 164, 0.3);
    border-radius: 14px;
    background: rgba(10, 22, 38, 0.55);
    padding: 14px;
    cursor: pointer;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.diary-ledger-card:hover {
    transform: translateY(-2px);
    border-color: rgba(168, 85, 247, 0.7);
    box-shadow: 0 4px 16px rgba(168, 85, 247, 0.2);
}

.diary-ledger-card.is-selected {
    border-color: #a855f7;
    box-shadow: 0 0 0 1px #a855f7, 0 4px 20px rgba(168, 85, 247, 0.25);
    background: rgba(168, 85, 247, 0.08);
}

.diary-ledger-card.is-inactive {
    filter: grayscale(0.6) opacity(0.7);
}

.diary-inactive-pill {
    display: inline-block;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 999px;
    background: #1e293b;
    color: #94a3b8;
    border: 1px solid #334155;
}

.diary-badge {
    display: inline-block;
    border: 1px solid rgba(127, 143, 164, 0.45);
    border-radius: 999px;
    padding: 2px 8px;
    font-size: 11px;
    font-family: 'SF Mono', 'Fira Code', monospace;
}

.diary-tags-cloud {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    padding: 4px 0 12px;
}

.diary-tags-cloud .match {
    background: rgba(168, 85, 247, 0.18);
    border-color: rgba(168, 85, 247, 0.85);
    color: #d9b8ff;
}

.diary-detail-body {
    padding: 20px;
    display: grid;
    gap: 16px;
}

/* ── Interactive Glass Toggle ── */
.diary-glass-toggle {
    position: relative;
    width: 56px;
    height: 30px;
    display: inline-block;
}

.diary-glass-toggle input {
    opacity: 0;
    width: 0;
    height: 0;
}

.diary-glass-slider {
    position: absolute;
    inset: 0;
    border-radius: 999px;
    background: #1f2937;
    transition: all 0.25s ease;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.diary-glass-slider:before {
    content: "";
    position: absolute;
    height: 24px;
    width: 24px;
    left: 3px;
    top: 3px;
    border-radius: 50%;
    background: #eef2ff;
    transition: all 0.25s ease;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
}

.diary-glass-toggle input:checked + .diary-glass-slider {
    background: #a855f7;
    box-shadow: 0 0 16px rgba(168, 85, 247, 0.7);
}

.diary-glass-toggle input:checked + .diary-glass-slider:before {
    transform: translateX(26px);
}

/* ── Coping Chat & Checklist ── */
.coping-chat-container {
    max-height: 240px;
    overflow-y: auto;
    display: grid;
    gap: 8px;
}

.coping-chat-entry {
    display: grid;
    gap: 4px;
}

.coping-chat-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}

.coping-chat-date {
    display: block;
    font-size: 11px;
    color: #8ea1bb;
}

.coping-chat-text {
    margin: 0;
    font-size: 14px;
    line-height: 1.4;
    color: #e2e8f0;
}

.coping-chat-actions {
    display: flex;
    gap: 8px;
    align-items: center;
}

.coping-chat-edit-row {
    display: flex;
    gap: 8px;
    align-items: center;
}

.diary-toggle-status {
    font-size: 12px;
    color: #cbd5e1;
    min-width: 66px;
    text-align: right;
}

.diary-chat-compose {
    display: flex;
    gap: 8px;
}

.diary-chat-compose input {
    flex: 1;
    min-width: 0;
}

.diary-amber-pulse {
    animation: diaryPulse 1.6s ease-in-out infinite;
}

.diary-check-item {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 10px;
    align-items: center;
    padding: 10px 14px;
    border: 1px solid rgba(127, 143, 164, 0.25);
    border-radius: 10px;
    background: rgba(8, 20, 33, 0.35);
}

.diary-ledger-filter {
    width: 100%;
    border: 1px solid rgba(127, 143, 164, 0.45);
    border-radius: 8px;
    padding: 8px;
    background: transparent;
    color: inherit;
}

.diary-mention {
    color: #5aa0ff;
    font-weight: 700;
    text-decoration: underline;
    cursor: pointer;
    white-space: nowrap;
    background: none;
    border: none;
    padding: 0;
}

@keyframes diaryPulse {
    0%, 100% { box-shadow: 0 0 0 rgba(245, 158, 11, 0.15); }
    50% { box-shadow: 0 0 20px rgba(245, 158, 11, 0.45); }
}

@keyframes diaryCardIn {
    from { opacity: 0.3; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 980px) {
    .diary-split {
        grid-template-columns: 1fr;
    }
}
"""


def extract_analysis_css() -> str:
    """Extract clean, dedicated styles for the Analysis & Fundamentals screen."""
    return """/* ═════════════════════════════════════════════════════════════════
   Roastfolio — Asset Analysis & Fundamentals Screen CSS
   ═════════════════════════════════════════════════════════════════ */

.analysis-container {
    padding: 0 0 24px;
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.analysis-favorites-container {
    display: flex;
    align-items: center;
    gap: 12px;
    overflow-x: auto;
    padding: 4px 2px 14px;
    -webkit-overflow-scrolling: touch;
}

.analysis-favorite-pill {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);
    border: 1px solid rgba(0, 242, 254, 0.2);
    border-radius: 14px;
    cursor: pointer;
    transition: all 0.2s;
    font-family: 'SF Mono', 'Fira Code', monospace;
    white-space: nowrap;
}

.analysis-favorite-pill:hover,
.analysis-favorite-pill.is-active {
    border-color: #00f2fe;
    box-shadow: 0 0 16px rgba(0, 242, 254, 0.3);
    background: rgba(0, 242, 254, 0.08);
}

.analysis-card {
    background: linear-gradient(135deg, rgba(8, 21, 38, 0.7) 0%, rgba(5, 14, 24, 0.9) 100%);
    border: 1px solid rgba(0, 242, 254, 0.2);
    border-radius: 20px;
    padding: 24px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

.analysis-price-chart-wrap {
    position: relative;
    height: 380px;
    width: 100%;
}

.analysis-grid-props {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 14px;
}

.analysis-prop-card {
    background: rgba(10, 22, 38, 0.6);
    border: 1px solid rgba(0, 242, 254, 0.15);
    border-radius: 12px;
    padding: 12px 14px;
}
"""



def wrap_html_shell(title: str, inner_html: str, extra_css: str | None = None) -> str:
    """Wrap component HTML in a standalone preview shell for Google Stitch."""
    extra_link = f'    <link rel="stylesheet" href="{extra_css}">' if extra_css else ""
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <title>Roastfolio — {title}</title>
    <link rel="stylesheet" href="../../src/styles/main.css">
    <link rel="stylesheet" href="00_design_tokens.css">
{extra_link}
    <style>
        /* Scoped layout wrapper for Google Stitch preview */
        body {{
            margin: 0;
            padding: 24px;
            background-color: #050e18;
            color: #eef7ff;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        .stitch-screen-container {{
            max-width: 1280px;
            margin: 0 auto;
        }}
    </style>
</head>
<body>
    <div class="stitch-screen-container">
        <!-- SCREEN: {title} -->
        {inner_html}
    </div>
</body>
</html>
"""


class SilentHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def build_mock_datasets():
    """Build rich synthetic datasets for realistic screenshots and populated DOMs."""
    base_wig = 82000.0
    base_wig_date = datetime.date(2026, 4, 1)
    today_bars_wig = []
    for i in range(120):
        d = base_wig_date + datetime.timedelta(days=i)
        if d.weekday() >= 5:
            continue
        day_str = d.isoformat()
        val = round(base_wig + (i * 45) + (150 * math.sin(i / 5)), 2)
        today_bars_wig.append({
            "t": day_str,
            "o": round(val - 30, 2),
            "h": round(val + 80, 2),
            "l": round(val - 60, 2),
            "c": val,
            "v": 150000 + (i * 200)
        })

    hourly_wig = []
    for h in range(24):
        ts = 1789000000 + h * 3600
        val = round(86500.0 + (h * 15) + (50 * (h % 3 - 1)), 2)
        hourly_wig.append({
            "t": ts,
            "o": val - 10,
            "h": val + 25,
            "l": val - 20,
            "c": val,
            "v": 20000
        })

    base_aapl_date = datetime.date(2025, 9, 23)
    today_bars_aapl = []
    for i in range(250):
        d = base_aapl_date + datetime.timedelta(days=i)
        if d.weekday() >= 5:
            continue
        day_str = d.isoformat()
        val = round(185.0 + (i * 0.22) + 6.0 * math.sin(i / 8), 2)
        today_bars_aapl.append({
            "t": day_str,
            "o": round(val - 1.2, 2),
            "h": round(val + 2.4, 2),
            "l": round(val - 1.8, 2),
            "c": val,
            "v": 48000000 + (i * 25000)
        })

    holdings_xtb = [
        {
            "holdingId": "h-aapl",
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "units": 100,
            "pricePLN": 945.20,
            "priceOriginal": 236.30,
            "priceOriginalCurrency": "USD",
            "purchaseValue": 70000.00,
            "currentValue": 94520.00,
            "dailyChangePLN": 1620.00,
            "dailyChangePct": 1.74,
            "ytdChangePct": 22.8,
            "profit": 24520.00,
            "returnPct": 35.03,
            "gainLossPLN": 24520.00,
            "gainLossPct": 35.03,
            "todayBars": [930, 932, 938, 942, 945.2],
            "yearBars": [780, 810, 850, 910, 945.2],
            "volume": 48200000,
            "avgVolume": 52000000,
            "volumeTz": "America/New_York",
            "pct": 45.35,
        },
        {
            "holdingId": "h-xtb",
            "ticker": "XTB.WA",
            "name": "XTB S.A.",
            "units": 1200,
            "pricePLN": 68.40,
            "priceOriginal": 68.40,
            "priceOriginalCurrency": "PLN",
            "purchaseValue": 54000.00,
            "currentValue": 82080.00,
            "dailyChangePLN": 1680.00,
            "dailyChangePct": 2.09,
            "ytdChangePct": 41.2,
            "profit": 28080.00,
            "returnPct": 52.00,
            "gainLossPLN": 28080.00,
            "gainLossPct": 52.00,
            "todayBars": [67.0, 67.2, 67.8, 68.1, 68.4],
            "yearBars": [48.0, 52.0, 58.0, 64.0, 68.4],
            "volume": 320000,
            "avgVolume": 290000,
            "volumeTz": "Europe/Warsaw",
            "pct": 39.38,
        },
        {
            "holdingId": "h-cash-xtb",
            "ticker": "CASH",
            "name": "Cash (PLN)",
            "units": 31820.50,
            "pricePLN": 1.00,
            "priceOriginal": 1.00,
            "priceOriginalCurrency": "PLN",
            "purchaseValue": 31820.50,
            "currentValue": 31820.50,
            "dailyChangePLN": 0.0,
            "dailyChangePct": 0.0,
            "ytdChangePct": 0.0,
            "profit": 0.0,
            "returnPct": 0.0,
            "gainLossPLN": 0.0,
            "gainLossPct": 0.0,
            "todayBars": [],
            "yearBars": [],
            "volume": 0,
            "avgVolume": 0,
            "pct": 15.27,
            "isCash": True,
        }
    ]

    holdings_ike = [
        {
            "holdingId": "h-msft",
            "ticker": "MSFT",
            "name": "Microsoft Corporation",
            "units": 50,
            "pricePLN": 1820.00,
            "priceOriginal": 455.00,
            "priceOriginalCurrency": "USD",
            "purchaseValue": 72000.00,
            "currentValue": 91000.00,
            "dailyChangePLN": 980.00,
            "dailyChangePct": 1.09,
            "ytdChangePct": 18.5,
            "profit": 19000.00,
            "returnPct": 26.39,
            "gainLossPLN": 19000.00,
            "gainLossPct": 26.39,
            "todayBars": [1800, 1805, 1812, 1818, 1820],
            "yearBars": [1540, 1620, 1710, 1780, 1820],
            "volume": 21000000,
            "avgVolume": 24000000,
            "volumeTz": "America/New_York",
            "pct": 64.95,
        },
        {
            "holdingId": "h-cdr",
            "ticker": "CDR.WA",
            "name": "CD Projekt S.A.",
            "units": 160,
            "pricePLN": 172.50,
            "priceOriginal": 172.50,
            "priceOriginalCurrency": "PLN",
            "purchaseValue": 29000.00,
            "currentValue": 27600.00,
            "dailyChangePLN": -260.20,
            "dailyChangePct": -0.93,
            "ytdChangePct": 8.4,
            "profit": -1400.00,
            "returnPct": -4.83,
            "gainLossPLN": -1400.00,
            "gainLossPct": -4.83,
            "todayBars": [174.0, 173.5, 173.0, 172.8, 172.5],
            "yearBars": [140.0, 155.0, 180.0, 165.0, 172.5],
            "volume": 180000,
            "avgVolume": 210000,
            "volumeTz": "Europe/Warsaw",
            "pct": 19.70,
        },
        {
            "holdingId": "h-cash-ike",
            "ticker": "CASH",
            "name": "Cash (IKE)",
            "units": 21500.00,
            "pricePLN": 1.00,
            "priceOriginal": 1.00,
            "priceOriginalCurrency": "PLN",
            "purchaseValue": 21500.00,
            "currentValue": 21500.00,
            "dailyChangePLN": 0.0,
            "dailyChangePct": 0.0,
            "ytdChangePct": 0.0,
            "profit": 0.0,
            "returnPct": 0.0,
            "gainLossPLN": 0.0,
            "gainLossPct": 0.0,
            "todayBars": [],
            "yearBars": [],
            "volume": 0,
            "avgVolume": 0,
            "pct": 15.35,
            "isCash": True,
        }
    ]

    all_holdings = holdings_xtb + holdings_ike

    prices_payload = {
        "updatedAt": "2026-09-23 17:30:00",
        "portfolioTotalValue": 348520.50,
        "portfolioDailyChangePLN": 4820.30,
        "portfolioDailyChangePCT": 1.40,
        "portfolioAth": {
            "portfolioId": "summary",
            "athValue": 352100.00,
            "athDate": "2026-09-18",
            "athSource": "AUTO"
        },
        "walletAths": {
            "Summary": {"athValue": 352100.00, "athDate": "2026-09-18", "athSource": "AUTO"},
            "XTB Brokerage": {"athValue": 210000.00, "athDate": "2026-09-18", "athSource": "AUTO"},
            "IKE Retirement": {"athValue": 142100.00, "athDate": "2026-09-18", "athSource": "AUTO"}
        },
        "walletPortfolioIds": {
            "XTB Brokerage": "p-xtb",
            "IKE Retirement": "p-ike"
        },
        "walletSummaries": {
            "Summary": {"total": 348520.50, "dailyPLN": 4820.30, "dailyPct": 1.40, "ath": 352100.00},
            "XTB Brokerage": {"total": 208420.50, "dailyPLN": 3150.20, "dailyPct": 1.53, "ath": 210000.00},
            "IKE Retirement": {"total": 140100.00, "dailyPLN": 1670.10, "dailyPct": 1.21, "ath": 142100.00}
        },
        "walletHoldings": {
            "Summary": all_holdings,
            "XTB Brokerage": holdings_xtb,
            "IKE Retirement": holdings_ike
        },
        "portfolioData": all_holdings,
        "benchmarkId": "WIG",
        "benchmarkName": "WIG",
        "benchmarkDailyPct": 0.85,
        "wigDailyPct": 0.85,
        "benchmarkData": {
            "daily": today_bars_wig,
            "hourly": hourly_wig,
            "intraday": hourly_wig,
            "updated": "2026-09-23"
        },
        "marketCarousel": [
            {"id": "WIG", "name": "WIG", "changePct": 0.85, "sparkline": [85200, 85400, 85600, 85900, 86200]},
            {"id": "WIG20", "name": "WIG20", "changePct": 1.12, "sparkline": [2410, 2420, 2425, 2435, 2442]},
            {"id": "SP500", "name": "S&P 500", "changePct": 0.65, "sparkline": [5810, 5825, 5830, 5845, 5860]},
            {"id": "NASDAQ", "name": "NASDAQ", "changePct": 1.05, "sparkline": [18200, 18250, 18310, 18380, 18420]},
            {"id": "DAX", "name": "DAX", "changePct": -0.22, "sparkline": [19400, 19380, 19360, 19340, 19350]},
            {"id": "MSCI_WORLD", "name": "MSCI World", "changePct": 0.48, "sparkline": [3710, 3715, 3720, 3725, 3730]}
        ],
        "roastData": {
            "message": "You beat the benchmark today. Enjoy the delusion before the next drawdown hits.",
            "tone": "praise",
            "scenarioKey": "benchmark_beat_modest",
            "templateId": "bm_win_1"
        }
    }

    sample_snapshots = []
    val = 200000.0
    inv = 180000.0
    for yr in (2024, 2025, 2026):
        for mo in range(1, 13):
            if yr == 2026 and mo > 9:
                break
            dt = f"{yr}-{mo:02d}-01"
            val += 5000 + (val * 0.012)
            inv += 4000
            sample_snapshots.append({
                "snapshotDate": dt,
                "portfolioValue": round(val, 2),
                "investmentValue": round(inv, 2),
                "unitPrice": round(val / 1000, 2),
                "cumulativeReturnPct": round((val - inv) / inv * 100, 2),
                "xirr": 14.8,
                "twr": round((val - inv) / inv * 100, 2),
            })

    transactions_xtb = [
        {"transactionId": "tx-1", "portfolioId": "p-xtb", "transactionDate": "2026-09-18", "date": "2026-09-18", "type": "BUY", "operation": "BUY", "ticker": "AAPL", "name": "Apple Inc.", "quantity": 10, "units": 10, "price": 945.20, "value": 9452.00, "commission": 0.0, "currency": "PLN"},
        {"transactionId": "tx-2", "portfolioId": "p-xtb", "transactionDate": "2026-09-10", "date": "2026-09-10", "type": "BUY", "operation": "BUY", "ticker": "XTB.WA", "name": "XTB S.A.", "quantity": 200, "units": 200, "price": 68.40, "value": 13680.00, "commission": 0.0, "currency": "PLN"},
        {"transactionId": "tx-3", "portfolioId": "p-xtb", "transactionDate": "2026-08-25", "date": "2026-08-25", "type": "DIVIDEND", "operation": "Dividend", "ticker": "XTB.WA", "name": "XTB S.A.", "quantity": 0, "units": 0, "price": 0.0, "value": 1840.00, "commission": 0.0, "currency": "PLN"},
        {"transactionId": "tx-4", "portfolioId": "p-xtb", "transactionDate": "2026-08-01", "date": "2026-08-01", "type": "DEPOSIT", "operation": "Deposit", "ticker": None, "name": "Deposit", "quantity": 1, "units": 1, "price": 5000.00, "value": 5000.00, "commission": 0.0, "currency": "PLN"},
        {"transactionId": "tx-5", "portfolioId": "p-ike", "transactionDate": "2026-07-22", "date": "2026-07-22", "type": "BUY", "operation": "BUY", "ticker": "MSFT", "name": "Microsoft Corporation", "quantity": 15, "units": 15, "price": 1820.00, "value": 27300.00, "commission": 0.0, "currency": "PLN"},
        {"transactionId": "tx-6", "portfolioId": "p-xtb", "transactionDate": "2026-06-14", "date": "2026-06-14", "type": "SELL", "operation": "SELL", "ticker": "CDR.WA", "name": "CD Projekt S.A.", "quantity": 50, "units": 50, "price": 175.00, "value": 8750.00, "commission": 0.0, "currency": "PLN"},
        {"transactionId": "tx-7", "portfolioId": "p-xtb", "transactionDate": "2026-05-02", "date": "2026-05-02", "type": "DEPOSIT", "operation": "Deposit", "ticker": None, "name": "Deposit", "quantity": 1, "units": 1, "price": 5000.00, "value": 5000.00, "commission": 0.0, "currency": "PLN"},
        {"transactionId": "tx-8", "portfolioId": "p-xtb", "transactionDate": "2026-04-12", "date": "2026-04-12", "type": "BUY", "operation": "BUY", "ticker": "AAPL", "name": "Apple Inc.", "quantity": 20, "units": 20, "price": 890.00, "value": 17800.00, "commission": 0.0, "currency": "PLN"},
    ]

    diary_entries = [
        {
            "note_id": "note-aapl",
            "ticker": "AAPL",
            "title": "Apple Inc. (AAPL)",
            "topic": "Apple Inc.",
            "note_text": "Long-term Apple ecosystem thesis. Services growth, recurring high-margin revenue, and Apple Intelligence roll-out. #HOLD #TECH #CONVICTION",
            "user_tags": ["#HOLD", "#TECH", "#CONVICTION"],
            "linked_assets": ["AAPL"],
            "is_active": True,
            "created_at": "2026-04-10T10:00:00Z",
            "updated_at": "2026-09-18T14:30:00Z",
            "hypothesis": {
                "why_buy": "Unmatched customer lock-in and high free cash flow conversion. Capital return program through steady buybacks.",
                "exit_plan": "Exit if Services gross margin contracts below 65% for 3 consecutive quarters.",
                "risk_factors": "Antitrust scrutiny in EU and US App Store fees.",
            },
            "hypothesis_checkpoints": [
                {"checkpoint_id": "cp-1", "title": "Check Services revenue YoY growth > 12%", "due_date": "2026-10-30", "checked": True},
                {"checkpoint_id": "cp-2", "title": "Review iPhone 17 supercycle upgrade rate", "due_date": "2026-11-15", "checked": False},
            ],
            "comments": [
                {"comment_id": "c-1", "text": "Q3 earnings confirmed Services acceleration (+14% YoY). Holding steady with conviction.", "created_at": "2026-08-02T16:00:00Z"},
            ],
        },
        {
            "note_id": "note-nvda",
            "ticker": "NVDA",
            "title": "NVIDIA Corporation (NVDA)",
            "topic": "NVIDIA Corporation",
            "note_text": "Datacenter AI infrastructure leadership. Blackwell architecture transition. #AI #GROWTH",
            "user_tags": ["#AI", "#GROWTH"],
            "linked_assets": ["NVDA"],
            "is_active": True,
            "created_at": "2026-05-15T09:00:00Z",
            "updated_at": "2026-08-28T11:20:00Z",
            "hypothesis": {
                "why_buy": "Full stack hardware + software (CUDA) moat. Hyperscaler capex remains elevated.",
            },
            "hypothesis_checkpoints": [
                {"checkpoint_id": "cp-3", "title": "Monitor hyperscaler capex guidance", "due_date": "2026-10-25", "checked": True},
            ],
            "comments": [],
        },
        {
            "note_id": "note-xtb",
            "ticker": "XTB.WA",
            "title": "XTB S.A. (XTB.WA)",
            "topic": "XTB S.A.",
            "note_text": "High dividend fintech broker expanding internationally into social trading and bond offerings. #DIVIDEND #FINTECH",
            "user_tags": ["#DIVIDEND", "#FINTECH"],
            "linked_assets": ["XTB.WA"],
            "is_active": True,
            "created_at": "2026-06-01T12:00:00Z",
            "updated_at": "2026-09-15T09:00:00Z",
            "hypothesis": {
                "why_buy": "Scalable software model with strong dividend payout policy (75%+ of net profit).",
            },
            "hypothesis_checkpoints": [],
            "comments": [],
        },
    ]

    return {
        "prices_payload": prices_payload,
        "holdings_xtb": holdings_xtb,
        "holdings_ike": holdings_ike,
        "sample_snapshots": sample_snapshots,
        "transactions_xtb": transactions_xtb,
        "today_bars_aapl": today_bars_aapl,
        "diary_entries": diary_entries,
    }


def capture_bundle(port: int):
    """Capture full-page PNG screenshots & fully populated screen HTMLs via Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[!] Playwright not installed. Skipping screenshots.")
        return

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    datasets = build_mock_datasets()
    prices_payload = datasets["prices_payload"]
    holdings_xtb = datasets["holdings_xtb"]
    holdings_ike = datasets["holdings_ike"]
    sample_snapshots = datasets["sample_snapshots"]
    transactions_xtb = datasets["transactions_xtb"]
    today_bars_aapl = datasets["today_bars_aapl"]
    diary_entries = datasets["diary_entries"]

    print(f"[*] Capturing fully rendered screens & HTML via Playwright on port {port}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})

        def mock_router(route, request):
            url = request.url
            if "/prices" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(prices_payload))
                return
            if url.endswith("/portfolios"):
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "portfolios": [
                        {"portfolioId": "summary", "name": "Total Portfolio", "currency": "PLN", "isSummary": True},
                        {"portfolioId": "p-xtb", "name": "XTB Brokerage", "type": "broker", "currency": "PLN", "order": 1, "total": 208420.50, "dailyPLN": 3150.20, "dailyPct": 1.53},
                        {"portfolioId": "p-ike", "name": "IKE Retirement", "type": "ike", "currency": "PLN", "order": 2, "total": 140100.00, "dailyPLN": 1670.10, "dailyPct": 1.21},
                    ]
                }))
                return
            if "/portfolios/p-xtb" in url and not any(k in url for k in ("/snapshots", "/transactions", "/holdings")):
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "portfolioId": "p-xtb",
                    "name": "XTB Brokerage",
                    "currency": "PLN",
                    "holdings": holdings_xtb,
                    "transactions": transactions_xtb,
                    "closedHoldings": [
                        {"holdingId": "h-closed-nvda", "ticker": "NVDA", "name": "NVIDIA Corporation", "closedDate": "2026-07-15", "realizedGainPLN": 8420.00, "returnPct": 42.1}
                    ]
                }))
                return
            if "/portfolios/p-ike" in url and not any(k in url for k in ("/snapshots", "/transactions", "/holdings")):
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "portfolioId": "p-ike",
                    "name": "IKE Retirement",
                    "currency": "PLN",
                    "holdings": holdings_ike,
                    "transactions": [],
                    "closedHoldings": []
                }))
                return
            if "/snapshots" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"snapshots": sample_snapshots}))
                return
            if "/transactions" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"transactions": transactions_xtb}))
                return
            if "/holdings" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"holdings": holdings_xtb}))
                return
            if "/ath" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "portfolioId": "summary", "athValue": 352100.00, "athDate": "2026-09-18", "athSource": "AUTO"
                }))
                return
            if "/profile" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "role": "ADVANCED",
                    "settings": {"benchmark": "WIG", "roast_intensity": "spicy", "notification_emails": ["investor@roastfolio.com"]}
                }))
                return
            if "/benchmarks" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "benchmarks": [
                        {"id": "WIG", "name": "WIG (Warsaw Stock Exchange)"},
                        {"id": "SP500", "name": "S&P 500 (US Large-Cap)"},
                        {"id": "NASDAQ", "name": "NASDAQ Composite"},
                        {"id": "DAX", "name": "DAX 40 (Germany)"},
                        {"id": "MSCI_WORLD", "name": "MSCI World"}
                    ]
                }))
                return
            if "/benchmark-returns" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "benchmarks": [
                        {"id": "WIG", "name": "WIG", "returnPct": 2.4, "status": "overtaken"},
                        {"id": "SP500", "name": "S&P 500", "returnPct": 1.8, "status": "overtaken"},
                        {"id": "NASDAQ", "name": "NASDAQ", "returnPct": 3.1, "status": "lost"},
                        {"id": "DAX", "name": "DAX", "returnPct": -0.5, "status": "overtaken"},
                        {"id": "MSCI_WORLD", "name": "MSCI World", "returnPct": 1.2, "status": "overtaken"}
                    ],
                    "score": "4 / 5 Overtaken"
                }))
                return
            if "/benchmark-daily" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "benchmarkId": "SP500", "dailyPct": 1.15, "price": 5860.20
                }))
                return
            if "/retirement-plans" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"plans": []}))
                return
            if "/favorites" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "favorites": [
                        {"ticker": "AAPL", "name": "Apple Inc."},
                        {"ticker": "MSFT", "name": "Microsoft Corporation"},
                        {"ticker": "CDR.WA", "name": "CD Projekt S.A."}
                    ]
                }))
                return
            if "/asset-analysis" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "ticker": "AAPL",
                    "history": today_bars_aapl,
                    "fundamentals": {
                        "sector": "Technology",
                        "industry": "Consumer Electronics",
                        "marketCap": 3450000000000,
                        "trailingPE": 32.4,
                        "forwardPE": 28.1,
                        "dividendYield": 0.0052,
                        "fiftyTwoWeekHigh": 237.23,
                        "fiftyTwoWeekLow": 164.08,
                        "longName": "Apple Inc."
                    },
                    "cashflow": {"freeCashFlow": 108000000000, "operatingCashFlow": 118000000000},
                    "financials": {"totalRevenue": 385000000000, "netIncome": 101000000000},
                    "earnings": [{"quarter": "Q1 2026", "eps": 2.18, "revenue": 119500000000}],
                    "transactions": [{"date": "2026-06-15", "type": "BUY", "price": 880.0, "units": 25}]
                }))
                return
            if "/diary" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"notes": diary_entries, "entries": diary_entries}))
                return
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True}))

        context.route("**/*.amazonaws.com/**", mock_router)
        page = context.new_page()

        # ── 1. Dashboard Screen ─────────────────────────────────────────
        page.goto(f"http://127.0.0.1:{port}/src/index.html?devAuth=1")
        page.wait_for_timeout(2000)

        page.evaluate("""() => {
            const splash = document.getElementById('splash-screen');
            if (splash) splash.remove();
            document.body.classList.remove('splash-active', 'splash-to-gauge');
            if (window.AuthGuard) window.AuthGuard.getRole = () => 'ADVANCED';
            document.querySelectorAll('.is-loading, .is-fetching-data').forEach(el => {
                el.classList.remove('is-loading', 'is-fetching-data');
            });
            const emptyModal = document.getElementById('dash-empty-state');
            if (emptyModal) emptyModal.style.display = 'none';

            window.BENCHMARK_LIVE_PRICES = { WIG: 86895.0, SP500: 5860.2, NASDAQ: 18420.0, DAX: 19350.0, MSCI_WORLD: 3730.0 };

            const mScore = document.getElementById('monthly-benchmarks-score');
            if (mScore) { mScore.textContent = 'Beat 4 / Lost 1'; mScore.style.color = '#27ae60'; }
            const yScore = document.getElementById('yearly-benchmarks-score');
            if (yScore) { yScore.textContent = 'Beat 5 / Lost 0'; yScore.style.color = '#27ae60'; }

            const mDeposit = document.getElementById('monthly-deposit-status');
            if (mDeposit) mDeposit.textContent = '5 000 / 5 000 PLN';
            const mDepositBar = document.getElementById('monthly-deposit-bar');
            if (mDepositBar) mDepositBar.style.width = '100%';
            const mDepositPct = document.getElementById('monthly-deposit-pct');
            if (mDepositPct) mDepositPct.textContent = '100%';

            if (typeof renderDashboard === 'function') renderDashboard();
        }""")
        page.wait_for_timeout(800)
        page.screenshot(path=str(SCREENSHOTS_DIR / "01_dashboard.png"), full_page=True)
        print("  -> Saved 01_dashboard.png (fully populated)")

        dash_html = page.locator("#tab-dashboard").inner_html()
        (EXPORT_DIR / "01_dashboard.html").write_text(wrap_html_shell("Dashboard", dash_html), encoding="utf-8")
        print("  -> Saved 01_dashboard.html (hydrated)")

        # ── 2. Wallets Tab ──────────────────────────────────────────────
        page.evaluate("""async () => {
            if (typeof showTab === 'function') showTab('wallets');
            if (typeof initWalletScreen === 'function') await initWalletScreen();
            document.querySelectorAll('.is-loading, .is-fetching-data').forEach(el => {
                el.classList.remove('is-loading', 'is-fetching-data');
            });
        }""")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "02_wallets.png"), full_page=True)
        print("  -> Saved 02_wallets.png (fully populated)")

        wallets_html = page.locator("#tab-wallets").inner_html()
        (EXPORT_DIR / "02_wallets.html").write_text(wrap_html_shell("Wallets & Management", wallets_html), encoding="utf-8")
        print("  -> Saved 02_wallets.html (hydrated)")

        # ── 3. Portfolio Screen (Breakdown & Holdings) ──────────────────
        page.evaluate("""async () => {
            if (typeof showTab === 'function') showTab('portfolio');
            if (typeof initPortfolioCharts === 'function') {
                window._portfolioInitialized = false;
                initPortfolioCharts();
            }
            document.querySelectorAll('.is-loading, .is-fetching-data').forEach(el => {
                el.classList.remove('is-loading', 'is-fetching-data');
            });
        }""")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "03_portfolio.png"), full_page=True)
        print("  -> Saved 03_portfolio.png (fully populated)")

        portfolio_html = page.locator("#tab-portfolio").inner_html()
        (EXPORT_DIR / "03_portfolio.html").write_text(
            wrap_html_shell("Portfolio Breakdown & Holdings", portfolio_html, extra_css="03_portfolio.css"),
            encoding="utf-8",
        )
        print("  -> Saved 03_portfolio.html (hydrated with 03_portfolio.css)")

        # ── 4. Statistics Screen ─────────────────────────────────────────
        page.evaluate("""async () => {
            if (typeof showTab === 'function') showTab('statistics');
            if (typeof renderStatisticsSummary === 'function') await renderStatisticsSummary(true);
            if (typeof refreshSnapshotTable === 'function') await refreshSnapshotTable();
            if (typeof refreshHeatmapTable === 'function') await refreshHeatmapTable();
            if (typeof refreshUnderwaterLakes === 'function') await refreshUnderwaterLakes();
            if (typeof toggleStatsAccordion === 'function') toggleStatsAccordion('bm-cmp');
            document.querySelectorAll('.is-loading, .is-fetching-data').forEach(el => el.classList.remove('is-loading', 'is-fetching-data'));
        }""")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "04_statistics.png"), full_page=True)
        print("  -> Saved 04_statistics.png (fully populated)")

        stats_html = page.locator("#tab-statistics").inner_html()
        (EXPORT_DIR / "04_statistics.html").write_text(
            wrap_html_shell("Statistics, Benchmarks & Lakes", stats_html, extra_css="04_statistics.css"),
            encoding="utf-8",
        )
        print("  -> Saved 04_statistics.html (hydrated with 04_statistics.css)")

        # ── 5. Retirement Screen ─────────────────────────────────────────
        page.evaluate("""async () => {
            if (typeof showTab === 'function') showTab('retirement');
            if (typeof initRetirementTab === 'function') await initRetirementTab();
            if (typeof _readPlanForm === 'function' && typeof _applyPreview === 'function') {
                const form = _readPlanForm();
                _applyPreview(form);
            }
            document.querySelectorAll('.is-loading, .is-fetching-data').forEach(el => el.classList.remove('is-loading', 'is-fetching-data'));
        }""")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "05_retirement.png"), full_page=True)
        print("  -> Saved 05_retirement.png (fully populated)")

        retirement_html = page.locator("#tab-retirement").inner_html()
        (EXPORT_DIR / "05_retirement.html").write_text(
            wrap_html_shell("Retirement & FIRE Forecast", retirement_html, extra_css="05_retirement.css"),
            encoding="utf-8",
        )
        print("  -> Saved 05_retirement.html (hydrated with 05_retirement.css)")

        # ── 6. Transactions Screen ───────────────────────────────────────
        page.evaluate("""async () => {
            if (typeof showTab === 'function') showTab('transactions');
            if (typeof refreshTransactionsTabData === 'function') await refreshTransactionsTabData(true);
            document.querySelectorAll('.is-loading, .is-fetching-data').forEach(el => el.classList.remove('is-loading', 'is-fetching-data'));
        }""")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "06_transactions.png"), full_page=True)
        print("  -> Saved 06_transactions.png (fully populated)")

        tx_html = page.locator("#tab-transactions").inner_html()
        (EXPORT_DIR / "06_transactions.html").write_text(
            wrap_html_shell("Transactions & Turnover Activity", tx_html, extra_css="06_transactions.css"),
            encoding="utf-8",
        )
        print("  -> Saved 06_transactions.html (hydrated with 06_transactions.css)")

        # ── 7. Coping Diary Screen ───────────────────────────────────────
        page.evaluate("""async () => {
            if (typeof showTab === 'function') showTab('diary');
            if (typeof window.initDiaryV2 === 'function') await window.initDiaryV2();
            if (typeof window.initCopingDiary === 'function') await window.initCopingDiary();
            document.querySelectorAll('.is-loading, .is-fetching-data').forEach(el => el.classList.remove('is-loading', 'is-fetching-data'));
            const firstCard = document.querySelector('.diary-ledger-card');
            if (firstCard) firstCard.click();
        }""")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "07_coping_diary.png"), full_page=True)
        print("  -> Saved 07_coping_diary.png (fully populated)")

        diary_html = page.locator("#tab-diary").inner_html()
        (EXPORT_DIR / "07_coping_diary.html").write_text(
            wrap_html_shell("Conviction & Emotional Coping Ledger", diary_html, extra_css="07_coping_diary.css"),
            encoding="utf-8",
        )
        print("  -> Saved 07_coping_diary.html (hydrated with 07_coping_diary.css)")

        # ── 8. Analysis Tab ─────────────────────────────────────────────
        page.evaluate("""async () => {
            if (typeof showTab === 'function') showTab('analysis');
            if (window._analysis && window._analysis.loadAssetData) {
                await window._analysis.loadAssetData('AAPL', '1y');
            }
            const fav = document.getElementById('analysis-favorites-section');
            if (fav) fav.style.display = 'block';
            const content = document.getElementById('analysis-content-area');
            if (content) content.style.display = 'block';
            document.querySelectorAll('.is-loading, .is-fetching-data').forEach(el => {
                el.classList.remove('is-loading', 'is-fetching-data');
            });
            const loader = document.getElementById('analysis-loader');
            if (loader) loader.style.display = 'none';
        }""")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "08_analysis.png"), full_page=True)
        print("  -> Saved 08_analysis.png (fully populated)")

        analysis_html = page.locator("#tab-analysis").inner_html()
        (EXPORT_DIR / "08_analysis.html").write_text(
            wrap_html_shell("Asset Analysis & Fundamentals", analysis_html, extra_css="08_analysis.css"),
            encoding="utf-8",
        )
        print("  -> Saved 08_analysis.html (hydrated with 08_analysis.css)")

        # ── 9. Monthly Audit / Recap ────────────────────────────────────
        try:
            audit_page = context.new_page()
            audit_page.goto(f"http://127.0.0.1:{port}/tests/monthly-audit.browser.html")
            audit_page.wait_for_function("() => typeof selectMonthlyAuditPeriod === 'function'")
            audit_page.evaluate("async () => { await selectMonthlyAuditPeriod('2026-08'); }")
            audit_page.wait_for_timeout(1000)
            audit_page.screenshot(path=str(SCREENSHOTS_DIR / "09_monthly_audit.png"), full_page=True)
            print("  -> Saved 09_monthly_audit.png (fully populated)")

            audit_html = audit_page.locator(".monthly-audit-shell").inner_html()
            (EXPORT_DIR / "09_monthly_audit.html").write_text(wrap_html_shell("Monthly Audit & Recap", audit_html), encoding="utf-8")
            print("  -> Saved 09_monthly_audit.html (hydrated)")
            audit_page.close()
        except Exception as e:
            print(f"  [!] Monthly Audit capture failed: {e}")

        # ── 10. Releases Screen ─────────────────────────────────────────
        page.goto(f"http://127.0.0.1:{port}/src/releases.html")
        page.wait_for_timeout(500)
        page.screenshot(path=str(SCREENSHOTS_DIR / "10_releases.png"), full_page=True)
        print("  -> Saved 10_releases.png")
        (EXPORT_DIR / "10_releases.html").write_text((ROOT / "src" / "releases.html").read_text(encoding="utf-8"), encoding="utf-8")
        print("  -> Saved 10_releases.html")

        # ── 11. Auth Screen (Clean context without auth token) ──────────
        auth_page = context.new_page()
        auth_page.goto(f"http://127.0.0.1:{port}/src/auth.html")
        auth_page.evaluate("() => localStorage.clear()")
        auth_page.goto(f"http://127.0.0.1:{port}/src/auth.html")
        auth_page.wait_for_timeout(500)
        auth_page.screenshot(path=str(SCREENSHOTS_DIR / "11_auth.png"), full_page=True)
        print("  -> Saved 11_auth.png")
        (EXPORT_DIR / "11_auth.html").write_text((ROOT / "src" / "auth.html").read_text(encoding="utf-8"), encoding="utf-8")
        print("  -> Saved 11_auth.html")
        auth_page.close()

        browser.close()


def main():
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[*] Exporting Roastfolio UI screens & tokens to {EXPORT_DIR.relative_to(ROOT)}...")

    # 1. Export Design Tokens and all Dedicated Screen CSS stylesheets
    tokens_css = extract_design_tokens()
    (EXPORT_DIR / "00_design_tokens.css").write_text(tokens_css, encoding="utf-8")
    print("  [x] Exported 00_design_tokens.css")

    portfolio_css = extract_portfolio_css()
    (EXPORT_DIR / "03_portfolio.css").write_text(portfolio_css, encoding="utf-8")
    print("  [x] Exported 03_portfolio.css")

    statistics_css = extract_statistics_css()
    (EXPORT_DIR / "04_statistics.css").write_text(statistics_css, encoding="utf-8")
    print("  [x] Exported 04_statistics.css")

    retirement_css = extract_retirement_css()
    (EXPORT_DIR / "05_retirement.css").write_text(retirement_css, encoding="utf-8")
    print("  [x] Exported 05_retirement.css")

    transactions_css = extract_transactions_css()
    (EXPORT_DIR / "06_transactions.css").write_text(transactions_css, encoding="utf-8")
    print("  [x] Exported 06_transactions.css")

    coping_diary_css = extract_coping_diary_css()
    (EXPORT_DIR / "07_coping_diary.css").write_text(coping_diary_css, encoding="utf-8")
    print("  [x] Exported 07_coping_diary.css")

    analysis_css = extract_analysis_css()
    (EXPORT_DIR / "08_analysis.css").write_text(analysis_css, encoding="utf-8")
    print("  [x] Exported 08_analysis.css")

    # 2. Start local server to capture live screenshots and hydrated HTMLs
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", 0), SilentHandler)
    port = httpd.server_address[1]

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    time.sleep(0.5)
    capture_bundle(port)
    httpd.shutdown()

    # 3. Clean up any leftover files with obsolete or conflicting numbering
    stale_files = [
        EXPORT_DIR / "04_analysis.html",
        EXPORT_DIR / "05_monthly_audit.html",
        EXPORT_DIR / "06_releases.html",
        EXPORT_DIR / "07_auth.html",
        SCREENSHOTS_DIR / "03_analysis.png",
        SCREENSHOTS_DIR / "04_analysis.png",
        SCREENSHOTS_DIR / "05_monthly_audit.png",
        SCREENSHOTS_DIR / "06_releases.png",
        SCREENSHOTS_DIR / "07_auth.png",
    ]
    for old_file in stale_files:
        if old_file.exists():
            old_file.unlink()
            print(f"  [-] Removed stale file: {old_file.name}")

    # 4. Write README guide for Google Stitch
    readme_content = """# Roastfolio UI Export for Google Stitch (stitch.withgoogle.com)

This directory contains modular screen components, design tokens, dedicated scoped CSS, and populated screenshots prepared specifically for Google Stitch.

## Screen Inventory

| Screen | Screenshot | HTML Component | Scoped CSS | Key Elements Included |
|---|---|---|---|---|
| **01 Dashboard** | `screenshots/01_dashboard.png` | `01_dashboard.html` | `00_design_tokens.css` | Total value card, 1D P&L, ATH drawdown, TWR dial gauge, Today's Movers cards, Monthly & Yearly returns, Retirement goals, WIG benchmark chart |
| **02 Wallets** | `screenshots/02_wallets.png` | `02_wallets.html` | `00_design_tokens.css` | Wallet chips (Summary, XTB, IKE), Active holdings table (AAPL, XTB, MSFT, CDR, Cash), Allocation donut, Quick Entry, Trade action buttons |
| **03 Portfolio** | `screenshots/03_portfolio.png` | `03_portfolio.html` | `03_portfolio.css` | Total portfolio donut chart with legend pills, individual wallet mini-donuts (XTB, IKE), holdings tabs, full holdings table with Price, Today, YTD, Current Value, Purchase Value, Profit/Loss, Total Return %, Portfolio % |
| **04 Statistics** | `screenshots/04_statistics.png` | `04_statistics.html` | `04_statistics.css` | All-Time / Monthly / Daily stats cards, Benchmark Comparison table (5 benchmarks vs Portfolio), Underwater Lakes drawdown charts, and Monthly Performance Heatmap table (2024–2026) |
| **05 Retirement** | `screenshots/05_retirement.png` | `05_retirement.html` | `05_retirement.css` | Retirement & FIRE forecast hero, Plan Setup inputs, past vs projected baseline simulation chart canvas, and key milestone summary cards |
| **06 Transactions** | `screenshots/06_transactions.png` | `06_transactions.html` | `06_transactions.css` | Turnover summary cards (Total, Inflow, Outflow, Dividends), Monthly turnover bar chart, 12-month activity calendar grid, and searchable transaction history table with op badges |
| **07 Coping Diary** | `screenshots/07_coping_diary.png` | `07_coping_diary.html` | `07_coping_diary.css` | Split pane Conviction Ledger with tag cloud chips (#HOLD, #TECH, #CONVICTION, #AI), active ledger cards, and Focus Sheet with note text, why buy thesis, checkpoints, and coping chat |
| **08 Analysis** | `screenshots/08_analysis.png` | `08_analysis.html` | `08_analysis.css` | Watchlist favorites strip with sparklines, interactive 1Y price chart, volume bars, technical indicator toggles (VOL, MA, MACD), fundamental properties grid |
| **09 Monthly Audit** | `screenshots/09_monthly_audit.png` | `09_monthly_audit.html` | `00_design_tokens.css` | Monthly recap bento grid, journey chart vs benchmark, milestone timeline, drawdown lakes, best/worst performance cards |
| **10 Releases** | `screenshots/10_releases.png` | `10_releases.html` | `00_design_tokens.css` | Release notes changelog, feature tags, version badge |
| **11 Auth** | `screenshots/11_auth.png` | `11_auth.html` | `00_design_tokens.css` | Fintech login / sign-up screen, credential inputs, OAuth actions |

## How to Show Screens to Google Stitch

### 1. Vision Input (Best for Visual Style & Layout)
- In Google Stitch, click the **Image Upload** icon next to the prompt bar.
- Upload the corresponding screenshot from `screenshots/` (e.g. `04_statistics.png`, `05_retirement.png`, `06_transactions.png`, or `07_coping_diary.png`).
- Stitch's vision model will instantly recognize the layout, dark-mode cards, gauges, charts, tables, and colors with **real numbers and filled components** (no loaders).

### 2. Code Input (For Semantic Structure & Data Fields)
- Open the corresponding `.html` file (e.g. `04_statistics.html`, `05_retirement.html`, `06_transactions.html`, or `07_coping_diary.html`).
- Copy the HTML section inside `<div class="stitch-screen-container">`.
- Also include the scoped CSS from the matching `.css` file (e.g. `04_statistics.css`, `05_retirement.css`, `06_transactions.css`, or `07_coping_diary.css`) along with `00_design_tokens.css`.
- Paste them into your prompt to tell Stitch what components, metrics, and actions exist.

---

## Example Prompts for Google Stitch

### Prompt for Statistics Screen (`04_statistics.html` + `04_statistics.css`):
```text
I am redesigning our fintech portfolio tracker web app "roastfolio".
I've attached a screenshot of our current Statistics & Benchmarks screen (04_statistics.png).
Here is the HTML structure and scoped CSS:

[PASTE HTML FROM 04_statistics.html HERE]
[PASTE CSS FROM 04_statistics.css HERE]

Design goals for this redesign:
- Keep the dark fintech neon aesthetic (cyan #00f2fe, emerald #4ade80, red #f87171, deep navy #050e18).
- Modernize the layout into a clean bento grid with glassmorphism cards.
- Highlight the 3 core sections:
  1. Performance metrics overview (All-time, monthly, daily cards).
  2. Benchmark comparison table (comparing portfolio return against WIG, S&P 500, NASDAQ, DAX, MSCI World).
  3. Underwater Lakes drawdown analysis and monthly performance heatmap grid.
- Keep tabular numbers aligned, with clear win/loss color badges and responsive mobile layout.
```

### Prompt for Retirement Screen (`05_retirement.html` + `05_retirement.css`):
```text
I am redesigning our fintech portfolio tracker web app "roastfolio".
I've attached a screenshot of our current Retirement & FIRE Forecast screen (05_retirement.png).
Here is the HTML structure and scoped CSS:

[PASTE HTML FROM 05_retirement.html HERE]
[PASTE CSS FROM 05_retirement.css HERE]

Design goals for this redesign:
- Maintain the dark fintech look and feel with high-contrast typography.
- Present a hero card showing the retirement target year, current nest egg, and monthly contribution progress.
- Include the simulation chart area with time range toggles (10Y, 20Y, 30Y, Full) comparing actual portfolio trajectory against baseline projections.
- Clean up the plan parameters form inputs (target amount, expected return, inflation, retirement age).
```

### Prompt for Transactions Screen (`06_transactions.html` + `06_transactions.css`):
```text
I am redesigning our fintech portfolio tracker web app "roastfolio".
I've attached a screenshot of our current Transactions screen (06_transactions.png).
Here is the HTML structure and scoped CSS:

[PASTE HTML FROM 06_transactions.html HERE]
[PASTE CSS FROM 06_transactions.css HERE]

Design goals for this redesign:
- Present 4 turnover KPI cards at top (Total Turnover, Inflow, Outflow, Dividends Received).
- Feature the 12-month activity heatmap calendar with Github-style intensity squares.
- Provide a clean, dense transaction ledger table with color-coded operation pills (BUY, SELL, DIVIDEND, DEPOSIT) and column filters.
```

### Prompt for Coping Diary Screen (`07_coping_diary.html` + `07_coping_diary.css`):
```text
I am redesigning our fintech portfolio tracker web app "roastfolio".
I've attached a screenshot of our Coping & Conviction Diary screen (07_coping_diary.png).
Here is the HTML structure and scoped CSS:

[PASTE HTML FROM 07_coping_diary.html HERE]
[PASTE CSS FROM 07_coping_diary.css HERE]

Design goals for this redesign:
- Elegant split-view layout: Left pane has the conviction tag cloud and asset ledger cards; Right pane has the Focus Sheet.
- The Focus Sheet displays:
  1. Header with investment thesis and active/inactive toggle slider.
  2. "Why Buy", "Exit Plan", and "Risk Factors" hypothesis cards.
  3. Milestone checkpoints checklist with due dates and checkboxes.
  4. Emotional coping log / commentary feed with timestamps and quick-entry input.
- Keep the purple/violet conviction accents (#a855f7) paired with cyber cyan (#00f2fe).
```
"""
    (EXPORT_DIR / "README.md").write_text(readme_content, encoding="utf-8")
    print("  [x] Generated README.md instructions")
    print("\n[✓] Export completed successfully!")


if __name__ == "__main__":
    main()

