import json
import urllib.parse
import sys

def get_chart_url(p_last):
    p_col = "#4ade80" if p_last >= 0 else "#f87171"
    bg_col = "rgba(74,222,128,0.2)" if p_last >= 0 else "rgba(248,113,113,0.2)"
    
    config = {
        "type": "line",
        "data": {
            "labels": ["Aug 01", "Aug 05", "Aug 10", "Aug 15", "Aug 20", "Aug 25", "Aug 31"],
            "datasets": [
                {
                    "data": [0.0, 1.2, -0.5, -2.0, 3.0, 4.5, p_last],
                    "borderColor": p_col,
                    "backgroundColor": bg_col,
                    "fill": True,
                    "borderWidth": 3,
                    "pointRadius": 0,
                    "lineTension": 0.4
                },
                {
                    "data": [0.0, 0.5, -1.0, -0.5, 4.0, 2.0, 4.8],
                    "borderColor": "#a78bfa",
                    "borderWidth": 2,
                    "borderDash": [5, 4],
                    "fill": False,
                    "pointRadius": 0,
                    "lineTension": 0.4
                }
            ]
        },
        "options": {
            "legend": {"display": False},
            "scales": {
                "xAxes": [{"display": False}],
                "yAxes": [{"display": False}]
            },
            "layout": {
                "padding": {"left": -10, "right": -10, "top": 10, "bottom": 10}
            },
            "annotation": {
                "annotations": [{
                    "type": "line",
                    "mode": "horizontal",
                    "scaleID": "y-axis-0",
                    "value": 0,
                    "borderColor": "#1e293b",
                    "borderWidth": 1,
                    "borderDash": [4, 4]
                }]
            }
        }
    }
    
    encoded = urllib.parse.quote(json.dumps(config))
    # Quickchart options: w, h, format, bkg, c
    return f"https://quickchart.io/chart?w=516&h=160&format=png&bkg=transparent&c={encoded}"

print("URL:", get_chart_url(4.2))
