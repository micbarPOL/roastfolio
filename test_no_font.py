import urllib.parse
import json

config = {
    "type": "line",
    "data": {
        "labels": ["1", "", "", "", "", "", "", "8", "", "", "", "", "", "", "15", "", "", "18", "", "", "", "", "", "", "", "", "", "", "", "", "31"],
        "datasets": [
            {
                "data": [0, -1, -2, -3, -4, -5, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 4.5, 4, 3, 2, 1, 0, -1, -2, -3, -4, -5, -4, -3, -2],
                "borderColor": "#4ade80",
                "backgroundColor": "getGradientFillHelper('vertical', ['rgba(74,222,128,0.2)', 'rgba(74,222,128,0.0)'])",
                "fill": True,
                "borderWidth": 2,
                "pointRadius": 0,
                "lineTension": 0.1
            },
            {
                "data": [-1, -2, -3, -4, -5, -6, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 3.5, 3, 2, 1, 0, -1, -2, -3, -4, -5, -6, -5, -4, -3],
                "borderColor": "#a78bfa",
                "borderWidth": 1.5,
                "borderDash": [4, 4],
                "fill": False,
                "pointRadius": 0,
                "lineTension": 0.1
            }
        ]
    },
    "options": {
        "legend": {"display": False},
        "scales": {
            "xAxes": [{
                "display": True,
                "gridLines": {"display": False, "drawBorder": False},
                "ticks": {"fontColor": "#64748b", "fontSize": 10, "autoSkip": False, "maxRotation": 0},
                "scaleLabel": {
                    "display": True,
                    "labelString": "August",
                    "fontColor": "#64748b",
                    "fontSize": 11,
                    "fontStyle": "bold",
                    "padding": {"top": 4}
                }
            }],
            "yAxes": [{
                "display": True,
                "gridLines": {"display": False, "drawBorder": False},
                "ticks": {
                    "fontColor": "#64748b", 
                    "fontSize": 10,
                    "callback": "function(value) { return value + '%'; }"
                },
                "afterBuildTicks": "function(scale) { scale.ticks = [4.5, 0, -7]; return scale.ticks; }"
            }]
        },
        "layout": {"padding": {"left": 0, "right": 10, "top": 10, "bottom": 0}},
        "annotation": {
            "annotations": [{
                "type": "line",
                "mode": "horizontal",
                "scaleID": "y-axis-0",
                "value": 0,
                "borderColor": "#1e293b",
                "borderWidth": 1,
                "borderDash": [2, 2]
            }]
        }
    }
}

encoded = urllib.parse.quote(json.dumps(config))
url = f"https://quickchart.io/chart?w=516&h=180&format=png&bkg=transparent&c={encoded}"
print("URL:", url)
import urllib.request
try:
    urllib.request.urlopen(url)
    print("SUCCESS")
except Exception as e:
    print("ERROR:", e)
    if hasattr(e, 'headers'):
        print(e.headers.get('x-quickchart-error'))
