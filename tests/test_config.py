"""Tests for application configuration."""

import os
from unittest.mock import patch

from alphawatch.config import Settings


class TestSettingsDefaults:
    """Verify default setting values for local development."""

    def test_default_environment(self):
        s = Settings()
        assert s.environment == "development"

    def test_default_db_host(self):
        s = Settings()
        assert s.db_host == "localhost"

    def test_default_db_port(self):
        s = Settings()
        assert s.db_port == 5432

    def test_default_db_name(self):
        s = Settings()
        assert s.db_name == "alphawatch"

    def test_default_redis_host(self):
        s = Settings()
        assert s.redis_host == "localhost"

    def test_default_redis_ssl_off(self):
        s = Settings()
        assert s.redis_ssl is False


class TestSettingsComputedProperties:
    """Verify computed URL properties."""

    def test_database_url(self):
        s = Settings(db_username="user", db_password="pass", db_host="db", db_port=5432, db_name="mydb")
        assert s.database_url == "postgresql+asyncpg://user:pass@db:5432/mydb"

    def test_redis_url_no_password(self):
        s = Settings(redis_host="redis", redis_port=6379, redis_db=0, redis_password="", redis_ssl=False)
        assert s.redis_url == "redis://redis:6379/0"

    def test_redis_url_with_password(self):
        s = Settings(redis_host="redis", redis_port=6379, redis_db=0, redis_password="secret", redis_ssl=False)
        assert s.redis_url == "redis://:secret@redis:6379/0"

    def test_redis_url_ssl(self):
        s = Settings(redis_host="redis", redis_port=6380, redis_db=0, redis_password="", redis_ssl=True)
        assert s.redis_url.startswith("rediss://")

    def test_cognito_issuer(self):
        s = Settings(cognito_region="us-west-2", cognito_user_pool_id="us-west-2_abc123")
        assert s.cognito_issuer == "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_abc123"

    def test_cognito_jwks_url(self):
        s = Settings(cognito_region="us-east-1", cognito_user_pool_id="us-east-1_xyz")
        assert s.cognito_jwks_url.endswith("/.well-known/jwks.json")


class TestSettingsEnvOverride:
    """Verify environment variable overrides."""

    def test_env_overrides_db_host(self):
        with patch.dict(os.environ, {"DB_HOST": "prod-db.example.com"}):
            s = Settings()
            assert s.db_host == "prod-db.example.com"

    def test_env_overrides_environment(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            s = Settings()
            assert s.environment == "production"
