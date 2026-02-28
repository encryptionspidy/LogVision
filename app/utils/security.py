"""
Security configuration (Rate Limits, etc).
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize Limiter
# In production, use Redis storage uri
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

def configure_security(app):
    """Apply security middleware to Flask app."""
    limiter.init_app(app)

    import os
    env = os.environ.get("ENV", "development").lower()
    is_prod = env == "production"

    # Secure cookie settings
    if is_prod:
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
        )

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if is_prod:
            # HSTS: enforce HTTPS for 1 year
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
