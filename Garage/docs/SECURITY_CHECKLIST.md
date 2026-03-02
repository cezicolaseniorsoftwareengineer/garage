# GARAGE Security Checklist
## 404 Garage · Bio Code Technology Ltda
**Versão:** 2.0 · **Atualizado:** 02/03/2026
**Referência:** OWASP Top 10 (2021)

---

## Legenda
- ✅ Implementado e validado
- ⚠️ Parcialmente implementado
- ❌ Pendente / planejado

---

## A01 — Broken Access Control

| Item | Status | Localização |
|------|--------|------------|
| RBAC: roles `admin` / `player` separadas | ✅ | `infrastructure/auth/`, `admin_routes.py` |
| Rotas `/api/admin/*` bloqueadas para `player` | ✅ | `admin_routes.py` — `Depends(require_admin)` |
| JWT validado em todo endpoint autenticado | ✅ | `infrastructure/auth/jwt_utils.py` |
| Usuário não acessa dados de outro usuário | ✅ | Filtro por `user_id` em todos os queries |
| Refresh token revogação persistida | ❌ | Planejado — requer tabela `revoked_tokens` |

## A02 — Cryptographic Failures

| Item | Status | Localização |
|------|--------|------------|
| Senhas com bcrypt (work factor 12) | ✅ | `infrastructure/auth/password.py` |
| JWT assinado com HS256 + secret forte | ✅ | `JWT_SECRET_KEY` no `.env` |
| Segredos NUNCA commitados | ✅ | `.env` no `.gitignore` |
| TLS na produção (Render.com) | ✅ | Terminado no load balancer do Render |
| OTP de 6 dígitos com TTL 15 min | ✅ | `auth_routes.py` — geração + expiração |
| RESEND_API_KEY não exposta no frontend | ✅ | Só usada no backend Python |

## A03 — Injection

| Item | Status | Localização |
|------|--------|------------|
| Queries via SQLAlchemy ORM (sem SQL raw) | ✅ | `infrastructure/repositories/` |
| Pydantic v2 valida todos os inputs | ✅ | Schemas em `api/routes/` |
| Código Java do player executado em sandbox | ✅ | `java-runner/` — sem acesso a rede/FS |
| Timeout de execução Java configurado | ✅ | `application.properties` — `execution.timeout` |
| Escape de HTML em respostas de erro | ⚠️ | FastAPI default; revisar mensagens customizadas |

## A04 — Insecure Design

| Item | Status | Localização |
|------|--------|------------|
| DDD com camadas de domínio isoladas | ✅ | `domain/`, `application/`, `infrastructure/` |
| Invariantes de domínio validadas no construtor | ✅ | `domain/invariant.py` |
| Casos de uso são a única porta de entrada | ✅ | `application/` — routes chamam use cases |
| Audit log de ações sensíveis | ✅ | `infrastructure/audit.py` → PostgreSQL |
| Rate limit em registro e login | ⚠️ | `bruteforce.py` ativo; CDN/WAF rate limit pendente |

## A05 — Security Misconfiguration

| Item | Status | Localização |
|------|--------|------------|
| CORS restrito em produção | ⚠️ | `ALLOWED_ORIGINS` no `.env`; validar no Render |
| `DEBUG=false` em produção | ⚠️ | Definir `DEBUG=false` no env da Render |
| `_debug_otp` não retornado com `DEBUG=false` | ✅ | `auth_routes.py` — `if _DEBUG_MODE` |
| Hot-reload desabilitado em produção | ✅ | `garage.py` — `reload=False` quando `ENV=production` |
| Stacktrace não exposta ao cliente | ✅ | FastAPI handlers retornam mensagens sanitizadas |
| Cabeçalhos de segurança HTTP | ❌ | Middleware de headers planejado (X-Frame, CSP) |

## A06 — Vulnerable and Outdated Components

| Item | Status | Localização |
|------|--------|------------|
| Verificar CVEs em dependências Python | ⚠️ | Rodar `pip-audit` antes de cada release |
| Verificar CVEs em dependências Java (Maven) | ⚠️ | `mvn dependency-check:check` no CI |
| Java 17 LTS (suporte até 2029) | ✅ | `java-runner/` |
| Python 3.13 (suporte até 2029) | ✅ | `requirements.txt` |
| Spring Boot 3.2.3 (suporte ativo) | ✅ | `pom.xml` |

## A07 — Identification and Authentication Failures

| Item | Status | Localização |
|------|--------|------------|
| Verificação de e-mail obrigatória pós-registro | ✅ | `auth_routes.py` — `/register` + `/verify-email` |
| Reset de senha via OTP por e-mail | ✅ | `/forgot-password` + `/reset-password` |
| Proteção de brute-force em login | ✅ | `infrastructure/auth/bruteforce.py` |
| JWT com expiração configurável | ✅ | `ACCESS_TOKEN_EXPIRE_MINUTES` no `.env` |
| Logout invalida token no cliente | ✅ | Frontend limpa token do localStorage |
| Rotação automática de JWT secret | ❌ | Planejado via secrets manager |

## A08 — Software and Data Integrity Failures

| Item | Status | Localização |
|------|--------|------------|
| Código Java do player não altera estado do servidor | ✅ | Sandbox no `java-runner/` sem acesso ao host |
| `challenges.json` versionado e imutável em runtime | ✅ | Leitura apenas; no-write em produção |
| Commits assinados / protegidos por branch | ⚠️ | Regra de branch main recomendada |

## A09 — Security Logging and Monitoring Failures

| Item | Status | Localização |
|------|--------|------------|
| Audit log de login, registro, reset, admin actions | ✅ | `infrastructure/audit.py` → tabela PostgreSQL |
| Logs com timestamp, user_id, action, IP | ✅ | Schema do audit log |
| Logs persistidos em PostgreSQL (durável) | ✅ | Neon Serverless |
| Alertas de falhas repetidas de login | ⚠️ | `bruteforce.py` local; alertas por e-mail pendentes |
| Centralização de logs em SIEM | ❌ | Planejado para escala |

## A10 — Server-Side Request Forgery (SSRF)

| Item | Status | Localização |
|------|--------|------------|
| `JAVA_RUNNER_URL` fixo no `.env` (sem input do usuário) | ✅ | `code_runner_routes.py` |
| Chamadas HTTP internas limitadas ao `java-runner` | ✅ | Apenas `httpx` para `JAVA_RUNNER_URL` |
| Player não controla URLs de requisições internas | ✅ | Nenhum endpoint aceita URL como parâmetro |

---

## Checklist Pré-Deploy

```
[ ] DEBUG=false no ambiente da Render
[ ] ALLOWED_ORIGINS aponta apenas para o domínio de produção
[ ] JWT_SECRET_KEY é UUID forte e único (mínimo 32 chars)
[ ] RESEND_API_KEY é a chave de produção (não dev)
[ ] DATABASE_URL aponta para o banco de produção (Neon)
[ ] pip-audit executado sem CVEs críticos
[ ] pytest Garage/app passou com 100% de testes
[ ] python Garage/scripts/validate_final.py OK
[ ] node Garage/test_all_challenges.js OK
[ ] Logs de audit verificados no PostgreSQL
[ ] Domínio biocodetechnology.com verificado no Resend (e-mail do OTP)
```

---

## Referências

- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Spring Boot Security Reference](https://docs.spring.io/spring-security/reference/)
- [Neon Serverless Security](https://neon.tech/docs/security/security-overview)
