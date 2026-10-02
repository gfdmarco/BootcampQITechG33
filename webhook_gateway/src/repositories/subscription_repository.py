from typing import Optional
from sqlalchemy import select
from models import WebhookSubscription


class SubscriptionRepository:
    def __init__(self, context):
        self.session = context.get_or_create_session()

    def create(self, subscription: WebhookSubscription) -> WebhookSubscription:
        self.session.add(subscription)
        self.session.flush()
        return subscription

    def get_by_key(self, key: str) -> Optional[WebhookSubscription]:
        stmt = select(WebhookSubscription).where(WebhookSubscription.key == key)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_corporate(self, owner_corporate_key: str) -> list:
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.owner_corporate_key == owner_corporate_key
        )
        return list(self.session.execute(stmt).scalars().all())

    def update_status(self, subscription: WebhookSubscription, status: str) -> WebhookSubscription:
        subscription.status = status
        self.session.flush()
        return subscription

    def delete(self, subscription: WebhookSubscription) -> None:
        self.session.delete(subscription)
        self.session.flush()