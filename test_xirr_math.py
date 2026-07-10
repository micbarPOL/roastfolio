from datetime import datetime

def calc(cashflows):
    dates = [datetime.fromisoformat(cf[0][:10].replace('Z', '+00:00')) for cf in cashflows]
    amounts = [cf[1] for cf in cashflows]
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
    return r

print("Test multiple deposits:", calc([('2022-01-01', -100000), ('2023-01-01', -100000), ('2024-01-01', 226000)]))
