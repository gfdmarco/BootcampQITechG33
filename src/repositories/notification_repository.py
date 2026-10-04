from uuid import uuid4

from database import Context
from models import Notification, NotificationOutbox
from sqlalchemy import func


class NotificationRepository:
    """Só query aqui, sem regra de negócio."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, customer_key: str, title: str, body: str, event_key: str) -> Notification:
        notification = Notification()
        notification.key = str(uuid4())
        notification.event_key = event_key
        notification.customer_key = customer_key
        notification.title = title
        notification.body = body
        notification.is_read = False
        self.session.add(notification)
        return notification

    def get_by_event_key(self, event_key: str) -> Notification | None:
        return self.session.query(Notification).filter(Notification.event_key == event_key).first()

    def create_outbox_event(self, customer_key: str, title: str, body: str, event_key: str) -> NotificationOutbox:
        event = NotificationOutbox()
        event.event_key = event_key
        event.customer_key = customer_key
        event.title = title
        event.body = body
        event.status = "pending"
        event.attempts = 0
        self.session.add(event)
        return event

    def get_outbox_by_event_key(self, event_key: str) -> NotificationOutbox | None:
        return self.session.query(NotificationOutbox).filter(NotificationOutbox.event_key == event_key).first()

    def mark_outbox_processed(self, event: NotificationOutbox) -> None:
        event.status = "processed"
        event.processed_at = func.now()
        event.last_error = None

    def mark_outbox_failed(self, event: NotificationOutbox, error: str) -> None:
        event.status = "failed"
        event.attempts = event.attempts + 1
        event.last_error = error[:1000]

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
