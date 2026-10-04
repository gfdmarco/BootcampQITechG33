import os

from sqlalchemy import create_engine, text

from tests.utils.api_helpers import call, deposit, new_customer, open_account, transfer


def _notifications(token):
    return call("GET", "/notifications", token)


def _database_url() -> str:
    db_port = os.environ.get("DB_PORT") or _env_file_value("DB_PORT") or "5432"
    return os.environ.get(
        "DATABASE_URL",
        f"postgresql+psycopg2://bootcamp:bootcamp@127.0.0.1:{db_port}/bootcamp",
    ).replace("@localhost:", "@127.0.0.1:")


def _env_file_value(name: str) -> str | None:
    try:
        with open(".env", "r", encoding="utf-8") as env_file:
            for line in env_file:
                if line.startswith(f"{name}="):
                    return line.strip().split("=", 1)[1]
    except FileNotFoundError:
        return None
    return None


def _notification_event_keys(transaction_key: str) -> list[str]:
    engine = create_engine(_database_url())
    connection = engine.connect()
    try:
        return [
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT event_key
                      FROM notification
                     WHERE event_key LIKE :event_key_prefix
                     ORDER BY event_key
                    """
                ),
                {"event_key_prefix": f"transaction:{transaction_key}:%"},
            ).all()
        ]
    finally:
        connection.close()
        engine.dispose()


def _notification_outbox_statuses(transaction_key: str) -> list[str]:
    engine = create_engine(_database_url())
    connection = engine.connect()
    try:
        return [
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT status
                      FROM notification_outbox
                     WHERE event_key LIKE :event_key_prefix
                     ORDER BY event_key
                    """
                ),
                {"event_key_prefix": f"transaction:{transaction_key}:%"},
            ).all()
        ]
    finally:
        connection.close()
        engine.dispose()


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
        # Alice recebe 1 pelo proprio deposito + 1 pelo envio da transferencia
        assert body["total"] == 2
        assert body["unread_count"] == 2

    def test_transfer_notifications_have_unique_event_keys(self):
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)
        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)
        deposit(alice_acc, 1000, alice_token)

        status, transfer_body = transfer(alice_acc, bob_acc, 100, alice_token)
        assert status == 201

        event_keys = _notification_event_keys(transfer_body["transaction_key"])
        assert event_keys == [
            f"transaction:{transfer_body['transaction_key']}:receiver",
            f"transaction:{transfer_body['transaction_key']}:sender",
        ]
        assert _notification_outbox_statuses(transfer_body["transaction_key"]) == ["processed", "processed"]

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
