from datetime import date
from passlib.hash import bcrypt

from errors.custom_errors import (
    InvalidDocumentNumber,
    DuplicatedDocumentNumber,
    DuplicatedEmail,
    InvalidBirthdate,
    UnderageCustomer,
)
from controllers.base_controller import BaseController
from repositories.customer_repository import CustomerRepository
from dtos.customer_dto import CustomerDTO
from utils.document_number import is_valid_cpf

MINIMUM_AGE = 18

class CustomerController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.customer_repository = CustomerRepository(self.context)

    def _parse_birthdate(self, birthdate_str: str) -> date:
        try:
            return date.fromisoformat(birthdate_str)
        except ValueError:
            raise InvalidBirthdate(birthdate_str)
            
    def _age_in_years(self, birthdate: date) -> int:
        today = date.today()
        age = today.year - birthdate.year

        if (today.month, today.day) < (birthdate.month, birthdate.day):
            age -= 1

        return age

    def create(self, customer_data: dict) -> dict:
        self.logger.debug("Criando um novo Customer")

        document_number = customer_data["document_number"]
        email = customer_data["email"]
        birthdate_str = customer_data["birthdate"]
        raw_password = customer_data["password"]

        birthdate = self._parse_birthdate(birthdate_str)
        age = self._age_in_years(birthdate)

        if age < MINIMUM_AGE:
            raise UnderageCustomer(age, MINIMUM_AGE)

        if not is_valid_cpf(document_number):
            raise InvalidDocumentNumber(document_number)

        if self.customer_repository.get_by_document_number(document_number) is not None:
            raise DuplicatedDocumentNumber(document_number)

        if self.customer_repository.get_by_email(email) is not None:
            raise DuplicatedEmail(email)

        # Hash da senha usando bcrypt (Seguro para Bancos, gera salt automaticamente)
        password_hash = bcrypt.hash(raw_password)

        customer = self.customer_repository.create(
            customer_data=customer_data,
            password_hash=password_hash
        )

        customer_dto = CustomerDTO.obj_to_dict(customer)
        self.session.commit()

        return customer_dto
