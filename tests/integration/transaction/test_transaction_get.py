from tests.utils.api_helpers import (
    deposit, get_transaction, new_customer, open_account, random_key, transfer,
)


class TestGetTransaction:
    def _alice_pays_bob(self):
        alice_key, alice_token, _ = new_customer()
        alice_account = open_account(alice_key, alice_token)
        deposit(alice_account, 1000, alice_token)

        bob_key, bob_token, _ = new_customer()
        bob_account = open_account(bob_key, bob_token)

        status, response = transfer(alice_account, bob_account, 300, alice_token, channel="ted")
        assert status == 201
        return response["transaction_key"], alice_account, alice_token, bob_account, bob_token

    def test_sender_sees_the_transaction(self):
        key, alice_account, alice_token, bob_account, _ = self._alice_pays_bob()

        status, transaction = get_transaction(key, alice_token)

        assert status == 200
        assert transaction["transaction_key"] == key
        assert transaction["origin_account_key"] == alice_account
        assert transaction["destination_account_key"] == bob_account
        assert transaction["amount"] == 300
        assert transaction["fee_amount"] == 15
        assert transaction["type"] == "transfer"
        assert transaction["channel"] == "ted"
        assert transaction["status"] == "confirmed"

    def test_detail_carries_the_status_trail(self):
        """O detalhe traz a trilha pending -> confirmed."""
        key, _, alice_token, _, _ = self._alice_pays_bob()

        status, transaction = get_transaction(key, alice_token)

        assert status == 200
        trail = [(e["from_status"], e["to_status"]) for e in transaction["status_events"]]
        assert trail == [("pending", "confirmed")]

    def test_receiver_sees_the_transaction(self):
        key, _, _, _, bob_token = self._alice_pays_bob()

        status, transaction = get_transaction(key, bob_token)

        assert status == 200
        assert transaction["transaction_key"] == key

    def test_third_party_cannot_see_the_transaction(self):
        key, _, _, _, _ = self._alice_pays_bob()
        _, carol_token, _ = new_customer()

        status, response = get_transaction(key, carol_token)

        assert status == 403
        assert response["code"] == "QIT002003"
        assert "amount" not in response

    def test_unknown_transaction(self):
        _, token, _ = new_customer()

        status, response = get_transaction(random_key(), token)

        assert status == 404
        assert response["code"] == "QIT001020"

    def test_requires_login(self):
        key, _, _, _, _ = self._alice_pays_bob()

        status, response = get_transaction(key, None)

        assert status == 401