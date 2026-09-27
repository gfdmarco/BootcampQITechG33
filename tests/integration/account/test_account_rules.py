from tests.utils import RequestGenerator
from tests.utils.api_helpers import call, deposit, new_customer, open_account


class TestAccountStatusTransitions:
    def test_block_and_unblock(self):
        """Tópico 3: active -> blocked -> active."""
        customer_key, token, _ = new_customer()
        account_key = open_account(customer_key, token)

        status, account = RequestGenerator.PUT_account(account_key, {"status": "blocked"}, token)
        assert status == 200
        assert account["status"] == "blocked"

        status, account = RequestGenerator.PUT_account(account_key, {"status": "active"}, token)
        assert status == 200
        assert account["status"] == "active"

    def test_close_empty_account_and_never_reopen(self):
        """Tópico 3: conta zerada encerra (200); encerrada não volta (409 QIT001016)."""
        customer_key, token, _ = new_customer()
        account_key = open_account(customer_key, token)

        status, account = RequestGenerator.PUT_account(account_key, {"status": "closed"}, token)
        assert status == 200
        assert account["status"] == "closed"

        status, response = RequestGenerator.PUT_account(account_key, {"status": "active"}, token)
        assert status == 409
        assert response["code"] == "QIT001016"

        status, account = RequestGenerator.GET_account(account_key, token)
        assert account["status"] == "closed"

    def test_same_status_is_not_a_valid_transition(self):
        """Bloquear uma conta já bloqueada não é uma transição -> 409."""
        customer_key, token, _ = new_customer()
        account_key = open_account(customer_key, token)
        RequestGenerator.PUT_account(account_key, {"status": "blocked"}, token)

        status, response = RequestGenerator.PUT_account(account_key, {"status": "blocked"}, token)
        assert status == 409
        assert response["code"] == "QIT001016"

    def test_refuses_unknown_status(self):
        """Tópico 3: status fora do enum é barrado pelo schema -> 400."""
        customer_key, token, _ = new_customer()
        account_key = open_account(customer_key, token)

        status, response = RequestGenerator.PUT_account(account_key, {"status": "xyz"}, token)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_status_change_on_unknown_account(self):
        customer_key, token, _ = new_customer()

        status, response = RequestGenerator.PUT_account(
            "00000000-0000-4000-8000-000000000000", {"status": "blocked"}, token
        )
        assert status == 404
        assert response["code"] == "QIT001011"


class TestAccountBalance:
    def test_owner_reads_exact_balance(self):
        """Tópico 4: o dono vê o saldo certo."""
        customer_key, token, _ = new_customer()
        account_key = open_account(customer_key, token)
        deposit(account_key, 1234, token)

        status, response = call("GET", f"/accounts/{account_key}/balance", token)
        assert status == 200
        assert response == {"balance": 1234}

    def test_other_customer_cannot_read_balance(self):
        """Tópico 4: outro cliente -> 403, sem vazar o valor."""
        alice_key, alice_token, _ = new_customer()
        alice_account = open_account(alice_key, alice_token)
        deposit(alice_account, 999, alice_token)

        _, bob_token, _ = new_customer()

        status, response = call("GET", f"/accounts/{alice_account}/balance", bob_token)
        assert status == 403
        assert response["code"] == "QIT002003"
        assert "balance" not in response

    def test_balance_requires_login(self):
        customer_key, token, _ = new_customer()
        account_key = open_account(customer_key, token)

        status, response = call("GET", f"/accounts/{account_key}/balance")
        assert status == 401