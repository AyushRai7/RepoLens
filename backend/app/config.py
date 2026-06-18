from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM
    groq_api_key: str = ""
    huggingface_api_key: str = ""

    # GitHub
    github_token: str = ""

    # LangSmith
    langchain_api_key: str = ""
    langchain_tracing_v2: str = "true"
    langchain_project: str = "repolens"

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/repoexplorer"
    redis_url: str = "redis://localhost:6379/0"

    # App
    secret_key: str = "dev-secret-key"
    environment: str = "development"
    allowed_origins: str = "http://localhost:3000"

    # Limits
    max_repo_files: int = 500
    max_file_size_kb: int = 100
    cache_ttl_hours: int = 24

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()

