import asyncio
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

from agent_service.client import HttpServiceClient
from deploy.combined import DemoGateway, create_app

TOKEN = "synthetic-internal-token-for-tests-only"


def test_catalog_can_explain_free_hosting_without_exposing_environment(monkeypatch):
    from agent_service.service import ResearchService

    class CatalogClient:
        def get(self, service, path):
            return {"cell_line_ids": ["SIDM00001"]} if path == "/cell-lines" else {"drug_names": ["Cisplatin"]}

    monkeypatch.setenv("HOSTING_NOTICE", "Free demo notice")
    monkeypatch.setenv("NCBI_API_KEY", "synthetic-secret-must-not-be-exposed")
    app = create_app(ResearchService(CatalogClient()), backends={}, token=TOKEN)
    with TestClient(app) as client:
        response = client.get("/catalog")
    assert response.json()["notice"] == "Free demo notice"
    assert "synthetic-secret-must-not-be-exposed" not in response.text


def test_literature_bootstrap_retries_without_logging_exception_secrets(monkeypatch, capsys):
    from deploy.seed_literature import main

    def fail():
        raise RuntimeError("url?api_key=synthetic-secret")

    monkeypatch.setattr("deploy.seed_literature.seed", fail)
    monkeypatch.setattr("deploy.seed_literature.wait_for_api", lambda: True)
    monkeypatch.setattr("deploy.seed_literature.time.sleep", lambda *_: None)
    assert main() == 1
    output = capsys.readouterr().out
    assert output.count("demo_literature_unavailable") == 3
    assert "synthetic-secret" not in output


def test_internal_backends_require_the_runtime_token():
    backend = FastAPI()

    @backend.get("/health")
    def health():
        return {"status": "ok"}

    app = create_app(backends={"prediction": backend}, token=TOKEN)
    with TestClient(app) as client:
        assert client.get("/internal/prediction/health").status_code == 404
        assert client.get("/internal/prediction/health", headers={"X-CancerBench-Internal": "wrong"}).status_code == 404
        assert client.get("/internal/prediction/health", headers={"X-CancerBench-Internal": TOKEN}).json() == {"status": "ok"}
        assert client.get("/").status_code == 200


def test_http_client_sends_internal_token_only_when_configured():
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"status":"ok"}'

    with patch("urllib.request.urlopen", return_value=Response()) as send:
        HttpServiceClient(internal_token=TOKEN).get("prediction", "/health")
        assert send.call_args.args[0].get_header("X-cancerbench-internal") == TOKEN
        HttpServiceClient().get("prediction", "/health")
        assert send.call_args.args[0].get_header("X-cancerbench-internal") is None


def test_free_demo_rejects_overlapping_work_and_releases_after_disconnect():
    async def scenario():
        started = asyncio.Event()
        finish = asyncio.Event()

        async def slow(scope, receive, send):
            started.set()
            await finish.wait()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        gateway = DemoGateway(slow, TOKEN)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway), base_url="http://test") as client:
            first = asyncio.create_task(client.post("/research/stream"))
            await started.wait()
            busy = await client.post("/research")
            assert busy.status_code == 429
            assert busy.headers["retry-after"] == "5"
            first.cancel()
            try:
                await first
            except asyncio.CancelledError:
                pass
            finish.set()
            assert (await client.post("/research")).status_code == 200

    asyncio.run(scenario())
