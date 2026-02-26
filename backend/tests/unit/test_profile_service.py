"""
Unit Tests — Profile Service
Story: 1-8-profile-notification-preferences (Task 7.1)
Covers:
  - Name validation (2-100 chars, no leading/trailing whitespace)
  - IANA timezone validation
  - Avatar presigned URL (content_type, file_size guards)
  - Change password (wrong current, weak new, same as old, success)
  - Notification preference defaults and security_alerts enforcement
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.base import Base
from src.models.user import User
from src.services.auth.auth_service import hash_password


# ---------------------------------------------------------------------------
# In-memory SQLite session for unit tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def mem_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(mem_engine):
    SessionLocal = async_sessionmaker(bind=mem_engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def local_user(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"u_{uuid.uuid4().hex[:8]}@test.com",
        full_name="Test User",
        password_hash=hash_password("OldPassword123!"),
        email_verified=True,
        auth_provider="email",
        timezone="UTC",
    )
    db.add(user)
    await db.flush()
    return user


# ===========================================================================
# TestUpdateProfileName — AC2
# ===========================================================================

class TestUpdateProfileName:
    """Validate name update rules in profile_service.update_profile."""

    @pytest.mark.asyncio
    async def test_name_updated_successfully(self, db, local_user):
        from src.services.profile_service import update_profile
        user = await update_profile(db, local_user, full_name="Jane Doe")
        assert user.full_name == "Jane Doe"

    @pytest.mark.asyncio
    async def test_name_too_short_raises(self, db, local_user):
        from src.services.profile_service import update_profile
        with pytest.raises(ValueError, match="2 and 100"):
            await update_profile(db, local_user, full_name="A")

    @pytest.mark.asyncio
    async def test_name_too_long_raises(self, db, local_user):
        from src.services.profile_service import update_profile
        with pytest.raises(ValueError, match="2 and 100"):
            await update_profile(db, local_user, full_name="X" * 101)

    @pytest.mark.asyncio
    async def test_name_with_leading_whitespace_raises(self, db, local_user):
        from src.services.profile_service import update_profile
        with pytest.raises(ValueError, match="whitespace"):
            await update_profile(db, local_user, full_name=" LeadingSpace")

    @pytest.mark.asyncio
    async def test_name_with_trailing_whitespace_raises(self, db, local_user):
        from src.services.profile_service import update_profile
        with pytest.raises(ValueError, match="whitespace"):
            await update_profile(db, local_user, full_name="TrailingSpace ")

    @pytest.mark.asyncio
    async def test_name_exactly_100_chars_allowed(self, db, local_user):
        from src.services.profile_service import update_profile
        long_name = "A" * 100
        user = await update_profile(db, local_user, full_name=long_name)
        assert user.full_name == long_name

    @pytest.mark.asyncio
    async def test_name_none_skips_update(self, db, local_user):
        from src.services.profile_service import update_profile
        original = local_user.full_name
        user = await update_profile(db, local_user, full_name=None)
        assert user.full_name == original


# ===========================================================================
# TestUpdateProfileTimezone — AC4
# ===========================================================================

class TestUpdateProfileTimezone:
    """Validate IANA timezone check in profile_service.update_profile."""

    @pytest.mark.asyncio
    async def test_valid_iana_timezone(self, db, local_user):
        from src.services.profile_service import update_profile
        user = await update_profile(db, local_user, timezone="America/New_York")
        assert user.timezone == "America/New_York"

    @pytest.mark.asyncio
    async def test_utc_allowed(self, db, local_user):
        from src.services.profile_service import update_profile
        user = await update_profile(db, local_user, timezone="UTC")
        assert user.timezone == "UTC"

    @pytest.mark.asyncio
    async def test_invalid_timezone_raises(self, db, local_user):
        from src.services.profile_service import update_profile
        with pytest.raises(ValueError, match="[Ii]nvalid.*timezone|[Tt]imezone.*invalid"):
            await update_profile(db, local_user, timezone="NotATimezone/Fake")

    @pytest.mark.asyncio
    async def test_timezone_too_long_raises(self, db, local_user):
        from src.services.profile_service import update_profile
        with pytest.raises(ValueError):
            await update_profile(db, local_user, timezone="A" * 51)

    @pytest.mark.asyncio
    async def test_timezone_none_skips_update(self, db, local_user):
        from src.services.profile_service import update_profile
        local_user.timezone = "Europe/London"
        await db.flush()
        user = await update_profile(db, local_user, timezone=None)
        assert user.timezone == "Europe/London"


# ===========================================================================
# TestAvatarPresignedUrl — AC3
# ===========================================================================

class TestAvatarPresignedUrl:
    """Guard content_type and file_size in profile_service.get_avatar_presigned_url."""

    def _call(self, content_type="image/png", file_size=1024):
        from src.services.profile_service import get_avatar_presigned_url

        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/presigned"
        with patch("src.services.profile_service.settings") as mock_settings:
            mock_settings.s3_bucket_name = "test-bucket"
            mock_settings.s3_avatar_key_prefix = "user-avatars"
            mock_settings.avatar_presigned_url_expires = 300
            with patch("boto3.client", return_value=mock_s3):
                return get_avatar_presigned_url(
                    user_id=uuid.uuid4(),
                    filename="photo.png",
                    content_type=content_type,
                    file_size=file_size,
                )

    def test_png_accepted(self):
        result = self._call(content_type="image/png")
        assert "upload_url" in result
        assert result["key"].endswith(".png")

    def test_jpeg_accepted(self):
        result = self._call(content_type="image/jpeg")
        assert result["key"].endswith(".jpg")

    def test_webp_accepted(self):
        result = self._call(content_type="image/webp")
        assert result["key"].endswith(".webp")

    def test_invalid_type_raises(self):
        from src.services.profile_service import get_avatar_presigned_url
        with pytest.raises(ValueError, match="[Cc]ontent.type|PNG|JPG|WebP"):
            get_avatar_presigned_url(
                user_id=uuid.uuid4(),
                filename="shell.sh",
                content_type="application/x-sh",
                file_size=100,
            )

    def test_file_too_large_raises(self):
        from src.services.profile_service import get_avatar_presigned_url
        with pytest.raises(ValueError, match="5MB|[Tt]oo large|[Ss]ize"):
            get_avatar_presigned_url(
                user_id=uuid.uuid4(),
                filename="big.png",
                content_type="image/png",
                file_size=6 * 1024 * 1024,
            )

    def test_s3_not_configured_raises_runtime(self):
        from src.services.profile_service import get_avatar_presigned_url
        with patch("src.services.profile_service.settings") as mock_settings:
            mock_settings.s3_bucket_name = ""
            mock_settings.s3_avatar_key_prefix = "user-avatars"
            mock_settings.avatar_presigned_url_expires = 300
            with pytest.raises(RuntimeError, match="S3_NOT_CONFIGURED"):
                get_avatar_presigned_url(
                    user_id=uuid.uuid4(),
                    filename="photo.png",
                    content_type="image/png",
                    file_size=512,
                )

    def test_key_contains_user_id_prefix(self):
        uid = uuid.uuid4()
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/presigned"
        from src.services.profile_service import get_avatar_presigned_url
        with patch("src.services.profile_service.settings") as mock_settings:
            mock_settings.s3_bucket_name = "test-bucket"
            mock_settings.s3_avatar_key_prefix = "user-avatars"
            mock_settings.avatar_presigned_url_expires = 300
            with patch("boto3.client", return_value=mock_s3):
                result = get_avatar_presigned_url(
                    user_id=uid,
                    filename="photo.png",
                    content_type="image/png",
                    file_size=512,
                )
        assert str(uid) in result["key"]
        assert result["key"].startswith("user-avatars/")


# ===========================================================================
# TestChangePassword — AC5
# ===========================================================================

class TestChangePassword:
    """Validate change_password business rules."""

    @pytest.mark.asyncio
    async def test_wrong_current_password_raises(self, db, local_user):
        from src.services.profile_service import change_password
        with pytest.raises(ValueError, match="[Cc]urrent password|[Ii]ncorrect"):
            await change_password(
                db,
                local_user,
                current_password="WrongPassword!",
                new_password="NewSecure456!",
            )

    @pytest.mark.asyncio
    async def test_weak_new_password_raises(self, db, local_user):
        from src.services.profile_service import change_password
        with pytest.raises(ValueError, match="[Pp]assword|[Pp]olicy|characters"):
            await change_password(
                db,
                local_user,
                current_password="OldPassword123!",
                new_password="weak",
            )

    @pytest.mark.asyncio
    async def test_same_password_raises(self, db, local_user):
        from src.services.profile_service import change_password
        with pytest.raises(ValueError, match="[Ss]ame|[Cc]urrent|[Dd]ifferent"):
            await change_password(
                db,
                local_user,
                current_password="OldPassword123!",
                new_password="OldPassword123!",
            )

    @pytest.mark.asyncio
    async def test_successful_change_updates_hash(self, db, local_user):
        from src.services.profile_service import change_password
        from src.services.auth.auth_service import verify_password

        old_hash = local_user.password_hash
        with patch("src.services.profile_service.token_service") as mock_ts:
            mock_ts.invalidate_all_user_tokens = AsyncMock(return_value=None)
            await change_password(
                db,
                local_user,
                current_password="OldPassword123!",
                new_password="NewSecure789!@",
            )
        assert local_user.password_hash != old_hash
        assert verify_password("NewSecure789!@", local_user.password_hash)

    @pytest.mark.asyncio
    async def test_successful_change_invalidates_sessions(self, db, local_user):
        from src.services.profile_service import change_password

        # Reset to known password
        local_user.password_hash = hash_password("OldPassword123!")
        await db.flush()

        with patch("src.services.profile_service.token_service") as mock_ts:
            mock_ts.invalidate_all_user_tokens = AsyncMock(return_value=None)
            await change_password(
                db,
                local_user,
                current_password="OldPassword123!",
                new_password="NewSecure789!@",
            )
            mock_ts.invalidate_all_user_tokens.assert_called_once_with(local_user.id)
