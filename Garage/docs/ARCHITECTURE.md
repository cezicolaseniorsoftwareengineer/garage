# Arquitetura do 404 Garage
## Bio Code Technology Ltda · CeziCola · Senior Software Engineer
**Versão:** 1.0 · **Data:** 02/03/2026

---

## 1. Visão Geral da Plataforma

O 404 Garage é composto por **três serviços** que se comunicam por HTTP:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        404 Garage Platform                              │
│                                                                         │
│  ┌─────────────────┐  HTTP/REST   ┌────────────────────────────────┐   │
│  │  Browser        │─────────────▶│  Python / FastAPI              │   │
│  │  HTML5 Canvas   │◀─────────────│  PORT 8000                     │   │
│  │  Monaco Editor  │              │  Auth · Game · Leaderboard     │   │
│  │  Vanilla JS     │              │  Study Chat · Admin            │   │
│  └─────────────────┘              └──────────────┬─────────────────┘   │
│                                                  │ HTTP (httpx)        │
│                                                  ▼                     │
│                                  ┌────────────────────────────────┐    │
│                                  │  Java / Spring Boot            │    │
│                                  │  PORT 8080                     │    │
│                                  │  Code Execution Sandbox        │    │
│                                  │  Compile + JUnit Runner        │    │
│                                  └────────────────────────────────┘    │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  PostgreSQL — Neon Serverless                                    │  │
│  │  Tabelas: users · sessions · leaderboard · audit_logs           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Domain-Driven Design (DDD)

O backend Python segue **DDD** com quatro camadas estritamente separadas.

### Regra de dependências

```
api/routes  →  application  →  domain  ←  infrastructure
```

- A camada `domain` **não importa nada** de fora. Zero acoplamento a FastAPI, SQLAlchemy ou qualquer lib.
- A camada `application` (casos de uso) conhece as interfaces de repositório, mas **não as implementações**.
- A camada `infrastructure` implementa as interfaces definidas em `application`.
- A camada `api/routes` é um adaptador HTTP: converte Request → UseCase → Response.

### Camada: `domain/`

Entidades puras com invariantes validadas no construtor.

```python
# Exemplo: domain/player.py
class Player:
    def __init__(self, id: str, username: str, xp: int = 0):
        if not id:
            raise ValueError("Player id cannot be blank")
        self.id = id
        self.username = username
        self.xp = xp

    @property
    def seniority(self) -> str:
        if self.xp < 100: return "Estagiário"
        if self.xp < 300: return "Junior"
        if self.xp < 700: return "Mid-Level"
        if self.xp < 1500: return "Senior"
        if self.xp < 3000: return "Staff"
        return "Principal Engineer"
```

**Arquivos:**
| Arquivo | Responsabilidade |
|---------|-----------------|
| `player.py` | Entidade Player, XP, seniority |
| `challenge.py` | MCQ, CodingChallenge, opções |
| `scoring.py` | Cálculo de score por tempo e tentativas |
| `user.py` | User, Registration, OTP |
| `enums.py` | GameState, Role, ActLocation, Seniority |
| `invariant.py` | Guards reutilizáveis (not_blank, positive_int...) |

### Camada: `application/`

Casos de uso que orquestram domain + infra. Cada caso de uso recebe suas dependências via injeção (constructor injection).

```python
# Exemplo: application/submit_answer.py
class SubmitAnswerUseCase:
    def __init__(self, player_repo, challenge_repo, event_service):
        self._players = player_repo
        self._challenges = challenge_repo
        self._events = event_service

    def execute(self, player_id: str, challenge_id: str, answer: str) -> AnswerResult:
        player = self._players.find_by_id(player_id)
        challenge = self._challenges.find_by_id(challenge_id)
        score = ScoreCalculator.compute(challenge, answer)
        player.award_xp(score.xp)
        self._players.save(player)
        self._events.publish(AnswerSubmittedEvent(player_id, challenge_id, score))
        return score
```

**Arquivos:**
| Arquivo | Caso de uso |
|---------|------------|
| `start_game.py` | Cria sessão, seleciona estágio atual do player |
| `submit_answer.py` | Valida MCQ, calcula score, atualiza XP |
| `progress_stage.py` | Avança o player para o próximo estágio/ato |
| `event_service.py` | Publica `GameEvent` (para métricas e audit) |
| `metrics_service.py` | Agrega métricas de uso por act/challenge |

### Camada: `infrastructure/`

Implementações concretas. Nunca importadas pelo `domain`.

```
infrastructure/
├── database/
│   ├── engine.py          # SQLAlchemy create_engine + sessionmaker
│   └── models.py          # ORM models (UserModel, SessionModel, etc.)
├── repositories/
│   ├── player_repo.py     # PlayerRepository (PostgreSQL)
│   ├── challenge_repo.py  # ChallengeRepository (JSON file ou PostgreSQL)
│   └── user_repo.py       # UserRepository (PostgreSQL)
├── auth/
│   ├── jwt_utils.py       # create_access_token, decode_token
│   ├── password.py        # hash_password, verify_password (bcrypt)
│   └── bruteforce.py      # BruteForceGuard — contador por IP/username
└── audit.py               # AuditLogger — insere em tabela audit_logs
```

### Camada: `api/routes/`

Adaptadores HTTP. Lógica mínima — apenas conversão de tipos e chamada ao UseCase.

```
api/routes/
├── auth_routes.py         # /register, /login, /verify-email, /forgot-password, /reset-password
├── game_routes.py         # /start, /answer, /progress, /leaderboard, /health
├── admin_routes.py        # /admin/users, /admin/challenges, /admin/audit
├── study_routes.py        # /study/chat, /study/hint (IA pedagógica)
├── code_runner_routes.py  # /code/execute → chama java-runner via httpx
└── ai_validator_routes.py # /ai/validate → valida resposta livre com IA
```

---

## 3. State Machine do Jogo

```
        ┌─────────┐
  start │         │
───────▶│  INTRO  │  (cutscene NPC)
        └────┬────┘
             │ cutscene_complete
             ▼
        ┌──────────┐
        │ LEARNING │  (teoria + diagrama)
        └────┬─────┘
             │ learning_done
             ▼
        ┌───────────┐
        │ CHALLENGE │  (MCQ — múltipla escolha)
        └────┬──────┘
             │ challenge_passed (score >= threshold)
             ▼
        ┌────────┐
        │ CODING │  (Monaco Editor — código Java)
        └────┬───┘
             │ tests_passed (JUnit 100%)
             ▼
        ┌──────┐
        │ BOSS │  (desafio de arquitetura integrado)
        └──────┘
```

Transições são validadas pelo enum `GameState` em `domain/enums.py`.
O `progress_stage.py` rejeita qualquer transição inválida com `InvalidStateTransitionError`.

---

## 4. Fluxo de Autenticação

```
Browser                      FastAPI                     PostgreSQL
   │                            │                              │
   │── POST /register ─────────▶│                              │
   │                     validate schema                       │
   │                     hash password (bcrypt)               │
   │                     generate OTP (6 digits, 15min TTL)   │
   │                            │── INSERT user (pending) ───▶│
   │                            │── send OTP via Resend ──────▶ (email)
   │◀── 201 {_debug_otp?} ──────│                              │
   │                            │                              │
   │── POST /verify-email ──────▶│                              │
   │                     validate OTP + TTL                    │
   │                            │── UPDATE user (verified) ──▶│
   │◀── 200 {access_token} ─────│                              │
   │                            │                              │
   │── POST /login ─────────────▶│                              │
   │                     verify password (bcrypt)              │
   │                     check email_verified                  │
   │                     create JWT (HS256)                    │
   │◀── 200 {access_token} ─────│                              │
```

**RBAC:**
- `player`: acessa `/api/game/*`, `/api/code/*`, `/api/study/*`
- `admin`: acessa tudo acima + `/api/admin/*`

---

## 5. Java Execution Service

Serviço dedicado à execução segura de código Java enviado pelo player.

### Fluxo

```
FastAPI (code_runner_routes.py)
  │
  │  POST http://localhost:8080/execute
  │  { challenge_id, player_code, language: "java17" }
  │
  ▼
Spring Boot (ExecutionController)
  │
  ├─ JavaCompilerService → javax.tools.JavaCompiler
  │    compila player_code em memória (sem disco)
  │    timeout: 5s para compilação
  │
  ├─ TestRunnerService → JUnit 5 Launcher
  │    carrega test suite do challenge_id
  │    executa N testes contra o código compilado
  │    timeout: 10s para execução total
  │
  └─ retorna ExecutionResult
       { compiled, compile_errors, tests_total, tests_passed,
         tests_failed, failures, score_percent, execution_time_ms, feedback }
```

### Segurança do Sandbox

- Execução em thread com `ThreadGroup` isolado
- Sem acesso a `System.exit()`, `Runtime.exec()`, operações de rede ou filesystem
- `SecurityManager` custom (ou `ProcessBuilder` com restrições no container Docker)
- Container Docker sem privilégios; sem montagem de volumes em produção

---

## 6. Persistência

### Estratégia Dual

| Modo | Condição | Implementação |
|------|---------|--------------|
| **PostgreSQL** | `DATABASE_URL` presente no `.env` | SQLAlchemy + psycopg2 + Neon |
| **JSON fallback** | `DATABASE_URL` ausente | Leitura/escrita em `app/data/*.json` |

O fallback JSON é apenas para desenvolvimento local sem banco configurado.

### Tabelas PostgreSQL

| Tabela | Propósito |
|--------|-----------|
| `users` | Credenciais, role, email_verified, OTP |
| `sessions` | Estado de jogo do player (act, stage, score, xp) |
| `leaderboard` | Score final + username para ranking global |
| `audit_logs` | Registro imutável de ações sensíveis |
| `events` | GameEvents publicados pelo event_service |
| `metrics` | Contadores de uso por challenge/act |

### Cache de Ativos

O `app/main.py` aplica `Cache-Control` via middleware:

| Tipo | Header | TTL |
|------|--------|-----|
| `.mp3`, `.png`, `.svg`, `.woff2` | `public, max-age=2592000, immutable` | 30 dias |
| `.js`, `.css` | `no-store, no-cache, must-revalidate` | Sem cache (versionado por `?v=`) |
| `.html`, API | `no-store, no-cache, must-revalidate` | Nunca cache |

---

## 7. Performance

| Técnica | Implementação | Ganho |
|---------|--------------|-------|
| GZip compressão | `GZipMiddleware(minimum_size=1024)` | ~70% em JS/CSS/JSON |
| Cache-Control inteligente | Middleware por extensão | Zero re-download de assets |
| Hot-reload restrito | `reload_dirs=[app/]` apenas | Sem restart desnecessário |
| Neon Serverless | Connection pooling automático | Baixa latência em cold start |
| Java process pool | Spring Boot mantém JVM aquecida | Compilação < 500ms após warm-up |

---

## 8. Deploy (Render.com)

```
Render Services:
├── Web Service (Python)
│   ├── Build: pip install -r requirements.txt
│   ├── Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
│   ├── ENV: DATABASE_URL, JWT_SECRET_KEY, RESEND_API_KEY, ...
│   └── PORT: 8000
│
└── Web Service (Java — Docker)
    ├── Build: docker build Garage/java-runner/
    ├── Start: java -jar execution-service.jar
    └── PORT: 8080
```

**O `garage.py` é usado apenas em desenvolvimento local** — em produção o Render usa o comando Uvicorn diretamente.

---

## 9. Decisões de Arquitetura (ADRs revisados)

### ADR-001: Por que FastAPI + Python e não Node.js?
**Contexto:** Precisávamos de um backend com tipagem forte, validação automática de schema e fácil integração com PostgreSQL.
**Decisão:** FastAPI 0.115 + Pydantic v2.
**Consequência:** Validação de entrada automática, OpenAPI docs gerados automaticamente, async nativo.

### ADR-002: Por que Java separado para Code Execution?
**Contexto:** O jogo ensina Java. O player precisa escrever e executar Java real.
**Decisão:** Spring Boot como serviço separado com sandbox JVM.
**Consequência:** Isolamento total — bug no código do player não derruba o FastAPI.

### ADR-003: Por que PostgreSQL (Neon) e não Supabase?
**Contexto:** O plano original usava Supabase. Migramos para controle total via SQLAlchemy.
**Decisão:** Neon Serverless PostgreSQL + SQLAlchemy ORM.
**Consequência:** Queries customizadas, schema versionado manualmente, sem vendor lock-in de auth.

### ADR-004: Por que JSON fallback e não só PostgreSQL?
**Contexto:** Desenvolvimento local sem banco configurado deve funcionar.
**Decisão:** Repositórios com interface dupla: PostgreSQL se `DATABASE_URL` existe, JSON caso contrário.
**Consequência:** Onboarding zero-friction para novos devs; JSON nunca usado em produção.

### ADR-005: Por que Resend e não SMTP próprio?
**Contexto:** Gmail SMTP tem limites. SendGrid é caro. Resend tem tier gratuito generoso.
**Decisão:** Resend API com domínio verificado `onboarding@resend.dev` (temporário) → `biocodetechnology.com` (definitivo).
**Consequência:** E-mails chegam na inbox; não vão para spam após verificação do domínio próprio.

---

## 10. Estrutura de Arquivos Críticos

```
Garage_Game/
├── README.md                    # Documentação principal do projeto
├── Garage/
│   ├── garage.py                # Launcher local (load .env, chdir, uvicorn)
│   ├── requirements.txt         # Dependências Python
│   ├── PLAN_MASTER.md           # Plano pedagógico e roadmap
│   ├── docs/
│   │   ├── ARCHITECTURE.md      # Este documento
│   │   ├── SECURITY_CHECKLIST.md# Checklist OWASP
│   │   └── JAVA_EXECUTION_SERVICE.md # Spec do serviço Java
│   ├── app/
│   │   ├── main.py              # FastAPI app factory + middlewares
│   │   ├── domain/              # Entidades puras
│   │   ├── application/         # Casos de uso
│   │   ├── infrastructure/      # BD, auth, email
│   │   ├── api/routes/          # Endpoints HTTP
│   │   ├── static/              # Frontend (game.js, index.html, CSS, sprites)
│   │   └── data/                # challenges.json (versionado)
│   ├── java-runner/
│   │   ├── pom.xml
│   │   ├── Dockerfile
│   │   └── src/main/java/com/garage/execution/
│   ├── scripts/                 # Utilitários de manutenção (não commitados em prod)
│   └── tests/                   # pytest — unit + integration
```

---

*Arquitetura documentada por CeziCola · Bio Code Technology Ltda · 02/03/2026*
