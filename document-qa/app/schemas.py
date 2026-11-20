from pydantic import BaseModel, Field, field_validator


class SessionResponse(BaseModel):
    session_id: str


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    chunk_count: int


class ChatRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be blank.")
        return value


class Citation(BaseModel):
    source_id: str
    filename: str
    page: int
    excerpt: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    abstained: bool
    citations: list[Citation]
    retrieved_count: int
