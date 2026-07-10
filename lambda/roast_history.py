import boto3
import os
import uuid
import time
from datetime import datetime, timezone, timedelta

# In a real app, this would be set via environment variables. 
# We default to something for tests.
TABLE_NAME = os.environ.get('ROAST_HISTORY_TABLE', 'dev-roastfolio-roast-history')
dynamodb = boto3.resource('dynamodb')

def get_table():
    return dynamodb.Table(TABLE_NAME)

def save_roast(roast_record: dict):
    """
    Save a generated roast to the history table with a 90-day TTL.
    """
    table = get_table()
    now = datetime.now(timezone.utc)
    
    # 90-day TTL
    expires_at = int((now + timedelta(days=90)).timestamp())
    
    # Ensure ID and timestamps exist
    if 'id' not in roast_record:
        roast_record['id'] = str(uuid.uuid4())
    if 'createdAt' not in roast_record:
        roast_record['createdAt'] = now.isoformat()
        
    roast_record['expiresAt'] = expires_at
    
    # DynamoDB does not support floats easily without Decimal, so we convert them
    # But for this module we can assume floats are decimals or just pass them as floats if using boto3 properly
    from decimal import Decimal
    def convert_floats(obj):
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: convert_floats(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_floats(v) for v in obj]
        return obj

    roast_record = convert_floats(roast_record)

    table.put_item(Item=roast_record)
    return roast_record

def get_recent_history(user_id: str, days: int = 90, period_type: str = "daily") -> list:
    """
    Fetch the user's roast history from the past `days` days.
    """
    table = get_table()
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    try:
        response = table.query(
            KeyConditionExpression="userId = :uid AND createdAt >= :cutoff",
            ExpressionAttributeValues={
                ":uid": user_id,
                ":cutoff": cutoff_date
            },
            ScanIndexForward=False  # Newest first
        )
        items = response.get('Items', [])
        
        # Filter by periodType if requested (default to daily if not specified in old records)
        if period_type:
            items = [item for item in items if item.get('periodType', 'daily') == period_type]
            
        return items
    except Exception:
        return []

def get_latest_roast_today(user_id: str) -> dict:
    """
    Fetch the most recent roast generated for the user today.
    """
    table = get_table()
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    try:
        response = table.query(
            KeyConditionExpression="userId = :uid AND createdAt >= :startOfDay",
            ExpressionAttributeValues={
                ":uid": user_id,
                ":startOfDay": start_of_day
            },
            ScanIndexForward=False,  # Newest first
            Limit=1
        )
        items = response.get('Items', [])
        return items[0] if items else None
    except Exception:
        return None

import re

def _get_opening_phrase(text: str) -> str:
    """Extract the first 5 words as the opening phrase."""
    if not text:
        return ""
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    words = text.split()
    return " ".join(words[:5]).lower()

def is_too_similar_to_recent_message(new_message: dict, recent_messages: list, options: dict = None) -> dict:
    """
    Advanced similarity detection comparing a new message to a list of recent messages.
    Returns: {"tooSimilar": bool, "reason": str, "matchedMessageId": str|None, "similarityScore": float}
    """
    if options is None:
        options = {
            "token_overlap_threshold": 0.6,
            "trigram_overlap_threshold": 0.4
        }
        
    candidate_text = new_message.get("messageText", "")
    candidate_title = new_message.get("title", "")
    
    STOPWORDS = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "is", "are", "was", "were", "it", "this", "that", "of", "your", "you", "i", "we", "they"}
    
    def normalize(text):
        if not text:
            return ""
        text = re.sub(r'[^\w\s]', '', text.lower())
        return " ".join(text.split())
        
    def get_tokens(norm_text):
        return [w for w in norm_text.split() if w not in STOPWORDS]
        
    def get_trigrams(tokens):
        if len(tokens) < 3:
            return set([" ".join(tokens)]) if tokens else set()
        return set(" ".join(tokens[i:i+3]) for i in range(len(tokens)-2))

    norm_cand = normalize(candidate_text)
    cand_tokens = set(get_tokens(norm_cand))
    cand_trigrams = get_trigrams(get_tokens(norm_cand))
    cand_opening = " ".join(norm_cand.split()[:5])
    
    for record in recent_messages:
        record_id = record.get("id")
        record_title = record.get("title", "")
        record_text = record.get("messageText", "")
        
        # 1. Exact match
        if candidate_text and candidate_text.strip().lower() == record_text.strip().lower():
            return {"tooSimilar": True, "reason": "Exact message match.", "matchedMessageId": record_id, "similarityScore": 1.0}
            
        # 2. Same title
        if candidate_title and record_title and candidate_title.strip().lower() == record_title.strip().lower():
            return {"tooSimilar": True, "reason": "Exact title match.", "matchedMessageId": record_id, "similarityScore": 1.0}
            
        norm_rec = normalize(record_text)
        
        # 3. Same opening phrase (first 5 words)
        rec_opening = " ".join(norm_rec.split()[:5])
        if cand_opening and rec_opening and cand_opening == rec_opening:
            return {"tooSimilar": True, "reason": "Same opening phrase.", "matchedMessageId": record_id, "similarityScore": 1.0}
            
        rec_tokens = set(get_tokens(norm_rec))
        
        # 4. Token overlap
        if cand_tokens and rec_tokens:
            overlap = len(cand_tokens.intersection(rec_tokens))
            union = len(cand_tokens.union(rec_tokens))
            token_ratio = overlap / union if union > 0 else 0.0
            
            if token_ratio > options.get("token_overlap_threshold", 0.6):
                return {"tooSimilar": True, "reason": f"High token overlap ({token_ratio:.2f}).", "matchedMessageId": record_id, "similarityScore": token_ratio}
                
            # 5. Distinctive phrases (word trigrams)
            rec_trigrams = get_trigrams(get_tokens(norm_rec))
            if cand_trigrams and rec_trigrams:
                tri_overlap = len(cand_trigrams.intersection(rec_trigrams))
                tri_union = len(cand_trigrams.union(rec_trigrams))
                tri_ratio = tri_overlap / tri_union if tri_union > 0 else 0.0
                
                if tri_ratio > options.get("trigram_overlap_threshold", 0.4):
                    return {"tooSimilar": True, "reason": f"High distinctive phrase overlap ({tri_ratio:.2f}).", "matchedMessageId": record_id, "similarityScore": tri_ratio}

    return {"tooSimilar": False, "reason": "Passed similarity checks.", "matchedMessageId": None, "similarityScore": 0.0}


def check_cooldowns(new_candidate: dict, history: list) -> dict:
    """
    Evaluates a proposed commentary against the fetched history.
    Returns: {"allowed": bool, "reason": str}
    """
    now = datetime.now(timezone.utc)
    
    candidate_template = new_candidate.get("templateId")
    candidate_hash = new_candidate.get("messageHash")
    
    # Check exact hash (90 days) and template cooldowns (14 days)
    for record in history:
        created_at_str = record.get("createdAt")
        if not created_at_str:
            continue
        try:
            record_date = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except ValueError:
            continue
            
        days_ago = (now - record_date).days
        
        if candidate_hash and record.get("messageHash") == candidate_hash and days_ago < 90:
            return {"allowed": False, "reason": f"Exact message used {days_ago} days ago (90-day cooldown)."}
            
        if candidate_template and record.get("templateId") == candidate_template and days_ago < 14:
            return {"allowed": False, "reason": f"Template used {days_ago} days ago (14-day cooldown)."}

    # Use advanced similarity detection for text checks
    # Only check against messages from the last 7 days for text similarity, to avoid exhausting valid phrases
    recent_7_days = []
    for record in history:
        created_at_str = record.get("createdAt")
        if created_at_str:
            try:
                record_date = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                if (now - record_date).days < 7:
                    recent_7_days.append(record)
            except ValueError:
                pass
                
    sim_result = is_too_similar_to_recent_message(new_candidate, recent_7_days)
    if sim_result["tooSimilar"]:
        return {"allowed": False, "reason": sim_result["reason"]}
        
    return {"allowed": True, "reason": "Cooldown checks passed."}
