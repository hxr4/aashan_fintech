import os
import uuid

import pytest

os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aashan.db")
# Unit tests use deterministic fakes for embedding behavior and never download
# model weights. Production defaults to lazy embedding loading when unset.
os.environ.setdefault("AASHAN_ENABLE_EMBEDDINGS", "false")


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Give every test its own database.

    The ledger is now the read model, so financial totals accumulate across
    imports for a user -- which is the correct behaviour. Tests that share one
    database would therefore see each other's transactions. Isolation keeps each
    test's arithmetic checkable on its own terms.
    """
    from app.config import settings
    from app.database import repository

    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/test.db")
    repository._repositories.clear()
    yield
    repository._repositories.clear()
