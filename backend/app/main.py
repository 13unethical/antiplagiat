import asyncio
import time
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import admin, auth, checks, corpus, groups, invitations, lti, org
from app.config import settings
from app.services.lti_keys import get_jwks

# Создаём папку для загрузок при старте
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Markly API",
    version="0.3.0",
    description="Plagiarism and AI detection service for Uzbek and Russian texts",
)


@app.on_event("startup")
async def _startup_corpus() -> None:
    """Наполняет стартовый корпус, загружает кэш шинглов и индексирует семантику."""
    import asyncio
    import logging
    from app.database import AsyncSessionLocal
    from app.services.seed_corpus import seed_and_load, index_semantics

    try:
        async with AsyncSessionLocal() as db:
            await seed_and_load(db)
        # семантику индексируем в фоне, чтобы не держать старт сервера
        asyncio.create_task(index_semantics())
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("Corpus startup init failed: %s", exc)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "https://markly.study",
        "https://www.markly.study",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApiLogMiddleware(BaseHTTPMiddleware):
    """Logs every request that uses X-API-Key authentication."""

    async def dispatch(self, request: Request, call_next):
        api_key_header = request.headers.get("X-API-Key")
        if not api_key_header:
            return await call_next(request)

        t0 = time.monotonic()
        response = await call_next(request)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        asyncio.create_task(
            self._log(api_key_header, request.method, request.url.path, response.status_code, elapsed_ms)
        )
        return response

    @staticmethod
    async def _log(api_key_header: str, method: str, path: str, status_code: int, response_ms: int) -> None:
        from app.database import AsyncSessionLocal
        from app.models.api_key import ApiKey
        from app.models.api_request_log import ApiRequestLog

        try:
            key_hash = sha256(api_key_header.encode()).hexdigest()
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
                api_key = result.scalar_one_or_none()
                if api_key:
                    db.add(ApiRequestLog(
                        org_id=api_key.org_id,
                        api_key_id=api_key.id,
                        method=method,
                        path=path,
                        status_code=status_code,
                        response_ms=response_ms,
                    ))
                    await db.commit()
        except Exception:
            pass  # logging must never crash the server


app.add_middleware(ApiLogMiddleware)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(org.router, prefix="/api/v1")
app.include_router(invitations.router, prefix="/api/v1")
app.include_router(checks.router, prefix="/api/v1")
app.include_router(corpus.router, prefix="/api/v1")
app.include_router(groups.router, prefix="/api/v1")
app.include_router(lti.router, prefix="/api/v1")


@app.get("/.well-known/jwks.json", tags=["lti"])
async def well_known_jwks():
    return get_jwks()


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
