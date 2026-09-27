from datetime import datetime, timedelta, timezone

import jwt

from constants import (
    JWT_ALGORITHM,
    JWT_EXPIRATION_MINUTES,
    JWT_REFRESH_EXPIRATION_DAYS,
    JWT_SECRET,
)


def _create_token(customer_key: str, token_type: str, delta: timedelta) -> str:
    expiration = datetime.now(timezone.utc) + delta

    payload = {
        "sub": customer_key,
        "exp": expiration,
        "type": token_type,
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(customer_key: str) -> str:
    """Gera um JWT de curta duração (Access Token)."""
    return _create_token(
        customer_key=customer_key,
        token_type="access",
        delta=timedelta(minutes=JWT_EXPIRATION_MINUTES),
    )


def create_refresh_token(customer_key: str) -> str:
    """Gera um JWT de longa duração (Refresh Token)."""
    return _create_token(
        customer_key=customer_key,
        token_type="refresh",
        delta=timedelta(days=JWT_REFRESH_EXPIRATION_DAYS),
    )


def decode_token(token: str, expected_type: str) -> dict:
    """Decodifica e valida o token.

    Além da expiração e assinatura (validadas pelo PyJWT),
    garante que não estão usando um Refresh Token no lugar de um
    Access Token, e vice-versa.
    """
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    if payload.get("type") != expected_type:
        raise jwt.PyJWTError(f"Invalid token type. Expected {expected_type}.")

    return payload
