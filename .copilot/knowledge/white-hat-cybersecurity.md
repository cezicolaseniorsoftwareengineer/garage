# White Hat Cybersecurity -- Knowledge Base do Cezi Cola

## Proposito

Base operacional de seguranca ofensiva e defensiva para o cerebro do Cezi.
O objetivo e rastrear vulnerabilidades com a mentalidade de um atacante,
mas corrigir com a disciplina de um engenheiro de seguranca.

Toda decisao de seguranca do Cezi deve passar por este filtro antes de ser aceita.

---

## Mestres de Cybersecurity (31-42)

### 31. Bruce Schneier

Dominio: criptografia aplicada, seguranca pragmatica, modelagem de ameacas
Responsavel por: avaliar se o sistema faz as perguntas certas antes de escolher algoritmos.
Principio: "Security is a process, not a product."
Aplicacao: nunca confiar em um unico controle; construir defesa em profundidade.

### 32. Kevin Mitnick

Dominio: engenharia social, penetration testing, evasao de controles
Responsavel por: pensar como atacante em cada endpoint publico.
Principio: "The weakest link in security is the human element."
Aplicacao: assumir que tokens vazam, que emails sao interceptados, que URLs sao compartilhadas.

### 33. OWASP Foundation (coletivo)

Dominio: Top 10 Web, ASVS, SAMM, Cheat Sheet Series
Responsavel por: baseline minimo de seguranca para qualquer aplicacao web.
Principio: varredura sistematica contra as 10 categorias de vulnerabilidade.
Aplicacao: toda revisao de seguranca deve cobrir A01-A10 explicitamente.

### 34. Troy Hunt

Dominio: exposicao de dados, breach analysis, seguranca de credenciais
Responsavel por: garantir que credenciais e PII nunca vazem por logs, headers ou responses.
Principio: "If it's been breached, it will be exploited."
Aplicacao: tratar todo dado sensivel como se ja estivesse exposto.

### 35. Tavis Ormandy (Google Project Zero)

Dominio: vulnerability research, zero-day discovery, hardening de runtime
Responsavel por: questionar cada dependencia, cada parser, cada deserializacao.
Principio: "The bug is always where you're not looking."
Aplicacao: auditar dependencias, verificar CVEs, desconfiar de inputs complexos.

### 36. James Forshaw

Dominio: privilege escalation, access control bypass, sandboxing
Responsavel por: validar que cada camada de autorizacao e independente.
Principio: "Every trust boundary must be explicitly verified."
Aplicacao: nunca derivar privilegio de email, IP ou header sem assinatura criptografica.

### 37. Parisa Tabriz (Google Security Princess)

Dominio: browser security, HTTPS adoption, organizacao de seguranca em escala
Responsavel por: garantir que headers de seguranca estejam em toda response HTTP.
Principio: "Make security invisible to users but impossible to bypass."
Aplicacao: CSP, HSTS, X-Frame-Options, X-Content-Type-Options em toda resposta.

### 38. Daniel Miessler

Dominio: application security, threat modeling, security automation
Responsavel por: sistematizar a busca por vulnerabilidades com checklists praticos.
Principio: "Automation finds bugs; humans find flaws."
Aplicacao: checklists executaveis para cada tipo de mudanca (endpoint, auth, dados, deploy).

### 39. Katie Moussouris

Dominio: vulnerability disclosure, bug bounty programs, seguranca organizacional
Responsavel por: pensar em como vulnerabilidades sao reportadas e corrigidas.
Principio: "A vulnerability you can't fix is worse than one you don't know about."
Aplicacao: toda vulnerabilidade encontrada deve ter correcao proposta, timeline e teste.

### 40. Ivan Ristic

Dominio: TLS/SSL, HTTP security headers, web application firewalls
Responsavel por: configuracao de transporte seguro e headers defensivos.
Principio: "The transport layer is the first line of defense."
Aplicacao: TLS 1.2+, HSTS, cookie flags, CORS restritivo, CSP robusto.

### 41. Dafydd Stuttard (PortSwigger/Burp Suite)

Dominio: web application hacking, injection, authentication bypass
Responsavel por: testar cada input como se fosse payload malicioso.
Principio: "Every input is an attack vector until proven otherwise."
Aplicacao: SQLi, XSS, SSRF, path traversal, header injection em todo input.

### 42. Tanya Janca (SheHacksPurple)

Dominio: secure SDLC, DevSecOps, application security training
Responsavel por: integrar seguranca no ciclo de desenvolvimento, nao depois.
Principio: "Security must be part of the design, not an afterthought."
Aplicacao: security review como gate obrigatorio antes de merge; threat model como artefato de design.

---

## Frameworks de Referencia

### OWASP Top 10 (2021) -- Checklist Operacional

| ID  | Categoria                        | Pergunta obrigatoria no Cezi                                   |
| --- | -------------------------------- | -------------------------------------------------------------- |
| A01 | Broken Access Control            | Todo endpoint valida quem e o usuario E o que ele pode fazer?  |
| A02 | Cryptographic Failures           | Dados sensiveis estao cifrados em transito e em repouso?       |
| A03 | Injection                        | Todo input externo e parametrizado antes de chegar ao SQL/OS?  |
| A04 | Insecure Design                  | O design tem threat model? Abuse cases foram mapeados?         |
| A05 | Security Misconfiguration        | CORS, headers, debug mode, defaults de secret estao seguros?   |
| A06 | Vulnerable Components            | Dependencias tem CVEs conhecidos? Estao atualizadas?           |
| A07 | Identification/Authentication    | JWT verifica exp+aud+alg? Senha usa argon2/bcrypt? MFA existe? |
| A08 | Software/Data Integrity Failures | Webhooks tem assinatura verificada? Deploys sao assinados?     |
| A09 | Logging/Monitoring Failures      | Falhas de auth sao logadas? Existe alerta para anomalias?      |
| A10 | SSRF                             | Requests server-side validam destino? Allow-list de hosts?     |

### OWASP ASVS v4.0 -- Niveis de Verificacao

| Nivel | Descricao                            | Quando usar no Cezi                          |
| ----- | ------------------------------------ | -------------------------------------------- |
| L1    | Baseline (automated tools)           | Todo commit -- minimo aceitavel              |
| L2    | Standard (manual review)             | Features de auth, pagamento, dados sensiveis |
| L3    | Advanced (threat modeling + pentest) | Pre-producao, compliance PCI DSS, fintech    |

### PCI DSS v4.0 -- Controles para Fintech

| Requisito | Controle                                 | Verificacao no Cezi                       |
| --------- | ---------------------------------------- | ----------------------------------------- | ----------------------------- |
| 3.4       | PAN mascarado (mostrar apenas ultimos 4) | grep: card_number                         | pan sem mascara               |
| 3.5       | Chaves de criptografia protegidas        | grep: SECRET_KEY                          | API_KEY com default hardcoded |
| 6.2       | Software seguro (sem vulns conhecidas)   | audit de dependencias (pip-audit, safety) |
| 6.5       | Injection prevention                     | zero raw SQL, zero f-string em queries    |
| 8.3       | MFA para acesso administrativo           | admin endpoints com segundo fator         |
| 10.1      | Audit trails para acesso a dados         | audit_log em toda operacao financeira     |
| 11.3      | Testes de penetracao periodicos          | security-audit skill como gate pre-deploy |

### LGPD -- Controles para Dados Pessoais

| Artigo  | Exigencia                          | Verificacao no Cezi                              |
| ------- | ---------------------------------- | ------------------------------------------------ |
| Art. 6  | Finalidade, adequacao, necessidade | Coletar apenas dados necessarios para a operacao |
| Art. 12 | Anonimizacao quando possivel       | CPF mascarado em logs e responses paginadas      |
| Art. 46 | Medidas tecnicas de protecao       | Criptografia, controle de acesso, audit logs     |
| Art. 48 | Comunicacao de incidentes          | Logs de breach tentado + alerta automatico       |

---

## Threat Model -- BioCodeTechPay

### Ativos criticos (o que proteger)

1. Saldo de usuarios (mutacao deve ser atomica e auditavel)
2. Credenciais (senha hash, JWT, API keys)
3. Dados pessoais (CPF, email, telefone, endereco)
4. Chaves PIX (associadas a identidade real)
5. Webhooks de pagamento (fonte de verdade financeira)

### Superficies de ataque

| Superficie       | Vetor                        | Controle esperado                                 |
| ---------------- | ---------------------------- | ------------------------------------------------- |
| API REST publica | Injection, brute force, CSRF | Pydantic, rate limit, CORS restritivo             |
| JWT cookie       | Roubo de token, forgery      | httpOnly, Secure, SameSite, exp curto             |
| Webhook Asaas    | Forjaria de payload, replay  | HMAC signature, idempotency, timestamp check      |
| Admin panel      | Privilege escalation, IDOR   | RBAC com flag de DB (nao email), auth obrigatoria |
| Database         | SQL injection, exposure      | ORM parametrizado, TLS, credenciais rotacionadas  |
| Logs             | PII leakage                  | Mascaramento, structured logging, sem PII         |
| Dependencias     | CVE em libs                  | pip-audit periodico, dependabot                   |
| Static assets    | XSS via template             | CSP header, Jinja2 autoescaping                   |
| Payment links    | Enumeration, abuse           | UUID v4 (122 bits), rate limit, expiracao         |
| QR code          | Payload manipulation         | Validate EMV format, payload_hash dedup           |

### Modelo STRIDE aplicado

| Ameaca              | Exemplo no BioCodeTechPay              | Mitigacao                                      |
| ------------------- | -------------------------------------- | ---------------------------------------------- |
| **S**poofing        | Forjar JWT com secret key publica      | Fail-fast se SECRET_KEY nao definido           |
| **T**ampering       | Alterar valor no request de credito    | Server-side value enforcement                  |
| **R**epudiation     | Negar que fez uma transferencia        | Audit log imutavel com timestamp e correlation |
| **I**nfo Disclosure | CPF no JWT payload (base64)            | Usar user_id opaco como sub, nao CPF           |
| **D**enial of Svc   | Flood em /pix/link                     | Rate limiting por IP                           |
| **E**lev. Privilege | Mudar email para admin e ganhar acesso | Usar is_admin flag, nao comparacao de email    |

---

## Invariantes de Seguranca do Cezi

### Autenticacao e Sessao

- SECRET_KEY sem default -- fail fast na inicializacao se ausente
- JWT exp maximo 24h para sessao normal, 15min para operacao financeira
- Cookie: httpOnly=True, Secure=True, SameSite=Strict
- sub claim: user_id opaco, nunca CPF/PII
- Refresh token: rotacionar e invalidar apos uso
- Admin: validar flag is_admin na DB, nunca comparar email

### Dados e Criptografia

- Senhas: argon2id (nunca MD5, SHA1, bcrypt simples)
- PII em logs: sempre mascarado (ultimos 4 chars no maximo)
- PII em responses: minimo necessario, nunca em listas paginadas sem RBAC
- TLS 1.2+ obrigatorio em producao
- API keys: mascarar com no maximo 4 chars visiveis em logs

### Input e Output

- Todo input externo e nao confiavel ate ser validado por Pydantic
- Zero f-string ou concatenacao em queries SQL
- Zero eval(), exec(), os.system() com input externo
- Output: CSP header, X-Content-Type-Options, X-Frame-Options em toda response
- File uploads: validar tipo, tamanho e conteudo (magic bytes)

### Transacoes Financeiras

- Mutacao de saldo: atomica dentro de transacao DB com lock pessimista
- Webhook: HMAC timing-safe + check de timestamp (rejeitar > 5min)
- Valor: sempre do banco, nunca do cliente
- Saldo: Decimal nativo (asdecimal=True), nunca float
- Idempotency: key + payload_hash como dupla barreira
- Limites: cap por transacao + cap diario + antifraud scoring

### Infraestrutura

- CORS: origins explicitos, nunca wildcard com credentials
- Rate limit: Redis ou equivalente distribuido, nao in-memory
- Proxy headers: trusted_hosts restrito ao load balancer real
- Debug: False em producao, fail-fast se True
- Dependencias: auditadas periodicamente (pip-audit)

---

## Checklists Executaveis

### Antes de adicionar endpoint publico

- [ ] Pydantic schema valida todos os inputs
- [ ] Endpoint requer autenticacao (ou justificativa documentada se nao)
- [ ] Rate limiting aplicado
- [ ] Response nao expoe PII desnecessario
- [ ] UUID validado por regex antes de query
- [ ] Headers de seguranca presentes (CSP, X-Frame-Options)

### Antes de alterar autenticacao

- [ ] SECRET_KEY fail-fast testado
- [ ] JWT decode verifica exp + aud + alg
- [ ] Cookie flags conferidos (httpOnly, Secure, SameSite)
- [ ] Logout invalida token (blacklist ou rotacao)
- [ ] Brute force mitigado (rate limit ou lockout)

### Antes de tocar em dinheiro

- [ ] Valor vem do banco, nao do request
- [ ] Operacao atomica (debit + credit na mesma transaction)
- [ ] Lock pessimista (SELECT FOR UPDATE) no saldo
- [ ] Idempotency key verificada antes de processar
- [ ] Audit log gravado com valor anterior e posterior
- [ ] Cap de valor por transacao verificado
- [ ] Antifraud scoring executado antes de confirmar

### Antes de processar webhook

- [ ] Assinatura verificada com hmac.compare_digest
- [ ] Timestamp do webhook validado (< 5 minutos)
- [ ] Idempotency: payload_hash evita reprocessamento
- [ ] Resposta e 200 APENAS se processamento completo (commit feito)
- [ ] Falha retorna 500 para permitir retry do gateway

### Antes de deploy em producao

- [ ] pip-audit sem vulnerabilidades criticas
- [ ] SECRET_KEY definido via env var (nao default)
- [ ] CORS restrito ao dominio real
- [ ] DEBUG=False
- [ ] ASAAS_USE_SANDBOX=False
- [ ] ProxyHeadersMiddleware trusted_hosts restrito
- [ ] CSP header configurado
- [ ] Logs nao contem PII em plaintext
- [ ] Database URL com sslmode=require

---

## Livros de Referencia em Cybersecurity

1. **The Web Application Hacker's Handbook** -- Dafydd Stuttard, Marcus Pinto
   Responsabilidade: guia pratico de teste de penetracao em web apps.

2. **Cryptography Engineering** -- Bruce Schneier, Niels Ferguson, Tadayoshi Kohno
   Responsabilidade: escolher e implementar criptografia corretamente.

3. **Threat Modeling** -- Adam Shostack
   Responsabilidade: STRIDE, attack trees, modelagem sistematica de ameacas.

4. **Alice and Bob Learn Application Security** -- Tanya Janca
   Responsabilidade: secure SDLC, DevSecOps, integracao de seguranca no desenvolvimento.

5. **The Art of Deception** -- Kevin Mitnick
   Responsabilidade: engenharia social, o fator humano em seguranca.

6. **OWASP Testing Guide v4** -- OWASP Foundation
   Responsabilidade: metodologia completa de teste de seguranca para web apps.

7. **Bulletproof SSL and TLS** -- Ivan Ristic
   Responsabilidade: configuracao correta de TLS, PKI, certificate management.

---

## Ativacao

Para auditorias de seguranca, usar esta base em conjunto com:

- `.github/prompts/security-audit.prompt.md`
- `.copilot/masters/23-masters-council.md`
- `.copilot/knowledge/master-library.md`
- `.copilot/knowledge/cezi-stack-expansion.md`
