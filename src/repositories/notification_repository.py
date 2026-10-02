from uuid import uuid4

from database import Context
from models import Notification


class NotificationRepository:
    """Só query aqui, sem regra de negócio."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, customer_key: str, title: str, body: str) -> Notification:
        notification = Notification()
        notification.key = str(uuid4())
        notification.customer_key = customer_key
        notification.title = title
        notification.body = body
        notification.is_read = False
        self.session.add(notification)
        return notification

    def list_by_customer(self, customer_key: str) -> list:
        return (
            self.session.query(Notification)
            .filter(Notification.customer_key == customer_key)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .all()
        )

    def get_by_key(self, key: str) -> Notification | None:
        return self.session.query(Notification).filter(Notification.key == key).first()

    def mark_read(self, notification: Notification) -> None:
        notification.is_read = True
