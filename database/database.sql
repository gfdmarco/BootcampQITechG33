CREATE TABLE customer_status (
    id          SERIAL PRIMARY KEY,
    enumerator  VARCHAR(50) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(enumerator)
);
INSERT INTO customer_status (enumerator) VALUES ('created'), ('pending'), ('success'), ('failed');

CREATE TABLE customer (
    id              SERIAL PRIMARY KEY,
    customer_key    CHAR(36) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    document_number CHAR(14) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    birth_date      DATE NOT NULL,
    status_id       INTEGER NOT NULL REFERENCES customer_status(id),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(customer_key), UNIQUE(document_number), UNIQUE(email)
);


CREATE TABLE customer_status_event (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customer(id),
    from_status_id  INTEGER REFERENCES customer_status(id),
    to_status_id    INTEGER NOT NULL REFERENCES customer_status(id),
    reason          VARCHAR(255),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE customer_idempotency_request (
    id               SERIAL PRIMARY KEY,
    idempotency_key  VARCHAR(120) NOT NULL,
    customer_id      INTEGER NOT NULL REFERENCES customer(id),
    request_hash     CHAR(64) NOT NULL,
    response_status  INTEGER NOT NULL,
    response_body    JSONB NOT NULL,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(idempotency_key)
);

CREATE TABLE account_status (
    id          SERIAL PRIMARY KEY,
    enumerator  VARCHAR(50) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(enumerator)
);
INSERT INTO account_status (enumerator) VALUES ('created'), ('active'), ('closed'), ('blocked');

CREATE TABLE account (
    id          SERIAL PRIMARY KEY,
    account_key CHAR(36) NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    branch      VARCHAR(10) NOT NULL,
    number      VARCHAR(20) NOT NULL,
    type        VARCHAR(20) NOT NULL,
    balance     BIGINT NOT NULL DEFAULT 0,
    status_id   INTEGER NOT NULL REFERENCES account_status(id),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(account_key), UNIQUE(branch, number),
    CHECK (balance >= 0)
);

CREATE TABLE account_status_event (
    id              SERIAL PRIMARY KEY,
    account_id      INTEGER NOT NULL REFERENCES account(id),
    from_status_id  INTEGER REFERENCES account_status(id),
    to_status_id    INTEGER NOT NULL REFERENCES account_status(id),
    reason          VARCHAR(255),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE fee (
    id          SERIAL PRIMARY KEY,
    type        VARCHAR(50) NOT NULL,
    percentage  NUMERIC(5,2) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(type)
);
INSERT INTO fee (type, percentage) VALUES ('pix', 0), ('ted', 5), ('card', 5), ('international', 8);

CREATE TABLE transaction_status (
    id          SERIAL PRIMARY KEY,
    enumerator  VARCHAR(50) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(enumerator)
);
INSERT INTO transaction_status (enumerator) VALUES ('pending'), ('confirmed'), ('failed');

CREATE TABLE transaction (
    id                      SERIAL PRIMARY KEY,
    transaction_key         CHAR(36) NOT NULL,
    origin_account_id       INTEGER REFERENCES account(id),        -- NULL for deposit
    destination_account_id  INTEGER NOT NULL REFERENCES account(id),
    amount                  BIGINT NOT NULL,
    fee_amount              BIGINT NOT NULL DEFAULT 0,              -- money charged (cents), not the percentage
    fee_id                  INTEGER REFERENCES fee(id),
    type                    VARCHAR(20) NOT NULL,   -- deposit / transfer
    channel                 VARCHAR(50) NOT NULL,   -- pix / ted / card / international / bank_slip
    status_id               INTEGER NOT NULL REFERENCES transaction_status(id),
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(transaction_key),
    CHECK (type <> 'transfer' OR origin_account_id IS NOT NULL)
);

CREATE TABLE transaction_status_event (
    id              SERIAL PRIMARY KEY,
    transaction_id  INTEGER NOT NULL REFERENCES transaction(id),
    from_status_id  INTEGER REFERENCES transaction_status(id),
    to_status_id    INTEGER NOT NULL REFERENCES transaction_status(id),
    reason          VARCHAR(255),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE bank_slip_status (
    id          SERIAL PRIMARY KEY,
    enumerator  VARCHAR(50) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(enumerator)
);

CREATE TABLE bank_slip (
    id              SERIAL PRIMARY KEY,
    bank_slip_key   CHAR(36) NOT NULL, 
    amount          BIGINT NOT NULL, 
    expiration_date DATE NOT NULL,
    external_key    CHAR(36),
    barcode         CHAR(47),
    account_id      INTEGER NOT NULL REFERENCES account(id),
    transaction_id  INTEGER REFERENCES transaction(id),
    status_id       INTEGER NOT NULL REFERENCES bank_slip_status(id),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(bank_slip_key), UNIQUE (external_key), UNIQUE (transaction_id),
    check (amount > 0)
);

INSERT INTO bank_slip_status (enumerator) VALUES ('pending'), ('issued'), ('paid'), ('failed'), ('expired');

CREATE TABLE bank_slip_status_event (
    id              SERIAL PRIMARY KEY,
    bank_slip_id  INTEGER NOT NULL REFERENCES bank_slip(id),
    from_status_id  INTEGER REFERENCES bank_slip_status(id),
    to_status_id    INTEGER NOT NULL REFERENCES bank_slip_status(id),
    reason          VARCHAR(255),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE corporate_status (
    id          SERIAL PRIMARY KEY,
    enumerator  VARCHAR(20) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(enumerator)
);
INSERT INTO corporate_status (enumerator) VALUES ('created'), ('pending'), ('active'), ('blocked');

CREATE TABLE corporate_customer (
    id            SERIAL PRIMARY KEY,
    corporate_key CHAR(36) NOT NULL,
    cnpj          CHAR(14) NOT NULL,
    company_name  VARCHAR(255) NOT NULL,
    trade_name    VARCHAR(255),
    status_id     INTEGER NOT NULL REFERENCES corporate_status(id),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(corporate_key), UNIQUE(cnpj)
);

CREATE TABLE corporate_member (
    id            SERIAL PRIMARY KEY,
    corporate_id  INTEGER NOT NULL REFERENCES corporate_customer(id),
    customer_id   INTEGER NOT NULL REFERENCES customer(id),
    role          VARCHAR(20) NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(corporate_id, customer_id)
);

CREATE TABLE corporate_account (
    id            SERIAL PRIMARY KEY,
    corporate_id  INTEGER NOT NULL REFERENCES corporate_customer(id),
    account_id    INTEGER NOT NULL REFERENCES account(id),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(corporate_id, account_id)
);

CREATE TABLE corporate_transfer_request (
    id                      SERIAL PRIMARY KEY,
    corporate_id            INTEGER NOT NULL REFERENCES corporate_customer(id),
    requester_customer_id   INTEGER NOT NULL REFERENCES customer(id),
    origin_account_id       INTEGER NOT NULL REFERENCES account(id),
    destination_account_key CHAR(36) NOT NULL,
    amount                  BIGINT NOT NULL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE corporate_audit (
    id                  SERIAL PRIMARY KEY,
    corporate_id        INTEGER NOT NULL REFERENCES corporate_customer(id),
    actor_customer_id   INTEGER REFERENCES customer(id),
    action              VARCHAR(100) NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================
-- Empréstimos
-- ============================================

CREATE TABLE loan (
    id                  SERIAL PRIMARY KEY,
    loan_key            CHAR(36) NOT NULL,
    account_id          INTEGER NOT NULL REFERENCES account(id),
    requested_amount    BIGINT NOT NULL,
    total_amount_due    BIGINT NOT NULL,
    interest_rate       INTEGER NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(loan_key)
);

CREATE TABLE loan_installment (
    id                  SERIAL PRIMARY KEY,
    loan_id             INTEGER NOT NULL REFERENCES loan(id),
    installment_number  INTEGER NOT NULL,
    amount              BIGINT NOT NULL,
    due_date            TIMESTAMP NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================
-- Notificações
-- ============================================

CREATE TABLE notification (
    id           SERIAL PRIMARY KEY,
    key          CHAR(36)      NOT NULL,
    event_key    VARCHAR(120)  NOT NULL,
    customer_key CHAR(36)      NOT NULL,
    title        VARCHAR(100)  NOT NULL,
    body         TEXT          NOT NULL,
    is_read      BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP     NOT NULL DEFAULT NOW(),
    UNIQUE(key), UNIQUE(event_key)
);

CREATE TABLE notification_outbox (
    id           SERIAL PRIMARY KEY,
    event_key    VARCHAR(120)  NOT NULL,
    customer_key CHAR(36)      NOT NULL,
    title        VARCHAR(100)  NOT NULL,
    body         TEXT          NOT NULL,
    status       VARCHAR(20)   NOT NULL DEFAULT 'pending',
    attempts     INTEGER       NOT NULL DEFAULT 0,
    last_error   TEXT,
    created_at   TIMESTAMP     NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP,
    UNIQUE(event_key)
);

-- ============================================
-- Conta interna do banco (tesouraria)
-- ============================================
-- Recebe as tarifas das transferências e o pagamento das parcelas de
-- empréstimo. O "cliente" dono dela é o próprio banco; ninguém loga com
-- ele (a senha é o hash de um segredo aleatório que foi jogado fora).
-- ON CONFLICT DO NOTHING: dá pra rodar este bloco num banco que já existe.
INSERT INTO customer (customer_key, name, document_number, email, password_hash, birth_date, status_id)
VALUES (
    '00000000-0000-4000-8000-000000000001',
    'QI Bank - Tesouraria',
    '000.000.000-00',
    'tesouraria@banco.interno',
    '$2b$12$TZ4/9J0plyFccztP5OeiI.BbEZlCDU.T4ijsmVjaZ1VU.XTLmJefO',
    '2000-01-01',
    (SELECT id FROM customer_status WHERE enumerator = 'success')
)
ON CONFLICT DO NOTHING;

INSERT INTO account (account_key, customer_id, branch, number, type, balance, status_id)
VALUES (
    '00000000-0000-4000-8000-000000000002',
    (SELECT id FROM customer WHERE customer_key = '00000000-0000-4000-8000-000000000001'),
    '0000',
    '00000000-0',
    'checking',
    0,
    (SELECT id FROM account_status WHERE enumerator = 'active')
)
ON CONFLICT DO NOTHING;
