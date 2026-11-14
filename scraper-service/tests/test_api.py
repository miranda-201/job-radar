import time

import httpx
import jwt
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.publisher import InMemoryPublisher
from app.store import InMemoryStore

SECRET = "test-secret-test-secret-test-secret-test-secret"


@pytest.fixture
def ctx(tmp_path):
    targets = tmp_path / "targets.json"
    targets.write_text(
        '[{"id": "acme", "company": "Acme", "source": "greenhouse", "board": "acme", "keywords": ["intern"]}]'
    )
    settings = Settings(jwt_secret=SECRET, targets_file=str(targets))
    pub = InMemoryPublisher()
    app = create_app(settings, store=InMemoryStore(), publisher=pub, start_scheduler=False)
    with TestClient(app) as client:
        yield client, pub


def auth(sub: str = "1", secret: str = SECRET, ttl: int = 300) -> dict:
    token = jwt.encode({"sub": sub, "exp": int(time.time()) + ttl}, secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_health_is_public(ctx):
    client, _ = ctx
    assert client.get("/health").json() == {"status": "UP", "redis": True, "rabbitmq": True}


def test_api_requires_valid_jwt(ctx):
    client, _ = ctx
    assert client.get("/api/scraper/targets").status_code == 401
    assert (
        client.get("/api/scraper/targets", headers=auth(secret="wrong-secret-wrong-secret-wrong!!")).status_code == 401
    )
    assert client.get("/api/scraper/targets", headers=auth(ttl=-10)).status_code == 401


def test_targets_are_seeded_and_crud_works(ctx):
    client, _ = ctx
    h = auth()
    assert [t["id"] for t in client.get("/api/scraper/targets", headers=h).json()] == ["acme"]

    new = {
        "id": "nvidia",
        "company": "NVIDIA",
        "source": "workday",
        "board": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
        "keywords": ["intern"],
    }
    assert client.post("/api/scraper/targets", json=new, headers=h).status_code == 201
    assert client.post("/api/scraper/targets", json=new, headers=h).status_code == 409

    new["keywords"] = ["intern", "co-op"]
    assert client.put("/api/scraper/targets/nvidia", json=new, headers=h).json()["keywords"] == ["intern", "co-op"]
    assert client.delete("/api/scraper/targets/nvidia", headers=h).status_code == 204
    assert client.delete("/api/scraper/targets/nvidia", headers=h).status_code == 404


@respx.mock
def test_manual_scrape_hits_greenhouse_and_publishes(ctx):
    client, pub = ctx
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {"id": 1, "title": "SWE Intern", "absolute_url": "https://acme/1", "location": {"name": "Remote"}},
                    {"id": 2, "title": "Principal Engineer", "absolute_url": "https://acme/2"},
                ]
            },
        )
    )
    report = client.post("/api/scraper/scrape", headers=auth()).json()
    assert report["results"][0] | {"duration_ms": 0} == {
        "target_id": "acme",
        "fetched": 2,
        "matched": 1,
        "new": 1,
        "error": None,
        "duration_ms": 0,
    }
    assert [e.title for e in pub.events] == ["SWE Intern"]
    assert client.get("/api/scraper/scrape/last", headers=auth()).json()["results"][0]["new"] == 1
    assert "scraper_jobs_published_total" in client.get("/metrics").text
