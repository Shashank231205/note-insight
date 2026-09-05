from fastapi.testclient import TestClient

from src.core.config import Environment, LLMProviderName, Settings
from src.main import create_app


def _settings(environment: Environment) -> Settings:
    return Settings(
        environment=environment,
        llm_provider=LLMProviderName.MOCK,
        firebase_project_id="note-insight-test",
    )


def test_health_is_public_and_reports_version(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.0.0"}


def test_every_response_carries_a_request_id(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Request-ID"]


def test_security_headers_are_applied(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_unknown_route_uses_the_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/not-a-route")

    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "NOT_FOUND"
    assert body["request_id"]


class TestSchemaExposure:
    """The interactive docs and the schema behind them are one decision.

    Turning off /docs while /openapi.json still answers hides the rendering,
    not the information.
    """

    def test_development_serves_docs_and_schema(self) -> None:
        app = create_app(_settings(Environment.DEVELOPMENT))
        client = TestClient(app)

        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200

    def test_production_serves_neither(self) -> None:
        app = create_app(_settings(Environment.PRODUCTION))
        client = TestClient(app)

        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
