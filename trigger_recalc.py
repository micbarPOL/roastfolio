import os
import runpy
import sys


os.environ.setdefault("AWS_REGION", "us-west-2")
os.environ.setdefault("DATA_TABLE", "roastfolio-data")
os.environ.setdefault("TRANSACTIONS_TABLE", "roastfolio-transactions")
os.environ.setdefault("SNAPSHOTS_TABLE", "roastfolio-snapshots")
os.environ.setdefault("USERS_TABLE", "roastfolio-users")


def run():
    lambda_dir = os.path.abspath("lambda")
    if lambda_dir not in sys.path:
        sys.path.insert(0, lambda_dir)
    module = runpy.run_path(os.path.join(lambda_dir, "trigger_recalc.py"))
    return module["run"]()


if __name__ == "__main__":
    run()
