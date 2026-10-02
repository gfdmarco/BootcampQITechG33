from uuid import uuid4

from tests.utils.api_helpers import call, deposit, new_customer, open_account, transfer


def _notifications(token):
    return call("GET", "/notifications", token)


def _mark_read(key, token):
    return call("PATCH", f"/notifications/{key}/read", token)


def _setup_bob_with_one_notification():
    alice_key, alice_token, _ = new_customer()
    alice_acc = open_account(alice_key, alice_token)
    bob_key, bob_token, _ = new_customer()
    bob_acc = open_account(bob_key, bob_token)
    deposit(alice_acc, 1000, alice_token)

    status, _ = transfer(alice_acc, bob_acc, 100, alice_token)
    assert status == 201

    status, body = _notifications(bob_token)
    assert status == 200, body
    assert body["total"] == 1
    return bob_token, body["notifications"][0]["key"]


class TestNotificationRead:
    def test_mark_as_read(self):
        """PATCH /notifications/{key}/read → is_read vira True."""
        bob_token, key = _setup_bob_with_one_notification()

        status, body = _mark_read(key, bob_token)
        assert status == 200, body
        assert body["is_read"] is True

        status, listed = _notifications(bob_token)
        assert status == 200, listed
        assert listed["unread_count"] == 0
        assert listed["notifications"][0]["is_read"] is True

    def test_mark_as_read_is_idempotent(self):
        """Marcar como lida duas vezes nao quebra."""
        bob_token, key = _setup_bob_with_one_notification()

        assert _mark_read(key, bob_token)[0] == 200
        status, body = _mark_read(key, bob_token)
        assert status == 200, body
        assert body["is_read"] is True

    def test_cannot_read_others_notification(self):
        """Bob nao consegue marcar notificacao de Alice como lida → 403."""
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)
        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)
        deposit(alice_acc, 1000, alice_token)
        transfer(alice_acc, bob_acc, 100, alice_token)

        status, alice_body = _notifications(alice_token)
        assert status == 200, alice_body
        alice_key_notif = alice_body["notifications"][0]["key"]

        status, _ = _mark_read(alice_key_notif, bob_token)
        assert status == 403

    def test_unknown_notification_returns_404(self):
        """Chave inexistente → 404."""
        _, bob_token, _ = new_customer()
        status, _ = _mark_read(str(uuid4()), bob_token)
        assert status == 404
