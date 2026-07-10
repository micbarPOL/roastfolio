import json
import re

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

new_content = ""
last_end = 0

mechanical_fixes_count = 0
remaining_flagged = 0

for start, end in arrays:
    new_content += content[last_end:start]
    json_str = content[start:end]
    
    try:
        data = json.loads(json_str)
    except:
        new_content += json_str
        last_end = end
        continue

    for item in data:
        if not isinstance(item, dict): continue
        if "_editor_comments" in item:
            comments = item["_editor_comments"]
            
            # Mechanical fix: requiredData sync
            text_to_check = item.get("titleTemplate", "") + " " + item.get("messageTemplate", "") + " " + item.get("mainReasonTemplate", "") + " " + (item.get("suggestedFocusTemplate") or "")
            placeholders_in_text = list(set(re.findall(r'\{\{([^}]+)\}\}', text_to_check)))
            
            has_placeholder_issue = any("requiredData" in c or "Missing keys" in c for c in comments)
            has_other_issues = any(not ("requiredData" in c or "Missing keys" in c) for c in comments)
            
            if has_placeholder_issue:
                item["requiredData"] = placeholders_in_text
                mechanical_fixes_count += 1
                
                if not has_other_issues:
                    del item["_editor_comments"]
                else:
                    item["_editor_comments"] = [c for c in comments if not ("requiredData" in c or "Missing keys" in c)]
                    remaining_flagged += 1
            else:
                remaining_flagged += 1

    new_content += json.dumps(data, indent=2)
    last_end = end

new_content += content[last_end:]

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Applied mechanical fixes to {mechanical_fixes_count} templates.")
print(f"Templates still needing creative rewrites: {remaining_flagged}")
