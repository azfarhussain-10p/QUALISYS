"""
QUALISYS — Invitation API Router
Story: 1-3-team-member-invitation
ACs: AC1–AC9

Admin endpoints (Owner/Admin only, under /api/v1/orgs/{org_id}/invitations):
  POST   /api/v1/orgs/{org_id}/invitations                         — bulk create
  GET    /api/v1/orgs/{org_id}/invitations                         — list pending/expired
  DELETE /api/v1/orgs/{org_id}/invitations/{invite_id}             — revoke
  POST   /api/v1/orgs/{org_id}/invitations/{invite_id}/resend      — resend expired

Public endpoints (token-authenticated, no Bearer required for new-user path):
  GET  /api/v1/invitations/{token}                                 — inspect token (M2: path param)
  POST /api/v1/invitations/accept                                  — accept invitation

Rate limiting (AC8):
  • 50 invites/org/hour   (key: rate:invite:{org_id})
  • 3 invites/email/org/24h (key: rate:invite:{org_id}:{email})
  • 10 failed accepts/IP/hour (key: rate:invite-accept-fail:{ip})  — only on failure
"""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.invitations.schemas import (
    AcceptInviteDetailsResponse,
    AcceptInviteRequest,
    AcceptInviteResponse,
    BulkInviteRequest,
    BulkInviteResponse,
    InviteItemError,
    InvitationResponse,
)
from src.cache import get_redis_client
from src.config import get_settings
from src.db import AsyncSessionLocal, get_db
from src.logger import logger
from src.middleware.rbac import get_current_user, require_role
from src.models.invitation import Invitation
from src.models.tenant import Tenant, TenantUser
from src.models.user import User
from src.services.invitation.invitation_service import (
    AlreadyMemberError,
    DuplicatePendingInviteError,
    EmailMismatchError,
    InvalidRoleError,
    InvitationNotRevocableError,
    InvitationService,
    TokenExpiredError,
    TokenNotFoundError,
    TokenRevokedError,
)
from src.services.notification.notification_service import send_invitation_email

settings = get_settings()
_invitation_svc = InvitationService()
_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Two APIRouter instances — one for admin (under /orgs), one for public
# ---------------------------------------------------------------------------

# Admin endpoints live under the orgs prefix so require_role can extract org_id
router_admin = APIRouter(prefix="/api/v1/orgs", tags=["invitations"])
# Public accept endpoints
router_public = APIRouter(prefix="/api/v1/invitations", tags=["invitations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _correlation_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def _client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _check_org_rate_limit(org_id: uuid.UUID) -> None:
    """
    AC8: Per-organization invite rate limit — 50 invitations per org per hour.
    Applied unconditionally before any invite lookup (M3 fix: prevents bypass
    by attacker supplying a non-existent invite ID in the resend endpoint).
    """
    redis = get_redis_client()
    org_key = f"rate:invite:{org_id}"
    pipe = redis.pipeline()
    pipe.incr(org_key)
    pipe.ttl(org_key)
    results = await pipe.execute()
    org_count, org_ttl = results[0], results[1]
    if org_ttl == -1:
        await redis.expire(org_key, 3600)
        org_ttl = 3600
    if org_count > 50:
        retry_after = max(org_ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many invitations sent from this organization. Retry after a while.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


async def _check_email_rate_limit(org_id: uuid.UUID, email: str) -> None:
    """
    AC8: Per-email-per-org invite rate limit — 3 invitations to same email per org per 24h.
    Applied after invite lookup so the email address is known.
    """
    redis = get_redis_client()
    email_key = f"rate:invite:{org_id}:{email.lower()}"
    pipe = redis.pipeline()
    pipe.incr(email_key)
    pipe.ttl(email_key)
    results = await pipe.execute()
    email_count, email_ttl = results[0], results[1]
    if email_ttl == -1:
        await redis.expire(email_key, 86400)
        email_ttl = 86400
    if email_count > 3:
        retry_after = max(email_ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many invitations sent to this email address. Retry after a while.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


async def _track_failed_accept(request: Request) -> None:
    """
    AC8: Track failed accept attempts per IP (brute-force prevention).
    10 failed accepts/IP/hour triggers a temporary block.
    Called ONLY on invalid-token failures (not on business logic rejections like email mismatch).
    """
    redis = get_redis_client()
    ip = _client_ip(request)
    key = f"rate:invite-accept-fail:{ip}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    results = await pipe.execute()
    count, ttl = results[0], results[1]
    if ttl == -1:
        await redis.expire(key, 3600)
        ttl = 3600
    if count > 10:
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many failed attempts. Please try again later.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


async def _audit_invite_action(
    db_session,
    schema_name: str,
    action: str,
    actor_id: uuid.UUID,
    actor_email: str,
    resource_id: uuid.UUID,
    details: dict,
    ip_address: Optional[str] = None,
) -> None:
    """Write an invitation audit event to the tenant schema's audit_logs table. AC9."""
    try:
        async with AsyncSessionLocal() as audit_db:
            await audit_db.execute(
                text(
                    f'INSERT INTO "{schema_name}".audit_logs '
                    "(action, actor_id, actor_email, resource_type, resource_id, details, ip_address) "
                    "VALUES (:action, :actor_id, :actor_email, :resource_type, :resource_id, "
                    "        :details::jsonb, :ip_address)"
                ),
                {
                    "action": action,
                    "actor_id": str(actor_id),
                    "actor_email": actor_email,
                    "resource_type": "invitation",
                    "resource_id": str(resource_id),
                    "details": json.dumps(details, default=str),
                    "ip_address": ip_address,
                },
            )
            await audit_db.commit()
    except Exception as exc:
        logger.error("Invitation audit log write failed", error=str(exc), action=action)


def _get_tenant_schema(tenant: Tenant) -> str:
    return f"tenant_{tenant.slug.replace('-', '_')}"


# ---------------------------------------------------------------------------
# POST /api/v1/orgs/{org_id}/invitations — AC1, AC2, AC3, AC8, AC9
# ---------------------------------------------------------------------------

@router_admin.post(
    "/{org_id}/invitations",
    response_model=BulkInviteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Insufficient role"},
        422: {"description": "Validation error"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def create_invitations(
    org_id: uuid.UUID,
    payload: BulkInviteRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> BulkInviteResponse:
    """
    Bulk-create invitations for the organization. AC1, AC2, AC3, AC8, AC9.

    - Max 20 per request (validated by Pydantic)
    - Per-email validation: duplicate, existing member, invalid role
    - Batch is NOT atomic: valid invitations are created even if some fail
    - Sends invitation email asynchronously per created invite
    - Rate limited: 50/org/hr + 3/email/org/24h
    """
    user, membership = auth
    correlation_id = _correlation_id(request)
    ip = _client_ip(request)

    # Load tenant for schema name (audit log)
    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
        )

    created: list[InvitationResponse] = []
    errors: list[InviteItemError] = []

    for item in payload.invitations:
        # AC8: org-level rate limit first, then per-email
        try:
            await _check_org_rate_limit(org_id)
            await _check_email_rate_limit(org_id, item.email)
        except HTTPException as exc:
            errors.append(InviteItemError(email=item.email, reason=exc.detail["error"]["message"]))
            continue

        try:
            # M1: create_invitation returns (Invitation, raw_token); raw_token used for email URL
            invitation, raw_token = await _invitation_svc.create_invitation(
                db=db,
                tenant_id=org_id,
                email=item.email,
                role=item.role,
                invited_by=user.id,
            )
            created.append(InvitationResponse.model_validate(invitation))

            # AC3: send invitation email asynchronously
            _invite_id = invitation.id
            _invite_token = raw_token  # plaintext token for accept URL (hash stored in DB)
            _invite_email = invitation.email
            _invite_role = invitation.role
            _invite_expires = invitation.expires_at

            background_tasks.add_task(
                send_invitation_email,
                recipient_email=_invite_email,
                inviter_name=user.full_name,
                org_name=tenant.name,
                role=_invite_role,
                invite_token=_invite_token,
                expires_at=_invite_expires,
                correlation_id=correlation_id,
            )

            # AC9: audit log (background)
            background_tasks.add_task(
                _audit_invite_action,
                None,  # db_session unused (uses own session)
                _get_tenant_schema(tenant),
                "invitation.sent",
                user.id,
                user.email,
                _invite_id,
                {"email": _invite_email, "role": _invite_role},
                ip,
            )

        except InvalidRoleError as exc:
            errors.append(InviteItemError(email=item.email, reason=str(exc)))
        except DuplicatePendingInviteError as exc:
            errors.append(InviteItemError(email=item.email, reason=str(exc)))
        except AlreadyMemberError as exc:
            errors.append(InviteItemError(email=item.email, reason=str(exc)))
        except Exception as exc:
            logger.error(
                "Unexpected error creating invitation",
                email=item.email,
                error=str(exc),
                correlation_id=correlation_id,
            )
            errors.append(InviteItemError(email=item.email, reason="Internal error. Please try again."))

    await db.commit()

    return BulkInviteResponse(data=created, errors=errors)


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/invitations — AC6
# ---------------------------------------------------------------------------

@router_admin.get(
    "/{org_id}/invitations",
    response_model=list[InvitationResponse],
    responses={
        403: {"description": "Insufficient role"},
    },
)
async def list_invitations(
    org_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: pending|expired"),
    auth: tuple = require_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationResponse]:
    """
    List pending and expired invitations for the organization. AC6.
    Owner/Admin only.
    """
    invitations = await _invitation_svc.list_invitations(
        db=db,
        tenant_id=org_id,
        status_filter=status_filter,
    )
    return [InvitationResponse.model_validate(inv) for inv in invitations]


# ---------------------------------------------------------------------------
# DELETE /api/v1/orgs/{org_id}/invitations/{invite_id} — AC6
# ---------------------------------------------------------------------------

@router_admin.delete(
    "/{org_id}/invitations/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Invitation not found or not revocable"},
    },
)
async def revoke_invitation(
    org_id: uuid.UUID,
    invite_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Revoke a pending invitation. Token is immediately invalidated. AC6, AC9.
    """
    user, membership = auth
    ip = _client_ip(request)

    # Load tenant for audit
    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()

    try:
        invitation = await _invitation_svc.revoke_invitation(
            db=db,
            invite_id=invite_id,
            tenant_id=org_id,
        )
        await db.commit()
    except TokenNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )
    except InvitationNotRevocableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )

    # AC9: audit log
    if tenant:
        background_tasks.add_task(
            _audit_invite_action,
            None,
            _get_tenant_schema(tenant),
            "invitation.revoked",
            user.id,
            user.email,
            invite_id,
            {"email": invitation.email, "role": invitation.role},
            ip,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/orgs/{org_id}/invitations/{invite_id}/resend — AC6
# ---------------------------------------------------------------------------

@router_admin.post(
    "/{org_id}/invitations/{invite_id}/resend",
    response_model=InvitationResponse,
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Invitation not found or not resendable"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def resend_invitation(
    org_id: uuid.UUID,
    invite_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    """
    Resend an expired invitation. Generates new token, resets 7-day expiry. AC6.
    """
    user, membership = auth
    correlation_id = _correlation_id(request)
    ip = _client_ip(request)

    # Load tenant for email + audit
    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
        )

    # AC8 M3: apply org-level rate limit UNCONDITIONALLY before invite lookup.
    # Previously this was gated on finding the invite (allowing bypass via fake UUIDs).
    await _check_org_rate_limit(org_id)

    # Load invite to get email for the per-email rate limit
    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invite_id,
            Invitation.tenant_id == org_id,
        )
    )
    old_invite = result.scalar_one_or_none()
    if old_invite:
        # AC8: per-email rate limit only when invite exists (email is known)
        await _check_email_rate_limit(org_id, old_invite.email)

    try:
        # M1: resend_invitation returns (Invitation, raw_token); raw_token used for email URL
        invitation, raw_token = await _invitation_svc.resend_invitation(
            db=db,
            invite_id=invite_id,
            tenant_id=org_id,
        )
        await db.commit()
        await db.refresh(invitation)
    except TokenNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )

    # AC3: resend email asynchronously using raw token (not the stored hash)
    background_tasks.add_task(
        send_invitation_email,
        recipient_email=invitation.email,
        inviter_name=user.full_name,
        org_name=tenant.name,
        role=invitation.role,
        invite_token=raw_token,
        expires_at=invitation.expires_at,
        correlation_id=correlation_id,
    )

    # AC9: audit log
    background_tasks.add_task(
        _audit_invite_action,
        None,
        _get_tenant_schema(tenant),
        "invitation.resent",
        user.id,
        user.email,
        invite_id,
        {"email": invitation.email, "role": invitation.role},
        ip,
    )

    return InvitationResponse.model_validate(invitation)


# ---------------------------------------------------------------------------
# GET /api/v1/invitations/{token} — AC4, AC5 (public)
# M2: Token in PATH param (not query string) to reduce log exposure surface.
# Tech spec §5.4 specifies path parameter.
# ---------------------------------------------------------------------------

@router_public.get(
    "/{token}",
    response_model=AcceptInviteDetailsResponse,
    responses={
        400: {"description": "Invalid or expired token"},
        410: {"description": "Invitation expired or revoked"},
    },
)
async def get_invite_details(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> AcceptInviteDetailsResponse:
    """
    Validate an invitation token and return invite details for the accept page.
    Frontend uses user_exists flag to show existing-user or new-user UI. AC4/AC5.
    No authentication required — public endpoint. Token is in the URL path.
    """
    try:
        details = await _invitation_svc.get_invite_details(db=db, token=token)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )
    except (TokenNotFoundError, TokenRevokedError) as exc:
        # AC9: no information leakage — map both to generic 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_INVITATION", "message": "This invitation link is invalid."}},
        )

    return AcceptInviteDetailsResponse(
        org_name=details["org_name"],
        role=details["role"],
        email=details["email"],
        user_exists=details["user_exists"],
        expires_at=details["expires_at"],
    )


# ---------------------------------------------------------------------------
# POST /api/v1/invitations/accept — AC4, AC5 (public/optional-auth)
# ---------------------------------------------------------------------------

@router_public.post(
    "/accept",
    response_model=AcceptInviteResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid token or email mismatch"},
        401: {"description": "Authentication required for existing-user path"},
        409: {"description": "Already a member"},
        410: {"description": "Invitation expired or revoked"},
        422: {"description": "Validation error"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def accept_invitation(
    payload: AcceptInviteRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AcceptInviteResponse:
    """
    Accept an invitation.

    Two paths (AC4/AC5):
    - Existing user: Bearer auth required, provide only token
    - New user: no auth, provide token + full_name + password

    AC8: Failed token lookups tracked per IP for brute-force prevention.
    AC9: Token invalidated on accept; email match enforced.
    """
    from src.services.auth.auth_service import (
        DuplicateEmailError,
        create_access_token,
        create_refresh_token,
        register_user,
    )

    correlation_id = _correlation_id(request)
    ip = _client_ip(request)

    # Validate token (also tracks failed accepts for brute-force — AC8)
    try:
        invite_details = await _invitation_svc.get_invite_details(db=db, token=payload.token)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )
    except (TokenNotFoundError, TokenRevokedError):
        # AC8: track failed attempt for brute-force prevention
        await _track_failed_accept(request)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_INVITATION", "message": "This invitation link is invalid."}},
        )

    invite_email = invite_details["email"]
    user_exists = invite_details["user_exists"]

    # ---------------------------------------------------------------------------
    # Determine flow: existing user or new user
    # ---------------------------------------------------------------------------

    if user_exists:
        # AC4: existing user path — requires Bearer auth
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "AUTHENTICATION_REQUIRED",
                        "message": "Please log in to accept this invitation.",
                    }
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Decode JWT to get user_id
        from jose import JWTError, jwt as jose_jwt
        from src.config import get_settings as _get_settings
        _settings = _get_settings()
        try:
            jwt_payload = jose_jwt.decode(
                credentials.credentials,
                _settings.jwt_secret,
                algorithms=[_settings.jwt_algorithm],
            )
            if jwt_payload.get("type") != "access":
                raise JWTError("Not an access token")
            authenticated_user_id = uuid.UUID(jwt_payload["sub"])
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token."}},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Load the authenticated user
        result = await db.execute(select(User).where(User.id == authenticated_user_id))
        current_user = result.scalar_one_or_none()
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found."}},
            )

        try:
            membership = await _invitation_svc.accept_invitation(
                db=db,
                token=payload.token,
                user_id=current_user.id,
                accepting_email=current_user.email,
            )
            await db.commit()
        except EmailMismatchError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": exc.code, "message": str(exc)}},
            )
        except (TokenNotFoundError, TokenExpiredError, TokenRevokedError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": exc.code, "message": str(exc)}},
            )

        # AC9: audit
        result = await db.execute(select(Tenant).where(Tenant.id == membership.tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant:
            background_tasks.add_task(
                _audit_invite_action,
                None,
                _get_tenant_schema(tenant),
                "invitation.accepted",
                current_user.id,
                current_user.email,
                membership.tenant_id,
                {"role": membership.role, "path": "existing_user"},
                ip,
            )

        return AcceptInviteResponse(
            user_id=current_user.id,
            org_id=membership.tenant_id,
            role=membership.role,
        )

    else:
        # AC5: new user path — full_name + password required
        if not payload.full_name or not payload.password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": "REGISTRATION_REQUIRED",
                        "message": "Full name and password are required to accept this invitation.",
                    }
                },
            )

        # Create user account (AC5: email auto-verified — trusted admin invite)
        try:
            new_user = await register_user(
                db=db,
                email=invite_email,
                password=payload.password,
                full_name=payload.full_name,
                correlation_id=correlation_id,
            )
        except DuplicateEmailError:
            # Race condition: user registered between GET and POST
            result = await db.execute(
                select(User).where(User.email == invite_email)
            )
            new_user = result.scalar_one()

        # AC5: mark email as verified (trusted admin invitation bypasses email verification)
        new_user.email_verified = True
        await db.flush()

        try:
            membership = await _invitation_svc.accept_invitation(
                db=db,
                token=payload.token,
                user_id=new_user.id,
                accepting_email=invite_email,
            )
            await db.commit()
        except (TokenNotFoundError, TokenExpiredError, TokenRevokedError, EmailMismatchError) as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": exc.code, "message": str(exc)}},
            )

        # Issue JWT tokens for new user (AC5: redirects to dashboard after signup)
        access_token = create_access_token(new_user.id, new_user.email)
        refresh_token = create_refresh_token()

        # AC9: audit
        result = await db.execute(select(Tenant).where(Tenant.id == membership.tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant:
            background_tasks.add_task(
                _audit_invite_action,
                None,
                _get_tenant_schema(tenant),
                "invitation.accepted",
                new_user.id,
                new_user.email,
                membership.tenant_id,
                {"role": membership.role, "path": "new_user"},
                ip,
            )

        return AcceptInviteResponse(
            user_id=new_user.id,
            org_id=membership.tenant_id,
            role=membership.role,
            access_token=access_token,
            refresh_token=refresh_token,
        )
