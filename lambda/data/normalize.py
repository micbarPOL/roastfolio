import json

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

desired_order = [
    "templateId", "scenarioKey", "tone", "intensity", "messageAngle", 
    "structureFamily", "metaphorCategory", "titleTemplate", "messageTemplate", 
    "mainReasonTemplate", "suggestedFocusTemplate", "requiredData", 
    "cooldownDays", "weight", "enabled", "_editor_comments"
]

new_content = ""
last_end = 0
normalized_count = 0

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

    normalized_data = []
    for item in data:
        if not isinstance(item, dict):
            normalized_data.append(item)
            continue
            
        # 2. enabled must be true
        item["enabled"] = True
        
        # 3. cooldownDays is number
        if "cooldownDays" in item:
            try:
                item["cooldownDays"] = int(item["cooldownDays"])
            except:
                pass
                
        # 4. weight is number
        if "weight" in item:
            try:
                item["weight"] = int(item["weight"])
            except:
                pass
                
        # 5. requiredData is array
        if "requiredData" not in item or not isinstance(item["requiredData"], list):
            item["requiredData"] = []
            
        # 6. suggestedFocusTemplate is string or null
        if "suggestedFocusTemplate" in item and not isinstance(item["suggestedFocusTemplate"], str) and item["suggestedFocusTemplate"] is not None:
            item["suggestedFocusTemplate"] = str(item["suggestedFocusTemplate"])
            
        # Ensure proper order
        ordered_item = {}
        for key in desired_order:
            if key in item:
                ordered_item[key] = item[key]
                
        for key in item.keys():
            if key not in desired_order:
                ordered_item[key] = item[key]
                
        normalized_data.append(ordered_item)
        normalized_count += 1

    # Python's json.dumps keeps the order of the dictionary
    new_content += json.dumps(normalized_data, indent=2)
    last_end = end

new_content += content[last_end:]

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Normalized {normalized_count} templates.")
