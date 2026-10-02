from tests.utils.api_helpers import call, deposit, new_customer, open_account, transfer


def _notifications(token):
    return call("GET", "/notifications", token)


class TestNotificationList:
    def test_list_shows_only_own_notifications(self):
        """Alice nao ve as notificacoes de Bob."""
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)
        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)
        deposit(alice_acc, 1000, alice_token)

        status, _ = transfer(alice_acc, bob_acc, 100, alice_token)
        assert status == 201

        status, alice_body = _notifications(alice_token)
        assert status == 200, alice_body
        status, bob_body = _notifications(bob_token)
        assert status == 200, bob_body

        alice_keys = {n["key"] for n in alice_body["notifications"]}
        bob_keys = {n["key"] for n in bob_body["notifications"]}
        assert alice_keys.isdisjoint(bob_keys)

    def test_list_is_ordered_newest_first(self):
        """Notificacoes mais recentes vêm antes."""
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)
        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)
        deposit(alice_acc, 1000, alice_token)

        transfer(alice_acc, bob_acc, 100, alice_token)
        transfer(alice_acc, bob_acc, 200, alice_token)

        status, body = _notifications(bob_token)
        assert status == 200, body
        assert body["total"] == 2
        first, second = body["notifications"]
        assert first["created_at"] >= second["created_at"]
        # Mais recente = transferencia de 200 cents = R$ 2,00
        assert "2,00" in first["body"]
        assert "1,00" in second["body"]

    def test_unread_count_is_correct(self):
        """Campo unread_count reflete quantas nao foram lidas."""
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)
        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)
        deposit(alice_acc, 1000, alice_token)

        transfer(alice_acc, bob_acc, 100, alice_token)

        status, body = _notifications(bob_token)
        assert status == 200, body
        assert body["total"] == 1
        assert body["unread_count"] == 1

    def test_requires_login(self):
        """GET /notifications sem JWT → 401."""
        status, _ = _notifications(None)
        assert status == 401
