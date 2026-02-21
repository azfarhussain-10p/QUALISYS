"""
Unit Tests — Slug generation and schema-name derivation
Story: 1-2-organization-creation-setup (Task 7.1)
AC: AC2 — slug format validation
AC: AC9 — schema name safe identifier check (SQL injection prevention)
"""

import pytest

from src.api.v1.orgs.router import _slugify
from src.services.tenant_provisioning import slug_to_schema_name, validate_safe_identifier


class TestSlugify:
    def test_basic_name(self):
        assert _slugify("Acme Corp") == "acme-corp"

    def test_extra_spaces(self):
        assert _slugify("  hello   world  ") == "hello-world"

    def test_special_characters_stripped(self):
        assert _slugify("Hello & World!") == "hello-world"

    def test_unicode_normalized(self):
        # accented chars should degrade to ascii
        result = _slugify("Société Générale")
        assert result == "societe-generale"

    def test_numbers_preserved(self):
        assert _slugify("Team 42") == "team-42"

    def test_truncated_to_50_chars(self):
        long_name = "A" * 200
        result = _slugify(long_name)
        assert len(result) <= 50

    def test_no_leading_trailing_hyphens(self):
        result = _slugify("---Test---")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_consecutive_special_chars_become_single_hyphen(self):
        assert _slugify("hello!!!world") == "hello-world"

    def test_empty_string_returns_empty(self):
        assert _slugify("") == ""

    def test_only_special_chars_returns_empty_or_short(self):
        result = _slugify("!@#$%")
        assert result == "" or len(result) <= 50


class TestSlugToSchemaName:
    def test_hyphen_converted_to_underscore(self):
        assert slug_to_schema_name("my-org") == "tenant_my_org"

    def test_plain_slug(self):
        assert slug_to_schema_name("acmecorp") == "tenant_acmecorp"

    def test_multiple_hyphens(self):
        assert slug_to_schema_name("my-big-org-2024") == "tenant_my_big_org_2024"

    def test_prefix_always_tenant(self):
        result = slug_to_schema_name("any-name")
        assert result.startswith("tenant_")

    def test_numbers_in_slug(self):
        assert slug_to_schema_name("org42") == "tenant_org42"


class TestValidateSafeIdentifier:
    def test_valid_schema_name(self):
        assert validate_safe_identifier("tenant_my_org") is True

    def test_must_start_with_letter(self):
        assert validate_safe_identifier("1bad_start") is False

    def test_rejects_hyphen(self):
        # schema names use underscores only
        assert validate_safe_identifier("tenant-bad") is False

    def test_rejects_semicolon(self):
        assert validate_safe_identifier("tenant_x; DROP SCHEMA") is False

    def test_rejects_quote(self):
        assert validate_safe_identifier("tenant_x'injection") is False

    def test_rejects_double_quote(self):
        assert validate_safe_identifier('tenant_x"injection') is False

    def test_rejects_empty_string(self):
        assert validate_safe_identifier("") is False

    def test_rejects_too_long(self):
        # max 63 chars for PostgreSQL identifiers
        long = "t" * 64
        assert validate_safe_identifier(long) is False

    def test_accepts_max_valid_length(self):
        # exactly 63 chars starting with letter
        valid = "t" + "a" * 62
        assert validate_safe_identifier(valid) is True

    def test_rejects_uppercase(self):
        # safe identifiers are lowercase only
        assert validate_safe_identifier("Tenant_upper") is False
