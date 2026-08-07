"""Average-cost portfolio analytics derived from the transaction ledger."""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping

import boto3


ZERO = Decimal("0")
EPSILON = Decimal("0.00000001")
ANALYSIS_VERSION = 1
IGNORED_STATUSES = {"DRAFT", "PENDING", "REJECTED", "UNVERIFIED"}
ASSET_TRANSACTION_TYPES = {"BUY", "SELL", "DIVIDEND", "SPINOFF"}


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return ZERO
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


def _date(value: Any) -> date:
    raw = str(value or "").strip()[:10]
    if not raw:
        raise ValueError("Asset transactions require transactionDate")
    return date.fromisoformat(raw)


def _asset_key(transaction: Mapping[str, Any]) -> str:
    holding_id = str(transaction.get("holdingId") or "").strip()
    if holding_id:
        return holding_id
    ticker = str(transaction.get("ticker") or "").strip().upper()
    if ticker:
        return ticker
    return str(transaction.get("name") or "").strip().upper()


class PortfolioAVCOCalculator:
    """Replay chronological transactions and calculate AVCO position analytics."""

    def __init__(
        self,
        current_prices: Mapping[str, Any] | None = None,
        current_values: Mapping[str, Any] | None = None,
    ) -> None:
        self.current_prices = {
            str(key).upper(): _decimal(value)
            for key, value in (current_prices or {}).items()
            if value is not None
        }
        self.current_values = {
            str(key).upper(): _decimal(value)
            for key, value in (current_values or {}).items()
            if value is not None
        }

    def calculate(self, transactions: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        states: dict[str, dict[str, Any]] = {}
        ordered = sorted(
            (tx for tx in transactions if self._is_verified(tx)),
            key=lambda tx: (
                str(tx.get("transactionDate") or tx.get("date") or "")[:10],
                str(tx.get("createdAt") or ""),
                str(tx.get("transactionId") or ""),
            ),
        )

        for transaction in ordered:
            tx_type = str(transaction.get("type") or "").strip().upper()
            if tx_type not in ASSET_TRANSACTION_TYPES:
                continue
            key = _asset_key(transaction)
            if not key:
                continue
            state = states.setdefault(key, self._new_state(key, transaction))
            self._refresh_identity(state, transaction)
            if tx_type in {"BUY", "SPINOFF"}:
                self._process_buy(state, transaction, is_spinoff=tx_type == "SPINOFF")
            elif tx_type == "SELL":
                self._process_sell(state, transaction)
            else:
                state["dividends_received"] += _decimal(transaction.get("value"))

        positions = [self._finalize(state) for state in states.values()]
        positions.sort(key=lambda row: (row["status"] != "ACTIVE", row["ticker"]))
        return {
            "analysis_version": ANALYSIS_VERSION,
            "positions": positions,
            "active": [row for row in positions if row["status"] == "ACTIVE"],
            "closed": [row for row in positions if row["status"] == "CLOSED"],
        }

    @staticmethod
    def _is_verified(transaction: Mapping[str, Any]) -> bool:
        if transaction.get("verified") is False:
            return False
        status = str(transaction.get("status") or "").strip().upper()
        return status not in IGNORED_STATUSES

    @staticmethod
    def _new_state(key: str, transaction: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "ticker": str(transaction.get("ticker") or key).strip().upper(),
            "holding_id": str(transaction.get("holdingId") or ""),
            "name": str(transaction.get("name") or key),
            "currency": str(transaction.get("currency") or "PLN"),
            "shares": ZERO,
            "avco": ZERO,
            "realized_return": ZERO,
            "dividends_received": ZERO,
            "peak_value": ZERO,
            "first_buy_date": None,
            "last_sell_date": None,
            "cycle_first_buy_date": None,
            "cycle_cost": ZERO,
            "cycle_realized": ZERO,
            "cycle_sale_value": ZERO,
            "cycle_sold_shares": ZERO,
            "closures": [],
            "loss_sale_dates": [],
            "major_loss_sale": False,
            "wash_sale": None,
        }

    @staticmethod
    def _refresh_identity(state: dict[str, Any], transaction: Mapping[str, Any]) -> None:
        state["holding_id"] = str(transaction.get("holdingId") or state["holding_id"])
        state["ticker"] = str(transaction.get("ticker") or state["ticker"]).strip().upper()
        state["name"] = str(transaction.get("name") or state["name"])
        state["currency"] = str(transaction.get("currency") or state["currency"])

    def _process_buy(self, state: dict[str, Any], transaction: Mapping[str, Any], is_spinoff: bool) -> None:
        shares = _decimal(transaction.get("quantity", transaction.get("units")))
        if shares <= ZERO:
            raise ValueError("BUY and SPINOFF quantity must be greater than zero")
        tx_date = _date(transaction.get("transactionDate") or transaction.get("date"))
        price = self._transaction_price(transaction, "SPINOFF" if is_spinoff else "BUY", shares)

        if state["shares"] <= EPSILON:
            state["shares"] = ZERO
            state["avco"] = ZERO
            state["cycle_first_buy_date"] = tx_date.isoformat()
            state["cycle_cost"] = ZERO
            state["cycle_realized"] = ZERO
            state["cycle_sale_value"] = ZERO
            state["cycle_sold_shares"] = ZERO

        for loss_sale in state["loss_sale_dates"]:
            days = (tx_date - loss_sale["date"]).days
            if 0 <= days <= 30:
                state["wash_sale"] = {
                    "sell_date": loss_sale["date"].isoformat(),
                    "rebuy_date": tx_date.isoformat(),
                    "days_between": days,
                    "loss": loss_sale["loss"],
                }
                break

        old_shares = state["shares"]
        new_shares = old_shares + shares
        state["avco"] = ((old_shares * state["avco"]) + (shares * price)) / new_shares
        state["shares"] = new_shares
        state["cycle_cost"] += shares * price
        state["peak_value"] = max(state["peak_value"], new_shares * price)
        if not state["first_buy_date"]:
            state["first_buy_date"] = tx_date.isoformat()

    def _process_sell(self, state: dict[str, Any], transaction: Mapping[str, Any]) -> None:
        sold_shares = _decimal(transaction.get("quantity", transaction.get("units")))
        if sold_shares <= ZERO:
            raise ValueError("SELL quantity must be greater than zero")
        if sold_shares - state["shares"] > EPSILON:
            raise ValueError(f"SELL quantity exceeds active shares for {state['ticker']}")

        tx_date = _date(transaction.get("transactionDate") or transaction.get("date"))
        sell_price = self._transaction_price(transaction, "SELL", sold_shares)
        realized_gain = sold_shares * (sell_price - state["avco"])
        sale_return_pct = ((sell_price - state["avco"]) / state["avco"] * 100) if state["avco"] > ZERO else ZERO
        state["realized_return"] += realized_gain
        state["cycle_realized"] += realized_gain
        state["cycle_sale_value"] += sold_shares * sell_price
        state["cycle_sold_shares"] += sold_shares
        state["last_sell_date"] = tx_date.isoformat()
        if realized_gain < ZERO:
            state["loss_sale_dates"].append({"date": tx_date, "loss": realized_gain})
        if sale_return_pct <= Decimal("-20"):
            state["major_loss_sale"] = True

        state["shares"] -= sold_shares
        if state["shares"] <= EPSILON:
            state["shares"] = ZERO
            average_sale_price = (
                state["cycle_sale_value"] / state["cycle_sold_shares"]
                if state["cycle_sold_shares"] > ZERO
                else ZERO
            )
            gain_pct = (
                state["cycle_realized"] / state["cycle_cost"] * 100
                if state["cycle_cost"] > ZERO
                else ZERO
            )
            state["closures"].append({
                "opened_at": state["cycle_first_buy_date"],
                "closed_at": tx_date.isoformat(),
                "realized_return": state["cycle_realized"],
                "return_pct": gain_pct,
                "average_sale_price": average_sale_price,
            })

    def _transaction_price(self, transaction: Mapping[str, Any], tx_type: str, shares: Decimal) -> Decimal:
        explicit = transaction.get("price")
        if explicit not in (None, ""):
            return _decimal(explicit)
        value = _decimal(transaction.get("value"))
        commission = _decimal(transaction.get("commission"))
        if tx_type == "BUY":
            gross = max(ZERO, value - commission)
        elif tx_type == "SELL":
            gross = value + commission
        else:
            gross = value
        return gross / shares if shares > ZERO else ZERO

    def _finalize(self, state: dict[str, Any]) -> dict[str, Any]:
        ticker = state["ticker"]
        current_price = self.current_prices.get(ticker)
        active_value = self.current_values.get(ticker)
        if active_value is None and current_price is not None:
            active_value = state["shares"] * current_price
        unrealized = (
            state["shares"] * (current_price - state["avco"])
            if current_price is not None and state["shares"] > ZERO
            else ZERO
        )
        total_return = state["realized_return"] + unrealized + state["dividends_received"]
        paper_hands = self._paper_hands_metadata(state, current_price)
        clown = bool(
            state["shares"] > ZERO
            and active_value is not None
            and active_value < Decimal("10")
            and state["peak_value"] > Decimal("250")
            and state["major_loss_sale"]
        )
        badges = {
            "clown_bagholder": clown,
            "paper_hands_fomo": paper_hands is not None,
            "wash_sale_violator": state["wash_sale"] is not None,
        }
        metadata = {
            "clown_bagholder": {
                "active_value": active_value,
                "peak_value": state["peak_value"],
                "major_loss_threshold_pct": Decimal("-20"),
            } if clown else None,
            "paper_hands_fomo": paper_hands,
            "wash_sale_violator": state["wash_sale"],
        }
        return {
            "ticker": ticker,
            "holding_id": state["holding_id"],
            "name": state["name"],
            "currency": state["currency"],
            "status": "ACTIVE" if state["shares"] > ZERO else "CLOSED",
            "shares": state["shares"],
            "avco": state["avco"] if state["shares"] > ZERO else ZERO,
            "realized_return": state["realized_return"],
            "unrealized_return": unrealized,
            "dividends_received": state["dividends_received"],
            "total_return": total_return,
            "first_buy_date": state["first_buy_date"],
            "last_sell_date": state["last_sell_date"],
            "peak_value": state["peak_value"],
            "current_market_price": current_price,
            "gamification": {"badges": badges, "metadata": metadata},
        }

    @staticmethod
    def _paper_hands_metadata(state: Mapping[str, Any], current_price: Decimal | None) -> dict[str, Any] | None:
        if current_price is None:
            return None
        for closure in reversed(state["closures"]):
            gain_pct = closure["return_pct"]
            average_sale_price = closure["average_sale_price"]
            if ZERO < gain_pct < Decimal("5") and average_sale_price > ZERO:
                price_increase_pct = (current_price / average_sale_price - 1) * 100
                if price_increase_pct >= Decimal("30"):
                    return {
                        "closed_at": closure["closed_at"],
                        "closure_return_pct": gain_pct,
                        "average_sale_price": average_sale_price,
                        "current_market_price": current_price,
                        "price_increase_pct": price_increase_pct,
                    }
        return None


def recalculate_portfolio_avco(
    user_id: str,
    portfolio_id: str,
    current_prices: Mapping[str, Any] | None = None,
    current_values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Read the live ledger, calculate AVCO analytics, and persist one portfolio record."""
    import portfolios

    transactions = portfolios.list_all_transactions(user_id, portfolio_id, scan_forward=True)
    return persist_portfolio_avco(
        user_id,
        portfolio_id,
        transactions,
        current_prices=current_prices,
        current_values=current_values,
    )


def persist_portfolio_avco(
    user_id: str,
    portfolio_id: str,
    transactions: Iterable[Mapping[str, Any]],
    current_prices: Mapping[str, Any] | None = None,
    current_values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate and persist AVCO using an already-loaded transaction ledger."""
    result = PortfolioAVCOCalculator(current_prices, current_values).calculate(transactions)
    item = {
        "userId": user_id,
        "sk": f"AVCO#{portfolio_id}",
        "portfolioId": portfolio_id,
        "analysisVersion": ANALYSIS_VERSION,
        "positions": result["positions"],
        "updatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    table_name = os.environ.get("DATA_TABLE", "roastfolio-data")
    boto3.resource("dynamodb").Table(table_name).put_item(Item=item)
    return result


def load_portfolio_avco(user_id: str, portfolio_id: str) -> dict[str, Any]:
    table_name = os.environ.get("DATA_TABLE", "roastfolio-data")
    response = boto3.resource("dynamodb").Table(table_name).get_item(
        Key={"userId": user_id, "sk": f"AVCO#{portfolio_id}"}
    )
    item = response.get("Item") or {}
    positions = item.get("positions") or []
    return {
        "analysis_version": item.get("analysisVersion", ANALYSIS_VERSION),
        "positions": positions,
        "active": [row for row in positions if row.get("status") == "ACTIVE"],
        "closed": [row for row in positions if row.get("status") == "CLOSED"],
        "updated_at": item.get("updatedAt"),
    }