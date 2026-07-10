"""
lambda/migrate.py — one-shot CSV → DynamoDB portfolio importer.

Imports current holdings and, when available, historical transaction CSVs
bundled with the Lambda package.
"""

import json
import logging
import os
import portfolios
from handler import parse_wallet_csv, _get_caller_identity, _resp, WALLETS
from transaction_import import import_transaction_history

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Map CSV wallet name → ticker/currency metadata (mirrors TICKER_MAP in handler.py)
_TICKER_MAP = {
    "XTB":                          ("XTB.WA",  "PLN"),
    "RAINBOW (RBW)":                ("RBW.WA",  "PLN"),
    "MOBRUK (MBR)":                 ("MBR.WA",  "PLN"),
    "Mobruk":                       ("MBR.WA",  "PLN"),
    "MOBRUK":                       ("MBR.WA",  "PLN"),
    "ARTIFEX":                      ("ART.WA",  "PLN"),
    "Artifex":                      ("ART.WA",  "PLN"),
    "Artifex Mundi":                ("ART.WA",  "PLN"),
    "ARTIFEX MUNDI":                ("ART.WA",  "PLN"),
    "CREOTECH (CRI)":               ("CRI.WA",  "PLN"),
    "CDPROJEKT (CDR)":              ("CDR.WA",  "PLN"),
    "Meta Platforms, Inc. (META)":  ("META",     "USD"),
    "Bitcoin (BTC)":                ("BTC-USD",  "USD"),
}

_HISTORY_WALLETS = {
    wallet_name: os.path.join(os.path.dirname(csv_path), f"myfund.pl_{wallet_name}_historiaOperacji.csv")
    for wallet_name, csv_path in WALLETS.items()
}
_HISTORY_ONLY_WALLETS = {
    "Schwab": os.path.join(os.path.dirname(__file__), "data", "myfund.pl_Schwab_historiaOperacji.csv"),
    "Binance": os.path.join(os.path.dirname(__file__), "data", "myfund.pl_Binance_historiaOperacji.csv"),
}
_LEGACY_PORTFOLIO_IDS = {"emerytura", "other"}
_LEGACY_PORTFOLIO_NAMES = {"emerytura", "other"}
_MIGRATION_WALLETS = {
    wallet_name: csv_path
    for wallet_name, csv_path in WALLETS.items()
    if portfolios._safe_id(wallet_name) not in _LEGACY_PORTFOLIO_IDS
}


def migrate_handler(event: dict) -> dict:
    """POST /migrate — import all CSV wallets to DynamoDB for the caller."""
    method = event.get("httpMethod", "POST")

    if method == "OPTIONS":
        return _resp(200, {})

    if method != "POST":
        return _resp(405, {"error": "Method not allowed"})

    # Block migration in non-prod environments to prevent real CSV data
    # from being imported into dev/staging DynamoDB tables.
    data_table = os.environ.get("DATA_TABLE", "")
    if not data_table or data_table.startswith("dev-"):
        return _resp(403, {"error": "Migration is disabled in the dev environment"})

    user_id, email, _ = _get_caller_identity(event)
    if not user_id:
        return _resp(401, {"error": "Missing or invalid Authorization header"})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _resp(400, {"error": "Invalid JSON"})

    rebuild_history = bool(body.get("rebuildHistory"))

    results = {}

    cleaned = []
    for existing in portfolios.list_portfolios(user_id):
        pid = str(existing.get("portfolioId") or "").strip().lower()
        name = str(existing.get("name") or "").strip().lower()
        if pid in _LEGACY_PORTFOLIO_IDS or name in _LEGACY_PORTFOLIO_NAMES:
            portfolios.delete_portfolio(user_id, existing["portfolioId"])
            cleaned.append(existing["portfolioId"])
    if cleaned:
        logger.info("Removed legacy portfolios for %s: %s", user_id, cleaned)

    for wallet_name, csv_path in _MIGRATION_WALLETS.items():
        try:
            raw_holdings = parse_wallet_csv(csv_path)
        except Exception as e:
            logger.error("Failed to parse CSV for %s: %s", wallet_name, e)
            results[wallet_name] = {"status": "error", "error": str(e)}
            continue

        portfolio_id = portfolios._safe_id(wallet_name)

        # Ensure portfolio metadata exists
        existing = portfolios.get_portfolio(user_id, portfolio_id)
        if not existing:
            portfolios.put_portfolio(user_id, {
                "portfolioId": portfolio_id,
                "name":        wallet_name,
                "type":        "real",
                "currency":    "PLN",
                "order":       portfolios._PORTFOLIO_ORDER.get(portfolio_id, 99),
            })

        history_path = _HISTORY_WALLETS.get(wallet_name)
        history_exists = bool(history_path and os.path.exists(history_path))
        history_result = None

        if history_exists:
            try:
                history_result = import_transaction_history(
                    user_id,
                    portfolio_id,
                    history_path,
                    rebuild=rebuild_history,
                )
            except Exception as e:
                logger.error("Failed to import history for %s: %s", wallet_name, e)
                results[wallet_name] = {"status": "error", "error": str(e)}
                continue

        try:
            synced_holdings = portfolios.replace_holdings_snapshots(user_id, portfolio_id, raw_holdings)
            imported_holdings = len(synced_holdings)
        except Exception as e:
            logger.error("Failed to sync holdings for %s: %s", wallet_name, e)
            results[wallet_name] = {"status": "error", "error": str(e)}
            continue

        results[wallet_name] = {
            "status": "ok",
            "holdingsImported": imported_holdings,
            "history": history_result or {"status": "missing", "imported": 0, "skipped": 0},
        }
        logger.info("Migrated %s: holdings=%d history=%s", wallet_name, imported_holdings, history_result or "missing")

    for wallet_name, history_path in _HISTORY_ONLY_WALLETS.items():
        if not os.path.exists(history_path):
            continue

        portfolio_id = portfolios._safe_id(wallet_name)
        existing = portfolios.get_portfolio(user_id, portfolio_id)
        if not existing:
            portfolios.put_portfolio(user_id, {
                "portfolioId": portfolio_id,
                "name": wallet_name,
                "type": "real",
                "currency": "USD" if wallet_name == "Schwab" else "PLN",
                "order": portfolios._PORTFOLIO_ORDER.get(portfolio_id, 99),
            })

        try:
            history_result = import_transaction_history(
                user_id,
                portfolio_id,
                history_path,
                rebuild=rebuild_history,
            )
            rebuilt_holdings = portfolios.rebuild_holdings_from_transactions(user_id, portfolio_id)
        except Exception as e:
            logger.error("Failed to import history for %s: %s", wallet_name, e)
            results[wallet_name] = {"status": "error", "error": str(e)}
            continue

        results[wallet_name] = {
            "status": "ok",
            "holdingsImported": len(rebuilt_holdings),
            "history": history_result,
        }
        logger.info("Migrated history-only wallet %s: history=%s", wallet_name, history_result)

    return _resp(200, {
        "message": "Migration complete",
        "userId":  user_id,
        "cleanedPortfolios": cleaned,
        "wallets": results,
    })
