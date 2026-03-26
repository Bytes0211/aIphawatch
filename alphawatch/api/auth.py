"""Cognito JWT verification with JWKS caching."""

import time
from typing import Any

import httpx
from jose import JWTError, jwk, jwt

from alphawatch.config import get_settings

# In-memory JWKS cache
_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0
_JWKS_CACHE_TTL_SECONDS: int = 3600


class AuthError(Exception):
    """Raised when JWT verification fails.

    Attributes:
        detail: Human-readable error description.
        status_code: HTTP status code to return.
    """

    def __init__(self, detail: str, status_code: int = 401) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


async def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from Cognito, using an in-memory cache with TTL.

    Returns:
        The parsed JWKS response containing signing keys.
    """
    global _jwks_cache, _jwks_fetched_at

    now = time.monotonic()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_CACHE_TTL_SECONDS:
        return _jwks_cache

    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.cognito_jwks_url, timeout=10.0)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = now

    return _jwks_cache


def _get_signing_key(token: str, jwks_data: dict[str, Any]) -> dict[str, Any]:
    """Find the signing key in JWKS that matches the token's ``kid`` header.

    Args:
        token: The raw JWT string.
        jwks_data: The JWKS response from Cognito.

    Returns:
        The matching JWK key dict.

    Raises:
        AuthError: If no matching key is found.
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AuthError(f"Invalid token header: {exc}") from exc

    kid = unverified_header.get("kid")
    for key in jwks_data.get("keys", []):
        if key.get("kid") == kid:
            return key

    raise AuthError("Unable to find matching signing key")


async def verify_cognito_token(token: str) -> dict[str, Any]:
    """Verify a Cognito JWT and return its claims.

    Fetches JWKS (cached), finds the matching signing key, and decodes
    the token with full signature + issuer + audience verification.

    Args:
        token: The raw JWT bearer token string.

    Returns:
        Decoded token claims dict containing ``sub``,
        ``custom:tenant_id``, ``custom:role``, etc.

    Raises:
        AuthError: If the token is invalid, expired, or cannot be verified.
    """
    settings = get_settings()

    jwks_data = await _fetch_jwks()
    signing_key_data = _get_signing_key(token, jwks_data)

    try:
        public_key = jwk.construct(signing_key_data)
        claims = jwt.decode(
            token,
            public_key.to_pem().decode("utf-8"),
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=settings.cognito_issuer,
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        raise AuthError(f"Token verification failed: {exc}") from exc

    # Validate required custom claims
    if "custom:tenant_id" not in claims:
        raise AuthError("Token missing required claim: custom:tenant_id")
    if "custom:role" not in claims:
        raise AuthError("Token missing required claim: custom:role")

    return claims


def extract_bearer_token(authorization: str | None) -> str:
    """Extract the bearer token from the Authorization header value.

    Args:
        authorization: Raw ``Authorization`` header value.

    Returns:
        The token string without the ``Bearer `` prefix.

    Raises:
        AuthError: If the header is missing or malformed.
    """
    if not authorization:
        raise AuthError("Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Authorization header must be: Bearer <token>")

    return parts[1]
