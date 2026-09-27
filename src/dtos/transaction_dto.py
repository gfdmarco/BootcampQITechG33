from typing import List

from models import Transaction


class TransactionDTO:
    """Traduz o objeto do banco no JSON que a API devolve.

    O repository entrega uma `Transaction` — cheia de relationships e
    de um `status_id` que não significa nada fora do banco. Nada disso
    sai para o cliente: aqui a transação vira um dicionário simples, e
    é esse dicionário que o FastAPI transforma no JSON da resposta.

    Compare com `src/models/transaction.py`, que descreve a TABELA: lá
    a origem é um `origin_account_id` que pode ser nulo, e o status é
    um número apontando pra outra tabela. Aqui os dois viram campos
    planos, com nome de gente — e nenhum termina em `_id`. Onde o model
    aponta pra outra tabela por chave estrangeira, o DTO devolve a
    `_key` pública dessa tabela (ou `None`, se a relação for opcional,
    como a origem de um depósito) — nunca o número interno.

    Campo novo na resposta se acrescenta aqui — e só aqui.
    """

    @staticmethod
    def obj_to_dict(transaction: Transaction) -> dict:
        """A transação INTEIRA, com a história de como ela chegou aqui.

        É o dossiê: quem abre UMA transação quer saber por onde ela
        passou — pending, depois confirmed, ou confirmed, depois
        failed. Cada mudança de status deixou uma linha em
        transaction_status_event, e é aqui que essas linhas viram
        resposta.
        """
        transaction_dto = TransactionDTO.obj_to_simplified_dict(transaction)
        transaction_dto["status_events"] = []

        for status_event in transaction.status_events:
            status_event_dto = dict()
            status_event_dto["from_status"] = (
                status_event.from_status.enumerator
                if status_event.from_status is not None
                else None
            )
            status_event_dto["to_status"] = status_event.to_status.enumerator
            status_event_dto["reason"] = status_event.reason
            status_event_dto["created_at"] = status_event.created_at.isoformat()

            transaction_dto["status_events"].append(status_event_dto)

        return transaction_dto

    @staticmethod
    def obj_to_simplified_dict(transaction: Transaction) -> dict:
        """A transação sem a trilha de status — o resumo.

        Existe pelo mesmo motivo do resumo em `SampleEntityDTO`: a
        trilha mora em OUTRA tabela, e montá-la item a item custa uma
        consulta por transação da página. Quem lista o extrato está
        varrendo; quem abre uma transação está investigando. São dois
        pedidos diferentes, e por isso são dois formatos.
        """
        dto = dict()
        dto["transaction_key"] = transaction.transaction_key

        # Depósito não tem origem — o relationship vem None, e o DTO
        # repete esse None em vez de inventar uma chave que não existe.
        dto["origin_account_key"] = (
            transaction.origin_account.account_key
            if transaction.origin_account is not None
            else None
        )
        dto["destination_account_key"] = transaction.destination_account.account_key

        dto["amount"] = transaction.amount
        dto["fee_amount"] = transaction.fee_amount
        dto["type"] = transaction.type
        dto["channel"] = transaction.channel
        dto["status"] = transaction.status.enumerator
        dto["created_at"] = transaction.created_at.isoformat()

        return dto

    @staticmethod
    def list_obj_to_list_dict(transactions_list: List[Transaction]) -> List[dict]:
        transactions_dict_list = []

        for transaction in transactions_list:
            transactions_dict_list.append(
                TransactionDTO.obj_to_simplified_dict(transaction)
            )

        return transactions_dict_list

    @staticmethod
    def only_obj_key(transaction: Transaction) -> dict:
        dto = dict()
        dto["transaction_key"] = transaction.transaction_key

        return dto