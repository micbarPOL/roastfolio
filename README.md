# Investment History Project

This project is a web application that displays the history of your investments and their values for each month. The data is sourced from an Excel file containing your investment records.

## Project Structure

```
investment-history
├── src
│   ├── index.html          # Main application shell
│   ├── styles/             # Application styles
│   ├── scripts/            # Dashboard, auth, live data, wallets, charts
│   └── data/               # CSV source files and static assets
├── package.json            # npm configuration file
└── README.md               # Project documentation
```

## Setup Instructions

1. **Clone the Repository**
   Clone this repository to your local machine using:
   ```
   git clone <repository-url>
   ```

2. **Install Dependencies**
   Navigate to the project directory and install the required npm packages:
   ```
   cd investment-history
   npm install
   ```

3. **Run the Application**
   Open the `src/index.html` file in your web browser to view the investment history.

## Data Source

The investment data is stored in `Stock.xlsx`, specifically in the "mBank" tab. The relevant columns are:
- **Column A**: Date of investment
- **Column B**: Amount invested
- **Column U**: Value of the investment

## Functionality

The application reads historical investment data, combines it with live Lambda/API data, and renders dashboard, portfolio, statistics, and transactions views in the browser.

## Historical transaction import

The authenticated backend migration route `POST /migrate` now imports both:

- current wallet holdings from the bundled `portfelSklad` CSV files
- historical transactions from the bundled `historiaOperacji` CSV files

Historical transaction import is idempotent. It preserves ledger-backed rows for `BUY`, `SELL`, `DEPOSIT`, `WITHDRAWAL`, `DIVIDEND`, `SPINOFF`, and `EXTRA_COST`, and skips intermediary `Dywidenda w drodze` rows that should not appear as final history entries.

The frontend `Transactions` and `Statistics` tabs now read from the live DynamoDB-backed ledger instead of `data-transactions.js`.

## License

This project is licensed under the MIT License.
