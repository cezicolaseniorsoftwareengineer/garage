# GARAGE Security Checklist (High-level)

1. Set `JWT_SECRET_KEY` to a strong random value in production.
2. Configure `DATABASE_URL` for PostgreSQL and ensure network controls.
3. Set `ALLOWED_ORIGINS` to the specific frontend origins in production.
4. Use TLS for all external endpoints; terminate TLS at load balancer.
5. Rotate secrets periodically and use a secrets manager in prod.
6. Configure rate-limiting and brute-force protection at edge (CDN/WAF).
7. Persist audit logs to a centralized immutable store (S3, object storage, or SIEM).
8. Implement refresh token revocation backed by persistent store.
9. Run dependency scanning and SCA in CI; fail on critical vulnerabilities.
10. Add unit and integration tests for auth and repository layer.
