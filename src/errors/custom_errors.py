from errors import QIException


# ──────────────────────────────────────────────────────────────────────────────
# QIT001xxx — Domínio de Negócio (Cadastro, Regras de Cliente e Conta)
# ──────────────────────────────────────────────────────────────────────────────

class NotFoundSampleEntity(QIException):
    code = "QIT001001"

    def __init__(self, sample_entity_key) -> None:
        title = "Entity not Found"
        http_status = 404
        description = f"Entity with key {sample_entity_key} was not found."
        translation = f"A entidade com chave {sample_entity_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class SampleEntityFinalStatus(QIException):
    code = "QIT001002"

    def __init__(self, old_status, new_status) -> None:
        title = "Entity cannot change status"
        http_status = 409
        description = f"Entity with status {old_status} cannot update to {new_status}."
        translation = "Essa entidade não pode ser atualizada."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidDocumentNumber(QIException):
    """O CPF tem o formato certo e não existe.

    422, e não 400, de propósito: 400 quer dizer "não consegui ler o seu
    pedido". Aqui a API leu, entendeu, e o valor é que não pode existir —
    os dois últimos dígitos não batem com a conta. A diferença está
    explicada em src/utils/document_number.py.
    """

    code = "QIT001003"

    def __init__(self, document_number) -> None:
        title = "Invalid Document Number"
        http_status = 422
        description = f"The document number {document_number} is not a valid CPF."
        translation = "O CPF informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedDocumentNumber(QIException):
    """Já existe um cadastro com este CPF.

    409 Conflict: o pedido está correto em si, e o que impede é o que já
    está no banco. É a mesma família do SampleEntityFinalStatus aqui em
    cima — conflito com o que já existe, não erro de quem pediu.
    """

    code = "QIT001004"

    def __init__(self, document_number) -> None:
        title = "Document Number already registered"
        http_status = 409
        description = f"There is already an entity with the document number {document_number}."
        translation = "Já existe um cadastro com este CPF."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedEmail(QIException):
    code = "QIT001005"

    def __init__(self, email) -> None:
        title = "Email already registered"
        http_status = 409
        description = f"There is already an entity with the email {email}."
        translation = "Já existe um cadastro com este e-mail."
        super().__init__(title, self.code, http_status, description, translation)


class UnderageSampleEntity(QIException):
    code = "QIT001006"

    def __init__(self, age, minimum_age) -> None:
        title = "Entity is underage"
        http_status = 422
        description = f"The entity is {age} years old, and the minimum is {minimum_age}."
        translation = f"É preciso ter pelo menos {minimum_age} anos."
        super().__init__(title, self.code, http_status, description, translation)


class UnderageCustomer(QIException):
    code = "QIT001007"

    def __init__(self, age, minimum_age) -> None:
        title = "Customer is underage"
        http_status = 422
        description = f"The customer is {age} years old, and the minimum is {minimum_age}."
        translation = f"Para abrir uma conta é preciso ter pelo menos {minimum_age} anos."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidDate(QIException):
    code = "QIT001008"

    def __init__(self, date) -> None:
        title = "Invalid Date"
        http_status = 422
        description = f"The Date {date} is not a real date."
        translation = "A data de nascimento informada não existe."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidBirthdate(QIException):
    """A data tem o formato certo e não existe no calendário.

    Existe porque o `pattern` do schema sabe contar dígitos, não dias:
    "2025-02-30" e "9999-99-99" passam pelo regex e morrem no
    `date.fromisoformat`. Sem esta classe, esse ValueError virava 500 —
    a API culpando a si mesma por um erro de quem chamou.
    """

    code = "QIT001009"

    def __init__(self, birthdate) -> None:
        title = "Invalid Birthdate"
        http_status = 422
        description = f"The birthdate {birthdate} is not a real birthdate."
        translation = "A data de nascimento informada não existe."
        super().__init__(title, self.code, http_status, description, translation)

class DuplicatedAccount(QIException):

    code = "QIT001010"

    def __init__(self, branch, number) -> None:
        title = "Duplicated Account"
        http_status = 422
        description = f"The branch {branch} and the number {number} already respond to an existing account."
        translation = "A agência e conta informadas já correspondem a uma conta existente"
        super().__init__(title, self.code, http_status, description, translation)

class NotFoundAccount(QIException):
    code = "QIT001011"

    def __init__(self, account_key) -> None:
        title = "Entity not Found"
        http_status = 404
        description = f"Entity with key {account_key} was not found."
        translation = f"A entidade com chave {account_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class UnderageCustomer(QIException):
    code = "QIT001012"

    def __init__(self, age, minimum_age) -> None:
        title = "Customer is underage"
        http_status = 422
        description = f"The customer is {age} years old, and the minimum is {minimum_age}."
        translation = f"Para abrir uma conta é preciso ter pelo menos {minimum_age} anos."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundCustomer(QIException):
    code = "QIT001013"

    def __init__(self, customer_key) -> None:
        title = "Customer not Found"
        http_status = 404
        description = f"Customer with key {customer_key} was not found."
        translation = f"O cliente com chave {customer_key} não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class CustomerAccountLimitReached(QIException):
    code = "QIT001014"

    def __init__(self) -> None:
        title = "Account Limit Reached"
        http_status = 422
        description = "The customer has reached the maximum number of active accounts (3)."
        translation = "O cliente atingiu o limite máximo de contas ativas permitidas (3)."
        super().__init__(title, self.code, http_status, description, translation)


class InsufficientBalance(QIException):
    """O cliente tentou transferir um valor superior ao saldo disponível na conta.

    Retorna 422 pois o formato está correto, mas a regra de negócio proíbe.
    """

    code = "QIT001015"

    def __init__(self) -> None:
        title = "Insufficient Balance"
        http_status = 422
        description = "The origin account does not have enough balance to complete the transaction."
        translation = "Saldo insuficiente para realizar a transferência."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidTransactionType(QIException):
    """O tipo de transação enviado não é reconhecido pelo sistema."""

    code = "QIT001016"

    def __init__(self, transaction_type) -> None:
        title = "Invalid Transaction Type"
        http_status = 422
        description = f"The transaction type '{transaction_type}' is not supported."
        translation = "O tipo de transação informado não é suportado pelo sistema."
        super().__init__(title, self.code, http_status, description, translation)

class AccountInvalidStatusTransition(QIException):
    code = "QIT001017"

    def __init__(self, old_status, new_status) -> None:
        title = "Invalid Account Status Transition"
        http_status = 409
        description = f"Account with status {old_status} cannot change to {new_status}."
        translation = "Essa conta não pode mudar para esse status."
        super().__init__(title, self.code, http_status, description, translation)


class AccountHasBalance(QIException):
    code = "QIT001018"

    def __init__(self, account_key, balance) -> None:
        title = "Account Has Balance"
        http_status = 409
        description = f"Account {account_key} cannot be closed with balance {balance}."
        translation = "Não é possível encerrar uma conta com saldo diferente de zero."
        super().__init__(title, self.code, http_status, description, translation)


# ──────────────────────────────────────────────────────────────────────────────
# QIT002xxx — Domínio de Segurança (Autenticação e Autorização)
# ──────────────────────────────────────────────────────────────────────────────

class InvalidCredentials(QIException):
    """Credenciais inválidas — CPF não encontrado ou senha errada.

    Propositalmente genérica: nunca dizemos se foi o CPF ou a senha
    que falhou. Dizer qual dos dois erra ajuda quem está tentando
    adivinhar — e num banco isso não é opção.
    """

    code = "QIT002001"

    def __init__(self) -> None:
        title = "Invalid Credentials"
        http_status = 401
        description = "The provided credentials are invalid."
        translation = "CPF ou senha inválidos."
        super().__init__(title, self.code, http_status, description, translation)


class UnauthorizedToken(QIException):
    """Token JWT ausente, expirado ou com assinatura inválida."""

    code = "QIT002002"

    def __init__(self, detail: str = "Invalid or expired token.") -> None:
        title = "Unauthorized"
        http_status = 401
        description = detail
        translation = "Token de acesso inválido ou expirado."
        super().__init__(title, self.code, http_status, description, translation)


class ForbiddenAction(QIException):
    """Cliente tentando agir em nome de outro cliente."""

    code = "QIT002003"

    def __init__(self) -> None:
        title = "Forbidden Action"
        http_status = 403
        description = "You do not have permission to access or modify this resource."
        translation = "Você não tem permissão para acessar ou modificar este recurso."
        super().__init__(title, self.code, http_status, description, translation)
