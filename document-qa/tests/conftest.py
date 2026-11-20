import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
from app.db import Base


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "SessionLocal", TestingSession)
    monkeypatch.setattr(main.settings, "max_requests_per_minute", 50)
    main.rate_log.clear()

    def embeddings(texts):
        return [[-1.0] + [0.0] * 511 if "unanswerable" in text.lower() else [1.0] + [0.0] * 511 for text in texts]

    def answer(question, history, passages):
        if "invalid citation" in question.lower():
            return {"answer": "Unsupported claim.", "abstain": False, "citation_ids": ["not-a-real-id"]}
        return {"answer": "The source states this fact.", "abstain": False, "citation_ids": [passages[0]["source_id"]]}

    monkeypatch.setattr(main.provider, "embed", embeddings)
    monkeypatch.setattr(main.provider, "answer", answer)
    yield TestClient(main.app)
    engine.dispose()


@pytest.fixture
def session_id(client):
    return client.post("/api/sessions").json()["session_id"]
