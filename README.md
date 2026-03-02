# GARAGE — 404 Garage

<img width="1914" height="967" alt="image" src="https://github.com/user-attachments/assets/24db1bd1-4c19-4169-b6fc-6a16e91e8425" />

<img width="1873" height="905" alt="image" src="https://github.com/user-attachments/assets/311086dc-5da8-4d30-a07a-a1c69ead0c7e" />

<img width="1906" height="891" alt="image" src="https://github.com/user-attachments/assets/53189e6e-dcb3-46fe-9ed0-cba4304ea1f5" />

> Every Big Tech started in a garage.

RPG de carreira técnica que leva o player da jornada de **Estagiário a Principal Engineer**, percorrendo as locações reais do Vale do Silício de 1973 a 2026. Criado em HTML5 Canvas com backend FastAPI + PostgreSQL e um motor de execução Java em Spring Boot.

---

## Como rodar localmente

```bash
# 1. Entre na pasta do backend
cd Garage

# 2. Crie e ative o virtualenv
python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# 3. Instale as dependências Python
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env   # edite com suas credenciais

# 5. Suba o servidor
python garage.py
```

O launcher `garage.py` carrega o `.env`, muda o CWD, sobe o Uvicorn com hot-reload na porta **8000** e abre o browser automaticamente em `http://localhost:8000`.

### Java Execution Service (opcional em dev)

```bash
cd Garage/java-runner
mvn spring-boot:run
# Sobe em http://localhost:8080
```

---

## Variáveis de ambiente (`.env`)

| Variável | Exemplo | Descrição |
|----------|---------|-----------|
| `DATABASE_URL` | `postgresql://user:pass@host/db` | PostgreSQL (Neon Serverless em produção) |
| `JWT_SECRET_KEY` | `<uuid aleatório>` | Segredo do token JWT HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | TTL do access token |
| `RESEND_API_KEY` | `re_...` | Chave Resend para envio de e-mail OTP |
| `RESEND_FROM` | `404 Garage <onboarding@resend.dev>` | Remetente verificado |
| `JAVA_RUNNER_URL` | `http://localhost:8080` | URL interna do Java Execution Service |
| `ALLOWED_ORIGINS` | `https://seudominio.com` | CORS permitido em produção |
| `ENV` | `development` ou `production` | Desativa hot-reload em produção |
| `DEBUG` | `true` | Expõe `_debug_otp` nas respostas de auth |
| `PORT` | `8000` | Porta do servidor Python |

---

## Stack técnica

### Backend (Python)

| Pacote | Versão | Uso |
|--------|--------|-----|
| FastAPI | 0.115.0 | Framework HTTP / REST API |
| Uvicorn | 0.34.0 | Servidor ASGI |
| Pydantic | 2.9.0 | Validação de schemas / request bodies |
| SQLAlchemy | >= 2.0.0 | ORM — models em `infrastructure/database/` |
| psycopg2-binary | >= 2.9.0 | Driver PostgreSQL |
| python-jose | >= 3.3.0 | Geração e validação de JWT (HS256) |
| bcrypt | >= 4.0.0 | Hash de senhas (work factor 12) |
| python-dotenv | >= 1.0.0 | Carregamento de `.env` |
| httpx | >= 0.27.0 | HTTP client assíncrono (FastAPI -> Java) |
| resend | >= 2.0.0 | Envio de e-mails transacionais (OTP) |

### Code Execution Service (Java)

| Tecnologia | Versão | Uso |
|-----------|--------|-----|
| Java | 17 (LTS) | Linguagem de ensino do jogo |
| Spring Boot | 3.2.3 | Framework REST embutido |
| JUnit 5 | 5.10 | Runner de testes do código do player |
| javax.tools | JDK 17 | Compilação em memória |
| Maven | 3.9+ | Build e gestão de dependências |

### Frontend

| Tecnologia | Uso |
|-----------|-----|
| HTML5 Canvas 2D | Engine gráfica (sprites, física, câmera) |
| JavaScript ES6 | State machine, input, render loop |
| CSS3 | Layout responsivo, tema CRT amber |
| Monaco Editor (CDN) | Editor de código in-browser na fase CODING |

### Infraestrutura

| Serviço | Uso |
|---------|-----|
| PostgreSQL (Neon Serverless) | Banco principal em produção |
| Render.com | Deploy Web Service Python + Container Java |
| Resend | E-mail transacional (OTP verificação + reset senha) |
| GitHub | Repositório + CI |

---

## Arquitetura DDD

```
Garage/app/
├── domain/              # Entidades puras — zero dependência de framework
│   ├── player.py        # Player, XP, seniority
│   ├── challenge.py     # MCQ e CodingChallenge
│   ├── scoring.py       # Cálculo de score
│   ├── enums.py         # GameState, Role, ActLocation
│   ├── invariant.py     # Guards de domínio
│   └── user.py          # User, OTP, Registration
│
├── application/         # Casos de uso — orquestram domain + infra
│   ├── start_game.py
│   ├── submit_answer.py
│   ├── progress_stage.py
│   ├── event_service.py
│   └── metrics_service.py
│
├── infrastructure/      # Implementações concretas
│   ├── database/        # SQLAlchemy engine + models
│   ├── repositories/    # PlayerRepo, ChallengeRepo, UserRepo
│   ├── auth/            # JWT, bcrypt, brute-force guard
│   └── audit.py         # AuditLogger -> PostgreSQL
│
└── api/routes/          # Adaptadores HTTP (FastAPI)
    ├── auth_routes.py        # /register /login /verify-email /forgot-password
    ├── game_routes.py        # /start /answer /progress /leaderboard
    ├── admin_routes.py       # /admin/* (RBAC: admin only)
    ├── study_routes.py       # /study/chat /study/hint
    ├── code_runner_routes.py # /code/execute -> java-runner
    └── ai_validator_routes.py# /ai/validate
```

**Fluxo de dependências:** `api -> application -> domain <- infrastructure`

---

## Locações (12 no total — 6 Atos)

| Ato | Período | Locação | NPCs | Temas técnicos |
|-----|---------|---------|------|----------------|
| I | 1973 | Xerox PARC | Alan Kay | OOP, Binário, GUI |
| I | 1976 | Apple Garage | Jobs, Wozniak | Algoritmos, Big O, Memória |
| II | 1975 | Harvard / Microsoft | Bill Gates | Estruturas de Dados, Compiladores |
| II | 1994 | Amazon Garage | Jeff Bezos | SQL/ACID, Monolito, Hash |
| III | 1998 | Stanford / Google | Page, Brin | PageRank, Indexação, NoSQL |
| III | 2000 | PayPal / X.com | Elon Musk | OWASP Top 10, Criptografia |
| IV | 2004 | Harvard Dorm | Zuckerberg, Saverin | Grafos, REST, OAuth |
| V | 2015 | AWS Re:Invent | Vogels | Microsserviços, Docker, CAP |
| V | 2016 | MIT 6.824 | Torvalds | Raft, CQRS, Kafka |
| V | 2016 | Google SRE HQ | Ben Treynor | SLI/SLO, Observabilidade |
| VI | 2020 | Enterprise Arch. | Mentor | SOLID, Clean Code, DDD |
| VI | 2026 | The Final Arena | ??? | Refatoração de legado |

---

## Técnicas e Padrões Adotados

- **DDD** (Domain-Driven Design) — camadas domain / application / infrastructure / api
- **Hexagonal Architecture** — portas e adaptadores; domain sem acoplamento externo
- **CQRS** — separação de commands (`submit_answer`) de queries (`leaderboard`)
- **State Machine** — `GameState` enum com transições validadas
- **JWT HS256** com expiração + RBAC `admin/player`
- **bcrypt** work factor 12 + OTP com TTL 15 min para e-mail
- **OWASP Top 10** — checklist em `docs/SECURITY_CHECKLIST.md`
- **GZip middleware** (~70% compressão) + **Cache-Control** por extensão de arquivo
- **Audit log** imutável em PostgreSQL via `infrastructure/audit.py`
- **Brute-force guard** em `infrastructure/auth/bruteforce.py`

---

## Endpoints principais

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/auth/register` | Cadastro + envio OTP por e-mail |
| `POST` | `/api/auth/verify-email` | Confirma OTP |
| `POST` | `/api/auth/login` | Login -> JWT |
| `POST` | `/api/auth/forgot-password` | Envia OTP de reset |
| `POST` | `/api/auth/reset-password` | Redefine senha com OTP |
| `POST` | `/api/game/start` | Inicia sessão de jogo |
| `POST` | `/api/game/answer` | Submete resposta MCQ |
| `POST` | `/api/code/execute` | Executa código Java do player |
| `GET` | `/api/game/leaderboard` | Top players |
| `GET` | `/health` | Health check |
| `GET` | `/api/admin/users` | Lista usuários (admin only) |

---

## Autor

**CeziCola** · Senior Software Engineer  
Bio Code Technology Ltda · cezicolatecnologia@gmail.com
