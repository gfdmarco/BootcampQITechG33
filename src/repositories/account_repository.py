from uuid import uuid4

from database import Context
from models import Account, AccountStatus, AccountStatusEvent
from sqlalchemy import or_

class AccountRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_status(self, enumerator: str) -> AccountStatus:
        return (
            self.session.query(AccountStatus)
            .filter(AccountStatus.enumerator == enumerator)
            .first()
        )

    def create(self, account_data: dict) -> Account:
        # o customer_id chega por responsabilidade do controller para construir o data corretamente
        account = Account()

        account.account_key = str(uuid4())
        account.customer_id = account_data["customer_id"]
        account.branch = account_data["branch"]
        account.number = account_data["number"]
        account.type = account_data["type"]
        account.balance = 0
        # pela relationship, o status_id é construído pelo SQLAlchemy
        account.status = self.get_status(AccountStatus.CREATED)

        self.session.add(account)
        return account

    def update_status(self, account: Account, new_status_enumerator: str) -> None:
        old_status = account.status
        new_status = self.get_status(new_status_enumerator)
        account.status = new_status

        new_status_event = AccountStatusEvent()
        new_status_event.to_status = new_status
        new_status_event.from_status = old_status

        account.status_events.append(new_status_event)

    def get_by_key(self, account_key: str) -> Account:
        return self.session.query(Account).filter(Account.account_key == account_key).first()

    def get_by_branch_and_number(self, branch: str, number: str) -> Account:
        return self.session.query(Account).filter(Account.branch == branch, Account.number == number).first()

    def get_by_type(self, type: str) -> Account:
        return self.session.query(Account).filter(Account.type == type).all()

    def get_by_balance(self, balance: str) -> Account:
        return self.session.query(Account).filter(Account.balance == balance).all()

    def count_by_customer(self, customer_id: int) -> int:
        return self.session.query(Account).filter(Account.customer_id == customer_id).count()

    def count_active_by_customer(self, customer_id: int) -> int:
        return (
            self.session.query(Account)
            .filter(Account.customer_id == customer_id)
            .join(Account.status)
            .filter(or_(AccountStatus.enumerator == AccountStatus.ACTIVE, AccountStatus.enumerator == AccountStatus.BLOCKED))
            .count()
        )

    def list_page(self, limit: int, offset: int, filters: dict) -> list:
        query = self.session.query(Account)

        status_enumerators = filters.get("status_enumerators")
        if status_enumerators:
            query = query.join(Account.status).filter(AccountStatus.enumerator.in_(status_enumerators))

        branch = filters.get("branch")
        if branch is not None:
            query = query.filter(Account.branch == branch)

        number = filters.get("number")
        if number is not None:
            query = query.filter(Account.number == number)

        account_type = filters.get("account_type")
        if account_type is not None:
            query = query.filter(Account.type == account_type)

        balance = filters.get("balance")
        if balance is not None:
            query = query.filter(Account.balance >= balance)

        customer_id = filters.get("customer_id")
        if customer_id is not None:
            query = query.filter(Account.customer_id == customer_id)
    
        query = query.order_by(Account.created_at.desc(), Account.id.desc())

        return query.limit(limit + 1).offset(offset).all()

    def debit(self, account_id: int, amount: int) -> bool:
        """Desconta só se houver saldo. Devolve False se não havia."""
        updated_rows = (
            self.session.query(Account)
            .filter(Account.id == account_id, Account.balance >= amount)
            .update({Account.balance: Account.balance - amount}, synchronize_session="fetch")
        )
        return updated_rows == 1

    def credit(self, account_id: int, amount: int) -> None:
        (
            self.session.query(Account)
            .filter(Account.id == account_id)
            .update({Account.balance: Account.balance + amount}, synchronize_session="fetch")
        )

    def list_by_customer(self, customer_id: int) -> list[Account]:
        return (
            self.session.query(Account)
            .filter(Account.customer_id == customer_id)
            .order_by(Account.id)
            .all()
        )

    def get_bank_account(self) -> Account:
        """A conta interna do banco (tesouraria). Falta dela é erro de
        instalação, não regra de negócio: estoura em vez de seguir calado."""
        from constants import BANK_ACCOUNT_KEY

        account = self.get_by_key(BANK_ACCOUNT_KEY)
        if account is None:
            raise RuntimeError(
                "Conta interna do banco não encontrada. Rode o bloco "
                "'Conta interna do banco' do database/database.sql "
                "(ou recrie o banco com docker compose down -v)."
            )
        return account