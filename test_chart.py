import sys

def generate_html_chart(parsed_points):
    p_vals = [pt["p"] for pt in parsed_points]
    b_vals = [pt["b"] for pt in parsed_points]

    min_val = min(min(p_vals), min(b_vals), 0.0)
    max_val = max(max(p_vals), max(b_vals), 0.0)
    if max_val == min_val:
        max_val += 1.0
        min_val -= 1.0

    chart_height = 120
    range_val = max_val - min_val if max_val > min_val else 1.0
    
    row1_height = int((max_val / range_val) * chart_height) if max_val > 0 else 0
    row2_height = chart_height - row1_height
    
    cols = len(parsed_points)
    col_width = 100.0 / cols if cols > 0 else 100
    
    bar_html = f'<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="table-layout: fixed; border-collapse: collapse; max-width: 516px; margin: 0 auto;">'
    
    # ROW 1: POSITIVE VALUES
    if row1_height > 0:
        bar_html += f'<tr height="{row1_height}">'
        for pt in parsed_points:
            p = pt["p"]
            b = pt["b"]
            
            if p >= 0:
                h_px = int((p / max_val) * row1_height)
                h_px = max(h_px, 1) if p > 0 else 0
                
                # Color logic
                if p >= b:
                    bar_color = "#4ade80" # Beat benchmark (Bright Green)
                else:
                    bar_color = "#166534" # Underperformed benchmark (Dark Green)
                    
                if h_px > 0:
                    bar_html += f'<td valign="bottom" width="{col_width}%" style="padding: 0 1px;">'
                    bar_html += f'<div style="width: 100%; height: {h_px}px; background-color: {bar_color}; border-top-left-radius: 2px; border-top-right-radius: 2px;"></div>'
                    bar_html += '</td>'
                else:
                    bar_html += f'<td width="{col_width}%" style="padding: 0 1px;"></td>'
            else:
                bar_html += f'<td width="{col_width}%" style="padding: 0 1px;"></td>'
        bar_html += '</tr>'
        
    # ZERO LINE ROW
    bar_html += f'<tr height="1"><td colspan="{cols}" style="background-color: #1e293b; line-height: 1px; font-size: 1px;">&nbsp;</td></tr>'
    
    # ROW 2: NEGATIVE VALUES
    if row2_height > 0:
        bar_html += f'<tr height="{row2_height}">'
        for pt in parsed_points:
            p = pt["p"]
            b = pt["b"]
            if p < 0:
                h_px = int((p / min_val) * row2_height)
                h_px = max(h_px, 1)
                
                # Color logic
                if p >= b:
                    bar_color = "#991b1b" # Beat benchmark (Dark Red)
                else:
                    bar_color = "#f87171" # Underperformed benchmark (Bright Red)
                    
                bar_html += f'<td valign="top" width="{col_width}%" style="padding: 0 1px;">'
                bar_html += f'<div style="width: 100%; height: {h_px}px; background-color: {bar_color}; border-bottom-left-radius: 2px; border-bottom-right-radius: 2px;"></div>'
                bar_html += '</td>'
            else:
                bar_html += f'<td width="{col_width}%" style="padding: 0 1px;"></td>'
        bar_html += '</tr>'
        
    bar_html += '</table>'
    
    # Add x-axis labels
    first_date = parsed_points[0]["date"][-5:].replace("-", "/")
    last_date = parsed_points[-1]["date"][-5:].replace("-", "/")
    labels_html = f'<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="max-width: 516px; margin: 4px auto 0;"><tr><td style="font-size:10px;color:#64748b;">{first_date}</td><td align="right" style="font-size:10px;color:#64748b;">{last_date}</td></tr></table>'
    
    return bar_html + labels_html

points = [
    {"date": "2026-08-01", "p": 0.0, "b": 0.0},
    {"date": "2026-08-05", "p": 1.2, "b": 0.5},
    {"date": "2026-08-10", "p": -0.5, "b": -1.0},
    {"date": "2026-08-15", "p": -2.0, "b": -0.5},
    {"date": "2026-08-20", "p": 3.0, "b": 4.0},
    {"date": "2026-08-25", "p": 4.5, "b": 2.0},
    {"date": "2026-08-31", "p": 4.2, "b": 4.8},
]

html = generate_html_chart(points)
with open("test_chart.html", "w") as f:
    f.write(html)
print("Chart generated.")
