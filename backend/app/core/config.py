from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GhostOS API"
    app_env: str = "development"
    database_url: str = "sqlite:///./ghostos.db"
    frontend_origins: str = "http://localhost:3000"
    llm_provider: str = "demo"
    llm_model: str | None = None
    openai_api_key: str | None = None
    vision_provider: str = "disabled"
    vision_model: str | None = None
    max_tool_calls: int = 20
    max_task_runtime_seconds: int = 300
    max_retries: int = 3
    ghostos_workspace: str = "../workspace"
    research_allowed_domains: str = ""
    browser_navigation_timeout_ms: int = 15_000
    browser_content_timeout_ms: int = 5_000
    desktop_automation_enabled: bool = False
    desktop_max_actions: int = 20

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def has_llm_credentials(self) -> bool:
        return self.llm_provider.lower() != "demo" and bool(self.openai_api_key)

    @property
    def effective_planner_provider(self) -> str:
        if self.llm_provider.lower() == "demo" or self.openai_api_key:
            return self.llm_provider
        return "demo"

    @property
    def vision_configured(self) -> bool:
        return self.vision_provider.lower() != "disabled" and bool(self.openai_api_key)

    @property
    def allowed_research_domains(self) -> list[str]:
        return [item.strip().lower() for item in self.research_allowed_domains.split(",") if item.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
