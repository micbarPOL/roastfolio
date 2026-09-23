import pytest

pytestmark = pytest.mark.full

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "update-prices.py"
SPEC = importlib.util.spec_from_file_location("update_prices_module", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_generate_returns_data_parses_polish_decimal_csv_and_keeps_manual_corrections(tmp_path, monkeypatch):
    src_dir = tmp_path / "src"
    data_dir = src_dir / "data"
    scripts_dir = src_dir / "scripts"
    data_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)

    csv_path = data_dir / "myfund.pl_Emerytura_StopaZwrotuWOkresach.csv"
    csv_path.write_text(
        "period;emerytura;wig;wig20;inflation;deposits;sp500;unused;mwig40\n"
        "2024-01;1,5;2,0;3,0;4,0;5,0;6,0;7,0;8,25\n"
        "2024-02;9,0;10,0;11,0;12,0;13,0;14,0;15,0;16,5\n",
        encoding="iso-8859-2",
    )

    existing = scripts_dir / "data-returns.js"
    existing.write_text(
        "var RETURNS_DATA = ["
        "{\"period\":\"2024-01\",\"mwig40\":99.9},"
        "{\"period\":\"2024-02\",\"mwig40\":0.0}"
        "];\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    MODULE.generate_returns_data()

    saved = json.loads((scripts_dir / "data-returns.js").read_text().split("=", 1)[1].strip().rstrip(";"))
    by_period = {row["period"]: row for row in saved}

    assert by_period["2024-01"]["mwig40"] == 99.9
    assert by_period["2024-02"]["mwig40"] == 16.5
