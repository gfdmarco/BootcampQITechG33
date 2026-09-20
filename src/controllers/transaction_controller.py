
from datetime import date
from repositories.transaction_repository import TransactionRepository
from repositories.transaction_status_repository import TransactionStatusRepository
from repositories.transaction_status_event_repository import TransactionStatusEventRepository
from repositories.fee_repository import FeeRepository
from repositories.account_repository import AccountRepository 
from errors import(

    InsufficientBalance,
    InvalidTransactionType,
)



class TransactionController:
    """
    Controlador responsável por orquestrar as regras de negócio das transações financeiras.
    """
    def __init__(self, session):
        self.session = session
        self.transaction_repo = TransactionRepository(session)
        self.status_repo = TransactionStatusRepository(session)
        self.event_repo = TransactionStatusEventRepository(session)
        self.fee_repo = FeeRepository(session)
        self.account_repo = AccountRepository(session)

    def process_transaction(self, payload: dict, authenticated_customer_id: int):
        """
        Processa depósitos ou transferências.
        
        Parâmetros:
        - payload: Dicionário validado (deve conter "type", "destination_account_key", "amount", "channel" e, opcionalmente, "origin_account_key").
        - authenticated_customer_id: O ID do cliente dono do token de acesso atual.
        """
        transaction_type = payload.get("type")
        
        # 1. Busca a conta destino (obrigatória para ambos os casos)
        destination_account = self.account_repo.get_by_key(payload["destination_account_key"])
        if not destination_account:
            raise Exception("AccountNotFound")#aqui eu preciso dessa exception de conta não encontrada

        if transaction_type == "deposit":
            # Depósitos não têm conta de origem nem cobrança de tarifa
            origin_account_id = None
            fee_amount = 0
            fee_id = None
            
            # Apenas credita o valor na conta destino
            self.account_repo.credit(destination_account.id, payload["amount"])
            
        elif transaction_type == "transfer":
            # Transferências exigem conta de origem
            origin_key = payload.get("origin_account_key")
            if not origin_key:
                raise Exception("OriginAccountRequired")#mais uma exception para depois
                
            origin_account = self.account_repo.get_by_key(origin_key)
            if not origin_account:
                raise Exception("AccountNotFound")

            # Valida se quem está logado é realmente o dono da conta de origem
            if origin_account.customer_id != authenticated_customer_id:
                raise Exception("ForbiddenAccess")#exception pqra ser lançada

            fee = self.fee_repo.get_by_type(payload["channel"])
            multiplier = float(fee.percentage) / 100.0
            fee_amount = int(payload["amount"] * multiplier)
            fee_id = fee.id
            
            total_debit = payload["amount"] + fee_amount

            # Atualização atômica do saldo da origem
            success = self.account_repo.debit(origin_account.id, total_debit)
            if not success:
                raise InsufficientBalance()

            # Credita o valor limpo no destino
            self.account_repo.credit(destination_account.id, payload["amount"])
            origin_account_id = origin_account.id
            
        else:
            raise InvalidTransactionType()

        # 3. Gravar no Banco de Dados
        status_confirmed = self.status_repo.get_by_enumerator("confirmed")

        transaction_data = {
            "origin_account_id": origin_account_id,
            "destination_account_id": destination_account.id,
            "amount": payload["amount"],
            "fee_amount": fee_amount,
            "fee_id": fee_id,
            "type": transaction_type,
            "channel": payload["channel"],
            "status_id": status_confirmed.id
        }
        transaction = self.transaction_repo.create_transaction(transaction_data)

        # 4. Criar evento de histórico
        self.event_repo.create_event(
            transaction_id=transaction.id,
            from_status_id=None,
            to_status_id=status_confirmed.id,
            reason=f"Operação de {transaction_type} realizada com sucesso"
        )

        # 5. Salva tudo definitivamente (Commit)
        self.session.commit()

        return transaction