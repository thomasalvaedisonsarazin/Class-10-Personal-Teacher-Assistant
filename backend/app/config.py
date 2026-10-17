"""Application settings loaded from environment variables / .env files."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "dev-insecure-secret-key-change-me"  # noqa: S105 - dev-only sentinel
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Typed application configuration.

    Values are read from (in order of precedence) process environment variables,
    ``backend/.env`` and the repository-root ``.env``. Every field has a
    development-safe default so the app boots without any configuration.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = "Personal Teacher Assistant"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",  # admin (vite dev + docker)
        "http://localhost:5173",
        "http://localhost:8081",
        "http://localhost:19006",
    ]
    ADMIN_EMAILS: list[str] = []
    # Test sign-in without Google. Must be switched on explicitly, never in production.
    DEV_LOGIN_ENABLED: bool = False

    # Database / queue
    DATABASE_URL: str = "sqlite:///./dev.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_ANDROID_CLIENT_ID: str = ""

    # Email sign-in (6-digit codes, email + password). "log" only writes codes to the
    # server log for local testing and is refused in production; use "smtp" there
    # (e.g. Brevo, Resend, Amazon SES or Gmail SMTP).
    EMAIL_PROVIDER: Literal["log", "smtp"] = "log"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "Personal Teacher Assistant <no-reply@example.com>"
    EMAIL_CODE_TTL_MINUTES: int = 10
    EMAIL_CODE_MAX_ATTEMPTS: int = 5
    EMAIL_CODES_PER_HOUR: int = 5

    # AI
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-5.4-mini"  # chosen 2026-10-15: natural Tamil/Tanglish
    # Reasoning models (gpt-5*, o*) think before answering; "low" keeps lessons fast and cheap.
    LLM_REASONING_EFFORT: Literal["minimal", "low", "medium", "high"] = "low"
    # A second, stricter pass that checks (and fixes) lessons, and answers every new
    # question without the key to drop wrong ones. Uses more reasoning than writing.
    FACT_CHECK_ENABLED: bool = True
    QUESTION_VERIFY_ENABLED: bool = True
    CHECK_REASONING_EFFORT: Literal["minimal", "low", "medium", "high"] = "medium"
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_MAX_RETRIES: int = 2
    TTS_PROVIDER: Literal["google", "azure", "fake"] = "fake"
    TTS_API_KEY: str = ""
    TTS_TIMEOUT_SECONDS: float = 30.0
    AI_GENERATIONS_PER_USER_PER_DAY: int = 10
    # Where AI jobs run: "celery" (worker via Redis), "thread" (in the API process,
    # for low-memory local dev), "sync" (inline, tests). "auto": celery in
    # production, sync under tests, thread otherwise.
    JOB_RUNNER: Literal["auto", "celery", "thread", "sync"] = "auto"
    VIDEO_RENDER_ENABLED: bool = True
    # Storybook illustrations (chosen 2026-10-15 after comparing samples).
    IMAGES_ENABLED: bool = True
    IMAGE_MODEL: str = "gpt-image-2"
    IMAGE_QUALITY: Literal["low", "medium", "high"] = "medium"
    IMAGE_PARALLELISM: int = 3
    FFMPEG_TIMEOUT_SECONDS: int = 300
    AI_QUESTIONS_AUTO_APPROVE: bool = True

    # Storage
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""
    # Host the phone/browser uses to download media (signed URLs embed the host).
    # Empty = same as S3_ENDPOINT_URL. In docker-compose set to e.g. http://<LAN-IP>:9000.
    S3_PUBLIC_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "us-east-1"
    SIGNED_URL_EXPIRE_SECONDS: int = 3600
    MEDIA_ROOT: str = "media"
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Quiz
    QUIZ_PASS_PCT: float = 60
    QUIZ_QUESTIONS_PER_ATTEMPT: int = 10
    QUIZ_ATTEMPT_EXPIRE_MINUTES: int = 60

    # Push
    EXPO_PUSH_URL: str = "https://exp.host/--/api/v2/push/send"
    PUSH_ENABLED: bool = False

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Force the psycopg (v3) driver for plain PostgreSQL URLs."""
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @field_validator("CORS_ORIGINS", "ADMIN_EMAILS", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Allow comma-separated strings in addition to JSON lists."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("ADMIN_EMAILS")
    @classmethod
    def _lower_emails(cls, value: list[str]) -> list[str]:
        """Normalise admin emails to lowercase."""
        return [email.lower() for email in value]

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        """Refuse to start in production with an insecure secret key."""
        if self.ENVIRONMENT == "production":
            weak = (
                self.SECRET_KEY == DEFAULT_SECRET_KEY
                or len(self.SECRET_KEY) < 32
                or any(
                    word in self.SECRET_KEY.lower()
                    for word in ("insecure", "change-me", "changeme")
                )
            )
            if weak:
                raise ValueError("SECRET_KEY must be a long random value (32+ chars) in production")
            if self.DEV_LOGIN_ENABLED:
                raise ValueError("DEV_LOGIN_ENABLED must be false in production")
            if self.EMAIL_PROVIDER != "smtp" or not self.SMTP_HOST:
                raise ValueError("Production needs EMAIL_PROVIDER=smtp and SMTP_HOST to send codes")
        return self

    @property
    def is_production(self) -> bool:
        """True when running in production."""
        return self.ENVIRONMENT == "production"

    @property
    def dev_login_allowed(self) -> bool:
        """Test sign-in only when explicitly enabled and never in production."""
        return self.DEV_LOGIN_ENABLED and not self.is_production

    @property
    def is_test(self) -> bool:
        """True when running under the test suite."""
        return self.ENVIRONMENT == "test"

    @property
    def media_root(self) -> Path:
        """Absolute local-media directory (relative MEDIA_ROOT resolves under backend/)."""
        root = Path(self.MEDIA_ROOT)
        return root if root.is_absolute() else BACKEND_DIR / root

    @property
    def job_runner(self) -> Literal["celery", "thread", "sync"]:
        """Resolved job runner (see ``JOB_RUNNER``)."""
        if self.JOB_RUNNER != "auto":
            return self.JOB_RUNNER
        if self.is_production:
            return "celery"
        return "sync" if self.is_test else "thread"

    @property
    def google_client_ids(self) -> list[str]:
        """All accepted Google OAuth audiences (web + Android)."""
        return [cid for cid in (self.GOOGLE_CLIENT_ID, self.GOOGLE_ANDROID_CLIENT_ID) if cid]


settings = Settings()
