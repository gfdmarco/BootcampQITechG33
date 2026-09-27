from datetime import date, timedelta

from tests.utils import RequestGenerator
from tests.utils.api_helpers import deposit, new_customer, open_account


def _account_with_two_deposits():
    customer_key, token, _ = new_customer()
    account_key = open_account(customer_key, token)
    deposit(account_key, 100, token)
    deposit(account_key, 200, token)
    return account_key, token


class TestStatementDateFilter:
    # Usamos "ontem" e "amanhã" em vez de "hoje": o banco grava a data em UTC
    # e a sua máquina pode estar em outro fuso — perto da meia-noite, "hoje"
    # seria um dia diferente para cada um e o teste ficaria instável.

    def test_range_around_today_brings_the_transactions(self):
        """Tópico 13: um intervalo que contém hoje traz as transações."""
        account_key, token = _account_with_two_deposits()
        params = {
            "date_from": (date.today() - timedelta(days=1)).isoformat(),
            "date_to": (date.today() + timedelta(days=1)).isoformat(),
        }

        status, response = RequestGenerator.GET_account_statement(account_key, params, token)

        assert status == 200
        assert sorted(t["amount"] for t in response["data"]) == [100, 200]

    def test_future_range_is_empty(self):
        """Tópico 13: date_from no futuro -> lista vazia e última página."""
        account_key, token = _account_with_two_deposits()

        status, response = RequestGenerator.GET_account_statement(
            account_key, {"date_from": "2099-01-01"}, token
        )

        assert status == 200
        assert response["data"] == []
        assert response["is_last_page"] is True

    def test_past_range_is_empty(self):
        """Tópico 13: date_to no passado -> lista vazia."""
        account_key, token = _account_with_two_deposits()

        status, response = RequestGenerator.GET_account_statement(
            account_key, {"date_to": "2000-01-01"}, token
        )

        assert status == 200
        assert response["data"] == []

    def test_date_that_does_not_exist(self):
        """Formato certo, dia que não existe -> 422 QIT001008."""
        account_key, token = _account_with_two_deposits()

        status, response = RequestGenerator.GET_account_statement(
            account_key, {"date_from": "2026-02-30"}, token
        )

        assert status == 422
        assert response["code"] == "QIT001008"


class TestStatementLimits:
    def test_limit_zero_is_refused(self):
        """Tópico 14: limit=0 não faz sentido -> 400.

        Falha enquanto o pattern do schema for ^(100|[1-9]?[0-9])$ — ele aceita 0.
        Troquem por ^(100|[1-9][0-9]?)$ em get_accounts.json,
        get_accounts_statement.json e get_transaction.json.
        """
        account_key, token = _account_with_two_deposits()

        status, response = RequestGenerator.GET_account_statement(account_key, {"limit": "0"}, token)

        assert status == 400
        assert response["code"] == "QIT000001"

    def test_limit_above_100_is_refused(self):
        """Tópico 14: teto de 100 por página."""
        account_key, token = _account_with_two_deposits()

        status, response = RequestGenerator.GET_account_statement(account_key, {"limit": "101"}, token)

        assert status == 400
        assert response["code"] == "QIT000001"

    def test_limit_must_be_a_number(self):
        account_key, token = _account_with_two_deposits()

        status, response = RequestGenerator.GET_account_statement(account_key, {"limit": "abc"}, token)

        assert status == 400

    def test_negative_page_is_refused(self):
        account_key, token = _account_with_two_deposits()

        status, response = RequestGenerator.GET_account_statement(account_key, {"page": "-1"}, token)

        assert status == 400

    def test_unknown_query_param_is_refused(self):
        """additionalProperties: false também vale para a query string."""
        account_key, token = _account_with_two_deposits()

        status, response = RequestGenerator.GET_account_statement(account_key, {"start_date": "2026-01-01"}, token)

        assert status == 400
        assert response["code"] == "QIT000001"

    def test_default_limit_is_10(self):
        """Sem limit, a API usa 10."""
        account_key, token = _account_with_two_deposits()

        status, response = RequestGenerator.GET_account_statement(account_key, None, token)

        assert status == 200
        assert response["limit"] == 10
        assert response["page"] == 0