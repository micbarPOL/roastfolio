import json
import sys
import os

sys.path.append(os.path.abspath('lambda'))

import handler
import db

# Override _require_role to simulate authenticated user
original_require_role = handler._require_role
def mock_require_role(event, min_role=db.ROLE_BASIC):
    return "e82153b0-10d1-70c7-dab9-824d6016be82", None

handler._require_role = mock_require_role

event = {
    "httpMethod": "GET",
    "path": "/portfolios/ike/snapshots",
    "pathParameters": {"portfolioId": "ike"},
    "headers": {"Authorization": "Bearer mocked"}
}

response = handler.portfolios_handler(event)
print("StatusCode:", response["statusCode"])
if response["statusCode"] == 500:
    print("Error:", response["body"])
else:
    print("Success, body length:", len(response["body"]))

