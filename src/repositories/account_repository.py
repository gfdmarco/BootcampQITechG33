from uuid import uuid4

from database import Context
from models import Account, AccountStatus, AccountStatusEvent

class AccountRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

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
     
    def list_page(self, limit: int, offset: int, filters: dict) -> list:
        """A pagina, estreitada por quantos filtros vierem preenchidos.

        Todo filtro segue a mesma forma: veio vazio, nao entra na query;
        veio preenchido, vira mais um `.filter()`. Como cada um deles
        acrescenta uma condicao a MESMA query, eles se somam com E — dois
        filtros sempre devolvem menos linhas que um, nunca mais.

        Repare que `ilike` e diferente de `==`: o nome casa por pedaco e
        sem ligar pra maiuscula, enquanto e-mail e CPF exigem o valor
        inteiro e exato. Essa diferenca e decisao de produto, nao detalhe
        tecnico — quem procura uma pessoa lembra meio nome, mas quem
        procura um CPF tem o CPF.

        A ordenacao no fim nao e enfeite: `limit` e `offset` recortam
        um conjunto, e um conjunto sem ordem pode voltar do banco em
        qualquer sequencia. Sem o `order_by`, a pagina 2 tem permissao
        de repetir uma linha da pagina 1 e sumir com outra. O desempate
        por `id` existe porque duas entidades podem nascer no mesmo
        instante — e ai `created_at` sozinho ainda deixaria a ordem em
        aberto.
        """
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
    
        query = query.order_by(Account.created_at.desc(), Account.id.desc())

        return query.limit(limit + 1).offset(offset).all()