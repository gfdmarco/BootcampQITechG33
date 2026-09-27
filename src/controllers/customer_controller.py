from datetime import date
from passlib.hash import bcrypt
import secrets

from controllers.base_controller import BaseController
from dtos import CustomerDTO
from errors import (
    InvalidDocumentNumber,
    DuplicatedDocumentNumber,
    DuplicatedEmail,
    InvalidBirthdate,
    UnderageCustomer,
    NotFoundCustomer,
    ForbiddenAction,
    AccountNumberGenerationFailed,
    AccountInvalidStatusTransition,
    CustomerHasBalance
)
from models import CustomerStatus, AccountStatus
from repositories import CustomerRepository
from repositories import AccountRepository
from utils.document_number import is_valid_cpf
from utils.account_number import generate_account_number

MINIMUM_AGE = 18


class CustomerController(BaseController):
    """As regras de negócio do Customer. Aqui mora o 'pode' e o 'não pode'."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.customer_repository = CustomerRepository(self.context)
        self.account_repository = AccountRepository(self.context)

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
        self.customer_repository.update_status(customer, CustomerStatus.SUCCESS)

        self.session.flush()
        customer_dto = CustomerDTO.obj_to_dict(customer)
        self.session.commit()

        return customer_dto

    def open_account(self, customer_key: str, account_data: dict, token_customer_key: str) -> dict:
        """Orquestra a abertura de conta.

        Validações de DOMÍNIO do customer ficam aqui:
        1. O customer_key da URL deve ser o mesmo do token (JWT).
        2. O customer deve existir no banco.

        A criação efetiva da conta é delegada ao AccountController.
        """
        self.logger.debug(f"Abrindo conta para o customer {customer_key}")

        if customer_key != token_customer_key:
            raise ForbiddenAction()

        customer = self.customer_repository.get_by_key(customer_key)
        if customer is None:
            raise NotFoundCustomer(customer_key)

        # Gera branch e number — são dados internos do banco
        account_data["branch"] = "0001"
        for _ in range(5): #tentamos 5 vezes - suficiente pra gerar um único
            account_data["number"] = generate_account_number()
            if self.account_repository.get_by_branch_and_number(account_data["branch"], account_data["number"]) is None:
                break #conseguimos gerar um id único
            else:
                raise AccountNumberGenerationFailed() #quase impossível bater neste erro

        # Delega para o AccountController — ele valida limite e duplicidade
        from controllers.account_controller import AccountController
        account_controller = AccountController()
        return account_controller.open_account(customer.id, account_data)

    def get_by_key(self, customer_key: str, caller_customer_key: str) -> dict:
        if customer_key != caller_customer_key:
            raise ForbiddenAction()
        
        self.logger.debug(f"Buscando o customer de chave {customer_key}")
        
        customer = self.customer_repository.get_by_key(customer_key)

        if customer is None:
            raise NotFoundCustomer(customer_key)

        return CustomerDTO.obj_to_dict(customer)

    def get_list(self, caller_customer_key: str, limit: int, offset: int, filters: dict) -> dict:
        caller_customer = self.customer_repository.get_by_key(caller_customer_key)
        
        if caller_customer is None:
            raise NotFoundCustomer(caller_customer_key)
        
        filters["customer_id"] = caller_customer.id

        self.logger.debug(f"Buscando lista de customers (limit={limit}, offset={offset})")
        
        customers = self.customer_repository.list_page(limit, offset, filters)

        is_last_page = len(customers) <= limit
        if not is_last_page:
            customers.pop()

        return {
            "customers_list_dto": CustomerDTO.list_obj_to_list_dict(customers),
            "is_last_page": is_last_page
        }

    def update(self, customer_key: str, payload: dict, token_customer_key: str) -> dict:
        self.logger.debug(f"Atualizando o customer de chave {customer_key}")

        # Regra de ouro da segurança: o cliente só pode alterar a si mesmo.
        if customer_key != token_customer_key:
            raise ForbiddenAction()

        customer = self.customer_repository.get_by_key(customer_key)
        if customer is None:
            raise NotFoundCustomer(customer_key)

        if "name" in payload:
            customer.name = payload["name"]

        if "email" in payload:
            new_email = payload["email"]
            # Precisamos checar se o novo e-mail não pertence a OUTRO cliente.
            existing = self.customer_repository.get_by_email(new_email)
            if existing and existing.customer_key != customer_key:
                raise DuplicatedEmail(new_email)
            
            customer.email = new_email

        self.session.commit()
        return CustomerDTO.obj_to_dict(customer)

    def delete(self, customer_key: str, token_customer_key: str) -> None:
        self.logger.debug(f"Encerrando (Deleção Lógica) o customer de chave {customer_key}")

        if customer_key != token_customer_key:
            raise ForbiddenAction()

        customer = self.customer_repository.get_by_key(customer_key)
        if customer is None:
            raise NotFoundCustomer(customer_key)

        if customer.status.enumerator == CustomerStatus.FAILED:
            return

        customer_accounts = self.account_repository.list_by_customer(customer.id)

        #primeiro verifico se alguma conta tem saldo
        for account in customer_accounts:
            if account.balance != 0 and account.status.enumerator != AccountStatus.CLOSED:
                raise CustomerHasBalance(customer_key)
            
        #agora podemos mexer de fato nos status
        for account in customer_accounts:
            if account.status.enumerator != AccountStatus.CLOSED:
                self.account_repository.update_status(account, AccountStatus.CLOSED)

        self.customer_repository.update_status(customer, CustomerStatus.FAILED, reason="Customer requested account closure")   

        # Deleção lógica e auditoria
        self.customer_repository.update_status(
            customer, 
            CustomerStatus.FAILED, 
            reason="Customer requested account closure."
        )
        
        # Anonimização LGPD (O CPF é mantido por compliance/Risco de fraude)
        customer.name = "DELETED_USER"
        customer.email = f"deleted_{customer.customer_key}@closed.invalid"
        
        # Invalida a senha para impedir qualquer tentativa futura de login
        customer.password_hash = bcrypt.hash(secrets.token_hex(16))

        self.session.commit()

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
