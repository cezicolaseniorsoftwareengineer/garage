-- Idempotent migration: create idempotency_keys table
CREATE TABLE IF NOT EXISTS idempotency_keys (
    id VARCHAR(100) PRIMARY KEY,
    method VARCHAR(10) NOT NULL,
    path VARCHAR(200) NOT NULL,
    status_code INTEGER,
    response_body JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_idempotency_created ON idempotency_keys(created_at DESC);
