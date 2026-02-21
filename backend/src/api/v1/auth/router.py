"""
QUALISYS Auth API Router
Story: 1-1-user-account-creation, 1-5-login-session-management
ACs: AC1–AC8 (1.1) | AC1–AC10 (1.5)

Endpoints:
  POST   /api/v1/auth/register                   — email/password signup (1.1)
  GET    /api/v1/auth/oauth/google/authorize      — initiate Google OAuth PKCE (1.1)
  GET    /api/v1/auth/oauth/google/callback       — handle OAuth callback + set cookies (1.1+1.5)
  POST   /api/v1/auth/verify-email               — validate verification token (1.1)
  POST   /api/v1/auth/resend-verification        — resend verification email (1.1)
  POST   /api/v1/auth/login                      — password login + issue cookies (1.5 AC1)
  POST   /api/v1/auth/refresh                    — rotate refresh token (1.5 AC4)
  POST   /api/v1/auth/logout                     — revoke current session (1.5 AC5)
  POST   /api/v1/auth/logout-all                 — revoke all sessions (1.5 AC5)
  GET    /api/v1/auth/sessions                   — list active sessions (1.5 AC5)
  DELETE /api/v1/auth/sessions/{session_id}      — revoke specific session (1.5 AC5)
  POST   /api/v1/auth/select-org                 — choose org after multi-org login (1.5 AC6)
  POST   /api/v1/auth/switch-org                 — switch org within active session (1.5 AC6)
"""

import base64
import hashlib
import secrets
import uuid
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.schemas import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    SelectOrgRequest,
    SessionInfo,
    SessionListResponse,
    SwitchOrgRequest,
    TenantOrgInfo,
    UserResponse,
    VerifyEmailRequest,
    ResendVerificationRequest,
)
from src.cache import get_redis_client
from src.config import get_settings
from src.db import get_db
from src.logger import logger
from src.middleware.rate_limit import check_rate_limit
from src.middleware.rbac import get_current_user
from src.models.tenant import Tenant, TenantUser
from src.models.user import User
from src.services.auth.auth_service import (
    AccountLockedError,
    AuthenticationError,
    DuplicateEmailError,
    EmailNotVerifiedError,
    RateLimitError,
    create_access_token,
    create_email_verification_token,
    decode_email_verification_token,
    get_or_create_oauth_user,
    login_with_password,
    register_user,
    verify_email,
)
from src.services.notification.notification_service import send_verification_email
from src.services.token_service import token_service, _token_hash

settings = get_settings()

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Cookie helpers (AC3 — httpOnly, Secure, SameSite=Lax)
# ---------------------------------------------------------------------------

def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    remember_me: bool = False,
) -> None:
    """Set access_token and refresh_token as httpOnly cookies."""
    access_max_age = settings.jwt_access_token_expire_minutes * 60
    refresh_days = (
        settings.jwt_refresh_token_expire_days_remember_me
        if remember_me
        else settings.jwt_refresh_token_expire_days
    )
    refresh_max_age = refresh_days * 86400

    cookie_kwargs = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
    }
    if settings.cookie_domain:
        cookie_kwargs["domain"] = settings.cookie_domain

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_max_age,
        path="/",
        **cookie_kwargs,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=refresh_max_age,
        path="/api/v1/auth",  # Scope to /auth — prevents sending on every API call
        **cookie_kwargs,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies on logout."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


def _correlation_id(request: Request) -> str:
    """Extract or generate correlation ID for log tracing."""
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def _session_info_from_request(request: Request) -> dict:
    """Extract ip and user_agent from request for session metadata."""
    ip = None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    return {
        "ip": ip,
        "user_agent": request.headers.get("User-Agent"),
        "device_name": None,
    }


async def _get_user_orgs(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[tuple[TenantUser, Tenant]]:
    """Load active tenant memberships for a user with tenant details."""
    stmt = (
        select(TenantUser, Tenant)
        .join(Tenant, TenantUser.tenant_id == Tenant.id)
        .where(
            TenantUser.user_id == user_id,
            TenantUser.is_active == True,  # noqa: E712
        )
        .order_by(Tenant.name.asc())
    )
    result = await db.execute(stmt)
    return result.all()


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register — 1.1 AC1, AC4, AC5, AC6, AC8
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Validation error"},
        409: {"description": "Duplicate email"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def register(
    payload: RegisterRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """
    Create a new user account with email + password.
    Tokens issued are RS256 JWT (access) + opaque (refresh).
    User must verify email before logging in (1.5 AC1).
    """
    correlation_id = _correlation_id(request)
    await check_rate_limit(request, action="signup", max_requests=5, window_seconds=60)

    try:
        user = await register_user(
            db=db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            correlation_id=correlation_id,
        )
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "DUPLICATE_EMAIL",
                    "message": "An account with this email already exists. Please log in or reset your password.",
                }
            },
        )

    # Issue tokens (not set as cookies for register — user must verify email first)
    access_token = create_access_token(user.id, user.email)
    session_info = _session_info_from_request(request)
    refresh_token = await token_service.create_refresh_token(
        user_id=user.id,
        tenant_id=None,
        session_info=session_info,
        remember_me=False,
    )

    verification_token = create_email_verification_token(user.id)
    background_tasks.add_task(
        send_verification_email,
        recipient_email=user.email,
        full_name=user.full_name,
        verification_token=verification_token,
        correlation_id=correlation_id,
    )

    return RegisterResponse(
        user=UserResponse.model_validate(user),
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login — 1.5 AC1, AC7, AC8
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"description": "Invalid credentials"},
        423: {"description": "Account locked"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate with email + password. Issues httpOnly session cookies (AC1, AC3).

    Multi-org flow (AC6):
      - 1 org: access token contains tenant_id + role; redirects to dashboard
      - N orgs: access token contains tenant_id=null; client must POST /select-org
    """
    correlation_id = _correlation_id(request)
    session_info = _session_info_from_request(request)

    # login_with_password enforces rate limit + lockout (AC7, AC8)
    try:
        user = await login_with_password(
            db=db,
            email=payload.email,
            password=payload.password,
            correlation_id=correlation_id,
        )
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "RATE_LIMITED", "message": str(exc)}},
        )
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={"error": {"code": "ACCOUNT_LOCKED", "message": str(exc)}},
        )
    except EmailNotVerifiedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "EMAIL_NOT_VERIFIED", "message": str(exc)}},
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": str(exc)}},
        )

    # Load active org memberships (AC6)
    memberships = await _get_user_orgs(db, user.id)
    orgs = [
        TenantOrgInfo(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            role=tu.role,
        )
        for tu, tenant in memberships
    ]

    # Multi-org: tenant_id=None in token; single org: embed tenant directly
    if len(orgs) == 1:
        active_tenant_id = orgs[0].id
        active_tenant_slug = orgs[0].slug
        active_role = orgs[0].role
    else:
        active_tenant_id = None
        active_tenant_slug = None
        active_role = None

    access_token = token_service.create_access_token(
        user_id=user.id,
        email=user.email,
        tenant_id=active_tenant_id,
        role=active_role,
        tenant_slug=active_tenant_slug,
    )
    refresh_token = await token_service.create_refresh_token(
        user_id=user.id,
        tenant_id=active_tenant_id,
        session_info=session_info,
        remember_me=payload.remember_me,
    )

    _set_auth_cookies(response, access_token, refresh_token, remember_me=payload.remember_me)

    return LoginResponse(
        user=UserResponse.model_validate(user),
        orgs=orgs,
        has_multiple_orgs=len(orgs) > 1,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh — 1.5 AC4
# ---------------------------------------------------------------------------

@router.post(
    "/refresh",
    response_model=RefreshResponse,
    responses={
        401: {"description": "Refresh token invalid or expired"},
    },
)
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    """
    Rotate refresh token — issues new access + refresh tokens as cookies (AC4).
    Reads refresh_token from httpOnly cookie.
    Reuse detection: if old token is reused, ALL sessions are revoked.
    """
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "MISSING_REFRESH_TOKEN", "message": "No refresh token provided."}},
        )

    session_info = _session_info_from_request(request)

    try:
        new_refresh, user_id, tenant_id, session_data = await token_service.rotate_refresh_token(
            old_raw_token=raw_refresh,
            session_info=session_info,
        )
    except ValueError as exc:
        _clear_auth_cookies(response)
        code = "REFRESH_TOKEN_REUSE" if "REUSE" in str(exc) else "INVALID_REFRESH_TOKEN"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": code, "message": "Session expired. Please log in again."}},
        )

    # Load current role + tenant slug from DB for the new access token
    role: Optional[str] = None
    tenant_slug: Optional[str] = None
    if tenant_id is not None:
        result = await db.execute(
            select(TenantUser, Tenant)
            .join(Tenant, TenantUser.tenant_id == Tenant.id)
            .where(
                TenantUser.tenant_id == tenant_id,
                TenantUser.user_id == user_id,
                TenantUser.is_active == True,  # noqa: E712
            )
        )
        row = result.one_or_none()
        if row:
            tu, tenant_obj = row
            role = tu.role
            tenant_slug = tenant_obj.slug

    # Load user email for access token claims
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "Session expired. Please log in again."}},
        )

    new_access = token_service.create_access_token(
        user_id=user_id,
        email=user.email,
        tenant_id=tenant_id,
        role=role,
        tenant_slug=tenant_slug,
    )
    remember_me = session_data.get("remember_me", False)
    _set_auth_cookies(response, new_access, new_refresh, remember_me=remember_me)

    return RefreshResponse(success=True)


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout — 1.5 AC5
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    response_model=MessageResponse,
)
async def logout(
    request: Request,
    response: Response,
) -> MessageResponse:
    """
    Revoke the current session's refresh token and clear cookies (AC5).
    Idempotent: returns 200 even if already logged out.
    """
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        await token_service.invalidate_refresh_token(raw_refresh)
    _clear_auth_cookies(response)
    return MessageResponse(message="Logged out successfully.")


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout-all — 1.5 AC5
# ---------------------------------------------------------------------------

@router.post(
    "/logout-all",
    response_model=MessageResponse,
)
async def logout_all(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Revoke ALL sessions for the current user across all devices and orgs (AC5).
    """
    count = await token_service.invalidate_all_user_tokens(current_user.id)
    _clear_auth_cookies(response)
    logger.info("Logout-all", user_id=str(current_user.id), sessions_revoked=count)
    return MessageResponse(message=f"All {count} session(s) revoked.")


# ---------------------------------------------------------------------------
# GET /api/v1/auth/sessions — 1.5 AC5
# ---------------------------------------------------------------------------

@router.get(
    "/sessions",
    response_model=SessionListResponse,
)
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> SessionListResponse:
    """
    Return all active sessions for the current user (AC5).
    Marks the calling session as is_current.
    """
    raw_refresh = request.cookies.get("refresh_token")
    current_hash = _token_hash(raw_refresh) if raw_refresh else None

    raw_sessions = await token_service.list_user_sessions(
        user_id=current_user.id,
        current_token_hash=current_hash,
    )

    sessions = [
        SessionInfo(
            session_id=s["session_id"],
            ip=s.get("ip"),
            user_agent=s.get("user_agent"),
            device_name=s.get("device_name"),
            created_at=s.get("created_at", ""),
            is_current=s.get("is_current", False),
            remember_me=s.get("remember_me", False),
            tenant_id=s.get("tenant_id"),
        )
        for s in raw_sessions
    ]
    return SessionListResponse(sessions=sessions)


# ---------------------------------------------------------------------------
# DELETE /api/v1/auth/sessions/{session_id} — 1.5 AC5
# ---------------------------------------------------------------------------

@router.delete(
    "/sessions/{session_id}",
    response_model=MessageResponse,
)
async def revoke_session(
    session_id: str,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Revoke a specific session by its session_id prefix (AC5).
    session_id is the first 16 hex chars of the token_hash (from GET /sessions).
    If the revoked session is the current session, cookies are cleared.
    """
    # session_id is the first 16 chars of the token hash — scan user_sessions
    from src.cache import get_redis_client
    redis = get_redis_client()
    user_sessions_key = f"user_sessions:{current_user.id}"
    members = await redis.smembers(user_sessions_key)

    target_member = None
    for member in members:
        member_str = member.decode() if isinstance(member, bytes) else member
        idx = member_str.index(":")
        thash = member_str[idx + 1:]
        if thash.startswith(session_id):
            target_member = member_str
            break

    if target_member is None:
        return MessageResponse(message="Session not found or already expired.")

    idx = target_member.index(":")
    tenant_key = target_member[:idx]
    thash = target_member[idx + 1:]

    pipe = redis.pipeline()
    pipe.delete(f"sessions:{current_user.id}:{tenant_key}:{thash}")
    pipe.delete(f"refresh_map:{thash}")
    pipe.srem(user_sessions_key, target_member)
    await pipe.execute()

    # If this was the current session, clear cookies
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh and _token_hash(raw_refresh).startswith(session_id):
        _clear_auth_cookies(response)

    return MessageResponse(message="Session revoked.")


# ---------------------------------------------------------------------------
# POST /api/v1/auth/select-org — 1.5 AC6
# ---------------------------------------------------------------------------

@router.post(
    "/select-org",
    response_model=LoginResponse,
)
async def select_org(
    payload: SelectOrgRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LoginResponse:
    """
    Finalize org selection after multi-org login (AC6).
    Rotates the refresh token to bind it to the chosen tenant.
    Issues a new access token with tenant_id + role embedded.
    """
    # Verify membership in requested org
    result = await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == payload.tenant_id,
            TenantUser.user_id == current_user.id,
            TenantUser.is_active == True,  # noqa: E712
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "NOT_A_MEMBER", "message": "You are not a member of this organization."}},
        )

    session_info = _session_info_from_request(request)
    raw_refresh = request.cookies.get("refresh_token")

    # Rotate token to bind to new tenant
    if raw_refresh:
        try:
            new_refresh, _, _, session_data = await token_service.rotate_refresh_token(
                old_raw_token=raw_refresh,
                session_info=session_info,
            )
            remember_me = session_data.get("remember_me", False)
        except ValueError:
            # Old token expired/invalid — issue fresh token
            new_refresh = await token_service.create_refresh_token(
                user_id=current_user.id,
                tenant_id=payload.tenant_id,
                session_info=session_info,
                remember_me=False,
            )
            remember_me = False
    else:
        new_refresh = await token_service.create_refresh_token(
            user_id=current_user.id,
            tenant_id=payload.tenant_id,
            session_info=session_info,
            remember_me=False,
        )
        remember_me = False

    # Load tenant slug for JWT claim
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == payload.tenant_id)
    )
    selected_tenant = tenant_result.scalar_one_or_none()

    new_access = token_service.create_access_token(
        user_id=current_user.id,
        email=current_user.email,
        tenant_id=payload.tenant_id,
        role=membership.role,
        tenant_slug=selected_tenant.slug if selected_tenant else None,
    )
    _set_auth_cookies(response, new_access, new_refresh, remember_me=remember_me)

    # Return updated org list
    memberships = await _get_user_orgs(db, current_user.id)
    orgs = [
        TenantOrgInfo(id=t.id, name=t.name, slug=t.slug, role=tu.role)
        for tu, t in memberships
    ]
    return LoginResponse(
        user=UserResponse.model_validate(current_user),
        orgs=orgs,
        has_multiple_orgs=len(orgs) > 1,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/switch-org — 1.5 AC6
# ---------------------------------------------------------------------------

@router.post(
    "/switch-org",
    response_model=LoginResponse,
)
async def switch_org(
    payload: SwitchOrgRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LoginResponse:
    """
    Switch active org during an existing authenticated session (AC6).
    Functionally identical to select-org — separated for semantic clarity.
    """
    return await select_org(
        payload=SelectOrgRequest(tenant_id=payload.tenant_id),
        request=request,
        response=response,
        db=db,
        current_user=current_user,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/auth/oauth/google/authorize — 1.1 AC2
# ---------------------------------------------------------------------------

@router.get("/oauth/google/authorize")
async def google_authorize(request: Request) -> RedirectResponse:
    """
    Redirect user to Google OAuth consent screen (PKCE flow).
    Stores state → code_verifier in Redis (5-min TTL) for CSRF protection.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={"error": {"code": "OAUTH_NOT_CONFIGURED", "message": "Google OAuth is not configured."}},
        )

    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(48)

    redis = get_redis_client()
    await redis.setex(f"oauth:state:{state}", 300, code_verifier)

    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
    }
    google_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url=google_url)


# ---------------------------------------------------------------------------
# GET /api/v1/auth/oauth/google/callback — 1.1+1.5 AC2
# Now sets httpOnly cookies instead of query params (1.5)
# ---------------------------------------------------------------------------

@router.get("/oauth/google/callback")
async def google_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
) -> RedirectResponse:
    """
    Handle Google OAuth callback. Creates/links account, sets httpOnly cookies (1.5).
    """
    correlation_id = _correlation_id(request)
    await check_rate_limit(request, action="oauth_callback", max_requests=10, window_seconds=60)

    if error:
        logger.info("Google OAuth consent denied", error=error, correlation_id=correlation_id)
        return RedirectResponse(url=f"{settings.frontend_url}/login?error=oauth_denied")

    if not code or not state:
        return RedirectResponse(url=f"{settings.frontend_url}/login?error=oauth_invalid")

    redis = get_redis_client()
    code_verifier = await redis.getdel(f"oauth:state:{state}")
    if not code_verifier:
        logger.info("OAuth state mismatch", correlation_id=correlation_id)
        return RedirectResponse(url=f"{settings.frontend_url}/login?error=oauth_state_mismatch")

    if isinstance(code_verifier, bytes):
        code_verifier = code_verifier.decode()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()

            profile_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()

    except httpx.HTTPError as exc:
        logger.error("Google OAuth token exchange failed", exc=str(exc), correlation_id=correlation_id)
        return RedirectResponse(url=f"{settings.frontend_url}/login?error=oauth_network_failure")

    user, created = await get_or_create_oauth_user(
        db=db,
        google_id=profile["sub"],
        email=profile["email"],
        full_name=profile.get("name", profile["email"].split("@")[0]),
        avatar_url=profile.get("picture"),
        correlation_id=correlation_id,
    )

    memberships = await _get_user_orgs(db, user.id)
    if len(memberships) == 1:
        active_tenant_id = memberships[0][1].id
        active_tenant_slug = memberships[0][1].slug
        active_role = memberships[0][0].role
    else:
        active_tenant_id = None
        active_tenant_slug = None
        active_role = None

    session_info = _session_info_from_request(request)
    access_token = token_service.create_access_token(
        user_id=user.id,
        email=user.email,
        tenant_id=active_tenant_id,
        role=active_role,
        tenant_slug=active_tenant_slug,
    )
    refresh_token = await token_service.create_refresh_token(
        user_id=user.id,
        tenant_id=active_tenant_id,
        session_info=session_info,
        remember_me=False,
    )

    redirect_path = "/onboarding/create-org" if created else (
        "/select-org" if len(memberships) != 1 else "/dashboard"
    )
    redirect_response = RedirectResponse(url=f"{settings.frontend_url}{redirect_path}")
    _set_auth_cookies(redirect_response, access_token, refresh_token, remember_me=False)
    return redirect_response


# ---------------------------------------------------------------------------
# POST /api/v1/auth/verify-email — 1.1 AC3
# ---------------------------------------------------------------------------

@router.post(
    "/verify-email",
    response_model=MessageResponse,
    responses={400: {"description": "Invalid or expired token"}},
)
async def verify_email_endpoint(
    payload: VerifyEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Validate email verification JWT and mark user email as verified."""
    correlation_id = _correlation_id(request)
    try:
        await verify_email(db=db, token=payload.token, correlation_id=correlation_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TOKEN", "message": str(exc)}},
        )
    return MessageResponse(message="Email verified successfully. You can now log in.")


# ---------------------------------------------------------------------------
# POST /api/v1/auth/resend-verification — 1.1 AC3
# ---------------------------------------------------------------------------

@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    responses={429: {"description": "Rate limit exceeded"}},
)
async def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Resend verification email. Rate-limited: 3/email/hour.
    No email enumeration — always returns 200.
    """
    correlation_id = _correlation_id(request)

    redis = get_redis_client()
    key = f"rate:resend_verification:{payload.email}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    results = await pipe.execute()
    count, ttl = results[0], results[1]
    if count == 1:
        await redis.expire(key, 3600)
    if count > 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many resend requests. Try again later."}},
            headers={"Retry-After": str(max(ttl, 1))},
        )

    stmt = select(User).where(func.lower(User.email) == payload.email.lower())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user and not user.email_verified:
        verification_token = create_email_verification_token(user.id)
        background_tasks.add_task(
            send_verification_email,
            recipient_email=user.email,
            full_name=user.full_name,
            verification_token=verification_token,
            correlation_id=correlation_id,
        )

    return MessageResponse(
        message="If an unverified account exists for that email, a new verification link has been sent."
    )
