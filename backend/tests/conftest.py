import os
import sys
import tempfile
from pathlib import Path

_db = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ.setdefault("BRANDGUARD_LLM_PROVIDER", "none")
os.environ["BRANDGUARD_DEMO_RATE_LIMIT"] = "1000"
os.environ["BRANDGUARD_FRONTEND_DIST"] = "/nonexistent"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.create_all(engine)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


class WS:
    def __init__(self, client, data):
        self.c = client
        self.id = data["workspace_id"]
        self.token = data["token"]

    def h(self, role="creator"):
        return {"X-Workspace-Token": self.token, "X-Demo-Role": role}

    def get(self, path, role="creator", **kw):
        return self.c.get(f"/api/w/{self.id}{path}", headers=self.h(role), **kw)

    def post(self, path, role="creator", **kw):
        return self.c.post(f"/api/w/{self.id}{path}", headers=self.h(role), **kw)

    def put(self, path, role="creator", **kw):
        return self.c.put(f"/api/w/{self.id}{path}", headers=self.h(role), **kw)

    def audit_text(self, text, channel="website", title="Test"):
        r = self.post("/submissions", json={"title": title, "channel": channel, "text": text})
        assert r.status_code == 201, r.text
        return r.json()


@pytest.fixture()
def ws(client):
    r = client.post("/api/workspaces/demo")
    assert r.status_code == 201, r.text
    return WS(client, r.json())
