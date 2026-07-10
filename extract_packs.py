import json
import re
import os

with open('lambda/data/comments.txt', 'r') as f:
    text = f.read()

# We need to find all top-level JSON arrays.
# A simple way is to find all text between [ and ] that successfully parses as JSON.
# Wait, brackets can be nested.
# Let's extract blocks starting with '[' and ending with ']' at the start/end of lines if possible, 
# or we can just try to find arrays.

import ast

def extract_json_arrays(text):
    arrays = []
    depth = 0
    start_idx = -1
    
    in_string = False
    escape = False
    
    for i, char in enumerate(text):
        if escape:
            escape = False
            continue
            
        if char == '\\':
            escape = True
            continue
            
        if char == '"':
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '[':
                if depth == 0:
                    start_idx = i
                depth += 1
            elif char == ']':
                depth -= 1
                if depth == 0 and start_idx != -1:
                    json_str = text[start_idx:i+1]
                    try:
                        arr = json.loads(json_str)
                        if isinstance(arr, list):
                            arrays.extend(arr)
                    except json.JSONDecodeError:
                        pass
                    start_idx = -1
    return arrays

all_templates = extract_json_arrays(text)
print(f"Extracted {len(all_templates)} templates from comments.txt")

os.makedirs('template_packs', exist_ok=True)
with open('template_packs/comments_extracted.json', 'w') as f:
    json.dump(all_templates, f, indent=2)

print("Saved to template_packs/comments_extracted.json")
