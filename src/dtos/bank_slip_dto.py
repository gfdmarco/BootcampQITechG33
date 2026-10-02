from typing import List
from models import BankSlip


class BankSlipDTO:
    @staticmethod
    def obj_to_dict(bank_slip: BankSlip) -> dict:
        bank_slip_dto = BankSlipDTO.obj_to_simplified_dict(bank_slip)
        bank_slip_dto["status_events"] = []

        for status_event in bank_slip.status_events:
            status_event_dto = dict()
            status_event_dto["to_status"] = status_event.to_status.enumerator
            status_event_dto["from_status"] = status_event.from_status.enumerator
            status_event_dto["event_datetime"] = status_event.created_at.isoformat()
            if status_event.reason:
                status_event_dto["reason"] = status_event.reason

            bank_slip_dto["status_events"].append(status_event_dto)

        return bank_slip_dto

    @staticmethod
    def obj_to_simplified_dict(bank_slip: BankSlip) -> dict:
        dto = dict()
        dto["bank_slip_key"] = bank_slip.bank_slip_key
        dto["account_key"] = bank_slip.account.account_key
        dto["expiration_date"] = bank_slip.expiration_date
        dto["amount"] = bank_slip.amount
        dto["transaction_key"] = bank_slip.transaction.transaction_key if bank_slip.transaction else None
        dto["status"] = bank_slip.status.enumerator
        dto["created_at"] = bank_slip.created_at
        dto["barcode"] = bank_slip.barcode if bank_slip.barcode else None
        return dto
    
    @staticmethod
    def only_obj_key(bank_slip: BankSlip) -> dict:
        dto = dict()
        dto["bank_slip_key"] = bank_slip.bank_slip_key
        return dto

    @staticmethod
    def list_obj_to_list_dict(bank_slips) -> list:
        return [BankSlipDTO.obj_to_simplified_dict(b) for b in bank_slips]
