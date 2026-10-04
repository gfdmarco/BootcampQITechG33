-- Tabela de enumeradores de score de risco
CREATE TABLE risk_score_status (
    id          SERIAL PRIMARY KEY,
    enumerator  VARCHAR(20) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(enumerator)
);
INSERT INTO risk_score_status (enumerator) VALUES ('low'), ('medium'), ('high'), ('unknown');

-- Perfil de risco por cliente (atualizado pelo LLM Worker)
CREATE TABLE risk_profile (
    id                  SERIAL PRIMARY KEY,
    customer_key        CHAR(36) NOT NULL,
    risk_score_id       INTEGER NOT NULL REFERENCES risk_score_status(id),
    reason              TEXT,
    last_evaluated_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(customer_key)
);

-- Histórico de avaliações (imutável, para auditoria)
CREATE TABLE risk_evaluation_event (
    id                  SERIAL PRIMARY KEY,
    customer_key        CHAR(36) NOT NULL,
    from_score_id       INTEGER REFERENCES risk_score_status(id),
    to_score_id         INTEGER NOT NULL REFERENCES risk_score_status(id),
    reason              TEXT,
    evaluated_by        VARCHAR(50) NOT NULL DEFAULT 'system',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Requisicoes de avaliacao em tempo real.
-- A evaluation_key torna POST /evaluate idempotente: se o Core repetir a
-- mesma tentativa por timeout, o Risk devolve a mesma decisao sem consumir
-- limite diario de novo.
CREATE TABLE risk_evaluation_request (
    id                  SERIAL PRIMARY KEY,
    evaluation_key      CHAR(36) NOT NULL,
    customer_key        CHAR(36) NOT NULL,
    transaction_type    VARCHAR(30) NOT NULL,
    amount              BIGINT NOT NULL,
    score               VARCHAR(20) NOT NULL,
    decision            VARCHAR(20) NOT NULL,
    reason              TEXT,
    status              VARCHAR(20) NOT NULL DEFAULT 'completed',
    transaction_key     CHAR(36),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(evaluation_key)
);

-- Consumo persistente de limite.
-- Redis pode acelerar leitura, mas esta tabela e a trilha reconstruivel.
CREATE TABLE risk_limit_consumption (
    id                  SERIAL PRIMARY KEY,
    consumption_key     CHAR(36) NOT NULL,
    evaluation_key      CHAR(36) NOT NULL REFERENCES risk_evaluation_request(evaluation_key),
    customer_key        CHAR(36) NOT NULL,
    transaction_key     CHAR(36),
    transaction_type    VARCHAR(30) NOT NULL,
    amount              BIGINT NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'reserved',
    requested_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    confirmed_at        TIMESTAMP,
    canceled_at         TIMESTAMP,
    expired_at          TIMESTAMP,
    UNIQUE(consumption_key),
    UNIQUE(evaluation_key)
);

-- Políticas de limite por score de risco
CREATE TABLE risk_limit_policy (
    id                      SERIAL PRIMARY KEY,
    risk_score_id           INTEGER NOT NULL REFERENCES risk_score_status(id),
    transaction_type        VARCHAR(30) NOT NULL,
    max_amount_per_tx       BIGINT NOT NULL,
    max_amount_daily        BIGINT NOT NULL,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(risk_score_id, transaction_type)
);
-- Defaults: LOW = sem restrição, MEDIUM = R$10k, HIGH = R$1k por transação
INSERT INTO risk_limit_policy (risk_score_id, transaction_type, max_amount_per_tx, max_amount_daily) VALUES
    (1, 'pix',             999999999, 999999999),
    (1, 'ted',             999999999, 999999999),
    (1, 'card',            999999999, 999999999),
    (1, 'international',   999999999, 999999999),
    (2, 'pix',             1000000,   2000000),
    (2, 'ted',             1000000,   2000000),
    (2, 'card',            1000000,   2000000),
    (2, 'international',   500000,    1000000),
    (3, 'pix',             100000,    200000),
    (3, 'ted',             100000,    200000),
    (3, 'card',            100000,    200000),
    (3, 'international',   0,         0),
    (4, 'pix',             1000000,   2000000),
    (4, 'ted',             1000000,   2000000),
    (4, 'card',            1000000,   2000000),
    (4, 'international',   500000,    1000000);
