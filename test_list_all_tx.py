import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'lambda'))

import portfolios

portfolios.list_all_transactions = lambda *args, **kwargs: [
    {'type': 'DEPOSIT', 'transactionDate': '2023-01-01', 'value': 1000},
    {'type': 'BUY', 'transactionDate': '2023-01-02', 'value': 1000}
]

cfs = portfolios.get_portfolio_cashflows('u', 'p')
print(cfs)
