import os
import json
import base64
from functools import wraps

from fastapi import HTTPException, Request

ALLOWED_ISSUERS = {
    issuer.strip()
    for issuer in os.getenv("ALLOWED_ISSUERS", "sso-platform,YourIssuer").split(",")
    if issuer.strip()
}


def decode_jwt_without_verification(token: str) -> dict:
    try:
        parts = token.split(".")

        if len(parts) != 3:
            raise ValueError("Invalid JWT format")

        payload = parts[1]

        # Fix Base64 padding
        payload += "=" * (-len(payload) % 4)

        decoded = base64.urlsafe_b64decode(payload)

        return json.loads(decoded)

    except Exception as ex:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(ex)}"
        )

def validate_issuer(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request: Request = kwargs.get("request")
        if request is None:
            raise HTTPException(
                status_code=500,
                detail="Request object not found"
            )
        authorization = request.headers.get("Authorization")

        if not authorization:
            raise HTTPException(
                status_code=401,
                detail="Authorization header missing"
            )

        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Invalid Authorization format"
            )

        token = authorization.replace("Bearer ", "").strip()
        payload = decode_jwt_without_verification(token)
        issuer = payload.get("iss")

        if not issuer:
            raise HTTPException(
                status_code=401,
                detail="Token issuer missing"
            )

        if issuer not in ALLOWED_ISSUERS:
            raise HTTPException(
                status_code=403,
                detail=f"Unauthorized issuer: {issuer}"
            )
        request.state.token_payload = payload
        return await func(*args, **kwargs)
    return wrapper