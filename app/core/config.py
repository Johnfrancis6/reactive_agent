
import os
from functools import lru_cache
from dotenv import load_dotenv
from pydantic import BaseModel, Field, PostgresDsn
from typing import Optional



class Settings(BaseModel):
    """Application configurations loaded from .env."""
    app_name: str = Field(default="reactive_agent", description="Application name")
    environment: str = Field(default="development", description="Deployment environment")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Default logging level")
    database_url: Optional[PostgresDsn] = Field(default=None, description="Async PostgreSQL connection URL (postgresql+asyncpg://...)")
    llm_generator: str = Field(default="groq/compound", description="Model used for agent generation")
    llm_clarifier: str = Field(default="groq/compound", description="Model used to clarify user requests and planning")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    smtp_host: Optional[str] = Field(default=None, description="SMTP host for email sending")
    smtp_port: Optional[int] = Field(default=None, description="SMTP port for sending email")
    smtp_user: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    smtp_from_email: Optional[str] = Field(default=None, description="Default email sender")

    @property
    def smtp_enabled(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_port
            and self.smtp_user
            and self.smtp_password
            and self.smtp_from_email
        )


def _parse_bool(value: str, default: bool = False) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1","true","yes","on",}

def _parse_int(value: Optional[str]) -> Optional[int]:
    if not value or not value.strip():
        return None

    try:
        return int(value.strip())
    except ValueError:
        return None


def _parse_origins(value: Optional[str]) -> list[str]:
    if not value:
        return ["http://localhost:3000"]

    return [
        origin.strip()
        for origin in value.split(",")
        if origin.strip()
    ]





@lru_cache
def get_settings() -> Settings:
    load_dotenv()

    smtp_port_raw = os.getenv("SMTP_PORT")

    return Settings(
        app_name=os.getenv("APP_NAME", "reactive_agent"),
        environment=os.getenv("ENVIRONMENT", "development"),
        debug=_parse_bool(os.getenv("DEBUG", "False")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        database_url=os.getenv("DATABASE_URL") or None,
        llm_generator=os.getenv("LLM_GENERATOR","groq/compound",),
        llm_clarifier=os.getenv("LLM_CLARIFIER","groq/compound",),
        cors_origins=_parse_origins(os.getenv("CORS_ORIGINS")),
        smtp_host=os.getenv("SMTP_HOST") or None,
        smtp_port=_parse_int(smtp_port_raw),
        smtp_user=os.getenv("SMTP_USER") or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or None,
        smtp_from_email=os.getenv("SMTP_FROM_EMAIL") or None,
    )



