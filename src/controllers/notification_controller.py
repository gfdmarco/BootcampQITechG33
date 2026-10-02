from controllers.base_controller import BaseController
from errors import ForbiddenAction
from errors.base_error import NotFoundResource
from models import Notification
from repositories import CustomerRepository, NotificationRepository


def _brl(amount_cents: int) -> str:
    return f"R$ {amount_cents / 100:.2f}".replace(".", ",")


class NotificationController(BaseController):
    """Regras de notificacao. Ponto unico de escrita: publish_event."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.notification_repository = NotificationRepository(self.context)
        self.customer_repository = CustomerRepository(self.context)

    def publish_event(self, customer_key: str, title: str, body: str) -> Notification:
        """Unico lugar que escreve notificacao.

        Hoje escreve direto no banco. Amanha, para extrair o modulo,
        troca-se esta funcao por um push no Redis — os chamadores nao mudam.
        """
        notification = self.notification_repository.create(customer_key, title, body)
        self.session.flush()
        return notification

    def notify_transfer(self, sender_key: str, receiver_key: str, amount: int, channel: str) -> None:
        self.publish_event(
            sender_key,
            "Transferência enviada",
            f"Você enviou {_brl(amount)} via {channel.upper()}.",
        )
        self.publish_event(
            receiver_key,
            "Transferência recebida",
            f"Você recebeu {_brl(amount)} via {channel.upper()}.",
        )

    def notify_deposit(self, receiver_key: str, amount: int, channel: str) -> None:
        self.publish_event(
            receiver_key,
            "Depósito recebido",
            f"Você recebeu {_brl(amount)} via {channel.upper()}.",
        )

    def notify_account_status(self, customer_key: str, new_status: str) -> None:
        titles = {"blocked": "Conta bloqueada", "active": "Conta desbloqueada"}
        title = titles.get(new_status)
        if title is None:
            return
        self.publish_event(customer_key, title, f"Sua conta foi atualizada: {title.lower()}.")

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
