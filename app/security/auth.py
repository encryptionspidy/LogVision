"""
JWT authentication and role-based access control (RBAC).

Provides:
- Token generation and verification
- @require_auth decorator for Flask endpoints
- Role-based access: admin (full), viewer (read-only)
- Dev auto-auth: auto-injects admin token when DEV_MODE=1

Configuration via environment variables:
- JWT_SECRET: Signing key (required in production)
- JWT_EXPIRY_HOURS: Token expiry (default: 24)
- DEV_MODE: Set to "1" to auto-inject admin token on missing auth
"""

from __future__ import annotations

import os
import logging
import functools
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask import request, jsonify, g, Flask

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

def is_dev_mode() -> bool:
    """Check if dev mode auto-auth is enabled."""
    return os.environ.get("DEV_MODE", "").strip() == "1"

# Valid roles
ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"
VALID_ROLES = {ROLE_ADMIN, ROLE_VIEWER}

# Roles allowed to mutate state
WRITE_ROLES = {ROLE_ADMIN}

# Cached dev token (generated once on first use)
_dev_token: str | None = None


def _get_secret() -> str:
    """Get JWT secret, warn if using insecure default."""
    secret = JWT_SECRET
    if not secret:
        logger.warning(
            "JWT_SECRET not set — using insecure fallback. "
            "Set JWT_SECRET env var in production!"
        )
        secret = "dev-insecure-secret-change-me"
    return secret


def _get_dev_token() -> str:
    """Get or create a cached dev-mode admin token."""
    global _dev_token
    if _dev_token is None:
        _dev_token = create_token("dev-admin", ROLE_ADMIN, expiry_hours=720)
        logger.warning(
            "🔓 DEV_MODE: Generated auto-auth admin token (dev-admin, 30d expiry)"
        )
    return _dev_token


# ─── Dev Auto-Auth Middleware ─────────────────────────────────────────────

def register_dev_middleware(app: Flask) -> None:
    """
    Register before_request middleware that auto-injects admin auth
    in dev mode. Auth decorators remain 100% intact.

    Only activates when DEV_MODE=1 environment variable is set.
    """
    if not is_dev_mode():
        return

    logger.warning(
        "⚠️  DEV_MODE is ON — requests without Authorization will be "
        "auto-authenticated as admin. NEVER use in production!"
    )

    # Log the dev token once at startup for curl usage
    token = _get_dev_token()
    logger.info("🔑 Dev token for curl: Authorization: Bearer %s", token)

    @app.before_request
    def _inject_dev_auth():
        """Auto-inject admin token if missing in dev mode."""
        auth_header = request.headers.get("Authorization", "")

        if not auth_header:
            # Mutate the request environ to inject the header
            # This way @require_auth sees a valid Bearer token
            dev_token = _get_dev_token()
            request.environ["HTTP_AUTHORIZATION"] = f"Bearer {dev_token}"
            logger.info(
                "DEV_MODE: Auto-injected admin token for %s %s",
                request.method, request.path,
            )


# ─── Token Management ────────────────────────────────────────────────────

def create_token(
    username: str,
    role: str = ROLE_VIEWER,
    expiry_hours: Optional[int] = None,
) -> str:
    """
    Generate a JWT token.

    Args:
        username: The authenticated user's name.
        role: User role (admin or viewer).
        expiry_hours: Custom expiry override.

    Returns:
        Encoded JWT string.

    Raises:
        ValueError: If role is invalid.
    """
    # Lazy import to avoid startup cost
    import jwt

    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of: {VALID_ROLES}")

    hours = expiry_hours or JWT_EXPIRY_HOURS
    payload = {
        "sub": username,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=hours),
    }

    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token.

    Args:
        token: The JWT string.

    Returns:
        Decoded payload dict with 'sub' and 'role'.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is malformed or invalid.
    """
    import jwt

    return jwt.decode(
        token,
        _get_secret(),
        algorithms=[JWT_ALGORITHM],
    )


# ─── Flask Decorators ────────────────────────────────────────────────────

def require_auth(f=None, *, roles: Optional[set[str]] = None):
    """
    Decorator to require JWT authentication on a Flask endpoint.

    Usage:
        @require_auth
        def my_endpoint(): ...

        @require_auth(roles={ROLE_ADMIN})
        def admin_only(): ...

    Sets g.current_user with decoded payload on success.
    """
    if f is None:
        # Called with arguments: @require_auth(roles=...)
        return functools.partial(require_auth, roles=roles)

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        import jwt

        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401

        token = auth_header[7:]  # Strip "Bearer "

        try:
            payload = verify_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        # Role check
        user_role = payload.get("role", ROLE_VIEWER)
        if roles and user_role not in roles:
            return jsonify({"error": "Insufficient permissions"}), 403

        # Store user info for the request
        g.current_user = {
            "username": payload["sub"],
            "role": user_role,
        }

        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    """Shortcut decorator: requires admin role."""
    return require_auth(f, roles=WRITE_ROLES)
