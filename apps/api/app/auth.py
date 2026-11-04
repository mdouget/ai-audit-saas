from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str


bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def verifier() -> tuple[str, str, str, jwt.PyJWKClient]:
    issuer = os.environ.get("OIDC_ISSUER_URL", "").rstrip("/") + "/"
    audience = os.environ.get("OIDC_AUDIENCE")
    client_id = os.environ.get("OIDC_CLIENT_ID")
    url = urlsplit(issuer)
    if (
        url.scheme != "https" or not url.hostname or url.username or url.password
        or url.path != "/" or url.query or url.fragment
        or not audience or not client_id or audience == client_id
    ):
        raise HTTPException(503, "Authentication is not configured")
    return issuer, audience, client_id, jwt.PyJWKClient(issuer + ".well-known/jwks.json", timeout=5)


def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Identity:
    unauthorized = HTTPException(401, "Invalid or missing access token", {"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise unauthorized
    issuer, audience, client_id, keys = verifier()
    token = credentials.credentials
    try:
        key = keys.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token, key, algorithms=["RS256"], audience=audience, issuer=issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "azp"]},
        )
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(503, "Authentication provider is unavailable") from None
    except jwt.PyJWTError:
        raise unauthorized from None
    subject = claims["sub"]
    if (
        claims["azp"] != client_id or claims.get("gty") == "client-credentials"
        or not subject or len(subject) > 255 or "\x00" in subject or subject.endswith("@clients")
    ):
        raise unauthorized
    return Identity(issuer, subject)
