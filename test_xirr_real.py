from datetime import datetime
def calculate_xirr(cashflows: list[tuple[str, float]]) -> float:
    if not cashflows or len(cashflows) < 2:
        return 0.0

    amounts = [cf[1] for cf in cashflows]
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return 0.0

    try:
        dates = [datetime.fromisoformat(cf[0][:10].replace('Z', '+00:00')) for cf in cashflows]
    except Exception as e:
        print(f"fromisoformat error: {e}")
        return 0.0

    d0 = dates[0]
    years = [(d - d0).days / 365.0 for d in dates]

    r = 0.1
    for _ in range(100):
        f_r = 0.0
        f_prime_r = 0.0
        for a, y in zip(amounts, years):
            f_r += a / ((1.0 + r) ** y)
            f_prime_r += -y * a / ((1.0 + r) ** (y + 1))
        
        if abs(f_prime_r) < 1e-10:
            break
            
        r_new = r - f_r / f_prime_r
        if abs(r_new - r) < 1e-6:
            return r_new
            
        r = r_new
        
        # If rate goes below -100%, cap it.
        if r <= -1.0:
            return -0.9999

    return r

cfs = [
    ('2024-06-20', -10000.0),
    ('2026-06-22', 12000.0)
]
print(calculate_xirr(cfs))
