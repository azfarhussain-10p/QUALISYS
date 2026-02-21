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
