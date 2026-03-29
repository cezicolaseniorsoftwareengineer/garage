-- Rollback migration: drop idempotency_keys (use with caution)
DROP TABLE IF EXISTS idempotency_keys;
