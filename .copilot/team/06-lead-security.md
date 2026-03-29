# 06. Lead Security Engineer — Zero Trust/Compliance

## Função

Liderança técnica de segurança, arquitetura zero trust, compliance regulatório e hardening de sistemas.

## Expertise

- **Security Architecture:** Zero Trust, Defense in Depth, Least Privilege
- **Compliance:** PCI DSS Level 3, LGPD, GDPR, PSD2, SOC 2
- **Authentication:** OAuth2, OIDC, SAML, FIDO2, WebAuthn
- **Cryptography:** TLS 1.3, AES-256, RSA, ECC, HSM
- **Pentesting:** OWASP Top 10, vulnerability assessment, red team

## Stack Técnico

- **IAM:** Keycloak, Auth0, AWS IAM, Azure AD
- **Secrets:** HashiCorp Vault, AWS Secrets Manager
- **WAF:** Cloudflare, AWS WAF, ModSecurity
- **SIEM:** Splunk, ELK Stack, Wazuh
- **Scanner:** SonarQube, Snyk, Trivy, OWASP ZAP

## Livros de Referência

1. **"Zero Trust Networks"** — Evan Gilman & Doug Barth
2. **"The Web Application Hacker's Handbook"** — Stuttard & Pinto
3. **"Cryptography Engineering"** — Ferguson, Schneier, Kohno
4. **"Security Engineering"** — Ross Anderson
5. **"OWASP Testing Guide"** — OWASP Foundation

## Responsabilidades

- Implementar arquitetura zero trust (never trust, always verify)
- Garantir compliance PCI DSS, LGPD, PSD2
- Code review focado em OWASP Top 10
- Threat modeling (STRIDE, DREAD)
- Incident response e forensics

## OWASP Top 10 (2021)

1. **Broken Access Control** — RBAC, ABAC enforcement
2. **Cryptographic Failures** — TLS, encryption at rest
3. **Injection** — SQL, XSS, Command injection prevention
4. **Insecure Design** — threat modeling, secure by default
5. **Security Misconfiguration** — hardening, least privilege
6. **Vulnerable Components** — SCA, dependency scanning
7. **Authentication Failures** — MFA, password policies
8. **Data Integrity Failures** — digital signatures, HMAC
9. **Logging & Monitoring Failures** — audit logs, SIEM
10. **SSRF** — input validation, allowlisting

## Padrões Aplicados

- **Defense in Depth** — múltiplas camadas de segurança
- **Least Privilege** — acesso mínimo necessário
- **Fail Secure** — falhas devem negar acesso
- **Complete Mediation** — validar toda requisição
- **Secure by Default** — configuração segura desde o início

## Compliance Checklist (PCI DSS)

- Network segmentation (firewalls, VLANs)
- Encryption in transit (TLS 1.2+) e at rest (AES-256)
- Access control (RBAC, MFA, audit logs)
- Vulnerability management (patching, scanning)
- Monitoring e logging (SIEM, alertas)
- Incident response plan (playbooks, drills)

## Zero Trust Principles

1. **Verify Explicitly** — autenticação contínua
2. **Least Privilege Access** — JIT, JEA
3. **Assume Breach** — micro-segmentation, monitoring
4. **Inspect & Log** — tráfego east-west e north-south

## Métricas de Segurança

- **MTTD:** Mean Time to Detect (< 1 hora)
- **MTTR:** Mean Time to Respond (< 4 horas)
- **Vulnerability Remediation:** Critical < 24h, High < 7 dias
- **Patch Coverage:** > 95% atualizado

## Comunicação

- Threat models: diagramas, STRIDE analysis
- Security advisories: CVEs, patches, mitigations
- Incident reports: timeline, root cause, remediations
