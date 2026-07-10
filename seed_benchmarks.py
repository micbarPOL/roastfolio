#!/usr/bin/env python3
"""
seed_benchmarks.py — upload Polish and global index monthly returns to DynamoDB.

Reads pre-built monthly OHLCV CSV files from src/data/ and computes
month-over-month returns using end-of-month close prices.  Writes items
to the SnapshotsTable using the same schema as benchmark_returns.py so
the Lambda and this script are interchangeable.

Usage:
    python3 seed_benchmarks.py                  # dry-run (no writes)
    python3 seed_benchmarks.py --env dev        # write to dev table
    python3 seed_benchmarks.py --env prod       # write to prod table
    python3 seed_benchmarks.py --env dev --profile myprofile

DynamoDB item schema (matches benchmark_returns.py):
    PK  userId      = "__benchmarks__"
    SK  sk          = "BENCHMARK#<id>#MONTH#<YYYY-MM>"
    benchmarkId     str
    month           "YYYY-MM"
    returnPct       Decimal  (Close[m] - Close[m-1]) / Close[m-1] * 100
    openPrice       Decimal  Close of previous month
    closePrice      Decimal  Close of this month
    updatedAt       ISO-8601 UTC
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# ── CSV file registry ─────────────────────────────────────────────────────
# Keys must match the benchmarkId used everywhere in the codebase.
DATA_DIR = Path(__file__).parent / "src" / "data"

BENCHMARK_FILES = {
    # Polish indices
    "WIG":        DATA_DIR / "wig_m.csv",
    "WIG20":      DATA_DIR / "wig20_m.csv",
    "MWIG40":     DATA_DIR / "mwig40_m.csv",
    "SWIG80":     DATA_DIR / "swig80_m.csv",
    # Global indices
    "MSCI_WORLD": DATA_DIR / "MSCI_m.csv",
    "NASDAQ":     DATA_DIR / "nasdaq.csv",
    "DAX":        DATA_DIR / "dax.csv",
    "SP500":      DATA_DIR / "sp500.csv",
}

# ── DynamoDB config ───────────────────────────────────────────────────────
_BENCHMARK_PK = "__benchmarks__"

TABLE_NAMES = {
    "dev":  "dev-roastfolio-snapshots",
    "prod": "roastfolio-snapshots",
}


def _sk(benchmark_id: str, ym: str) -> str:
    return f"BENCHMARK#{benchmark_id}#MONTH#{ym}"


# ── Data helpers ──────────────────────────────────────────────────────────

def decrement_month(ym: str) -> str:
    y, m = map(int, ym.split("-"))
    m -= 1
    if m == 0:
        m = 12
        y -= 1
    return f"{y:04d}-{m:02d}"


def load_monthly_returns_from_csv(benchmark_id: str, path: Path) -> list[dict]:
    """
    Parse a monthly OHLCV CSV and produce a list of DynamoDB-ready item dicts.
    """
    import datetime as dt

    raw_rows = []

    with open(path, newline="", encoding="utf-8-sig") as fh:
        # Detect delimiter
        first_line = fh.readline()
        fh.seek(0)
        delim = ";" if ";" in first_line else ","
        
        reader = csv.DictReader(fh, delimiter=delim)
        for row in reader:
            row_cleaned = {k.strip(): v for k, v in row.items() if k is not None}
            date_str = (row_cleaned.get("Date") or row_cleaned.get("Month Starting") or "").strip()
            if not date_str or date_str.lower() in ("date", "month starting"):
                continue

            # Clean commas if present (e.g. thousands separator)
            close_str = (row_cleaned.get("Close") or row_cleaned.get("Close/Last") or "").strip()
            open_str = (row_cleaned.get("Open") or "").strip()

            if close_str:
                close_str = close_str.replace(",", "")
            if open_str:
                open_str = open_str.replace(",", "")

            # Handle format like "Jun. 01, 2026" or "Jun 01, 2026"
            # We convert it to YYYY-MM-DD
            parsed_date = None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b. %d, %Y", "%b %d, %Y"):
                try:
                    parsed_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    pass

            if not parsed_date:
                # Fallback to simple slicing if format is YYYY-MM-DD or similar
                try:
                    parts = date_str.split("-")
                    if len(parts) >= 3:
                        parsed_date = dt.date(int(parts[0]), int(parts[1]), int(parts[2]))
                except Exception:
                    pass

            if not parsed_date:
                continue

            raw_rows.append({
                "date": parsed_date,
                "close_str": close_str,
                "open_str": open_str
            })

    if not raw_rows:
        print(f"  {benchmark_id}: no rows parsed from {path.name}")
        return []

    # Determine if dataset is daily or monthly
    months_seen = set(r["date"].strftime("%Y-%m") for r in raw_rows)
    avg_rows_per_month = len(raw_rows) / len(months_seen)
    is_daily = avg_rows_per_month > 3.0

    rows_map: dict[str, float] = {}  # YYYY-MM -> price

    if is_daily:
        grouped = {}
        for r in raw_rows:
            ym = r["date"].strftime("%Y-%m")
            grouped.setdefault(ym, []).append(r)
        for ym, group in grouped.items():
            best_entry = max(group, key=lambda x: x["date"])
            price_str = best_entry["close_str"]
            if price_str:
                try:
                    price = float(price_str)
                    if price > 0:
                        rows_map[ym] = price
                except ValueError:
                    pass
    else:
        for r in raw_rows:
            day = r["date"].day
            ym = r["date"].strftime("%Y-%m")
            if day <= 7:
                target_ym = decrement_month(ym)
                price_str = r["open_str"] or r["close_str"]
            else:
                target_ym = ym
                price_str = r["close_str"]

            if price_str:
                try:
                    price = float(price_str)
                    if price > 0:
                        rows_map[target_ym] = price
                except ValueError:
                    pass

    rows = sorted(rows_map.items())

    if len(rows) < 2:
        print(f"  {benchmark_id}: not enough data in {path.name} ({len(rows)} rows)")
        return []

    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    items: list[dict] = []

    for i in range(1, len(rows)):
        prev_ym, prev_close = rows[i - 1]
        curr_ym, curr_close = rows[i]
        ret_pct = (curr_close - prev_close) / prev_close * 100

        items.append({
            "userId":      _BENCHMARK_PK,
            "sk":          _sk(benchmark_id, curr_ym),
            "benchmarkId": benchmark_id,
            "month":       curr_ym,
            "returnPct":   Decimal(str(round(ret_pct, 6))),
            "openPrice":   Decimal(str(round(prev_close, 4))),
            "closePrice":  Decimal(str(round(curr_close, 4))),
            "updatedAt":   now_str,
            "source":      "csv",
        })

    return items


# ── DynamoDB upload ───────────────────────────────────────────────────────

def upload_to_dynamodb(
    items: list[dict],
    table_name: str,
    region: str,
    profile: str | None,
    overwrite: bool = True,
) -> int:
    """Batch-write items.  Returns count actually written."""
    import boto3  # noqa: PLC0415 (lazy import — not needed for dry-run)

    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    ddb = session.resource("dynamodb", region_name=region)
    table = ddb.Table(table_name)

    if not overwrite:
        # Check which months are already present and skip them
        existing_sks: set[str] = set()
        for item in items:
            resp = table.get_item(
                Key={"userId": _BENCHMARK_PK, "sk": item["sk"]},
                ProjectionExpression="sk",
            )
            if resp.get("Item"):
                existing_sks.add(item["sk"])
        items = [i for i in items if i["sk"] not in existing_sks]

    if not items:
        return 0

    written = 0
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
            written += 1

    return written


def remove_benchmark_from_dynamodb(
    benchmark_id: str,
    table_name: str,
    region: str,
    profile: str | None,
) -> None:
    """Query and delete all entries for a specific benchmark from DynamoDB."""
    import boto3  # noqa: PLC0415
    from boto3.dynamodb.conditions import Key  # noqa: PLC0415

    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    ddb = session.resource("dynamodb", region_name=region)
    table = ddb.Table(table_name)

    print(f"  Removing old DynamoDB entries for {benchmark_id} from {table_name}…")
    
    sk_prefix = f"BENCHMARK#{benchmark_id}#"
    response = table.query(
        KeyConditionExpression=Key("userId").eq(_BENCHMARK_PK) & Key("sk").begins_with(sk_prefix)
    )
    items = response.get("Items", [])
    
    if not items:
        print("  → No entries found to delete.")
        return

    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"userId": _BENCHMARK_PK, "sk": item["sk"]})
            
    print(f"  → Successfully deleted {len(items)} entries from {table_name}.")


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed benchmark monthly returns into DynamoDB."
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        default=None,
        help="Target environment. Omit for a dry-run (no writes).",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile name (defaults to the environment default).",
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region (default: us-west-2).",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Skip months that already exist in DynamoDB.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and compute returns but do not write to DynamoDB.",
    )
    args = parser.parse_args()

    dry_run = args.dry_run or args.env is None
    if dry_run and args.env is not None:
        dry_run = False  # explicit --env overrides implicit dry-run

    if dry_run:
        print("\n[DRY RUN] No data will be written to DynamoDB.\n")
    else:
        table_name = TABLE_NAMES[args.env]
        print(f"\nTarget table : {table_name}  (region: {args.region})\n")
        # Explicitly remove NIKKEI from the target database
        try:
            remove_benchmark_from_dynamodb("NIKKEI", table_name, args.region, args.profile)
        except Exception as e:
            print(f"  WARNING: Failed to remove NIKKEI from DynamoDB: {e}")

    total_computed = 0
    total_written  = 0

    for bid, path in BENCHMARK_FILES.items():
        if not path.exists():
            print(f"  {bid:<12} SKIP — file not found: {path}")
            continue

        items = load_monthly_returns_from_csv(bid, path)
        if not items:
            continue

        first = items[0]["month"]
        last  = items[-1]["month"]
        rets  = [float(i["returnPct"]) for i in items]
        avg   = round(sum(rets) / len(rets), 2)
        total_computed += len(items)

        print(
            f"  {bid:<12}  {len(items):>3} months  {first}–{last}"
            f"  avg={avg:+.2f}%  min={min(rets):+.2f}%  max={max(rets):+.2f}%",
            end="",
        )

        if dry_run:
            print("  [dry-run, not written]")
        else:
            written = upload_to_dynamodb(
                items,
                table_name=table_name,
                region=args.region,
                profile=args.profile,
                overwrite=not args.no_overwrite,
            )
            total_written += written
            print(f"  → {written} rows written")

    print()
    if dry_run:
        print(f"Dry-run complete. {total_computed} rows computed (0 written).")
        print("Run with --env dev or --env prod to upload.")
    else:
        print(f"Done. {total_computed} computed, {total_written} written to {table_name}.")


if __name__ == "__main__":
    main()
