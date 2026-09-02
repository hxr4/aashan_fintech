from app.database.db import privacy_database_status
from app.services.mock_aa import generate_mock_transactions
from app.services.pipeline import process_raw_rows


def test_raw_data_is_not_persisted():
    aggregate = process_raw_rows(generate_mock_transactions(10))
    status = privacy_database_status()
    assert aggregate["transaction_count"] == 10
    assert status["raw_transactions_persisted"] is False
    assert status["aggregate_data_persisted"] is True
    assert "transactions" not in status["persisted_tables"]

