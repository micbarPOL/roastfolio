from datetime import datetime
def _xirr(cashflows):
    if not cashflows or len(cashflows) < 2:
        return 0.0
    try:
        if isinstance(cashflows[0][0], str):
            dates = [datetime.fromisoformat(cf[0].replace('Z', '+00:00')[:10]) for cf in cashflows]
        else:
            dates = [cf[0] for cf in cashflows]
    except Exception:
        return 0.0
    amounts = [cf[1] for cf in cashflows]
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return 0.0
    t0 = dates[0]
    years = [(d - t0).days / 365.0 for d in dates]
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
        if r <= -1.0:
            return -0.9999
    return r

cf1 = [("2026-01-01", -10000), ("2027-01-01", 11000)]
print("Test 1:", _xirr(cf1)) # Expect ~0.1 (10%)

cf2 = [("2026-01-15", -10000), ("2026-06-15", 11000)]
print("Test 2:", _xirr(cf2)) # Expect > 0.1

cf3 = [("2026-01-15", -10000), ("2026-03-10", -1700), ("2026-05-05", -2000), ("2026-06-02", -1500), ("2026-06-22", 15500)]
print("Test 3:", _xirr(cf3))
