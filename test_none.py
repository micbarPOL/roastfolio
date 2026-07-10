import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'lambda'))

import portfolios
from datetime import datetime

tx = {'type': 'DEPOSIT', 'transactionDate': None, 'value': 1000}
date = tx.get('transactionDate', portfolios._today())
print(repr(date))
