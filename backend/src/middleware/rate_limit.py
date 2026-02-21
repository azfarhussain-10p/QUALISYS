"""
Redis-backed sliding window rate limiter.
Story: 1-1-user-account-creation
AC: AC6 — 5 req/IP/min for signup; 10 req/IP/min for OAuth callback
AC: AC8 — HTTP 429 with Retry-After header on exceeded limit

Pattern: INCR + EXPIRE (atomic via Redis pipeline)
Key format: rate:{action}:{ip}  TTL: window_seconds
"""

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from src.cache import get_redis_client


async def check_rate_limit(
    request: Request,
    action: str,
    max_requests: int,
    window_seconds: int = 60,
) -> None:
    """
    Raises HTTP 429 if the client IP has exceeded max_requests within window_seconds.

    Args:
        request:        FastAPI Request object (to extract client IP).
        action:         Key namespace, e.g. 'signup', 'oauth_callback'.
        max_requests:   Maximum allowed requests within the window.
        window_seconds: Sliding window duration in seconds.
    """
    client_ip = _get_client_ip(request)
    redis: Redis = get_redis_client()
    key = f"rate:{action}:{client_ip}"

    # Atomic INCR + EXPIRE via pipeline
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    results = await pipe.execute()

    count: int = results[0]
    ttl: int = results[1]

    if ttl == -1:
        # Key has no TTL — set the sliding window expiry.
        # Covers both the first request (count==1) and the defensive case where
        # a key somehow lost its TTL; merging the two conditions eliminates the
        # redundant second expire call that the original code made (code-review L2).
        await redis.expire(key, window_seconds)
        ttl = window_seconds

    if count > max_requests:
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many requests. Retry after {retry_after} seconds.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, honouring X-Forwarded-For from reverse proxy.

    TRUST ASSUMPTION: X-Forwarded-For is accepted without further validation.
    This is safe only when all inbound traffic is routed through a trusted
    reverse proxy (nginx ingress, AWS ALB, Cloudflare, etc.) that strips and
    re-sets the header before forwarding. Verify your ingress configuration:

      nginx:  use-forwarded-headers: "true"
      ALB:    proxy_protocol enabled; set-real-ip-from matches the ALB CIDR

    If the service is ever exposed directly (no proxy), remove the
    X-Forwarded-For branch or validate the source IP against a trusted CIDR
    allowlist to prevent IP spoofing (code-review L5).
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
