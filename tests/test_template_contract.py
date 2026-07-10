import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TemplateContractTests(unittest.TestCase):
    def test_prices_function_has_batch_write_permissions_for_migration_cleanup(self):
        template = (ROOT / "template.yaml").read_text()
        self.assertGreaterEqual(template.count("- dynamodb:BatchWriteItem"), 3)
        self.assertIn("- !GetAtt DataTable.Arn", template)
        self.assertIn("- !GetAtt TransactionsTable.Arn", template)
        self.assertIn("- !GetAtt SnapshotsTable.Arn", template)

    def test_snapshot_function_timeout_can_finish_historical_backfills(self):
        template = (ROOT / "template.yaml").read_text()
        snapshot_function = template.split("SnapshotFunction:", 1)[1].split("SnapshotScheduleRole:", 1)[0]

        self.assertIn("Timeout: 300", snapshot_function)


if __name__ == "__main__":
    unittest.main()
