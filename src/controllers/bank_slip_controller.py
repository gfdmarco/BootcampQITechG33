from datetime import date, timedelta

import requests

from connectors import BankSlipConnector
from controllers.base_controller import BaseController
from dtos import BankSlipDTO
from errors import (
    BankSlipNotPayable,
    BankSlipProviderUnavailable,
    ForbiddenAction,
    InvalidExpirationDate,
    NotFoundAccount,
    NotFoundBankSlip,
)
from models import AccountStatus, BankSlipStatus, TransactionStatus
from repositories import AccountRepository, BankSlipRepository, TransactionRepository

DEFAULT_EXPIRATION_DAYS = 3
MAX_EXPIRATION_DAYS = 60


class BankSlipController(BaseController):

    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)
        self.bank_slip_repository = BankSlipRepository(self.context)

    def issue(self, account_key: str, token_customer_key: str, bank_slip_data: dict) -> dict:
        account = self._get_owned_active_account(account_key, token_customer_key)
        expiration_date = self._parse_expiration(bank_slip_data.get("expiration_date"))

        bank_slip_data["expiration_date"] = expiration_date
        bank_slip = self.bank_slip_repository.create(account.id, bank_slip_data)
        self.session.commit()

        try:
            response = BankSlipConnector().create_bank_slip(
                amount=bank_slip_data["amount"],
                expiration_date=expiration_date.isoformat(),
                payer_name=account.customer.name,
                payer_document_number=account.customer.document_number,
            )
        except requests.RequestException as error:   # timeout, conexão recusada, DNS
            self._fail(bank_slip, f"Provider unreachable: {type(error).__name__}")

        if response.status != 201 or not response.json:
            self._fail(bank_slip, f"Provider answered {response.status}")

        bank_slip.external_key = response.json["bank_slip_key"]
        bank_slip.barcode = response.json["barcode"]
        self.bank_slip_repository.update_status(bank_slip, BankSlipStatus.ISSUED, reason="Registered at provider")

        self.session.flush()
        bank_slip_dto = BankSlipDTO.obj_to_dict(bank_slip)
        self.session.commit()
        return bank_slip_dto

    def _fail(self, bank_slip, reason: str) -> None:
        self.logger.warning(f"Bank slip {bank_slip.bank_slip_key} failed: {reason}")
        self.bank_slip_repository.update_status(bank_slip, BankSlipStatus.FAILED, reason=reason[:255])
        self.session.commit()
        raise BankSlipProviderUnavailable()

    def pay(self, bank_slip_key: str) -> dict:
        # FOR UPDATE: avisos simultâneos viram uma fila
        bank_slip = self.bank_slip_repository.get_by_key_for_update(bank_slip_key)
        if bank_slip is None:
            raise NotFoundBankSlip(bank_slip_key)

        # só boleto emitido pode ser pago (cobre pago, falho e pendente)
        if bank_slip.status.enumerator != BankSlipStatus.ISSUED:
            raise BankSlipNotPayable(bank_slip_key, bank_slip.status.enumerator)

        account = bank_slip.account
        if account.status.enumerator != AccountStatus.ACTIVE:
            raise BankSlipNotPayable(bank_slip_key, f"account {account.status.enumerator}")

        self.account_repository.credit(account.id, bank_slip.amount)
        transaction = self.transaction_repository.create_transaction({
            "origin_account": None,
            "destination_account": account,
            "amount": bank_slip.amount,
            "fee_amount": 0,
            "type": "deposit",
            "channel": "bank_slip",
        })
        self.transaction_repository.update_status(transaction, TransactionStatus.CONFIRMED, reason="Bank slip paid")

        bank_slip.transaction = transaction
        self.bank_slip_repository.update_status(bank_slip, BankSlipStatus.PAID, reason="Payment confirmed by provider")

        self.session.flush()
        dto = BankSlipDTO.obj_to_dict(bank_slip)
        self.session.commit()
        return dto

    def get_by_key(self, bank_slip_key: str, token_customer_key: str) -> dict:
        bank_slip = self.bank_slip_repository.get_by_key(bank_slip_key)
        if bank_slip is None:
            raise NotFoundBankSlip(bank_slip_key)
        if bank_slip.account.customer.customer_key != token_customer_key:
            raise ForbiddenAction()
        return BankSlipDTO.obj_to_dict(bank_slip)

    def list_by_account(self, account_key: str, token_customer_key: str, limit: int, offset: int) -> dict:
        account = self._get_owned_account(account_key, token_customer_key)

        bank_slips = self.bank_slip_repository.list_by_account(account.id, limit, offset)

        is_last_page = len(bank_slips) <= limit      # não veio o item extra → acabou
        bank_slips = bank_slips[:limit]              # descarta o extra antes de responder

        return {
            "data": BankSlipDTO.list_obj_to_list_dict(bank_slips),
            "is_last_page": is_last_page,
        }

    def _get_owned_account(self, account_key: str, token_customer_key: str):
        account = self.account_repository.get_by_key(account_key)
        if account is None:
            raise NotFoundAccount(account_key)
        if account.customer.customer_key != token_customer_key:
            raise ForbiddenAction()
        return account

    def _get_owned_active_account(self, account_key: str, token_customer_key: str):
        account = self._get_owned_account(account_key, token_customer_key)
        if account.status.enumerator != AccountStatus.ACTIVE:
            raise ForbiddenAction()
        return account

    def _parse_expiration(self, raw: str) -> date:
        today = date.today()
        if raw is None:
            return today + timedelta(days=DEFAULT_EXPIRATION_DAYS)
        try:
            expiration = date.fromisoformat(raw)
        except ValueError:                     # ex.: 2026-02-30
            raise InvalidExpirationDate()
        if not (today <= expiration <= today + timedelta(days=MAX_EXPIRATION_DAYS)):
            raise InvalidExpirationDate()
        return expiration