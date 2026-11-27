"""
LTI 1.3 endpoints for Canvas (and generic LMS) plagiarism integration.

  GET  /.well-known/jwks.json          — public JWKS (mounted in main)
  GET  /api/v1/lti/oidc/login          — OIDC login initiation
  POST /api/v1/lti/launch              — resource link launch
  GET  /api/v1/lti/config/canvas.json  — Developer Key config JSON
  POST /api/v1/lti/canvas/submissions  — Canvas plagiarism submission ingest
"""
from __future__ import annotations

import secrets
import time
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from jose import jwt
from jose.backends import RSAKey
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import any_authenticated
from app.config import settings
from app.database import get_db
from app.models.check import Check
from app.models.lti import LtiPlatform, LtiSubmission
from app.models.user import User
from app.services.lti_keys import get_jwks
from app.services.processor import process_check

router = APIRouter(prefix="/lti", tags=["lti"])

# In-memory OIDC state (dev/single-node; replace with Redis in prod scale-out)
_oidc_states: dict[str, dict[str, Any]] = {}


def public_api_base() -> str:
    return settings.API_PUBLIC_URL.rstrip("/")


@router.get("/jwks.json")
async def jwks():
    return get_jwks()


@router.get("/config/canvas.json")
async def canvas_developer_key_config():
    """JSON for Canvas Developer Key → LTI 1.3 configuration."""
    base = public_api_base()
    front = settings.FRONTEND_URL.rstrip("/")
    return {
        "title": "Markly",
        "description": "Plagiarism and AI detection for Uzbek and Russian",
        "oidc_initiation_url": f"{base}/api/v1/lti/oidc/login",
        "target_link_uri": f"{base}/api/v1/lti/launch",
        "public_jwk_url": f"{base}/.well-known/jwks.json",
        "scopes": [
            "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
            "https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly",
            "https://purl.imsglobal.org/spec/lti-ags/scope/score",
            "https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly",
            "https://purl.imsglobal.org/spec/lti/scope/noticehandlers",
            "https://canvas.instructure.com/lti/public_jwk/scope/update",
            "https://canvas.instructure.com/lti/account_lookup/scope/show",
            "https://purl.imsglobal.org/spec/lti-ap/scope/control.all",
            "https://canvas.instructure.com/lti/originality_report",
        ],
        "extensions": [
            {
                "domain": base.replace("https://", "").replace("http://", "").split("/")[0],
                "tool_id": "antiplagiat",
                "platform": "canvas.instructure.com",
                "settings": {
                    "text": "Markly",
                    "icon_url": f"{front}/icon.png",
                    "placements": [
                        {
                            "placement": "similarity_detection",
                            "message_type": "LtiResourceLinkRequest",
                            "target_link_uri": f"{base}/api/v1/lti/launch",
                        }
                    ],
                },
            }
        ],
        "custom_fields": {},
    }


@router.api_route("/oidc/login", methods=["GET", "POST"])
async def oidc_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    iss: Optional[str] = None,
    login_hint: Optional[str] = None,
    target_link_uri: Optional[str] = None,
    lti_message_hint: Optional[str] = None,
    client_id: Optional[str] = None,
    lti_deployment_id: Optional[str] = None,
):
    if request.method == "POST":
        form = await request.form()
        iss = form.get("iss") or iss
        login_hint = form.get("login_hint") or login_hint
        target_link_uri = form.get("target_link_uri") or target_link_uri
        lti_message_hint = form.get("lti_message_hint") or lti_message_hint
        client_id = form.get("client_id") or client_id
        lti_deployment_id = form.get("lti_deployment_id") or lti_deployment_id

    if not iss or not client_id:
        raise HTTPException(400, "Missing iss or client_id")

    result = await db.execute(
        select(LtiPlatform).where(
            LtiPlatform.issuer == iss,
            LtiPlatform.client_id == client_id,
            LtiPlatform.is_active == True,  # noqa: E712
        )
    )
    platform = result.scalar_one_or_none()
    if not platform:
        raise HTTPException(404, "LTI platform not registered for this issuer/client_id")

    if not platform.auth_login_url:
        raise HTTPException(400, "Platform auth_login_url is not configured")

    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    _oidc_states[state] = {
        "platform_id": str(platform.id),
        "nonce": nonce,
        "exp": time.time() + 600,
    }

    params = {
        "scope": "openid",
        "response_type": "id_token",
        "response_mode": "form_post",
        "prompt": "none",
        "client_id": client_id,
        "redirect_uri": f"{public_api_base()}/api/v1/lti/launch",
        "login_hint": login_hint or "",
        "state": state,
        "nonce": nonce,
    }
    if lti_message_hint:
        params["lti_message_hint"] = lti_message_hint
    if lti_deployment_id:
        params["lti_deployment_id"] = lti_deployment_id

    return RedirectResponse(f"{platform.auth_login_url}?{urlencode(params)}", status_code=302)


async def _fetch_platform_jwks(jwks_url: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        return resp.json()


@router.api_route("/launch", methods=["GET", "POST"])
async def lti_launch(
    request: Request,
    db: AsyncSession = Depends(get_db),
    id_token: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
):
    if request.method == "GET":
        # Browser open of launch URL — show status page
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;padding:2rem'>"
            "<h1>Markly LTI</h1>"
            "<p>Tool is registered. Launch happens via Canvas/Moodle POST.</p>"
            "</body></html>"
        )

    if not id_token or not state:
        raise HTTPException(400, "Missing id_token or state")

    stored = _oidc_states.pop(state, None)
    if not stored or stored["exp"] < time.time():
        raise HTTPException(400, "Invalid or expired OIDC state")

    platform = await db.get(LtiPlatform, uuid.UUID(stored["platform_id"]))
    if not platform or not platform.jwks_url:
        raise HTTPException(404, "Platform not found")

    try:
        jwks = await _fetch_platform_jwks(platform.jwks_url)
        header = jwt.get_unverified_header(id_token)
        jwk = None
        for candidate in jwks.get("keys", []):
            if candidate.get("kid") == header.get("kid"):
                jwk = candidate
                break
        if jwk is None and jwks.get("keys"):
            jwk = jwks["keys"][0]
        if not jwk:
            raise ValueError("No JWK in platform JWKS")
        key = RSAKey(jwk, algorithm="RS256")
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=platform.client_id,
            issuer=platform.issuer,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(401, f"Invalid LTI id_token: {exc}") from exc

    if claims.get("nonce") != stored["nonce"]:
        raise HTTPException(401, "Nonce mismatch")

    # Minimal launch success — redirect teacher to frontend integrations
    return RedirectResponse(
        f"{settings.FRONTEND_URL.rstrip('/')}/admin/integrations?lti=ok",
        status_code=302,
    )


class CanvasSubmissionIn(BaseModel):
    """Payload from Canvas plagiarism service or our connector."""
    platform_id: uuid.UUID
    assignment_id: str
    submission_id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    filename: Optional[str] = None
    file_url: Optional[str] = None
    text_content: Optional[str] = None
    originality_report_url: Optional[str] = None


@router.post("/canvas/submissions", status_code=201)
async def ingest_canvas_submission(
    data: CanvasSubmissionIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """
    Ingest a Canvas (or connector) submission: download file, create Check,
    link LtiSubmission for originality report push.
    Auth: JWT of school_admin/teacher OR org API key.
    """
    platform = await db.get(LtiPlatform, data.platform_id)
    if not platform or not platform.is_active:
        raise HTTPException(404, "LTI platform not found")
    if current_user.org_id and platform.org_id != current_user.org_id:
        if current_user.role != "superadmin":
            raise HTTPException(403, "Platform belongs to another organization")

    existing = await db.execute(
        select(LtiSubmission).where(
            LtiSubmission.platform_id == platform.id,
            LtiSubmission.external_assignment_id == data.assignment_id,
            LtiSubmission.external_submission_id == data.submission_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Submission already registered")

    content: bytes
    filename: str
    if data.file_url:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(data.file_url)
            if resp.status_code >= 400:
                raise HTTPException(400, f"Could not download file: HTTP {resp.status_code}")
            content = resp.content
        filename = data.filename or Path(data.file_url.split("?")[0]).name or "submission.docx"
    elif data.text_content:
        content = data.text_content.encode("utf-8")
        filename = data.filename or "submission.txt"
    else:
        raise HTTPException(400, "Provide file_url or text_content")

    if len(content) < 50 and not (data.text_content and len(data.text_content) >= 50):
        # allow short binary docs; text path already validated length loosely
        pass

    check_id = uuid.uuid4()
    upload_dir = Path(settings.UPLOAD_DIR) / str(check_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    file_path.write_bytes(content)

    check = Check(
        id=check_id,
        org_id=platform.org_id,
        submitted_by=current_user.id,
        filename=filename,
        file_size=len(content),
        file_path=str(file_path),
        status="processing",
        work_title=f"Canvas assignment {data.assignment_id}",
        student_name=data.user_name,
        student_id=data.user_id,
    )
    db.add(check)

    sub = LtiSubmission(
        id=uuid.uuid4(),
        platform_id=platform.id,
        check_id=check_id,
        external_assignment_id=data.assignment_id,
        external_submission_id=data.submission_id,
        student_lms_id=data.user_id,
        student_name=data.user_name,
        report_status="processing",
        canvas_report_url=data.originality_report_url,
    )
    db.add(sub)
    await db.commit()

    background_tasks.add_task(process_check, check_id)
    return {
        "id": str(check_id),
        "lti_submission_id": str(sub.id),
        "status": "processing",
    }
