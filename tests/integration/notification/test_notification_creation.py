from tests.utils.api_helpers import call, deposit, new_customer, open_account, transfer


def _notifications(token):
    return call("GET", "/notifications", token)


class TestNotificationOnTransfer:
    def test_transfer_creates_notification_for_sender(self):
        """Apos transferencia, remetente tem 1 notificacao."""
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)
        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)
        deposit(alice_acc, 1000, alice_token)

        status, _ = transfer(alice_acc, bob_acc, 100, alice_token)
        assert status == 201

        status, body = _notifications(alice_token)
        assert status == 200, body
        assert body["total"] == 1
        assert body["unread_count"] == 1

    def test_transfer_creates_notification_for_receiver(self):
        """Apos transferencia, destinatario tem 1 notificacao."""
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

    def test_deposit_creates_notification_only_for_receiver(self):
        """Deposito gera notif so pra quem recebeu."""
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)
        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)
        deposit(alice_acc, 1000, alice_token)

        status, _ = transfer(alice_acc, bob_acc, 100, alice_token)
        assert status == 201

        _, alice_body = _notifications(alice_token)
        _, bob_body = _notifications(bob_token)
        # Alice transferiu: 1 (envio). Bob recebeu: 1.
        # Deposito inicial da Alice nao conta para Bob.
        assert alice_body["total"] >= 1
        assert bob_body["total"] == 1

    def test_failed_transfer_does_not_create_notification(self):
        """Transferencia 422 (saldo insuficiente) nao gera notificacao."""
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)
        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)
        deposit(alice_acc, 100, alice_token)

        status, _ = transfer(alice_acc, bob_acc, 900, alice_token)
        assert status == 422

        status, bob_body = _notifications(bob_token)
        assert status == 200, bob_body
        assert bob_body["total"] == 0

    def test_risk_denied_transfer_does_not_create_notification(self):
        """Transferencia bloqueada pelo antifraude (403) nao gera notificacao."""
        import os

        import requests

        risk_host = os.environ.get("SERVER_LOCALHOST", "0.0.0.0")
        risk_port = os.environ.get("RISK_API_PORT", "8001")
        risk_token = os.environ.get("RISK_INTERNAL_TOKEN", "risk_default_token")

        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)
        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)
        deposit(alice_acc, 500_000, alice_token)

        resp = requests.patch(
            f"http://{risk_host}:{risk_port}/risk_profile/{alice_key}",
            json={"score": "high", "reason": "notif test"},
            headers={"INTERNAL-TOKEN": risk_token},
            timeout=10,
        )
        assert resp.status_code == 200, resp.text

        status, _ = transfer(alice_acc, bob_acc, 200_000, alice_token)
        assert status == 403

        status, bob_body = _notifications(bob_token)
        assert status == 200, bob_body
        assert bob_body["total"] == 0
