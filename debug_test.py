import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lambda'))

import roast_engine
from unittest.mock import patch

def debug_it():
    user_id = "u3"
    recent_history = []
    
    with patch("roast_history.get_recent_history") as m_hist, \
         patch("roast_history.save_roast") as m_save:
         
        m_hist.side_effect = lambda uid, **kw: list(recent_history)
        def save_fn(r):
            recent_history.insert(0, r)
            return r
        m_save.side_effect = save_fn
        
        for i in range(5):
            val = 10000 - (i * 200)
            snapshot = {"totalPortfolioValue": val, "portfolioValue": val, "dailyChangePct": -2.0, "isAth": False}
            benchmark = {"dailyChangePct": 1.0}
            
            res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
            print(f"Iter {i}: Tone={res.get('tone')}, Scenario={res.get('scenarioKey')}, Template={res.get('templateId')}")
            
if __name__ == '__main__':
    debug_it()
