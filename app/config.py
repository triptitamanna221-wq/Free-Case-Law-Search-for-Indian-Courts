from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/case_law"
    search_result_limit: int = 20
    rrf_k: int = 60
    bm25_candidate_count: int = 100
    vector_candidate_count: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
