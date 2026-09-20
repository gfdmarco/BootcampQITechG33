from datetime import date
from passlib.hash import bcrypt

from controllers.base_controller import BaseController
from dtos import CustomerDTO
from errors import (
    InvalidDocumentNumber,
    DuplicatedDocumentNumber,
    DuplicatedEmail,
    InvalidBirthdate,
    UnderageCustomer,
    NotFoundCustomer,
)
from models import CustomerStatus
from repositories import CustomerRepository
from utils.document_number import is_valid_cpf

MINIMUM_AGE = 18


class CustomerController(BaseController):
    """As regras de negócio do Customer. Aqui mora o 'pode' e o 'não pode'."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.customer_repository = CustomerRepository(self.context)

    def create(self, customer_data: dict) -> dict:
        self.logger.debug("Criando um novo Customer")

        document_number = customer_data["document_number"]
        email = customer_data["email"]
        birthdate = self._parse_birthdate(customer_data["birthdate"])
        age = self._age_in_years(birthdate)

        if age < MINIMUM_AGE:
            raise UnderageCustomer(age, MINIMUM_AGE)

        if not is_valid_cpf(document_number):
            raise InvalidDocumentNumber(document_number)

        if self.customer_repository.get_by_document_number(document_number) is not None:
            raise DuplicatedDocumentNumber(document_number)

        if self.customer_repository.get_by_email(email) is not None:
            raise DuplicatedEmail(email)

        # Hash da senha usando bcrypt — gera salt automaticamente, padrão bancário
        password_hash = bcrypt.hash(customer_data["password"])

        customer = self.customer_repository.create(
            customer_data=customer_data,
            password_hash=password_hash,
            birth_date=birthdate,
        )

        # O evento de status precisa ser criado ANTES de montar o DTO,
        # para que status_events já apareça na resposta do POST.
        self.customer_repository.update_status(customer, CustomerStatus.CREATED)

        customer_dto = CustomerDTO.obj_to_dict(customer)
        self.session.commit()

        return customer_dto

    def get_by_key(self, customer_key: str) -> dict:
        self.logger.debug(f"Buscando o customer de chave {customer_key}")

        customer = self.customer_repository.get_by_key(customer_key)

        if customer is None:
            raise NotFoundCustomer(customer_key)

        return CustomerDTO.obj_to_dict(customer)

    def _parse_birthdate(self, raw_birthdate: str) -> date:
        """Converte a data, ou recusa com 422 em vez de 500.

        O schema já garantiu o FORMATO (quatro dígitos, traço, dois,
        traço, dois). O que ele não sabe é quantos dias fevereiro tem —
        um `pattern` conta caracteres, não consulta calendário. Por isso
        "2025-02-30" chega aqui intacto, e é aqui que ele para.
        """
        try:
            return date.fromisoformat(raw_birthdate)
        except ValueError:
            raise InvalidBirthdate(raw_birthdate)

    def _age_in_years(self, birthdate: date) -> int:
        today = date.today()
        age = today.year - birthdate.year

        # Quem ainda não fez aniversário este ano tem um ano a menos do
        # que a subtração acima diz.
        if (today.month, today.day) < (birthdate.month, birthdate.day):
            age = age - 1

        return age
