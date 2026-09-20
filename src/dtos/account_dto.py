from typing import List
from models import Account


class AccountDTO:
    @staticmethod
    def obj_to_dict(account: Account) -> dict:
        """Conta completa, com histórico de status."""
        account_dto = AccountDTO.obj_to_simplified_dict(account)
        account_dto["status_events"] = []

        for status_event in account.status_events:
            status_event_dto = dict()
            status_event_dto["status"] = status_event.to_status.enumerator
            status_event_dto["event_datetime"] = status_event.created_at.isoformat()
            if status_event.reason:
                status_event_dto["reason"] = status_event.reason

            account_dto["status_events"].append(status_event_dto)

        return account_dto

    @staticmethod
    def obj_to_simplified_dict(account: Account) -> dict:
        """Conta resumida, sem histórico de status."""
        dto = dict()
        dto["account_key"] = account.account_key
        dto["customer_key"] = account.customer.customer_key
        dto["branch"] = account.branch
        dto["number"] = account.number
        dto["type"] = account.type
        dto["balance"] = account.balance
        dto["status"] = account.status.enumerator
        return dto

    @staticmethod
    def list_obj_to_list_dict(accounts_list: List[Account]) -> List[dict]:
        """Lista de contas resumidas."""
        accounts_dict_list = []

        for account in accounts_list:
            accounts_dict_list.append(AccountDTO.obj_to_simplified_dict(account))

        return accounts_dict_list

    @staticmethod
    def only_obj_key(account: Account) -> dict:
        """Apenas a chave da conta — usado em respostas 204/202."""
        return {"account_key": account.account_key}
