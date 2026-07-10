import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import json
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import monthly_job

@pytest.fixture
def mock_db():
    with patch("monthly_job.db.list_users") as list_users:
        list_users.return_value = [{"userId": "user_monthly_1", "settings": {"roastIntensity": "sarcastic"}}]
        yield list_users

@pytest.fixture
def mock_portfolios():
    with patch("portfolios.list_portfolios") as list_ports:
        list_ports.return_value = [{"portfolioId": "port_1", "benchmarkId": "SPY"}]
        yield list_ports

@pytest.fixture
def mock_snapshots():
    now = datetime.now(timezone.utc)
    target_date = now.replace(day=1) - timedelta(days=1)
    target_month = target_date.strftime("%Y-%m")
    
    baseline_date = target_date.replace(day=1) - timedelta(days=1)
    baseline_month = baseline_date.strftime("%Y-%m")
    
    with patch("monthly_job.snapshots.list_snapshots") as list_snaps:
        list_snaps.return_value = [
            {"sk": f"PORTFOLIO#port_1#SNAPSHOT#{target_month}-30", "portfolioValue": 10500, "topAsset": "AAPL", "topAssetPct": 5.0, "worstAsset": "TSLA", "worstAssetPct": -2.0},
            {"sk": f"PORTFOLIO#port_1#SNAPSHOT#{baseline_month}-30", "portfolioValue": 10000}
        ]
        yield list_snaps

@pytest.fixture
def mock_roast_engine():
    with patch("monthly_job.roast_engine.generate_monthly_roast") as generate_monthly_roast:
        yield generate_monthly_roast

def test_monthly_job_success(mock_db, mock_portfolios, mock_snapshots, mock_roast_engine):
    # Execute the cron handler
    response = monthly_job.handler({}, None)
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["processed"] == 1
    assert body["failed"] == 0
    
    # Verify generate_monthly_roast was called with correct monthly calculation
    mock_roast_engine.assert_called_once()
    kwargs = mock_roast_engine.call_args.kwargs
    
    assert kwargs["user_id"] == "user_monthly_1"
    assert kwargs["current_snapshot"]["portfolioValue"] == 10500
    assert kwargs["prev_month_snapshot"]["portfolioValue"] == 10000
    assert kwargs["enable_ai"] is True
