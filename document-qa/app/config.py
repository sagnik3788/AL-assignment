from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./document_qa.db"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "google/gemini-2.5-flash-lite"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimensions: int = 512
    max_upload_bytes: int = 10_485_760
    max_pdf_pages: int = 150
    max_chunks_per_document: int = 800
    max_chunks_per_session: int = 2000
    chunk_words: int = 180
    chunk_overlap_words: int = 30
    top_k: int = 5
    min_relevance_score: float = 0.28
    max_requests_per_minute: int = 20
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
