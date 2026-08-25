import decimal
def _to_decimal(val): return decimal.Decimal(str(val)) if val not in (None, "") else None

updates = {"quantity": 10, "price": 15, "commission": 0}
existing = {"quantity": 10, "price": 10, "commission": 0, "value": 100, "type": "BUY"}

tx_type = "BUY"
requires_quantity = tx_type in {"BUY", "SELL", "DIVIDEND", "SPINOFF"}
quantity = None
if requires_quantity:
    quantity_raw = updates.get("quantity", updates.get("units", existing.get("quantity", 0)))
    quantity = _to_decimal(quantity_raw)

price_raw = updates.get("price", existing.get("price"))
price = None if price_raw in (None, "") else _to_decimal(price_raw)
commission = _to_decimal(updates.get("commission", existing.get("commission", 0)))

raw_value = updates.get("value") if "value" in updates else None
if raw_value not in (None, ""):
    value = _to_decimal(raw_value)
elif tx_type == "BUY" and quantity is not None and price is not None:
    value = quantity * price + commission
elif tx_type == "SELL" and quantity is not None and price is not None:
    value = quantity * price - commission
else:
    value = _to_decimal(existing.get("value", 0))

print(value)
