from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/antiplagiat"

    @field_validator("DATABASE_URL")
    @classmethod
    def _force_asyncpg(cls, v: str) -> str:
        # Managed Postgres (Render/Railway/Neon) выдаёт postgres:// или postgresql://.
        # Приложение и Alembic работают через asyncpg — приводим схему.
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v
    SECRET_KEY: str = "dev-secret-key-CHANGE-IN-PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_URL: str = "http://localhost:3000"
    UPLOAD_DIR: str = "./uploads"
    # Qdrant: если QDRANT_URL пуст — используется локальный режим (на диске), без сервера/Docker
    QDRANT_URL: str = ""
    QDRANT_PATH: str = "./qdrant_local"
    # Мультиязычная модель, поддерживаемая fastembed (uz/ru), ~0.22 ГБ:
    EMBED_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # Каталог с обученной ONNX-моделью ИИ-детектора (model.onnx + токенайзер).
    # Пусто -> используется эвристика heuristic-v1.
    AI_MODEL_DIR: str = ""

    # Stage 9: Live web search via Brave Search API
    BRAVE_API_KEY: str = ""
    WEB_SEARCH_ENABLED: bool = True
    # Max Brave API calls per check (each call = 1 fragment query)
    WEB_SEARCH_MAX_QUERIES: int = 20
    # Max URLs to fetch and analyse per check
    WEB_SEARCH_MAX_URLS: int = 10
    # Minimum rapidfuzz token_set_ratio score to count as a match (0-100)
    WEB_SEARCH_MATCH_THRESHOLD: int = 70
    # Cache TTL in seconds (default 7 days)
    WEB_SEARCH_CACHE_TTL: int = 60 * 60 * 24 * 7

    # Stage 19: Email (SMTP)
    # Leave SMTP_HOST empty to disable real sending (prints to console instead)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@antiplagiat.uz"
    # True = STARTTLS on port 587 (most providers); False = plain on port 25
    SMTP_TLS: bool = True

    # LTI 1.3 tool (Canvas / Moodle)
    # Path to RSA private key PEM. Empty → auto-generate ./lti_private.pem on first use.
    LTI_PRIVATE_KEY_PATH: str = "./lti_private.pem"
    # Public base URL of this API (used in JWKS, OIDC redirects, Canvas launch URLs)
    API_PUBLIC_URL: str = "http://localhost:8000"


settings = Settings()
