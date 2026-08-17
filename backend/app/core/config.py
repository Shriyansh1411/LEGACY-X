from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(default="postgresql+psycopg://legacyx:legacyx@db:5432/legacyx", alias="DATABASE_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    azure_openai_api_key: str | None = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str = Field(default="https://example.openai.azure.com", alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment: str = Field(default="gpt-4o-mini", alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(default="2024-02-01", alias="AZURE_OPENAI_API_VERSION")
    # LLM provider selection: AZURE_OPENAI, OPENAI, or GEMINI
    llm_provider: str = Field(default="AZURE_OPENAI", alias="LLM_PROVIDER")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_base_url: str = Field(default="https://generativelanguage.googleapis.com", alias="GEMINI_BASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
