-- ============================================
-- Webhook Gateway — Schema
-- ============================================

CREATE TABLE webhook_subscription (
    id                   SERIAL PRIMARY KEY,
    key                  CHAR(36) NOT NULL,
    owner_corporate_key  CHAR(36) NOT NULL,
    target_url           VARCHAR(500) NOT NULL,
    secret_hash          VARCHAR(255) NOT NULL,
    event_types          TEXT[] NOT NULL,
    status               VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at           TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(key)
);

CREATE TABLE webhook_delivery (
    id              SERIAL PRIMARY KEY,
    subscription_id INTEGER NOT NULL REFERENCES webhook_subscription(id),
    event_id        CHAR(36) NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    payload         JSONB NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_status_code INTEGER,
    next_retry_at   TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(event_id, subscription_id)
);