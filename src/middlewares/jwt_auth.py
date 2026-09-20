import jwt
from fastapi import FastAPI, Request

from constants import JWT_PUBLIC_ENDPOINTS
from errors.custom_errors import UnauthorizedToken
from errors.handlers import qi_exception_to_response
from utils.jwt_handler import decode_token


def register_jwt_middleware(application: FastAPI) -> None:
    """Valida o token JWT nas requisições.

    Verifica se a rota é pública. Se não for, exige o header Authorization
    com um token Bearer válido. Se falhar, retorna 401.
    """

    @application.middleware("http")
    async def verify_jwt_token(request: Request, call_next):
        # OPTIONS passa direto por conta de CORS
        if request.method == "OPTIONS":
            return await call_next(request)

        # Se for uma rota que já é isenta do INTERNAL_TOKEN, como a raiz
        # e o health_check, não checa o JWT
        from constants import BYPASS_ENDPOINTS
        if request.url.path in BYPASS_ENDPOINTS:
            return await call_next(request)

        # Checa se é uma rota pública do negócio (ex: /customers, /auth/login)
        for endpoint, method in JWT_PUBLIC_ENDPOINTS:
            if request.url.path.startswith(endpoint) and request.method == method:
                return await call_next(request)

        # A partir daqui, o token é obrigatório
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return qi_exception_to_response(UnauthorizedToken("Missing or invalid Authorization header."))

        token = auth_header.split(" ")[1]
        try:
            payload = decode_token(token, expected_type="access")
            request.state.customer_key = payload.get("sub")

        except jwt.ExpiredSignatureError:
            return qi_exception_to_response(UnauthorizedToken("Token has expired."))
        except jwt.PyJWTError:
            return qi_exception_to_response(UnauthorizedToken("Invalid token."))

        return await call_next(request)
