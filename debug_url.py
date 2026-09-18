import sys
import os
import json
sys.path.insert(0, os.path.abspath('lambda'))
import email_service

profile = {"userId": "user-1", "email": "test@example.com"}
wrap = {
    "period": "2026-06",
    "market_context": [{"id": "WIG", "name": "WIG", "return_pct": -0.99}],
    "journey": {
        "benchmark_id": "WIG",
        "benchmark_return_pct": 1.20,
        "points": [
            {"date": f"2026-06-{i:02d}", "portfolio_pct": i, "benchmark_pct": i/2.0} for i in range(1, 31)
        ]
    }
}

_, _, html_body = email_service.render_monthly_recap_email(profile, wrap)
import re
match = re.search(r'img src="(https://quickchart\.io/chart\?[^"]+)"', html_body)
if match:
    print(match.group(1))
else:
    print("Not found")
