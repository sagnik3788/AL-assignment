import hashlib
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, create_schema
from app.documents import DocumentInputError, chunk_pages, extract_pages
from app.models import ChatMessage, ChatSession, Document, DocumentChunk
from app.openrouter import OpenRouter, ProviderError
from app.retrieval import contextual_query, retrieve
from app.schemas import ChatRequest, ChatResponse, Citation, DocumentResponse, SessionResponse

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
web_root = Path(__file__).resolve().parent.parent / "web"
rate_log: dict[str, deque[float]] = defaultdict(deque)
provider = OpenRouter(settings)


@asynccontextmanager
async def lifespan(_app):
    if settings.app_env != "production":
        create_schema()
    yield
    provider.close()


app = FastAPI(title="Margin — Document Q&A", version="1.0.0", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def valid_id(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(404, "Session not found") from exc


@app.middleware("http")
async def request_guard(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    content_length = request.headers.get("content-length")
    if content_length and request.url.path.startswith("/api/"):
        try:
            if int(content_length) > settings.max_upload_bytes + 262_144:
                return JSONResponse({"detail": "Request body is too large."}, status_code=413, headers={"X-Request-ID": request_id})
        except ValueError:
            return JSONResponse({"detail": "Invalid request size."}, status_code=400, headers={"X-Request-ID": request_id})
    if request.url.path in {"/api/sessions", "/api/documents", "/api/chat"} and request.method == "POST":
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = rate_log[ip]
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= settings.max_requests_per_minute:
            return JSONResponse({"detail": "Request limit reached. Please wait a minute and try again."}, status_code=429, headers={"X-Request-ID": request_id})
        bucket.append(now)
        if len(rate_log) > 10_000:
            rate_log.pop(next(iter(rate_log)))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; connect-src 'self'"
    return response


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(web_root / "index.html")


@app.get("/health/live", tags=["health"])
def live():
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
def ready(db: Session = Depends(get_db)):
    from sqlalchemy import text

    db.execute(text("SELECT 1"))
    return {"status": "ready", "provider_configured": bool(settings.openrouter_api_key)}


@app.post("/api/sessions", response_model=SessionResponse, status_code=201, tags=["sessions"])
def create_session(db: Session = Depends(get_db)):
    session = ChatSession()
    db.add(session)
    db.commit()
    return {"session_id": session.id}


@app.get("/api/sessions/{session_id}", tags=["sessions"])
def get_session(session_id: str, db: Session = Depends(get_db)):
    session_id = valid_id(session_id)
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    messages = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.desc()).limit(100)).all()
    messages.reverse()
    return {"session_id": session_id, "messages": [{"role": item.role, "content": item.content, "citations": item.citations} for item in messages]}


@app.delete("/api/sessions/{session_id}", status_code=204, tags=["sessions"])
def delete_session(session_id: str, db: Session = Depends(get_db)):
    session_id = valid_id(session_id)
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    db.delete(session)
    db.commit()


@app.get("/api/documents", tags=["documents"])
def list_documents(session_id: str, db: Session = Depends(get_db)):
    session_id = valid_id(session_id)
    if not db.get(ChatSession, session_id):
        raise HTTPException(404, "Session not found")
    documents = db.scalars(select(Document).where(Document.session_id == session_id).order_by(Document.created_at)).all()
    return [{"document_id": d.id, "filename": d.filename, "page_count": d.page_count, "chunk_count": len(d.chunks)} for d in documents]


@app.post("/api/documents", response_model=DocumentResponse, status_code=201, tags=["documents"])
def upload_document(session_id: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    session_id = valid_id(session_id)
    if not db.get(ChatSession, session_id):
        raise HTTPException(404, "Session not found")
    if not file.filename or len(file.filename) > 255:
        raise HTTPException(422, "A filename of 255 characters or fewer is required.")
    if Path(file.filename).suffix.lower() not in {".pdf", ".txt"}:
        raise HTTPException(422, "Only PDF and UTF-8 TXT files are supported.")
    data = file.file.read(settings.max_upload_bytes + 1)
    if not data:
        raise HTTPException(422, "The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"Files are limited to {settings.max_upload_bytes // (1024 * 1024)} MB.")
    digest = hashlib.sha256(data).hexdigest()
    if db.scalar(select(Document.id).where(Document.session_id == session_id, Document.sha256 == digest)):
        raise HTTPException(409, "This document is already in your library.")
    try:
        pages = extract_pages(file.filename, data, settings.max_pdf_pages)
        chunks = chunk_pages(pages, settings.chunk_words, settings.chunk_overlap_words)
    except DocumentInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not chunks:
        raise HTTPException(422, "No readable text was found in this document.")
    if len(chunks) > settings.max_chunks_per_document:
        raise HTTPException(413, f"This document creates too many sections; the limit is {settings.max_chunks_per_document} chunks.")
    existing_chunks = db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.session_id == session_id)) or 0
    if existing_chunks + len(chunks) > settings.max_chunks_per_session:
        raise HTTPException(413, f"This desk is limited to {settings.max_chunks_per_session} passages. Remove a document before adding more.")
    try:
        vectors: list[list[float]] = []
        for start in range(0, len(chunks), 64):
            vectors.extend(provider.embed([chunk.content for chunk in chunks[start:start + 64]]))
    except ProviderError as exc:
        raise HTTPException(504 if exc.timeout else 502, str(exc)) from exc
    document = Document(session_id=session_id, filename=Path(file.filename.replace("\\", "/")).name, sha256=digest, page_count=max(page.page_number for page in pages))
    db.add(document)
    try:
        db.flush()
        db.add_all([
            DocumentChunk(document_id=document.id, session_id=session_id, page_number=chunk.page_number,
                          ordinal=chunk.ordinal, content=chunk.content, embedding=vector)
            for chunk, vector in zip(chunks, vectors)
        ])
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This document is already in your library.") from exc
    return {"document_id": document.id, "filename": document.filename, "page_count": document.page_count, "chunk_count": len(chunks)}


@app.delete("/api/documents/{document_id}", status_code=204, tags=["documents"])
def delete_document(document_id: str, session_id: str, db: Session = Depends(get_db)):
    session_id = valid_id(session_id)
    document = db.scalar(select(Document).where(Document.id == document_id, Document.session_id == session_id))
    if not document:
        raise HTTPException(404, "Document not found")
    db.delete(document)
    db.commit()


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    session_id = valid_id(request.session_id)
    if not db.get(ChatSession, session_id):
        raise HTTPException(404, "Session not found")
    if not db.scalar(select(Document.id).where(Document.session_id == session_id).limit(1)):
        return {"answer": "Upload a PDF or text document first, and I’ll answer from its contents.", "abstained": True, "citations": [], "retrieved_count": 0}
    history_rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.desc()).limit(6)).all()
    history_rows.reverse()
    history = [{"role": row.role, "content": row.content} for row in history_rows]
    retrieval_question = contextual_query(request.question, history)
    try:
        vector = provider.embed([retrieval_question])[0]
        passages = retrieve(db, session_id, vector, settings.top_k)
        relevant = [item for item in passages if item["score"] >= settings.min_relevance_score]
        if not relevant:
            result = {"answer": "I couldn’t find enough evidence in your documents to answer that. Try asking about a specific section or upload another source.", "abstain": True, "citation_ids": []}
        else:
            prompt_passages = [{"source_id": p["source_id"], "filename": p["filename"], "page": p["page"], "text": p["content"]} for p in relevant]
            result = provider.answer(request.question, history, prompt_passages)
    except ProviderError as exc:
        raise HTTPException(504 if exc.timeout else 502, str(exc)) from exc
    allowed = {item["source_id"]: item for item in relevant} if passages else {}
    chosen = [allowed[item] for item in dict.fromkeys(result["citation_ids"]) if item in allowed]
    abstained = bool(result["abstain"]) or (not chosen and bool(relevant))
    answer = result["answer"] if not abstained else (result["answer"] if result["abstain"] else "I couldn’t verify a cited answer from the retrieved passages. Try rephrasing your question.")
    citations = [] if abstained else [Citation(source_id=p["source_id"], filename=p["filename"], page=p["page"], excerpt=p["content"][:360], score=round(p["score"], 4)) for p in chosen]
    db.add(ChatMessage(session_id=session_id, role="user", content=request.question))
    db.add(ChatMessage(session_id=session_id, role="assistant", content=answer, citations=[citation.model_dump() for citation in citations]))
    db.commit()
    return {"answer": answer, "abstained": abstained, "citations": citations, "retrieved_count": len(relevant)}
