"""Test bootstrap: point the app at a throwaway SQLite file BEFORE importing
app modules (database.py builds its engine from the env var at import time),
and guarantee fault state never leaks between tests.
"""
import os
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_faults():
    from app.faults import FAULTS

    FAULTS.reset()
    yield
    FAULTS.reset()
