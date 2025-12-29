import hashlib
import secrets
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode


@dataclass
class TokenData:
    """Stores OAuth token data."""

    access_token: str
    token_type: str
    expires_at: Optional[datetime] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if the token is expired (with 5 min buffer)."""
        if self.expires_at is None:
            return False
        return datetime.now() >= self.expires_at - timedelta(minutes=5)


def generate_code_verifier(length: int = 128) -> str:
    """Generate a code verifier for PKCE OAuth flow."""
    return secrets.token_urlsafe(length)[:length]


def generate_code_challenge(verifier: str) -> str:
    """Generate a code challenge from the verifier using S256 method."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return urlsafe_b64encode(digest).decode().rstrip("=")


def generate_state() -> str:
    """Generate a random state parameter for OAuth."""
    return secrets.token_urlsafe(32)


def build_authorization_url(
    base_url: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    code_challenge: Optional[str] = None,
    extra_params: Optional[dict] = None,
) -> str:
    """Build an OAuth authorization URL."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }

    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"

    if extra_params:
        params.update(extra_params)

    return f"{base_url}?{urlencode(params)}"
