import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def retrieve(db: Session, session_id: str, query_vector: list[float], top_k: int) -> list[dict]:
    rows = db.execute(
        select(DocumentChunk, Document.filename)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.session_id == session_id)
    ).all()
    ranked = [
        {"source_id": chunk.id, "filename": filename, "page": chunk.page_number, "content": chunk.content,
         "score": cosine_similarity(query_vector, chunk.embedding)}
        for chunk, filename in rows
    ]
    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:top_k]


def contextual_query(question: str, history: list[dict]) -> str:
    followup_terms = {"it", "its", "they", "them", "that", "those", "this", "these", "there", "their"}
    words = question.lower().split()
    if len(words) <= 10 and followup_terms.intersection(word.strip(".,?!") for word in words):
        previous = next((item["content"] for item in reversed(history) if item["role"] == "user"), "")
        if previous:
            return f"Earlier question: {previous}\nFollow-up question: {question}"
    return question
