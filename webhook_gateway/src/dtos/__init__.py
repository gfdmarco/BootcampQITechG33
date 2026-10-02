from models import WebhookSubscription, WebhookDelivery


class SubscriptionDTO:
    @staticmethod
    def to_dict(subscription: WebhookSubscription) -> dict:
        return {
            "key": subscription.key,
            "owner_corporate_key": subscription.owner_corporate_key,
            "target_url": subscription.target_url,
            "event_types": subscription.event_types,
            "status": subscription.status,
            "created_at": subscription.created_at.isoformat() if subscription.created_at else None,
        }


class DeliveryDTO:
    @staticmethod
    def to_dict(delivery: WebhookDelivery) -> dict:
        return {
            "id": delivery.id,
            "event_id": delivery.event_id,
            "event_type": delivery.event_type,
            "status": delivery.status,
            "attempts": delivery.attempts,
            "last_status_code": delivery.last_status_code,
            "next_retry_at": delivery.next_retry_at.isoformat() if delivery.next_retry_at else None,
            "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
        }