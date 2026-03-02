# PLANEJAMENTO MASTER: 404 GARAGE (The Engineering Journey)
## "De Estagiário a Principal Engineer"

**Documento de Design Técnico e Pedagógico v3.0**
**Author:** CeziCola · Senior Software Engineer | Bio Code Technology Ltda
**Última atualização:** 02/03/2026
**Target**: Transformar o jogo em uma plataforma completa de formação em Engenharia de Software (nível Staff/Principal).

---

## 1. Visão Geral e Arquitetura

O jogo é um RPG de carreira linear, onde a progressão depende da absorção e prática de conceitos complexos de Ciência da Computação e Engenharia de Software Distribuída.

O player progride por 12 locações históricas do Vale do Silício (1973–2026), enfrentando quizzes técnicos (MCQ), desafios de código Java e chefes que testam arquitetura de sistemas.

### Stack Tecnológica Atual (v3 — Produção)

| Camada | Tecnologia | Versão | Observação |
|--------|-----------|--------|-----------|
| Frontend | HTML5 Canvas 2D | — | Gráficos + física do jogo |
| Frontend | JavaScript ES6 | — | Vanilla JS sem framework |
| Frontend | CSS3 | — | Layout responsivo |
| Frontend | Monaco Editor | via CDN | Editor de código in-browser (fase CODING) |
| Backend API | Python / FastAPI | 3.13 / 0.115.0 | Game logic, auth, leaderboard |
| Backend API | Uvicorn | 0.34.0 | Servidor ASGI com hot-reload |
| Code Runner | Java / Spring Boot | 17 / 3.2.3 | Compila e executa código do jogador |
| Banco de dados | PostgreSQL (Neon Serverless) | 15+ | Produção; JSON files como fallback dev |
| ORM / SQL | SQLAlchemy | 2.0+ | Async-ready; models em `infrastructure/database/` |
| Driver BD | psycopg2-binary | 2.9+ | Conexão síncrona via SQLAlchemy |
| Auth | JWT HS256 | python-jose 3.3+ | Access token com expiração configurável |
| Auth | RBAC | — | Roles: `admin` / `player` |
| Auth | bcrypt | 4.0+ | Hash de senhas (work factor 12) |
| Email | Resend API | resend 2.0+ | OTP de verificação e reset de senha |
| Email from | `onboarding@resend.dev` | — | Domínio verificado (biocodetechnology.com pendente) |
| HTTP client | httpx | 0.27+ | Chamadas internas Python→Java |
| Launcher | `garage.py` | — | Carrega `.env`, `chdir`, abre browser |
| Deploy | Render.com | — | Web Service (Python) + Container (Java) |
| Segredos | `.env` + dotenv | — | DATABASE_URL, JWT_SECRET_KEY, RESEND_API_KEY |

### State Machine do Jogo
```
INTRO → LEARNING → CHALLENGE → CODING → BOSS
```

- **INTRO**: cutscene com o NPC histórico
- **LEARNING**: conteúdo teórico (texto + diagrama)
- **CHALLENGE**: MCQ — múltipla escolha sobre o tema
- **CODING**: editor Monaco + execução Java via Spring Boot
- **BOSS**: desafio de arquitetura integrado (fase final do ato)

### Portas por Serviço (Convenção)
| Serviço | Porta | Comando de start |
|---------|-------|-----------------|
| Python / FastAPI | **8000** | `python garage.py` |
| Java / Spring Boot | **8080** | `mvn spring-boot:run` (dentro de `java-runner/`) |

---

## 2. Cronograma de Cidades e Currículo (The Path)

O jogo será dividido em 6 Atos Históricos, cobrindo 1973 a 2026.

### ATO I: As Fundações (Bit & Bytes)
**Local 1: Xerox PARC (1973) - Palo Alto, CA**
- **NPC**: Alan Kay.
- **Tema**: "Tudo é um Objeto".
- **Currículo**: Binário, Lógica Booleana, OOP Básico, GUI.
- **Desafio**: Consertar o primeiro mouse gráfico.

**Local 2: Apple Garage (1976) - Los Altos, CA**
- **NPC**: Steve Jobs & Steve Wozniak.
- **Tema**: "Eficiência de Recursos".
- **Currículo**: Algoritmos, Notação Big O, Gerenciamento de Memória (Ram vs Disk).
- **Desafio**: Otimizar o boot do Apple I (menos ciclos de clock).

### ATO II: A Ascensão do Software (Estruturas)
**Local 3: Harvard / Microsoft (1975) - Cambridge, MA**
- **NPC**: Bill Gates.
- **Tema**: "Lógica de Negócios".
- **Currículo**: Estruturas de Dados (Arrays, Listas Encadeadas), Condicionais, Compiladores.
- **Desafio**: Escrever um interpretador BASIC simples.

**Local 4: Amazon (1994) - Seattle Garage**
- **NPC**: Jeff Bezos.
- **Tema**: "Escala Logística".
- **Currículo**: Monólitos, Bancos de Dados Relacionais (SQL/ACID), Estruturas de Hash.
- **Desafio**: Criar um sistema de inventário que não trave com 1000 pedidos.

### ATO III: A Web e o Caos (Internet Scale)
**Local 5: Stanford / Google (1998) - Menlo Park**
- **NPC**: Larry Page & Sergey Brin.
- **Tema**: "Organizando a Informação Mundial".
- **Currículo**: Algoritmos de Ordenação, PageRank, Indexação, NoSQL Inicial.
- **Desafio**: Crawled da web eficiente.

**Local 6: PayPal / X.com (2000) - Palo Alto**
- **NPC**: Elon Musk (Jovem).
- **Tema**: "Missão Crítica & Segurança".
- **Currículo**: Segurança (OWASP Top 10), Criptografia Assimétrica, Transações Atômicas.
- **Desafio**: Impedir uma fraude de pagamento em tempo real.

### ATO IV: A Era Social e Mobile (Conexões)
**Local 7: Harvard Dorm Room (2004) - Kirkland House**
- **NPC**: Mark Zuckerberg.
- **Cena Especial (Eduardo Saverin)**: Eduardo aparece para ensinar matemática financeira e o conceito de **Grafo Social** e **Edge Rank** antes do "TheFacebook" ir ao ar.
- **Currículo**: Teoria dos Grafos (BFS/DFS), APIs REST, Autenticação (OAuth).
- **Desafio**: Escalar a rede social para suportar 1 milhão de conexões simultâneas.

### ATO V: Nuvem e Sistemas Distribuídos (The Cloud)
**Local 8: AWS Re:Invent (2015)**
- **NPC**: Werner Vogels.
- **Tema**: "Everything Fails All the Time".
- **Currículo**: Microsserviços, Containers (Docker/K8s), Infrastructure as Code (IaC), CAP Theorem.
- **Desafio**: Desenhar uma arquitetura resiliente que sobrevive ao desligamento de servidores (Chaos Engineering).

**Local 9: MIT 6.824 Class (2009/2016)**
- **NPC**: Robert Morris / Linus Torvalds (Convidado).
- **Tema**: "Consenso Distribuído".
- **Currículo**: Raft Algorithm, Event Sourcing, CQRS, Apache Kafka.
- **Desafio**: Implementar um Log Replicado (Basis of Blockchain/Distributed DBs).

**Local 10: Google SRE HQ (2016) - Mountain View**
- **NPC**: Ben Treynor / SRE Team.
- **Tema**: "Confiabilidade como Feature".
- **Currículo**: SLI/SLO/SLA, Observabilidade, Incident Management, Post-Mortems.
- **Desafio**: Gerenciar um incidente de produção em tempo real (System Down).

### ATO VI: O Arquiteto (2020-2026)
**Local 11: Enterprise Architecture (2020)**
- **NPC**: O "Mentor" (Garage Mentor Aura).
- **Tema**: "Design Limpo e Longevidade".
- **Currículo**: SOLID, Clean Code, DDD (Domain-Driven Design), Hexagonal Architecture.
- **Desafio**: Refatorar um sistema legado gigante sem quebrar a produção.

**Local 12: A Arena Final (2026)**
- **NPC**: ???
- **Plot Twist**: O Chefe Final é **VOCÊ** (O Jogador).
- **Confronto**: Você deve enfrentar o código "ruim" que você escreveu no início do jogo.
- **Objetivo**: Provar que você domina a arquitetura para corrigir seus próprios erros do passado.

---

## 3. Elementos Técnicos Obrigatórios no Gameplay

### 3.1 Cena do Eduardo Saverin (Harvard — Ato IV)
- Cutscene obrigatória no nível de Harvard.
- Foco técnico: explicar como $N$ usuários geram $N^2$ conexões potenciais → teoria dos grafos.
- Ensino de Grafo Social, Edge Rank e BFS/DFS no contexto do TheFacebook.

### 3.2 Mecânica de "Coding Blocks"
- O jogador coleta blocos de código (`if`, `while`, `KafkaProducer`, `RateLimiter`) e os monta para resolver puzzles.
- Ex: _"Para passar pela 'fogueira do tráfego', coloque um bloco `CircuitBreaker` na cadeia."_

### 3.3 Sistema de Senioridade (XP)
- Progressão: `Estagiário → Junior → Mid-Level → Senior → Staff → Principal`.
- O título muda conforme o acerto acumulado em quizzes e desafios de código.
- Exibido no HUD e salvo no perfil PostgreSQL do player.

### 3.4 Chat de IA Pedagógico (feature ativa)
- Rota `/api/study/chat` — player faz perguntas técnicas ao "Mentor".
- Implementado via `study_routes.py` + `ai_validator_routes.py`.
- O contexto da locação atual é injetado no system prompt.

### 3.5 Autenticação Completa (implementada)
- Registro com verificação de e-mail por OTP (6 dígitos, TTL 15 min).
- Login com JWT (`ACCESS_TOKEN_EXPIRE_MINUTES` configurável).
- Reset de senha por e-mail com OTP.
- RBAC: `admin` acessa `/api/admin/`, `player` acessa rotas de jogo.
- Proteção contra brute-force: `infrastructure/auth/bruteforce.py`.
- Auditoria de ações sensíveis: `infrastructure/audit.py`.

### 3.6 Java Execution Service (implementado — `java-runner/`)
- Spring Boot 3.2.3 + Java 17 em container separado.
- `POST /execute` recebe código Java do player + `challenge_id`.
- Compila via `javax.tools`, roda JUnit 5, retorna resultado por teste.
- Sandbox com timeout e sem acesso à rede ou filesystem.
- FastAPI chama o serviço via `httpx` em `code_runner_routes.py`.

### 3.7 Leaderboard Global
- Salvo em PostgreSQL (tabela `leaderboard`).
- Endpoint `GET /api/leaderboard` — top players por score.
- Acessível no menu principal do jogo.

### 3.8 Estilo Visual
- Visual "terminal CRT" — fundo `#0d1117`, amber `#fbbf24`.
- Favicon SVG + logo SVG com identidade `404 Garage`.
- Skins desbloqueáveis planejadas (Moleton do Zuck, Jaqueta Jensen Huang, etc.).

---

## 4. Arquitetura DDD do Backend

```
Garage/app/
├── domain/              # Entidades puras — sem framework, sem I/O
│   ├── player.py        # Player, seniority, XP
│   ├── challenge.py     # Challenge, MCQ, CodingChallenge
│   ├── scoring.py       # ScoreCalculator
│   ├── enums.py         # GameState, Role, ActLocation
│   ├── invariant.py     # Guard functions (validações de negócio)
│   └── user.py          # User, Registration, OTP
│
├── application/         # Casos de uso — orquestram domain + infra
│   ├── start_game.py    # StartGameUseCase
│   ├── submit_answer.py # SubmitAnswerUseCase
│   ├── progress_stage.py# ProgressStageUseCase
│   ├── event_service.py # Publica GameEvents
│   └── metrics_service.py# Coleta métricas de uso
│
├── infrastructure/      # Implementações concretas (BD, Auth, Email)
│   ├── database/        # SQLAlchemy models + engine
│   ├── repositories/    # PlayerRepo, ChallengeRepo, UserRepo
│   ├── auth/            # JWT utils, bcrypt, brute-force guard
│   └── audit.py         # AuditLogger → PostgreSQL
│
└── api/routes/          # Adaptadores HTTP (FastAPI)
    ├── auth_routes.py   # /register, /login, /verify-email, /forgot-password
    ├── game_routes.py   # /start, /answer, /progress, /leaderboard
    ├── admin_routes.py  # /admin/users, /admin/challenges
    ├── study_routes.py  # /study/chat, /study/hint
    ├── code_runner_routes.py  # /code/execute → java-runner
    └── ai_validator_routes.py # /ai/validate
```

**Princípio de dependências:** `api → application → domain ← infrastructure`
A camada `domain` não importa NADA de fora. Toda inversão de dependência via interfaces em `application/`.

---

## 5. Próximos Passos de Desenvolvimento (Action Plan)

### Curto prazo (sprint atual)
- [ ] Testar flow completo de registro → verificação OTP → login → play em produção (Render)
- [ ] Confirmar domínio `biocodetechnology.com` no Resend para resolver spam de OTP
- [ ] Implementar cutscene Eduardo Saverin (Ato IV — Harvard)
- [ ] Adicionar testes de integração para `code_runner_routes.py`

### Médio prazo
- [ ] Implementar skins desbloqueáveis (visual layer sobre o sprite base)
- [ ] Cena "Post-Mortem de Incidente" — Ato V (Google SRE)
- [ ] Métricas de observabilidade: Prometheus endpoint em `/metrics`
- [ ] Refresh token com revogação persistida em PostgreSQL

### Longo prazo
- [ ] Modo Local Co-op (2 players, mesmo challenge, quem passa primeiro avança)
- [ ] Exportar "Portfólio Técnico" do player como PDF (tecnologias dominadas)
- [ ] Marketplace de skins e certificados NFT (blockchain — Ato VI)

---

## 6. Convenções de Desenvolvimento

- **Commits:** `tipo(escopo): descrição` + `Evidência:` + `Trade-off:` + `Testes:`
- **Segredos:** NUNCA commitados. `.env` + `.gitignore`.
- **Idioma do código:** inglês. Comunicação com usuário: pt-BR.
- **Testes:** `pytest Garage/app` antes de qualquer commit.
- **Pré-deploy:** `python Garage/scripts/validate_final.py` + `node Garage/test_all_challenges.js`.
- **Runtime files fora do git:** `leaderboard.json`, `sessions.json`, `users.json`.

---
*Este plano serve como a "Bíblia" do projeto 404 Garage — atualizado em 02/03/2026.*
