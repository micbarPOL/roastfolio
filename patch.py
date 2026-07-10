import re

with open("lambda/handler.py", "r") as f:
    content = f.read()

# Remove iterencode from _DecimalEncoder
content = re.sub(
    r"    def iterencode\(self, o, _one_shot=False\):\n        # Walk the object tree before encoding and replace nan/inf with None\n        return super\(\)\.iterencode\(self\._sanitize\(o\), _one_shot\)\n\n",
    "",
    content
)

# Update _resp to call _sanitize explicitly
content = content.replace(
    'return {"statusCode": status, "headers": _cors_headers(cache_seconds), "body": json.dumps(body, cls=_DecimalEncoder)}',
    'return {"statusCode": status, "headers": _cors_headers(cache_seconds), "body": json.dumps(_DecimalEncoder._sanitize(body), cls=_DecimalEncoder)}'
)

with open("lambda/handler.py", "w") as f:
    f.write(content)
