import urllib.parse
import json
import re

config = {
    "type": "line",
    "data": {
        "labels": ["1", "8", "15", "30"],
        "datasets": [
            {
                "data": [0, -1, 2, 4],
                "fill": True,
                "backgroundColor": "getGradientFillHelper('vertical', ['rgba(74,222,128,0.2)', 'rgba(74,222,128,0.0)'])"
            }
        ]
    },
    "options": {
        "scales": {
            "yAxes": [{
                "ticks": {
                    "callback": "function(value) { return value + '%'; }"
                },
                "afterBuildTicks": "function(scale) { scale.ticks = [4.5, 0, -7]; return scale.ticks; }"
            }]
        }
    }
}

s = json.dumps(config)
s = re.sub(r'"(function\([^)]*\)\s*\{.*?\})"', r'\1', s)
s = re.sub(r'"(getGradientFillHelper\([^)]*\))"', r'\1', s)

encoded = urllib.parse.quote(s)
url = f"https://quickchart.io/chart?w=516&h=180&format=png&bkg=transparent&c={encoded}"
import urllib.request
try:
    urllib.request.urlopen(url)
    print("SUCCESS")
except Exception as e:
    print("ERROR:", e)
    if hasattr(e, 'headers'):
        print(e.headers.get('x-quickchart-error'))
