import json
import re

file_path = "/Users/michal.bardadyn/Documents/Code/Dash/investment-history/lambda/data/comments.txt"
out_path = "/Users/michal.bardadyn/Documents/Code/Dash/investment-history/lambda/data/flagged_templates.json"

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

flagged = []

for start, end in arrays:
    json_str = content[start:end]
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "_editor_comments" in item:
                    flagged.append(item)
    except:
        pass

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(flagged, f, indent=2)

print(f"Extracted {len(flagged)} flagged templates to {out_path}")
