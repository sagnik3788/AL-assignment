from app.schemas import Action
from app.main import get_agent_dependency
import app.main as main_module


class StubAgent:
    mode = "openrouter"

    def respond(self, content, history, state):
        if "plan" in content.lower():
            return type("Result", (), {"action": Action.STUDY_PLAN, "text": "Plan created", "data": {"topic": "algebra"}, "rationale": "The user requested a plan."})()
        return type("Result", (), {"action": Action.QUIZ, "text": "Quiz created", "data": {"topic": state.get("last_topic")}, "rationale": "Follow-up based on session context."})()


def test_session_persists_context_and_can_be_deleted(client):
    client.app.dependency_overrides[get_agent_dependency] = StubAgent
    session = client.post("/api/sessions")
    assert session.status_code == 201
    session_id = session.json()["session_id"]
    first = client.post(f"/api/sessions/{session_id}/messages", json={"content": "Make me a plan"})
    second = client.post(f"/api/sessions/{session_id}/messages", json={"content": "Quiz me now"})
    assert first.json()["action"] == Action.STUDY_PLAN.value
    assert second.json()["data"]["topic"] == "algebra"
    restored = client.get(f"/api/sessions/{session_id}").json()
    assert len(restored["messages"]) == 4
    assert restored["state"]["topic"] == "algebra"
    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    assert client.get(f"/api/sessions/{session_id}").status_code == 404


def test_unknown_session_returns_404(client):
    response = client.post("/api/sessions/missing/messages", json={"content": "Explain algebra"})
    assert response.status_code == 404


def test_empty_message_is_rejected(client):
    session_id = client.post("/api/sessions").json()["session_id"]
    response = client.post(f"/api/sessions/{session_id}/messages", json={"content": ""})
    assert response.status_code == 422


def test_request_id_header_is_returned(client):
    response = client.get("/health/live", headers={"X-Request-ID": "assessment-test"})
    assert response.headers["x-request-id"] == "assessment-test"


def test_api_key_protects_api_but_keeps_login_page_and_health_available(client, monkeypatch):
    monkeypatch.setattr(main_module.settings, "app_api_key", "assessment-secret")
    assert client.get("/").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.post("/api/sessions").status_code == 401
    assert client.post("/api/sessions", headers={"X-API-Key": "assessment-secret"}).status_code == 201


def test_message_rate_limit(client, monkeypatch):
    client.app.dependency_overrides[get_agent_dependency] = StubAgent
    monkeypatch.setattr(main_module.settings, "rate_limit_per_minute", 2)
    session_id = client.post("/api/sessions").json()["session_id"]
    url = f"/api/sessions/{session_id}/messages"
    assert client.post(url, json={"content": "Make me a plan"}).status_code == 200
    assert client.post(url, json={"content": "Quiz me"}).status_code == 200
    assert client.post(url, json={"content": "One more"}).status_code == 429


def test_oversized_api_body_is_rejected_before_parsing(client):
    response = client.post("/api/sessions", content=b"{}", headers={"Content-Length": "20000"})
    assert response.status_code == 413
