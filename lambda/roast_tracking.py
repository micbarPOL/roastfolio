import boto3
import os
import uuid
from datetime import datetime, timezone, timedelta
from boto3.dynamodb.conditions import Key, Attr
from collections import defaultdict

TABLE_NAME = os.environ.get('ROAST_EVENTS_TABLE', 'dev-roastfolio-roast-events')
dynamodb = boto3.resource('dynamodb')

def get_table():
    return dynamodb.Table(TABLE_NAME)

VALID_EVENTS = {
    "roast_displayed", 
    "roast_copied", 
    "roast_reacted_positive", 
    "roast_reacted_negative", 
    "roast_hidden", 
    "roast_regenerated"
}

VALID_REACTIONS = {
    "good", "repetitive", "wrong", "boring"
}

def record_event(payload: dict) -> dict:
    """
    Record a roast performance tracking event.
    """
    event_type = payload.get("eventType")
    if event_type not in VALID_EVENTS:
        raise ValueError(f"Invalid eventType: {event_type}")

    # Reaction validation
    if event_type in ("roast_reacted_positive", "roast_reacted_negative"):
        reaction = payload.get("reaction")
        if reaction and reaction not in VALID_REACTIONS:
            raise ValueError(f"Invalid reaction: {reaction}")

    table = get_table()
    now = datetime.now(timezone.utc).isoformat()
    
    item = {
        "templateId": payload.get("templateId", "unknown"),
        "createdAt": now,
        "userId": payload.get("userId", "anonymous"),
        "scenarioKey": payload.get("scenarioKey", "unknown"),
        "intensity": payload.get("intensity", "unknown"),
        "messageAngle": payload.get("messageAngle", "unknown"),
        "structureFamily": payload.get("structureFamily", "unknown"),
        "metaphorCategory": payload.get("metaphorCategory", "unknown"),
        "source": payload.get("source", "template"),
        "eventType": event_type,
        "portfolioChange": payload.get("portfolioChange"),
        "benchmarkChange": payload.get("benchmarkChange"),
        "bestAsset": payload.get("bestAsset"),
        "worstAsset": payload.get("worstAsset")
    }
    
    if payload.get("reaction"):
        item["reaction"] = payload.get("reaction")

    from decimal import Decimal
    def convert_floats(obj):
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: convert_floats(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_floats(v) for v in obj]
        return obj

    item = convert_floats(item)

    table.put_item(Item=item)
    return item

def get_template_report(days: int = 30) -> dict:
    """
    Generate a simple developer report computing display counts, positive/negative rates,
    and identifying potentially bad templates based on repetitive/harsh reactions.
    """
    table = get_table()
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    # We do a full scan since it's a developer report script and we need all templates.
    # In a real large app, this would be an aggregation pipeline or partitioned scan.
    response = table.scan(
        FilterExpression=Attr('createdAt').gte(cutoff_date)
    )
    items = response.get('Items', [])
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('createdAt').gte(cutoff_date),
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response.get('Items', []))

    # Aggregations
    template_stats = defaultdict(lambda: {
        "displayed": 0,
        "positive": 0,
        "negative": 0,
        "repetitive": 0,
        "wrong": 0,
        "boring": 0,
        "copied": 0
    })

    scenario_stats = defaultdict(lambda: {"displayed": 0, "positive": 0, "negative": 0})

    for item in items:
        tid = item.get("templateId")
        scen = item.get("scenarioKey")
        evt = item.get("eventType")
        rxn = item.get("reaction")

        if evt == "roast_displayed":
            template_stats[tid]["displayed"] += 1
            scenario_stats[scen]["displayed"] += 1
        elif evt == "roast_reacted_positive":
            template_stats[tid]["positive"] += 1
            scenario_stats[scen]["positive"] += 1
        elif evt == "roast_reacted_negative":
            template_stats[tid]["negative"] += 1
            scenario_stats[scen]["negative"] += 1
            if rxn == "repetitive":
                template_stats[tid]["repetitive"] += 1
            elif rxn == "wrong":
                template_stats[tid]["wrong"] += 1
            elif rxn == "boring":
                template_stats[tid]["boring"] += 1
        elif evt == "roast_copied":
            template_stats[tid]["copied"] += 1

    report = {
        "templates": {},
        "scenarios": dict(scenario_stats),
        "disable_candidates": []
    }

    for tid, stats in template_stats.items():
        disp = stats["displayed"]
        # Allow metrics even if display is 0 (e.g. edge cases where displayed event wasn't sent but reaction was)
        pos_rate = stats["positive"] / disp if disp > 0 else 0.0
        neg_rate = stats["negative"] / disp if disp > 0 else 0.0
        
        report["templates"][tid] = {
            "displayCount": disp,
            "positiveRate": round(pos_rate, 4),
            "negativeRate": round(neg_rate, 4),
            "repetitiveCount": stats["repetitive"],
            "wrongCount": stats["wrong"],
            "boringCount": stats["boring"],
            "copiedCount": stats["copied"]
        }

        # Rule for disable suggestion: high negative rate or high repetitive count
        if (disp >= 5 and neg_rate >= 0.5) or stats["repetitive"] >= 3:
            report["disable_candidates"].append({
                "templateId": tid,
                "reason": "high_negative_rate" if neg_rate >= 0.5 else "highly_repetitive",
                "stats": report["templates"][tid]
            })

    return report
