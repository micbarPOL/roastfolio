import urllib.parse
import json

config = {
    "type": "line",
    "data": {
        "labels": ["1", "", "", "", "", "", "", "8", "", "", "", "", "", "", "15", "", "", "18", "", "", "", "", "", "", "", "", "", "", "", "", "31"],
        "datasets": [{
            "data": [0, -1, -2, -3, -4, -5, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 4.5, 4, 3, 2, 1, 0, -1, -2, -3, -4, -5, -4, -3, -2],
            "borderColor": "#4ade80",
            "fill": False
        }]
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
                    "fontSize": 12,
                    "fontStyle": "bold"
                }
            }],
            "yAxes": [{
                "display": True,
                "gridLines": {"display": False, "drawBorder": False},
                "ticks": {
                    "fontColor": "#64748b", 
                    "fontSize": 10
                },
                "afterBuildTicks": "function(scale) { scale.ticks = [4.5, 0, -6]; return scale.ticks; }"
            }]
        },
        "layout": {"padding": {"left": 0, "right": 0, "top": 10, "bottom": 0}}
    }
}

encoded = urllib.parse.quote(json.dumps(config))
print(f"https://quickchart.io/chart?w=516&h=160&format=png&bkg=transparent&c={encoded}")
