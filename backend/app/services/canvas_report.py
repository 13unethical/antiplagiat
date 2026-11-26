"""Push originality reports back to Canvas after a check completes."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from jose import jwt
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.check import Check
from app.models.lti import LtiPlatform, LtiSubmission
from app.services.lti_keys import get_kid, get_private_key_pem

logger = logging.getLogger(__name__)


async def _canvas_access_token(platform: LtiPlatform) -> str | None:
    if not platform.auth_token_url or not platform.client_id:
        return None
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": platform.client_id,
            "sub": platform.client_id,
            "aud": platform.auth_token_url,
            "iat": now,
            "exp": now + 300,
            "jti": f"{platform.client_id}-{now}",
        },
        get_private_key_pem(),
        algorithm="RS256",
        headers={"kid": get_kid()},
    )
    data = {
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": assertion,
        "scope": " ".join([
            "https://purl.imsglobal.org/spec/lti-ap/scope/report",
            "https://canvas.instructure.com/lti/originality_report",
            "https://purl.imsglobal.org/spec/lti-ags/scope/score",
        ]),
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(platform.auth_token_url, data=data)
        if resp.status_code >= 400:
            logger.warning("Canvas token error %s: %s", resp.status_code, resp.text[:300])
            return None
        return resp.json().get("access_token")


async def push_originality_report(check: Check) -> None:
    async with AsyncSessionLocal() as db:
        sub_q = await db.execute(
            select(LtiSubmission).where(LtiSubmission.check_id == check.id)
        )
        submission = sub_q.scalar_one_or_none()
        if not submission:
            return

        plat_q = await db.execute(
            select(LtiPlatform).where(LtiPlatform.id == submission.platform_id)
        )
        platform = plat_q.scalar_one_or_none()
        if not platform or platform.platform_type != "canvas":
            return

        token = await _canvas_access_token(platform)
        if not token:
            submission.report_status = "failed"
            submission.error_message = "Could not obtain Canvas access token"
            await db.commit()
            return

        report_url = submission.canvas_report_url
        if not report_url and platform.api_base_url:
            report_url = (
                f"{platform.api_base_url.rstrip('/')}/api/lti/assignments/"
                f"{submission.external_assignment_id}/submissions/"
                f"{submission.external_submission_id}/originality_report"
            )

        if not report_url:
            submission.report_status = "failed"
            submission.error_message = "No Canvas originality report URL"
            await db.commit()
            return

        launch = f"{settings.FRONTEND_URL.rstrip('/')}/verify/{check.id}"
        score = float(check.similarity_percent or 0)
        payload: dict[str, Any] = {
            "originality_report": {
                "originality_score": score,
                "originality_report_url": launch,
                "error_message": check.error_message if check.status == "failed" else None,
                "submission_time": check.created_at.isoformat() if check.created_at else None,
            }
        }
        # Canvas accepts both nested and flat forms; send flat preferred fields too
        flat = {
            "originality_score": score,
            "originality_report_url": launch,
        }
        if check.status == "failed":
            flat["error_message"] = check.error_message or "Check failed"
            payload["originality_report"]["error_message"] = flat["error_message"]

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.put(report_url, json=flat, headers=headers)
                if resp.status_code >= 400:
                    resp = await client.put(report_url, json=payload, headers=headers)
            if resp.status_code >= 400:
                submission.report_status = "failed"
                submission.error_message = f"Canvas {resp.status_code}: {resp.text[:400]}"
            else:
                submission.report_status = "reported"
                submission.error_message = None
                submission.canvas_report_url = report_url
        except Exception as exc:  # noqa: BLE001
            submission.report_status = "failed"
            submission.error_message = str(exc)[:500]
        await db.commit()
