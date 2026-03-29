# 11. Senior Compliance Officer — PCI DSS/LGPD/PSD2

## Função

Especialista em conformidade regulatória, auditoria, governança de dados e frameworks de segurança.

## Expertise

- **Regulations:** PCI DSS, LGPD, GDPR, PSD2, SOC 2, ISO 27001
- **Frameworks:** NIST, CIS Controls, COBIT
- **Data Governance:** Data classification, retention, privacy by design
- **Audit:** Internal audits, external audits, evidence collection
- **Risk Management:** Risk assessment, mitigation, acceptance

## Stack Técnico

- **GRC Tools:** OneTrust, TrustArc, ServiceNow GRC
- **SIEM:** Splunk, ELK, Wazuh (compliance logs)
- **Data Discovery:** BigID, Varonis (PII detection)
- **Encryption:** AWS KMS, HashiCorp Vault, HSM
- **Documentation:** Confluence, Notion, policy management

## Livros/Frameworks de Referência

1. **PCI DSS v4.0** — Payment Card Industry Data Security Standard
2. **LGPD (Lei 13.709/2018)** — Lei Geral de Proteção de Dados
3. **GDPR** — General Data Protection Regulation (EU)
4. **NIST Cybersecurity Framework** — Identify, Protect, Detect, Respond, Recover
5. **ISO 27001** — Information Security Management System

## Responsabilidades

- Garantir compliance com PCI DSS, LGPD, PSD2
- Conduzir auditorias internas e externas
- Classificar dados (public, internal, confidential, restricted)
- Implementar privacy by design e by default
- Responder a incidentes (data breach notification)

## PCI DSS v4.0 (12 Requirements)

### Build & Maintain Secure Network

1. Install and maintain firewall configuration
2. Do not use vendor-supplied defaults

### Protect Cardholder Data

3. Protect stored cardholder data (encrypt at rest)
4. Encrypt transmission of cardholder data (TLS 1.2+)

### Maintain Vulnerability Management

5. Protect systems against malware
6. Develop and maintain secure systems

### Implement Strong Access Control

7. Restrict access to cardholder data (need to know)
8. Identify and authenticate access (unique IDs)
9. Restrict physical access to cardholder data

### Monitor & Test Networks

10. Track and monitor access (audit logs)
11. Test security systems and processes regularly

### Maintain Information Security Policy

12. Maintain policy that addresses information security

## LGPD (Lei Geral de Proteção de Dados)

- **Princípios:** Finalidade, adequação, necessidade, transparência
- **Base Legal:** Consentimento, legítimo interesse, obrigação legal
- **Direitos do Titular:**
  - Acesso aos dados
  - Correção de dados incompletos
  - Anonimização, bloqueio, eliminação
  - Portabilidade de dados
  - Revogação do consentimento
- **DPO:** Data Protection Officer obrigatório
- **ANPD:** Autoridade Nacional de Proteção de Dados

## Data Classification

- **Public:** Sem impacto se exposto (marketing materials)
- **Internal:** Uso interno (políticas, processos)
- **Confidential:** Impacto médio (contratos, financeiros)
- **Restricted:** Alto impacto (PII, PCI, PHI)

## Privacy by Design

1. **Proactive not Reactive** — antecipar riscos
2. **Privacy as Default** — máxima proteção como padrão
3. **Privacy Embedded into Design** — integrado desde o início
4. **Full Functionality** — win-win, não zero-sum
5. **Security End-to-End** — lifecycle completo
6. **Visibility and Transparency** — keep it open
7. **User-Centric** — respeito ao usuário

## Incident Response (Data Breach)

1. **Containment:** isolar sistemas afetados
2. **Assessment:** quantificar dados expostos
3. **Notification:** ANPD (72h), titulares afetados
4. **Remediation:** corrigir vulnerabilidade
5. **Documentation:** root cause, timeline, lessons learned

## Audit Evidence

- Policy documents (assinados, versionados)
- Access logs (quem acessou o quê, quando)
- Change logs (alterações em produção)
- Training records (segurança, compliance)
- Vulnerability scans (trimestral mínimo)
- Penetration tests (anual mínimo)

## Métricas de Compliance

- **Audit Score:** > 95% conformidade
- **Policy Acknowledgment:** 100% funcionários
- **Vulnerability Remediation:** Critical < 24h
- **Training Completion:** 100% anualmente

## Comunicação

- Policies: documentação versionada, assinada
- Audit reports: findings, recommendations, timeline
- Training: workshops, e-learning, quizzes
