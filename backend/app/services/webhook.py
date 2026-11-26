"""Outbound webhook delivery with HMAC-SHA256 signature and retries."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (1.0, 3.0, 8.0)


def sign_payload(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def build_check_payload(check: Any) -> dict:
    return {
        "id": str(check.id),
        "status": check.status,
        "filename": check.filename,
        "work_title": check.work_title,
        "student_name": check.student_name,
        "student_id": getattr(check, "student_id", None),
        "group_name": check.group_name,
        "similarity_percent": check.similarity_percent,
        "similarity_sources_count": check.similarity_sources_count,
        "ai_percent": check.ai_percent,
        "ai_model_version": check.ai_model_version,
        "mt_flag": check.mt_flag,
        "mt_percent": check.mt_percent,
        "word_count": check.word_count,
        "language": check.language,
        "error_message": check.error_message,
        "completed_at": check.completed_at.isoformat() if check.completed_at else None,
    }


async def fire_webhook(
    url: str,
    payload: dict,
    secret: Optional[str] = None,
    event: str = "check.completed",
) -> bool:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Antiplagiat-Event": event,
    }
    if secret:
        headers["X-Antiplagiat-Signature"] = sign_payload(body, secret)

    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, content=body, headers=headers)
            if 200 <= resp.status_code < 300:
                return True
            logger.warning(
                "[WEBHOOK] %s returned %s (attempt %s/%s)",
                url, resp.status_code, attempt + 1, MAX_ATTEMPTS,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "[WEBHOOK] Failed to deliver to %s (attempt %s/%s): %s",
                url, attempt + 1, MAX_ATTEMPTS, exc,
            )
        if attempt < MAX_ATTEMPTS - 1:
            await asyncio.sleep(BACKOFF_SECONDS[attempt])

    if last_exc:
        logger.error("[WEBHOOK] Giving up on %s: %s", url, last_exc)
    return False
