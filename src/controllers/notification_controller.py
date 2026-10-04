from controllers.base_controller import BaseController
from errors import ForbiddenAction
from errors.base_error import NotFoundResource
from models import Notification
from repositories import CustomerRepository, NotificationRepository
from uuid import uuid4


def _brl(amount_cents: int) -> str:
    return f"R$ {amount_cents / 100:.2f}".replace(".", ",")


class NotificationController(BaseController):
    """Regras de notificacao. Ponto unico de escrita: publish_event."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.notification_repository = NotificationRepository(self.context)
        self.customer_repository = CustomerRepository(self.context)

    def publish_event(self, customer_key: str, title: str, body: str, event_key: str = None) -> Notification:
        """Unico lugar que escreve notificacao.

        A escrita e idempotente por `event_key`. Hoje cria a notificacao
        direto no banco; amanha, o mesmo identificador vira a chave natural
        de outbox/fila sem duplicar mensagem em retry.
        """
        event_key = event_key or f"manual:{uuid4()}"
        existing = self.notification_repository.get_by_event_key(event_key)
        if existing is not None:
            return existing

        notification = self.notification_repository.create(customer_key, title, body, event_key)
        self.session.flush()
        return notification

    def enqueue_event(self, customer_key: str, title: str, body: str, event_key: str = None) -> str:
        event_key = event_key or f"manual:{uuid4()}"
        existing = self.notification_repository.get_outbox_by_event_key(event_key)
        if existing is None:
            self.notification_repository.create_outbox_event(customer_key, title, body, event_key)
            self.session.flush()
        return event_key

    def process_event_key(self, event_key: str) -> Notification | None:
        event = self.notification_repository.get_outbox_by_event_key(event_key)
        if event is None:
            return None
        if event.status == "processed":
            return self.notification_repository.get_by_event_key(event_key)

        try:
            notification = self.publish_event(
                event.customer_key.strip(),
                event.title,
                event.body,
                event_key=event.event_key,
            )
            self.notification_repository.mark_outbox_processed(event)
            self.session.flush()
            return notification
        except Exception as exc:
            self.notification_repository.mark_outbox_failed(event, str(exc))
            self.session.flush()
            raise

    def process_event_keys(self, event_keys: list[str]) -> None:
        for event_key in event_keys:
            self.process_event_key(event_key)

    def reprocess_pending_outbox(self, limit: int = 50) -> dict:
        events = self.notification_repository.list_outbox_for_reprocessing(limit)
        processed_count = 0
        failed_count = 0

        for event in events:
            try:
                self.process_event_key(event.event_key)
                processed_count = processed_count + 1
            except Exception:
                failed_count = failed_count + 1

        self.session.commit()
        return {
            "processed_count": processed_count,
            "failed_count": failed_count,
            "limit": limit,
        }

    def notify_transfer(self, sender_key: str, receiver_key: str, amount: int, channel: str, transaction_key: str = None) -> None:
        self.publish_event(
            sender_key,
            "Transferência enviada",
            f"Você enviou {_brl(amount)} via {channel.upper()}.",
            event_key=f"transaction:{transaction_key}:sender" if transaction_key else None,
        )
        self.publish_event(
            receiver_key,
            "Transferência recebida",
            f"Você recebeu {_brl(amount)} via {channel.upper()}.",
            event_key=f"transaction:{transaction_key}:receiver" if transaction_key else None,
        )

    def notify_deposit(self, receiver_key: str, amount: int, channel: str, transaction_key: str = None) -> None:
        self.publish_event(
            receiver_key,
            "Depósito recebido",
            f"Você recebeu {_brl(amount)} via {channel.upper()}.",
            event_key=f"transaction:{transaction_key}:deposit" if transaction_key else None,
        )

    def enqueue_transfer(self, sender_key: str, receiver_key: str, amount: int, channel: str, transaction_key: str) -> list[str]:
        return [
            self.enqueue_event(
                sender_key,
                "Transferência enviada",
                f"Você enviou {_brl(amount)} via {channel.upper()}.",
                event_key=f"transaction:{transaction_key}:sender",
            ),
            self.enqueue_event(
                receiver_key,
                "Transferência recebida",
                f"Você recebeu {_brl(amount)} via {channel.upper()}.",
                event_key=f"transaction:{transaction_key}:receiver",
            ),
        ]

    def enqueue_deposit(self, receiver_key: str, amount: int, channel: str, transaction_key: str) -> list[str]:
        return [
            self.enqueue_event(
                receiver_key,
                "Depósito recebido",
                f"Você recebeu {_brl(amount)} via {channel.upper()}.",
                event_key=f"transaction:{transaction_key}:deposit",
            )
        ]

    def notify_account_status(self, customer_key: str, new_status: str, account_key: str = None) -> None:
        titles = {"blocked": "Conta bloqueada", "active": "Conta desbloqueada"}
        title = titles.get(new_status)
        if title is None:
            return
        event_key = f"account:{account_key}:{new_status}" if account_key else None
        self.publish_event(customer_key, title, f"Sua conta foi atualizada: {title.lower()}.", event_key=event_key)

    def enqueue_account_status(self, customer_key: str, new_status: str) -> list[str]:
        titles = {"blocked": "Conta bloqueada", "active": "Conta desbloqueada"}
        title = titles.get(new_status)
        if title is None:
            return []
        return [
            self.enqueue_event(
                customer_key,
                title,
                f"Sua conta foi atualizada: {title.lower()}.",
            )
        ]

    def list_for_customer(self, customer_key: str) -> dict:
        rows = self.notification_repository.list_by_customer(customer_key)
        return {
            "notifications": [
                {
                    "key": r.key.strip(),
                    "title": r.title,
                    "body": r.body,
                    "is_read": r.is_read,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
            "total": len(rows),
            "unread_count": sum(1 for r in rows if not r.is_read),
        }

    def mark_read(self, key: str, customer_key: str) -> dict:
        notification = self.notification_repository.get_by_key(key)
        if notification is None:
            raise NotFoundResource()
        if notification.customer_key.strip() != customer_key:
            raise ForbiddenAction()
        self.notification_repository.mark_read(notification)
        self.session.flush()
        self.session.commit()
        return {"key": notification.key.strip(), "is_read": True}
