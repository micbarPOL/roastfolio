import json
import re
from collections import defaultdict

file_path = "/Users/michal.bardadyn/Documents/Code/Dash/investment-history/lambda/data/comments.txt"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

arrays = []
start_idx = -1
bracket_level = 0
in_string = False
escape = False

for i, char in enumerate(content):
    if char == '"' and not escape:
        in_string = not in_string
    if not in_string:
        if char == '[':
            if bracket_level == 0:
                start_idx = i
            bracket_level += 1
        elif char == ']':
            bracket_level -= 1
            if bracket_level == 0 and start_idx != -1:
                arrays.append((start_idx, i + 1))
                start_idx = -1
    
    if char == '\\' and not escape:
        escape = True
    else:
        escape = False

print(f"Found {len(arrays)} potential JSON arrays.")

allowed_keys = {
    "templateId", "scenarioKey", "tone", "intensity", "messageAngle", 
    "structureFamily", "metaphorCategory", "titleTemplate", "messageTemplate", 
    "mainReasonTemplate", "suggestedFocusTemplate", "requiredData", 
    "cooldownDays", "weight", "enabled", "_editor_comments"
}

allowed_placeholders = {
    "totalPortfolioValue", "portfolioReturnPercent", "portfolioDailyReturnAmount", 
    "dailyBestAsset", "currency", "benchmarkName", "benchmarkReturnPercent", 
    "relativePerformancePercent", "dailyWorstAsset", "currentDrawdownFromATH"
}

unsafe_words = re.compile(r'\b(kill|suicide|rope|jump off|hang yourself|slit|bleach|fuck|shit|bitch|cunt|dick|cock|pussy|asshole|faggot|retard)\b', re.IGNORECASE)
advice_words = re.compile(r'\b(you should buy|you should sell|invest in|allocate more|short this|long this)\b', re.IGNORECASE)
prediction_words = re.compile(r'\b(will hit|will crash|going to zero|guaranteed to)\b', re.IGNORECASE)
procedural_phrases = re.compile(r'(Expected behavior:|Actual behavior:|Severity:|Incident logged:|Root cause:)', re.IGNORECASE)
double_negative = re.compile(r'\}\}\s*(down|loss|drop|negative)\b', re.IGNORECASE)

modifications = 0
new_content = ""
last_end = 0

for start, end in arrays:
    new_content += content[last_end:start]
    json_str = content[start:end]
    
    try:
        data = json.loads(json_str)
        if not isinstance(data, list):
            new_content += json_str
            last_end = end
            continue
    except json.JSONDecodeError as e:
        print(f"Failed to parse array at {start}: {e}")
        new_content += json_str
        last_end = end
        continue

    template_ids = set()
    title_templates = set()
    message_templates = set()
    opening_phrases = defaultdict(int)
    punchlines = defaultdict(int)

    for item in data:
        if not isinstance(item, dict): continue
        comments = []
        
        # Schema mismatch
        keys = set(item.keys())
        if not keys.issubset(allowed_keys) or not allowed_keys.difference({"_editor_comments"}).issubset(keys):
            missing = allowed_keys.difference({"_editor_comments"}) - keys
            extra = keys - allowed_keys
            if missing:
                comments.append(f"Missing keys: {missing}")
            if extra:
                comments.append(f"Extra keys: {extra}")

        # Duplicate templateId
        t_id = item.get("templateId", "")
        if t_id in template_ids:
            comments.append("Duplicate templateId")
        template_ids.add(t_id)

        # Duplicate titleTemplate
        title = item.get("titleTemplate", "")
        if title in title_templates:
            comments.append("Duplicate titleTemplate")
        title_templates.add(title)

        # Duplicate messageTemplate
        msg = item.get("messageTemplate", "")
        if msg in message_templates:
            comments.append("Duplicate messageTemplate")
        message_templates.add(msg)
        
        # Length
        if len(msg) > 180:
            comments.append("Message too long for dashboard card (> 180 chars)")
        if len(title) > 60:
            comments.append("Title too long (> 60 chars)")

        words = msg.split()
        if len(words) >= 3:
            opening = " ".join(words[:3]).lower()
            punchline = " ".join(words[-3:]).lower()
            opening_phrases[opening] += 1
            punchlines[punchline] += 1

        if procedural_phrases.search(msg):
            comments.append("Message sounds procedurally generated")

        if unsafe_words.search(msg) or unsafe_words.search(title):
            comments.append("Unsafe, vulgar, or profane content detected")

        if advice_words.search(msg) or advice_words.search(title) or advice_words.search(item.get("suggestedFocusTemplate") or ""):
            comments.append("Direct financial advice detected")

        if prediction_words.search(msg) or prediction_words.search(title):
            comments.append("Future prediction detected")

        text_to_check = title + " " + msg + " " + item.get("mainReasonTemplate", "") + " " + (item.get("suggestedFocusTemplate") or "")
        placeholders_in_text = set(re.findall(r'\{\{([^}]+)\}\}', text_to_check))
        req_data = set(item.get("requiredData", []) if isinstance(item.get("requiredData"), list) else [])
        
        unsupported = placeholders_in_text - allowed_placeholders
        if unsupported:
            comments.append(f"Unsupported placeholders: {unsupported}")
            
        missing_from_req = placeholders_in_text - req_data
        if missing_from_req:
            comments.append(f"Placeholders missing from requiredData: {missing_from_req}")
            
        unused_req = req_data - placeholders_in_text
        if unused_req:
            comments.append(f"requiredData fields not used in text: {unused_req}")

        if double_negative.search(msg):
            comments.append("Possible double negative with placeholders")

        if comments:
            item["_editor_comments"] = comments

    for item in data:
        if not isinstance(item, dict): continue
        msg = item.get("messageTemplate", "")
        words = msg.split()
        if len(words) >= 3:
            opening = " ".join(words[:3]).lower()
            punchline = " ".join(words[-3:]).lower()
            new_comments = []
            if opening_phrases[opening] > 5:
                new_comments.append("Highly repeated opening phrase")
            if punchlines[punchline] > 5:
                new_comments.append("Highly repeated punchline structure")
            if new_comments:
                if "_editor_comments" not in item:
                    item["_editor_comments"] = []
                item["_editor_comments"].extend(new_comments)

    for item in data:
        if isinstance(item, dict) and "_editor_comments" in item:
            item["_editor_comments"] = list(dict.fromkeys(item["_editor_comments"]))
            modifications += 1

    new_content += json.dumps(data, indent=2)
    last_end = end

new_content += content[last_end:]

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Validation complete. Modified {modifications} templates with _editor_comments.")
