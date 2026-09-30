import os
import tempfile
from pathlib import Path

_dir = Path(tempfile.mkdtemp(prefix="bbliga-"))
os.environ["BB_DATABASE"] = f"sqlite:///{_dir / 'test.db'}"
os.environ["MASTER_KEY"] = "test-master"
os.environ["BB_SECRET"] = "test-secret"
os.environ["BB_AUTO_SEED"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine, init_db
from app.main import app


@pytest.fixture()
def client():
    SQLModel.metadata.drop_all(engine)
    init_db()
    with TestClient(app) as test_client:
        yield test_client
