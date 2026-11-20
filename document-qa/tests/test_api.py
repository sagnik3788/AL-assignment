import io

import app.main as main


def upload(client, session_id, name="notes.txt", content=b"The field report is due on 16 March and has a 35 percent grade."):
    return client.post("/api/documents", data={"session_id": session_id}, files={"file": (name, io.BytesIO(content), "text/plain")})


def test_upload_chat_cites_source_and_persists_history(client, session_id):
    response = upload(client, session_id)
    assert response.status_code == 201
    document = response.json()
    assert document["chunk_count"] == 1
    answer = client.post("/api/chat", json={"session_id": session_id, "question": "When is the report due?"})
    assert answer.status_code == 200
    body = answer.json()
    assert body["abstained"] is False
    assert body["citations"][0]["filename"] == "notes.txt"
    assert body["citations"][0]["page"] == 1
    history = client.get(f"/api/sessions/{session_id}").json()["messages"]
    assert [message["role"] for message in history] == ["user", "assistant"]


def test_unknown_answer_abstains_and_untrusted_citation_is_discarded(client, session_id):
    upload(client, session_id)
    result = client.post("/api/chat", json={"session_id": session_id, "question": "unanswerable question"}).json()
    assert result["abstained"] is True
    assert result["citations"] == []
    result = client.post("/api/chat", json={"session_id": session_id, "question": "invalid citation please"}).json()
    assert result["abstained"] is True
    assert result["citations"] == []


def test_no_documents_returns_safe_abstention_without_provider_call(client, session_id):
    result = client.post("/api/chat", json={"session_id": session_id, "question": "Anything?"}).json()
    assert result["abstained"] is True
    assert result["retrieved_count"] == 0


def test_documents_are_isolated_and_foreign_delete_is_blocked(client, session_id):
    upload(client, session_id)
    second = client.post("/api/sessions").json()["session_id"]
    result = client.post("/api/chat", json={"session_id": second, "question": "When is the report due?"}).json()
    assert result["abstained"] is True
    document_id = client.get(f"/api/documents?session_id={session_id}").json()[0]["document_id"]
    assert client.delete(f"/api/documents/{document_id}?session_id={second}").status_code == 404


def test_duplicate_and_invalid_upload_errors(client, session_id):
    assert upload(client, session_id).status_code == 201
    assert upload(client, session_id).status_code == 409
    assert upload(client, session_id, "bad.docx").status_code == 422
    assert upload(client, session_id, "bad.pdf", b"broken").status_code == 422
    assert upload(client, session_id, "empty.txt", b"").status_code == 422


def test_upload_size_limit(client, session_id, monkeypatch):
    monkeypatch.setattr(main.settings, "max_upload_bytes", 10)
    response = upload(client, session_id, content=b"this file is much larger than ten bytes")
    assert response.status_code == 413


def test_session_chunk_budget_is_enforced(client, session_id, monkeypatch):
    upload(client, session_id)
    monkeypatch.setattr(main.settings, "max_chunks_per_session", 1)
    response = upload(client, session_id, "another.txt", b"a different document body")
    assert response.status_code == 413


def test_delete_document_and_session_cascade(client, session_id):
    document_id = upload(client, session_id).json()["document_id"]
    assert client.delete(f"/api/documents/{document_id}?session_id={session_id}").status_code == 204
    assert client.get(f"/api/documents?session_id={session_id}").json() == []
    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    assert client.get(f"/api/sessions/{session_id}").status_code == 404


def test_invalid_session_and_question_validation(client):
    assert client.get("/api/sessions/not-an-id").status_code == 404
    assert client.post("/api/chat", json={"session_id": "00000000-0000-0000-0000-000000000000", "question": " "}).status_code == 422


def test_provider_failure_is_reported_without_secret(client, session_id, monkeypatch):
    from app.openrouter import ProviderError

    upload(client, session_id)
    monkeypatch.setattr(main.provider, "embed", lambda _texts: (_ for _ in ()).throw(ProviderError("The AI provider is temporarily unavailable. Please try again.")))
    response = client.post("/api/chat", json={"session_id": session_id, "question": "When?"})
    assert response.status_code == 502
    assert "temporarily unavailable" in response.json()["detail"]
    assert "Bearer" not in response.text


def test_delete_session_cascades_documents(client, session_id):
    upload(client, session_id)
    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    assert client.get(f"/api/documents?session_id={session_id}").status_code == 404


def test_health_and_request_id(client):
    response = client.get("/health/live", headers={"X-Request-ID": "test-request"})
    assert response.json() == {"status": "alive"}
    assert response.headers["x-request-id"] == "test-request"


def test_rate_limit_returns_retryable_status(client, session_id, monkeypatch):
    main.rate_log.clear()
    monkeypatch.setattr(main.settings, "max_requests_per_minute", 1)
    assert client.post("/api/chat", json={"session_id": session_id, "question": "Question"}).status_code == 200
    assert client.post("/api/chat", json={"session_id": session_id, "question": "Again"}).status_code == 429
