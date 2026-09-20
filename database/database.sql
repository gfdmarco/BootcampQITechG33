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

CREATE TABLE account_status (
    id          SERIAL PRIMARY KEY,
    enumerator  VARCHAR(50) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(enumerator)
);
INSERT INTO account_status (enumerator) VALUES ('created'), ('active'), ('blocked'), ('closed');

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
    channel                 VARCHAR(50) NOT NULL,   -- pix / ted / card / international
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