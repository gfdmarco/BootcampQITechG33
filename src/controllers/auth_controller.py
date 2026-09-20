import jwt
from passlib.hash import bcrypt

from controllers.base_controller import BaseController
from errors.custom_errors import InvalidCredentials
from models import CustomerStatus
from repositories import CustomerRepository
from utils.jwt_handler import create_access_token, create_refresh_token, decode_token


class AuthController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.customer_repository = CustomerRepository(self.context)

    def login(self, credentials: dict) -> dict:
        self.logger.debug("Tentativa de login")

        document_number = credentials["document_number"]
        raw_password = credentials["password"]

        customer = self.customer_repository.get_by_document_number(document_number)

        dummy_hash = "$2b$12$KIXbGz6j6r1YzlTmv8h5oe7Yq8HZW9Z5M6uR5cR5cR5cR5cR5cR5"
        hash_to_check = customer.password_hash if customer else dummy_hash

        password_ok = bcrypt.verify(raw_password, hash_to_check)

        if customer is None or not password_ok:
            raise InvalidCredentials()
            
        # Não deixa logar se o cliente estiver falho/bloqueado
        if customer.status.enumerator == CustomerStatus.FAILED:
            raise InvalidCredentials()

        access_token = create_access_token(customer.customer_key)
        refresh_token = create_refresh_token(customer.customer_key)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer"
        }

    def refresh(self, payload: dict) -> dict:
        """Emite um novo Access Token usando um Refresh Token válido."""
        self.logger.debug("Tentativa de refresh token")

        refresh_token = payload["refresh_token"]

        try:
            token_data = decode_token(refresh_token, expected_type="refresh")
        except jwt.PyJWTError:
            from errors.custom_errors import UnauthorizedToken
            raise UnauthorizedToken("Invalid or expired refresh token.")

        customer_key = token_data.get("sub")
        customer = self.customer_repository.get_by_key(customer_key)

        if customer is None or customer.status.enumerator == CustomerStatus.FAILED:
            from errors.custom_errors import UnauthorizedToken
            raise UnauthorizedToken("Customer no longer active.")

        new_access_token = create_access_token(customer.customer_key)

        # Retornamos apenas um novo access_token. O refresh token continua o mesmo
        # até expirar, forçando um novo login real.
        return {
            "access_token": new_access_token,
            "token_type": "Bearer"
        }

    def update_password(self, payload: dict, token_customer_key: str) -> None:
        self.logger.debug(f"Atualizando senha do cliente {token_customer_key}")

        customer = self.customer_repository.get_by_key(token_customer_key)
        
        # O token validou o cliente, mas ele pode ter sido deletado nesse milissegundo
        if customer is None:
            from errors.custom_errors import NotFoundCustomer
            raise NotFoundCustomer(token_customer_key)

        current_password = payload["current_password"]
        new_password = payload["new_password"]

        # Se a senha atual não bater, levantamos credenciais inválidas (401)
        if not bcrypt.verify(current_password, customer.password_hash):
            raise InvalidCredentials()

        # Atualizamos a senha com um novo hash bancário
        customer.password_hash = bcrypt.hash(new_password)
        self.session.commit()

