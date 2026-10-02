from typing import Optional
from sqlalchemy import select
from models import WebhookDelivery


class DeliveryRepository:
    def __init__(self, context):
        self.session = context.get_or_create_session()

    def create(self, delivery: WebhookDelivery) -> WebhookDelivery:
        self.session.add(delivery)
        self.session.flush()
        return delivery

    def get_by_id(self, delivery_id: int) -> Optional[WebhookDelivery]:
        stmt = select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_event_and_subscription(self, event_id: str, subscription_id: int) -> Optional[WebhookDelivery]:
        stmt = select(WebhookDelivery).where(
            WebhookDelivery.event_id == event_id,
            WebhookDelivery.subscription_id == subscription_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_subscription(self, subscription_id: int) -> list:
        stmt = select(WebhookDelivery).where(
            WebhookDelivery.subscription_id == subscription_id
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_pending(self, limit: int = 100) -> list:
        stmt = select(WebhookDelivery).where(
            WebhookDelivery.status.in_(["pending", "failed"])
        ).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def update_status(self, delivery: WebhookDelivery, status: str,
                      last_status_code: Optional[int] = None) -> WebhookDelivery:
        delivery.status = status
        if last_status_code is not None:
            delivery.last_status_code = last_status_code
        self.session.flush()
        return delivery

    def increment_attempts(self, delivery: WebhookDelivery) -> WebhookDelivery:
        delivery.attempts += 1
        self.session.flush()
        return delivery

    def set_next_retry(self, delivery: WebhookDelivery, next_retry_at) -> WebhookDelivery:
        delivery.next_retry_at = next_retry_at
        self.session.flush()
        return delivery