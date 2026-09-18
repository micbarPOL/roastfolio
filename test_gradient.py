import urllib.parse
import json
import urllib.request

bg_col = "getGradientFillHelper('vertical', ['rgba(74,222,128,0.3)', 'rgba(74,222,128,0.0)'])"

chart_config = {
    "type": "line",
    "data": {
        "labels": ["1", "2", "3"],
        "datasets": [{
            "data": [0, 5, 10],
            "backgroundColor": bg_col,
            "borderColor": "#4ade80",
            "fill": True
        }]
    }
}
encoded = urllib.parse.quote(json.dumps(chart_config))
url = f"https://quickchart.io/chart?c={encoded}"
print(url)
urllib.request.urlretrieve(url, "test_grad.png")
print("Downloaded test_grad.png")
