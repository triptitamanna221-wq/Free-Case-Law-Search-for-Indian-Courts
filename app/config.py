from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/case_law"
    search_result_limit: int = 20
    rrf_k: int = 60
    bm25_candidate_count: int = 100
    vector_candidate_count: int = 100
    embedding_model: str = "all-MiniLM-L6-v2"
    # comma-separated origins, e.g. "https://my-app.vercel.app,http://localhost:3000"
    cors_origins: str = ""

    @field_validator("database_url")
    @classmethod
    def _require_psycopg_driver(cls, value: str) -> str:
        # Managed Postgres providers (Render included) hand back a plain
        # "postgres://" or "postgresql://" connection string. Only psycopg3 is
        # installed here (no psycopg2), so SQLAlchemy needs the explicit
        # "+psycopg" driver suffix or engine creation fails at startup.
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
