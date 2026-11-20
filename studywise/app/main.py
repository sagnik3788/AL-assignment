import json
import logging
import time
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import StudyAgent
from app.config import get_settings
from app.db import SessionLocal, create_schema
from app.llm import OpenRouter
from app.models import StudyMessage, StudySession, utcnow
from app.schemas import IncomingMessage, MessageResponse

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
web_root = Path(__file__).resolve().parent.parent / "web"
rate_log: dict[str, deque[float]] = defaultdict(deque)
openrouter = OpenRouter(settings)


@asynccontextmanager
async def lifespan(_app):
    if settings.app_env != "production":
        create_schema()
    yield
    openrouter.client.close()


app = FastAPI(title="AI Study Assistant", version="1.0.0", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    content_length = request.headers.get("content-length")
    if content_length and request.url.path.startswith("/api/"):
        try:
            if int(content_length) > 16_384:
                return Response(status_code=413, headers={"X-Request-ID": request_id})
        except ValueError:
            return Response(status_code=400, headers={"X-Request-ID": request_id})
    if request.url.path.endswith("/messages") and request.method == "POST":
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = rate_log[ip]
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_per_minute:
            return Response(content='{"detail":"Rate limit exceeded"}', status_code=429, media_type="application/json", headers={"X-Request-ID": request_id})
        bucket.append(now)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def get_agent() -> StudyAgent:
    return StudyAgent(openrouter, settings)


def get_agent_dependency() -> StudyAgent:
    return get_agent()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(web_root / "index.html")


@app.get("/health/live", tags=["health"])
def live():
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
def ready(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ready", "model_configured": bool(settings.openrouter_api_key)}


@app.post("/api/sessions", status_code=201, tags=["sessions"])
def create_session(db: Session = Depends(get_db)):
    study_session = StudySession()
    db.add(study_session)
    db.commit()
    return {"session_id": study_session.id, "created_at": study_session.created_at}


@app.get("/api/sessions/{session_id}", tags=["sessions"])
def get_session(session_id: str, db: Session = Depends(get_db)):
    study_session = db.get(StudySession, session_id)
    if not study_session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = db.scalars(select(StudyMessage).where(StudyMessage.session_id == session_id).order_by(StudyMessage.created_at)).all()
    state = json.loads(study_session.state_json or "{}")
    return {
        "session_id": session_id,
        "state": {"topic": state.get("last_topic")},
        "messages": [{"role": m.role, "content": m.content, "action": m.action} for m in messages],
    }


@app.delete("/api/sessions/{session_id}", status_code=204, tags=["sessions"])
def delete_session(session_id: str, db: Session = Depends(get_db)):
    study_session = db.get(StudySession, session_id)
    if not study_session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(study_session)
    db.commit()


@app.post("/api/sessions/{session_id}/messages", response_model=MessageResponse, tags=["study"])
def send_message(session_id: str, message: IncomingMessage, request: Request, db: Session = Depends(get_db), agent: StudyAgent = Depends(get_agent_dependency)):
    if len(message.content) > settings.max_request_chars:
        raise HTTPException(status_code=413, detail="Message is too long")
    study_session = db.get(StudySession, session_id)
    if not study_session:
        raise HTTPException(status_code=404, detail="Session not found")
    history_rows = db.scalars(select(StudyMessage).where(StudyMessage.session_id == session_id).order_by(StudyMessage.created_at.desc()).limit(settings.max_history_messages)).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]
    state = json.loads(study_session.state_json or "{}")
    db.rollback()  # Release the database connection before the slower external model call.
    result = agent.respond(message.content, history, state)
    study_session = db.get(StudySession, session_id)
    if not study_session:
        raise HTTPException(status_code=404, detail="Session was deleted while processing")
    if result.data.get("topic"):
        state["last_topic"] = result.data["topic"]
    db.add(StudyMessage(session_id=session_id, role="user", content=message.content))
    db.add(StudyMessage(session_id=session_id, role="assistant", content=result.text, action=result.action.value))
    study_session.state_json = json.dumps(state)
    study_session.updated_at = utcnow()
    db.commit()
    logger.info("study_turn request_id=%s session_id=%s action=%s mode=%s", request.state.request_id, session_id, result.action.value, agent.mode)
    return MessageResponse(session_id=session_id, action=result.action, response=result.text, data=result.data, rationale=result.rationale, mode=agent.mode)
