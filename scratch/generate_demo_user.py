import os
import sys
import uuid
import datetime
from decimal import Decimal
import boto3

# Ensure lambda path is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../lambda")))

import db
import portfolios
import snapshots

# Demo User Details
DEMO_EMAIL = "roastfolio@app"
DEMO_NAME = "Jan"

# Environment Configurations
ENVS = {
    "test": {
        "userId": "a8715360-2041-709a-974c-961bb486f03c",
        "users_table": "dev-roastfolio-users",
        "data_table": "dev-roastfolio-data",
        "tx_table": "dev-roastfolio-transactions",
        "snapshots_table": "dev-roastfolio-snapshots",
        "roast_table": "dev-roastfolio-roast-history",
    },
    "prod": {
        "userId": "58617340-6021-700b-18bf-a8c21f359461",
        "users_table": "roastfolio-users",
        "data_table": "roastfolio-data",
        "tx_table": "roastfolio-transactions",
        "snapshots_table": "roastfolio-snapshots",
        "roast_table": "roastfolio-roast-history",
    }
}

# 8 Active Holdings (4 in Retirement, 4 in Global)
ACTIVE_RETIREMENT = [
    ("AAPL", "Apple Inc.", 200, 120000),
    ("MSFT", "Microsoft Corp.", 150, 180000),
    ("NVDA", "NVIDIA Corp.", 300, 110000),
    ("AMZN", "Amazon.com Inc.", 250, 140000),
]

ACTIVE_GLOBAL = [
    ("GOOGL", "Alphabet Inc.", 180, 100000),
    ("META", "Meta Platforms Inc.", 120, 130000),
    ("TSLA", "Tesla Inc.", 150, 90000),
    ("JPM", "JPMorgan Chase & Co.", 220, 110000),
]

# 32 Past Holdings (Bought and sold off completely)
PAST_TICKERS = [
    ("V", "Visa Inc."),
    ("UNH", "UnitedHealth Group"),
    ("XOM", "Exxon Mobil Corp."),
    ("JNJ", "Johnson & Johnson"),
    ("PG", "Procter & Gamble"),
    ("HD", "Home Depot Inc."),
    ("MA", "Mastercard Inc."),
    ("COST", "Costco Wholesale"),
    ("ABBV", "AbbVie Inc."),
    ("DIS", "Walt Disney Co."),
    ("PEP", "PepsiCo Inc."),
    ("ADBE", "Adobe Inc."),
    ("CRM", "Salesforce Inc."),
    ("NFLX", "Netflix Inc."),
    ("AMD", "Advanced Micro Devices"),
    ("INTC", "Intel Corp."),
    ("CSCO", "Cisco Systems"),
    ("NKE", "NIKE Inc."),
    ("WMT", "Walmart Inc."),
    ("MCD", "McDonald's Corp."),
    ("TMO", "Thermo Fisher Scientific"),
    ("PFE", "Pfizer Inc."),
    ("MRK", "Merck & Co."),
    ("BAC", "Bank of America"),
    ("ORCL", "Oracle Corp."),
    ("ACN", "Accenture plc"),
    ("CVX", "Chevron Corp."),
    ("LLY", "Eli Lilly and Co."),
    ("ABT", "Abbott Laboratories"),
    ("QCOM", "Qualcomm Inc."),
    ("TXN", "Texas Instruments"),
    ("AVGO", "Broadcom Inc."),
]


def generate_transactions_for_user(user_id):
    """
    Generates a realistic transaction history over 5 years (2021 to 2026).
    """
    tx_list = []
    
    def add_tx(portfolio_id, tx_date, tx_type, name, ticker, currency, qty, val, source_op, holding_id=None, comment=""):
        if not holding_id:
            if ticker:
                holding_id = name.lower().replace(" ", "-").replace(".", "") + "--" + ticker.lower().replace(".", "").replace("-", "") + "-"
            else:
                holding_id = "__cash__"
                
        tx_id = f"demo-{uuid.uuid4().hex[:12]}"
        sk = f"PORTFOLIO#{portfolio_id}#TX#{tx_date}#{tx_id}"
        
        tx_item = {
            "userId": user_id,
            "portfolioId": portfolio_id,
            "transactionId": tx_id,
            "sk": sk,
            "transactionDate": tx_date,
            "type": tx_type,
            "name": name,
            "ticker": ticker,
            "currency": currency or "PLN",
            "quantity": Decimal(str(qty)),
            "value": Decimal(str(val)),
            "commission": Decimal("0"),
            "tax": Decimal("0"),
            "holdingId": holding_id,
            "sourceOperation": source_op,
            "importSource": "manual",
            "importVersion": Decimal("1"),
            "createdAt": f"{tx_date}T10:00:00Z",
            "comment": comment
        }
        if ticker:
            tx_item["price"] = Decimal(str(round(val / qty, 4))) if qty > 0 else Decimal("0")
        tx_list.append(tx_item)

    # 1. Quarterly deposits & accumulation over 20 quarters (2021 Q1 to 2026 Q3)
    start_year = 2021
    end_year = 2026
    
    past_idx = 0
    
    for year in range(start_year, end_year + 1):
        for q in range(1, 5):
            if year == 2026 and q > 3:
                break
                
            m = (q - 1) * 3 + 1
            deposit_date_ret = f"{year}-{m:02d}-05"
            deposit_date_glo = f"{year}-{m:02d}-10"
            
            # Deposits each quarter
            dep_val_ret = 12000 + (year - 2021) * 1500
            dep_val_glo = 10000 + (year - 2021) * 1200
            
            add_tx("retirement", deposit_date_ret, "DEPOSIT", "Cash", None, "PLN", 0, dep_val_ret, "Wpłata")
            add_tx("global", deposit_date_glo, "DEPOSIT", "Cash", None, "PLN", 0, dep_val_glo, "Wpłata")
            
            # Active buys (buy chunks of active stocks each year/quarter)
            buy_date_ret = f"{year}-{m:02d}-12"
            buy_date_glo = f"{year}-{m:02d}-15"
            
            # Retirement active buying
            act_ret = ACTIVE_RETIREMENT[(q - 1) % len(ACTIVE_RETIREMENT)]
            add_tx("retirement", buy_date_ret, "BUY", act_ret[1], act_ret[0], "USD", 10, dep_val_ret * 0.8, "Kupno")
            
            # Global active buying
            act_glo = ACTIVE_GLOBAL[(q - 1) % len(ACTIVE_GLOBAL)]
            add_tx("global", buy_date_glo, "BUY", act_glo[1], act_glo[0], "USD", 8, dep_val_glo * 0.8, "Kupno")
            
            # Past holdings: buy 2 past companies in Q1/Q2, sell them off in Q3/Q4
            if past_idx < len(PAST_TICKERS):
                past1 = PAST_TICKERS[past_idx]
                past_idx += 1
                target_wallet = "retirement" if (past_idx % 2 == 0) else "global"
                
                # Buy
                buy_val = 6000 + (year - 2021) * 500
                add_tx(target_wallet, f"{year}-{m:02d}-18", "BUY", past1[1], past1[0], "USD", 25, buy_val, "Kupno")
                
                # Sell off a few months later (with profit)
                sell_month = min(m + 2, 12)
                sell_date = f"{year}-{sell_month:02d}-25"
                sell_val = buy_val * 1.18  # 18% profit
                add_tx(target_wallet, sell_date, "SELL", past1[1], past1[0], "USD", 25, sell_val, "Sprzedaż")

            # Dividend payments
            if q in (2, 4):
                div_date = f"{year}-{m:02d}-28"
                add_tx("retirement", div_date, "DIVIDEND", "Apple Inc.", "AAPL", "USD", 0, 150 + (year - 2021) * 30, "Dywidenda")
                add_tx("global", div_date, "DIVIDEND", "JPMorgan Chase & Co.", "JPM", "USD", 0, 180 + (year - 2021) * 40, "Dywidenda")

    return tx_list


def populate_environment(env_key):
    cfg = ENVS[env_key]
    user_id = cfg["userId"]
    print(f"\n=======================================================")
    print(f"Populating Environment: {env_key.upper()} (UserId: {user_id})")
    print(f"=======================================================")

    # Set environment variables and override module-level table constants
    os.environ["DATA_TABLE"] = cfg["data_table"]
    os.environ["USERS_TABLE"] = cfg["users_table"]
    os.environ["TRANSACTIONS_TABLE"] = cfg["tx_table"]
    os.environ["SNAPSHOTS_TABLE"] = cfg["snapshots_table"]
    os.environ["ROAST_HISTORY_TABLE"] = cfg["roast_table"]

    db._USERS_TABLE_NAME = cfg["users_table"]
    db._DATA_TABLE_NAME = cfg["data_table"]
    db._users_table_ref = None
    db._data_table_ref = None

    portfolios._DATA_TABLE_NAME = cfg["data_table"]
    portfolios._TRANSACTIONS_TABLE_NAME = cfg["tx_table"]
    portfolios._data_table = None
    portfolios._transactions_table_ref = None

    snapshots._DATA_TABLE_NAME = cfg["data_table"]
    snapshots._TRANSACTIONS_TABLE_NAME = cfg["tx_table"]
    snapshots._SNAPSHOTS_TABLE_NAME = cfg["snapshots_table"]
    snapshots._snapshots_table_ref = None

    dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
    users_table = dynamodb.Table(cfg["users_table"])
    data_table = dynamodb.Table(cfg["data_table"])
    tx_table = dynamodb.Table(cfg["tx_table"])
    snaps_table = dynamodb.Table(cfg["snapshots_table"])

    # 1. Update / Create User Profile
    user_profile = {
        "userId": user_id,
        "email": DEMO_EMAIL,
        "nickname": DEMO_NAME,
        "role": "ADVANCED",
        "createdAt": "2021-01-01T00:00:00Z",
        "updatedAt": datetime.datetime.utcnow().isoformat() + "Z",
        "settings": {
            "theme": "dark",
            "currency": "PLN",
            "defaultWallet": "Summary",
            "notifications": False,
            "benchmark": "WIG"
        },
        "portfolioMeta": {
            "wallets": ["Retirement", "Global"],
            "lastSyncAt": None,
            "totalValuePLN": None
        },
        "subscription": {
            "tier": "free",
            "stripeCustomerId": None,
            "validUntil": None
        }
    }
    users_table.put_item(Item=user_profile)
    print("✓ User profile created/updated in DynamoDB.")

    # 2. Create Wallets (Retirement & Global)
    p_ret = {
        "userId": user_id,
        "sk": "PORTFOLIO#retirement",
        "portfolioId": "retirement",
        "name": "Retirement",
        "currency": "PLN",
        "type": "real",
        "color": "#4a9fd4",
        "order": Decimal("1"),
        "createdAt": "2021-01-01T00:00:00Z",
        "updatedAt": datetime.datetime.utcnow().isoformat() + "Z"
    }
    p_glo = {
        "userId": user_id,
        "sk": "PORTFOLIO#global",
        "portfolioId": "global",
        "name": "Global",
        "currency": "PLN",
        "type": "real",
        "color": "#34c97a",
        "order": Decimal("2"),
        "createdAt": "2021-01-01T00:00:00Z",
        "updatedAt": datetime.datetime.utcnow().isoformat() + "Z"
    }
    data_table.put_item(Item=p_ret)
    data_table.put_item(Item=p_glo)
    print("✓ Wallets 'Retirement' and 'Global' created.")

    # 3. Clean old transactions and write new 5-year transactions
    print("Cleaning existing transactions...")
    from boto3.dynamodb.conditions import Key
    res = tx_table.query(KeyConditionExpression=Key("userId").eq(user_id))
    with tx_table.batch_writer() as batch:
        for item in res.get("Items", []):
            batch.delete_item(Key={"userId": user_id, "sk": item["sk"]})

    tx_list = generate_transactions_for_user(user_id)
    print(f"Writing {len(tx_list)} new 5-year transactions...")
    with tx_table.batch_writer() as batch:
        for tx in tx_list:
            batch.put_item(Item=tx)
    print(f"✓ {len(tx_list)} transactions written.")

    # 4. Rebuild Holdings from Transactions
    print("Rebuilding current holdings...")
    ret_holdings = portfolios.rebuild_holdings_from_transactions(user_id, "retirement")
    glo_holdings = portfolios.rebuild_holdings_from_transactions(user_id, "global")
    print(f"✓ Retirement active holdings: {len(ret_holdings)}")
    print(f"✓ Global active holdings: {len(glo_holdings)}")

    # 5. Seed daily snapshot items from 2021-01-01 to today so history recalculation populates every day
    print("Seeding daily snapshot placeholders from 2021-01-01 to present...")
    start_dt = datetime.date(2021, 1, 1)
    end_dt = datetime.date.today()
    delta = datetime.timedelta(days=1)
    
    dates_list = []
    curr = start_dt
    while curr <= end_dt:
        dates_list.append(curr.strftime("%Y-%m-%d"))
        curr += delta

    for pid in ["retirement", "global", "summary"]:
        with snaps_table.batch_writer() as batch:
            for d_str in dates_list:
                batch.put_item(Item={
                    "userId": user_id,
                    "sk": f"PORTFOLIO#{pid}#SNAPSHOT#{d_str}",
                    "portfolioId": pid,
                    "snapshotDate": d_str,
                    "portfolioValue": Decimal("0"),
                    "investmentValue": Decimal("0"),
                    "dailyReturn": Decimal("0"),
                    "createdAt": f"{d_str}T23:59:59Z",
                    "updatedAt": f"{d_str}T23:59:59Z"
                })

    print(f"✓ Seeded {len(dates_list)} daily snapshot placeholders for retirement, global, and summary.")

    print("Recalculating daily snapshot history from 2021-01-01...")
    ret_res = snapshots.recalculate_portfolio_snapshots_from_date(user_id, "retirement", "2021-01-01")
    glo_res = snapshots.recalculate_portfolio_snapshots_from_date(user_id, "global", "2021-01-01")
    sum_res = snapshots.recalculate_summary_snapshots_from_date(user_id, "2021-01-01")
    print(f"✓ Snapshots created - Retirement: {ret_res.get('updated')}, Global: {glo_res.get('updated')}, Summary: {sum_res}")

    # 6. Recalculate ATHs
    snapshots.recalculate_ath(user_id, "retirement")
    snapshots.recalculate_ath(user_id, "global")
    snapshots.recalculate_ath(user_id, "summary")
    print("✓ ATH calculations complete.")


if __name__ == "__main__":
    populate_environment("test")
    populate_environment("prod")
    print("\n=======================================================")
    print("🎉 Demo user 'roastfolio@ai' setup complete for Test & Prod!")
    print("=======================================================")
