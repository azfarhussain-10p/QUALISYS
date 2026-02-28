"""
QUALISYS API — Application Configuration
Story: 1-1-user-account-creation, 1-2-organization-creation-setup, 1-5-login-session-management
AC: AC4, AC6, AC7, AC8 (1.1) | AC6 — S3 logo upload settings (1.2) | AC3, AC8 (1.5)
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    environment: str = "development"
    port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://qualisys:qualisys_dev@localhost:5432/qualisys_master"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # JWT — RS256 asymmetric key pair (Story 1.5 AC3)
    # Leave empty in development: keys are auto-generated at startup.
    # In production: set PEM strings via environment variables or AWS Secrets Manager.
    jwt_private_key_pem: str = ""
    jwt_public_key_pem: str = ""
    # HS256 secret kept for email-verification JWT only (separate purpose — constraint)
    jwt_secret: str = "dev_jwt_secret_change_in_production"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_refresh_token_expire_days_remember_me: int = 30

    # Cookie settings (Story 1.5 AC3)
    cookie_secure: bool = False          # True in production (HTTPS)
    cookie_samesite: str = "lax"
    cookie_domain: Optional[str] = None  # None = current domain only

    # Login rate limiting (Story 1.5 AC8)
    login_max_attempts: int = 5           # Per-email within rate window → 429
    login_lockout_attempts: int = 10      # Per-email within lockout window → 423
    login_rate_window_seconds: int = 900  # 15 minutes
    login_lockout_window_seconds: int = 3600  # 1 hour

    # Email verification JWT (separate secret from session JWT — constraint)
    email_verification_secret: str = "dev_email_verification_secret_change_in_production"
    email_verification_expire_hours: int = 24

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    sendgrid_api_key: str = ""
    from_email: str = "noreply@qualisys.ai"
    from_name: str = "QUALISYS"

    # MFA — Story 1.7 (AC3, AC9)
    # AES-256-GCM key for TOTP secret encryption.
    # In production: set via AWS Secrets Manager / Azure Key Vault.
    # Must be a base64-encoded 32-byte (256-bit) key.
    # Default is a dev-only key — MUST be overridden in production.
    mfa_encryption_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="  # dev-only 32-byte base64

    # GitHub PAT encryption — Story 2.3 (AC-09)
    # Fernet symmetric key for encrypting GitHub Personal Access Tokens at rest.
    # In production: set via GITHUB_TOKEN_ENCRYPTION_KEY env var.
    # Must be a URL-safe base64-encoded 32-byte Fernet key (44 chars).
    # Default is a dev-only key — MUST be overridden in production.
    github_token_encryption_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="  # dev-only

    # Token budget — Story 2-8 (AC-17)
    monthly_token_budget: int = 100_000  # env: MONTHLY_TOKEN_BUDGET

    # MFA rate limiting
    mfa_token_ttl_seconds: int = 300        # 5 min mfa_token validity
    mfa_setup_ttl_seconds: int = 600        # 10 min temp secret during setup
    mfa_max_attempts_per_token: int = 5     # per mfa_token before invalidation
    mfa_max_failures_per_hour: int = 10     # per user per hour before lockout
    mfa_lockout_seconds: int = 3600         # 1 hour lockout after 10 failures

    # Profile — Story 1.8
    s3_avatar_key_prefix: str = "user-avatars"
    avatar_presigned_url_expires: int = 300        # 5 minutes (AC: presigned URLs expire quickly)
    change_password_rate_limit: int = 3             # per user per hour (AC5)
    change_password_rate_window_seconds: int = 3600  # 1 hour

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # S3 / AWS — Logo upload (Story 1.2 AC6)
    s3_bucket_name: str = ""
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_logo_key_prefix: str = "org-logos"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
