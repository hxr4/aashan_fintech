import os

os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aashan.db")
# Unit tests use deterministic fakes for embedding behavior and never download
# model weights. Production defaults to lazy embedding loading when unset.
os.environ.setdefault("AASHAN_ENABLE_EMBEDDINGS", "false")
