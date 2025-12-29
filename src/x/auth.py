import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

from src.common.auth import (
    TokenData,
    build_authorization_url,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)

X_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
X_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
REQUIRED_SCOPES = "tweet.read users.read bookmark.read offline.access"


class XAuthHandler:
    """Handles OAuth 2.0 PKCE authentication for X API."""

    def __init__(
        self,
        client_id: str,
        client_secret: Optional[str] = None,
        redirect_uri: str = "http://localhost:8001/callback",
        token_file: Optional[Path] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_file = token_file or Path.home() / ".x_tokens.json"
        self._token_data: Optional[TokenData] = None
        self._code_verifier: Optional[str] = None
        self._state: Optional[str] = None

    def get_authorization_url(self) -> tuple[str, str, str]:
        """
        Generate the authorization URL for the OAuth flow.

        Returns:
            Tuple of (authorization_url, state, code_verifier)
        """
        self._code_verifier = generate_code_verifier()
        self._state = generate_state()
        code_challenge = generate_code_challenge(self._code_verifier)

        url = build_authorization_url(
            base_url=X_AUTH_URL,
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=REQUIRED_SCOPES,
            state=self._state,
            code_challenge=code_challenge,
        )

        return url, self._state, self._code_verifier

    async def exchange_code(
        self,
        code: str,
        code_verifier: Optional[str] = None,
    ) -> TokenData:
        """
        Exchange authorization code for access token.

        Args:
            code: The authorization code from the callback
            code_verifier: The PKCE code verifier (uses stored one if not provided)
        """
        verifier = code_verifier or self._code_verifier
        if not verifier:
            raise ValueError("No code verifier available")

        async with httpx.AsyncClient() as client:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": verifier,
            }

            if self.client_secret:
                auth = (self.client_id, self.client_secret)
            else:
                data["client_id"] = self.client_id
                auth = None

            response = await client.post(
                X_TOKEN_URL,
                data=data,
                auth=auth,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_response = response.json()

        self._token_data = TokenData(
            access_token=token_response["access_token"],
            token_type=token_response["token_type"],
            expires_at=datetime.now() + timedelta(seconds=token_response.get("expires_in", 7200)),
            refresh_token=token_response.get("refresh_token"),
            scope=token_response.get("scope"),
        )

        self._save_tokens()
        return self._token_data

    async def refresh_access_token(self) -> TokenData:
        """Refresh the access token using the refresh token."""
        if not self._token_data or not self._token_data.refresh_token:
            raise ValueError("No refresh token available")

        async with httpx.AsyncClient() as client:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self._token_data.refresh_token,
            }

            if self.client_secret:
                auth = (self.client_id, self.client_secret)
            else:
                data["client_id"] = self.client_id
                auth = None

            response = await client.post(
                X_TOKEN_URL,
                data=data,
                auth=auth,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_response = response.json()

        self._token_data = TokenData(
            access_token=token_response["access_token"],
            token_type=token_response["token_type"],
            expires_at=datetime.now() + timedelta(seconds=token_response.get("expires_in", 7200)),
            refresh_token=token_response.get("refresh_token", self._token_data.refresh_token),
            scope=token_response.get("scope"),
        )

        self._save_tokens()
        return self._token_data

    async def get_valid_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if not self._token_data:
            self._load_tokens()

        if not self._token_data:
            raise ValueError("Not authenticated. Please complete the OAuth flow first.")

        if self._token_data.is_expired():
            await self.refresh_access_token()

        return self._token_data.access_token

    def _save_tokens(self) -> None:
        """Save tokens to file."""
        if not self._token_data:
            return

        data = {
            "access_token": self._token_data.access_token,
            "token_type": self._token_data.token_type,
            "expires_at": self._token_data.expires_at.isoformat() if self._token_data.expires_at else None,
            "refresh_token": self._token_data.refresh_token,
            "scope": self._token_data.scope,
        }

        self.token_file.write_text(json.dumps(data, indent=2))

    def _load_tokens(self) -> None:
        """Load tokens from file."""
        if not self.token_file.exists():
            return

        data = json.loads(self.token_file.read_text())
        self._token_data = TokenData(
            access_token=data["access_token"],
            token_type=data["token_type"],
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
        )

    def is_authenticated(self) -> bool:
        """Check if we have valid tokens."""
        if not self._token_data:
            self._load_tokens()
        return self._token_data is not None

    @classmethod
    def from_env(cls) -> "XAuthHandler":
        """Create an XAuthHandler from environment variables."""
        client_id = os.environ.get("X_CLIENT_ID")
        if not client_id:
            raise ValueError("X_CLIENT_ID environment variable is required")

        return cls(
            client_id=client_id,
            client_secret=os.environ.get("X_CLIENT_SECRET"),
            redirect_uri=os.environ.get("X_REDIRECT_URI", "http://localhost:8001/callback"),
        )
