# JORNADA 2 — OS MESTRES DA ENGENHARIA
## Especificação Completa de Design e Implementação
### 404 Garage · Bio Code Technology Ltda · CeziCola
**Versão:** 1.0 · **Data:** 02/03/2026 · **Status:** Aprovado para Implementação

---

## AVISO DE IMPLEMENTAÇÃO

> Este documento é a fonte da verdade para a Jornada 2.
> **Nenhuma linha do código existente da Jornada 1 deve ser removida ou alterada.**
> Toda implementação é **aditiva**: novos dados em `challenges.json`, nova flag `journey: 2`
> nos registros, novo campo `journey_2_stage` no perfil do player.
> Os cenários, a engine, o Monaco Editor, o GARAGE AI, o sistema de MCQ e o State Machine
> são **reaproveitados integralmente**. Apenas NPC, conteúdo e dados mudam.

---

## 1. A TELA DE CONGRATULATIONS E O TWIST

### 1.1 Fluxo após completar a Jornada 1

```
[Boss Final - Ato VI - Jornada 1]
           │
           │ player vence
           ▼
[TELA: CONGRATULATIONS]
  - Animação de confete + trilha sonora épica
  - Título: "PRINCIPAL ENGINEER — Jornada 1 Completa"
  - Score final + ranking no leaderboard global
  - Resumo: X desafios, Y linhas de código, Z empresas visitadas
  - Badge desbloqueado: "Conhece a História"
           │
           │ (após 5s ou clique)
           ▼
[MODAL: O TWIST]
  Texto que aparece letra por letra (efeito máquina de escrever):

  "Você aprendeu ONDE e QUANDO a computação evoluiu.
   Você conheceu os CEOs que construíram o Vale do Silício.

   Mas existe uma pergunta que nenhum CEO respondeu:

   COMO eles pensavam?

   Os segredos reais não estão nas garagens.
   Eles estão nos livros que esses engenheiros leram,
   sublinharam e levaram para suas mesas de trabalho.

   Existe uma segunda camada desta jornada.
   Os Mestres te aguardam. Nas mesmas empresas.
   Com os mesmos desafios. Mas agora você é Senior.

   E eles vão te mostrar como pensar."

           │
           ▼
[BOTÃO]: "INICIAR JORNADA 2 — OS MESTRES"
[BOTÃO SECUNDÁRIO]: "Voltar ao Menu" (jogador pode adiar)
```

### 1.2 O que acontece ao clicar "INICIAR JORNADA 2"

1. Backend registra `journey_2_unlocked = true` no perfil do player
2. Seniority é **travada em "Senior"** para toda a Jornada 2 (não regride, não avança)
3. O jogo recarrega do Ato I mas com `journey = 2` no estado da sessão
4. A locação é **Xerox PARC (1973)** — o mesmo cenário, mas o NPC agora é **Uncle Bob**
5. Uma faixa no HUD indica: `▸ JORNADA 2 · SENIOR ENGINEER · OS MESTRES`

---

## 2. OS 24 LIVROS — FONTE DE VERDADE

Todo MCQ, todo live coding, todo diálogo de NPC da Jornada 2 é baseado **exclusivamente**
nestes 24 livros. Nenhum conteúdo pode ser inventado fora desta lista.

| # | Livro | Autor(es) | Ano | Qtd Livros do Autor |
|---|-------|-----------|-----|-------------------|
| 1 | A Discipline of Programming | Edsger W. Dijkstra | 1976 | 1 |
| 2 | The Art of Computer Programming (Vol. 1–4) | Donald E. Knuth | 1968–2011 | 4 volumes → 4× expansão |
| 3 | Structure and Interpretation of Computer Programs (SICP) | Abelson & Sussman | 1985 | 1 |
| 4 | The Mythical Man-Month | Frederick P. Brooks Jr. | 1975 | 1 |
| 5 | Code Complete (2ª ed.) | Steve McConnell | 2004 | 1 |
| 6 | Design Patterns: Elements of Reusable OO Software | Gamma, Helm, Johnson, Vlissides (GoF) | 1994 | 1 |
| 7 | The Pragmatic Programmer (20th Anniversary) | Hunt & Thomas | 1999 | 1 |
| 8 | Refactoring: Improving the Design of Existing Code | Martin Fowler | 1999 | 2 |
| 9 | Patterns of Enterprise Application Architecture | Martin Fowler | 2002 | 2 |
| 10 | Extreme Programming Explained | Kent Beck | 1999 | 3 |
| 11 | TDD by Example | Kent Beck | 2002 | 3 |
| 12 | Implementation Patterns | Kent Beck | 2007 | 3 |
| 13 | Working Effectively with Legacy Code | Michael C. Feathers | 2004 | 1 |
| 14 | Domain-Driven Design (Blue Book) | Eric J. Evans | 2003 | 1 |
| 15 | Agile Software Development: Principles, Patterns & Practices | Robert C. Martin | 2002 | 4 |
| 16 | Clean Code | Robert C. Martin | 2008 | 4 |
| 17 | The Clean Coder | Robert C. Martin | 2011 | 4 |
| 18 | Clean Architecture | Robert C. Martin | 2017 | 4 |
| 19 | Designing Data-Intensive Applications | Martin Kleppmann | 2017 | 1 |
| 20 | The Phoenix Project | Gene Kim, Behr, Spafford | 2013 | 3 |
| 21 | The DevOps Handbook | Gene Kim, Humble, Willis, Debois | 2016 | 3 |
| 22 | Accelerate | Nicole Forsgren, Jez Humble, Gene Kim | 2018 | 3 |
| 23 | Site Reliability Engineering | Google SRE Team (Beyer et al.) | 2016 | 2 |
| 24 | The Site Reliability Workbook | Google SRE Team | 2018 | 2 |

> **Nota sobre o livro de live coding esquecido:** O livro provável é
> *"Programming Pearls"* de Jon Bentley (1986) ou *"Cracking the Coding Interview"*
> de Gayle Laakmann McDowell. Se confirmado pelo autor, deve ser inserido como
> **Livro Bônus** na localização MIT 6.824 com 1 live coding adicional.
> Campo reservado: `challenge_type: "coding_pearls"` em `challenges.json`.

---

## 3. DISTRIBUIÇÃO MATEMÁTICA — A REGRA DOS LIVROS

### Princípio

> Se o AUTOR tem **N livros** na lista dos 24, o encontro com ele terá **N sessões de live coding**.
> Cada sessão é uma "expansão" — mesma mecânica de IDE + testes JUnit, conteúdo diferente.

### Tabela de Expansões por Autor

| Autor | Livros | Live Codings | Tipo |
|-------|--------|-------------|------|
| Edsger Dijkstra | 1 | 1 sessão | Único |
| Donald Knuth | 4 volumes | 4 sessões | Expansão ×4 |
| Abelson & Sussman | 1 | 1 sessão | Único |
| Fred Brooks | 1 | 1 sessão | Único |
| Steve McConnell | 1 | 1 sessão | Único |
| Gang of Four (GoF) | 1 | 1 sessão | Único |
| Hunt & Thomas | 1 | 1 sessão | Único |
| Martin Fowler | 2 | 2 sessões | Expansão ×2 |
| Kent Beck | 3 | 3 sessões | Expansão ×3 |
| Michael Feathers | 1 | 1 sessão | Único |
| Eric Evans | 1 | 1 sessão | Único |
| Robert C. Martin (Uncle Bob) | 4 | 4 sessões | Expansão ×4 |
| Martin Kleppmann | 1 | 1 sessão | Único |
| Gene Kim et al. | 3 | 3 sessões | Expansão ×3 |
| Google SRE Team | 2 | 2 sessões | Expansão ×2 |
| **CeziCola (Boss Final)** | — | 1 sessão | Meta-revisão |

**Total de live codings na Jornada 2: 29 sessões**
(1+4+1+1+1+1+1+2+3+1+1+4+1+3+2+1 = 28 + 1 CeziCola = **29**)

### Como funciona a Expansão

Quando um autor tem N livros, a sequência na locação é:

```
INTRO (NPC aparece, cita o livro 1)
  → MCQ livro 1 (5 perguntas)
  → LIVE CODING 1 (desafio baseado no livro 1)
  → [se N >= 2]: "expansão desbloqueada" — NPC cita o livro 2
  → MCQ livro 2 (5 perguntas)
  → LIVE CODING 2
  → [se N >= 3]: repetir
  → BOSS (desafio integrado — aplica conceitos de todos os livros do autor)
```

Para autores com 1 livro:
```
INTRO → MCQ (10 perguntas — mais denso) → LIVE CODING → BOSS
```

---

## 4. MAPEAMENTO: LOCAÇÃO × AUTOR × LIVROS

A cronologia respeita tanto o ano da empresa quanto o ano de publicação do livro
(o Mestre que recebe o player é o mais relevante para aquela era histórica).

---

### LOCAÇÃO 1 — Xerox PARC (1973)
**Mestre:** Robert C. Martin — Uncle Bob
**Razão histórica:** O Xerox PARC inventou a OOP. Uncle Bob dedicou sua vida a
ensinar como usar OOP corretamente. É o encontro natural: onde nasceu o objeto,
nasce a disciplina de usá-lo bem.

**Expansões: 4× (4 livros)**

| Expansão | Livro | Tema Central | Live Coding |
|----------|-------|-------------|-------------|
| 1 | Agile Software Development (2002) | Princípios SOLID, coesão, coupling | Refatorar uma classe que viola SRP e OCP |
| 2 | Clean Code (2008) | Nomes, funções pequenas, comentários | Renomear + Extract Method em código sujo |
| 3 | The Clean Coder (2011) | Profissionalismo, dizer não, estimativas | Código com deadline: player escolhe o que cortar sem quebrar invariantes |
| 4 | Clean Architecture (2017) | Dependency Rule, Clean Architecture diagram | Implementar porta + adaptador desacoplando domain de infra |

**MCQ base (por expansão):** 5 perguntas por livro = 20 questões no total nesta locação.

**Diálogo de abertura Uncle Bob:**
> *"Você passou pela Xerox PARC como estagiário e viu o mouse, a GUI, o objeto.
> Mas ninguém te disse como escrever um objeto que dure 20 anos.
> Sente-se. Vou mostrar."*

**BOSS da Locação 1:**
- Código com 200 linhas em 1 classe, violando todos os SOLID, sem testes
- Player deve: extrair interfaces, separar responsabilidades, mover para camadas corretas
- JUnit suite com 8 testes — todos devem passar no final

---

### LOCAÇÃO 2 — Apple Garage (1976)
**Mestre:** Donald E. Knuth
**Razão histórica:** Jobs e Woz otimizaram para o hardware. Knuth é o pai da análise
de algoritmos — a linguagem que torna possível falar sobre eficiência com precisão.

**Expansões: 4× (4 volumes TAOCP)**

| Expansão | Volume TAOCP | Tema Central | Live Coding |
|----------|-------------|-------------|-------------|
| 1 | Vol. 1 — Fundamental Algorithms | Estruturas de dados, análise de complexidade | Implementar uma lista ligada com operações O(1) documentadas |
| 2 | Vol. 2 — Seminumerical Algorithms | Geração de números aleatórios, aritmética | Implementar LCG (Linear Congruential Generator) com análise de período |
| 3 | Vol. 3 — Sorting and Searching | QuickSort, MergeSort, B-Trees | Implementar e comparar 2 algoritmos de ordenação com Big O anotado |
| 4 | Vol. 4 — Combinatorial Algorithms | Grafos, SAT, backtracking | Resolver permutação com backtracking comentado linha a linha |

**Diálogo de abertura Knuth:**
> *"Jobs queria que fosse rápido. Mas 'rápido' sem medida não é engenharia.
> Aqui você vai aprender a PROVAR que é rápido. Com matemática.
> Cada algoritmo que você escrever daqui para frente, você vai saber o custo exato."*

**BOSS da Locação 2:**
- Input: 10.000 registros desordenados
- Código inicial: bubble sort O(n²)
- Player deve: reescrever para O(n log n), documentar com análise de complexidade
- Validação automática: performance test (tempo de execução medido no java-runner)

---

### LOCAÇÃO 3 — Harvard / Microsoft (1975)
**Mestre:** Frederick P. Brooks Jr. + Steve McConnell (2 Mestres, 2 livros únicos)

> **Regra especial:** Quando 2 Mestres com 1 livro cada ocupam a mesma locação,
> o encontro é sequencial: Brooks primeiro (cronológico), McConnell depois.
> Cada um tem seu INTRO, MCQ (10 perguntas) e LIVE CODING próprio.

**Expansões: 1× Brooks + 1× McConnell**

**Brooks — The Mythical Man-Month (1975):**

| Fase | Conteúdo |
|------|---------|
| INTRO | Brooks aparece: *"Gates entrou nesta sala com linhas de código. Você vai entrar com algo mais valioso: saber quando NÃO escrever código."* |
| MCQ (10) | Lei de Brooks, No Silver Bullet, Second-System Effect, conceito de "surgical team", estimativas de software |
| LIVE CODING | Simulação: player recebe um projeto atrasado, deve decidir escopo/recursos. O código representa a arquitetura — adicionar classe = adicionar dev. Player escolhe o que REMOVER para entregar. JUnit valida que o núcleo ainda funciona. |
| BOSS Brooks | Escrever um ADR (Architecture Decision Record) justificando uma remoção de feature. Avaliado por critérios: clareza, impacto, alternativas consideradas |

**McConnell — Code Complete 2ª ed. (2004):**

| Fase | Conteúdo |
|------|---------|
| INTRO | McConnell: *"Brooks te ensinou o QUE não fazer. Eu vou te ensinar o COMO fazer bem, linha a linha."* |
| MCQ (10) | Construção defensiva, pseudocódigo antes de codificar, debugging por hipótese, inspeções de código, complexidade ciclomática |
| LIVE CODING | Recebe um método de 80 linhas. Deve: (1) escrever pseudocódigo antes de modificar, (2) extrair para métodos com complexidade ciclomática ≤ 5, (3) adicionar assertions defensivas. Tudo com comentário pedagógico inline. |
| BOSS McConnell | Code review de um PR com 5 problemas clássicos do Code Complete escondidos. Player deve identificar todos os 5. |

---

### LOCAÇÃO 4 — Amazon Garage (1994)
**Mestre:** Gang of Four — Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides
**Razão histórica:** 1994 — o mesmo ano da Amazon e do livro. A Amazon construiu
seu catálogo de produtos com padrões que o GoF acabara de nomenclar.

**Expansões: 1× (1 livro)**

| Fase | Conteúdo |
|------|---------|
| INTRO | Os 4 autores aparecem em sequência, cada um revelando uma categoria de padrão: Criacional, Estrutural, Comportamental, + a meta-ideia de "program to an interface, not an implementation" |
| MCQ (10) | Identificar padrão correto para um problema, diferença entre Decorator e Proxy, quando usar Factory vs Abstract Factory, Strategy vs State, Observer vs Mediator |
| LIVE CODING | Sistema de pedidos Amazon com Strategy para cálculo de frete, Observer para notificação de status, Factory para tipos de produto. Player implementa os 3 padrões com JUnit validando o comportamento polimórfico |
| BOSS GoF | Recebe um código monolítico com if/else gigante. Deve identificar qual padrão resolve, refatorar aplicando o padrão, sem alterar os testes existentes. |

---

### LOCAÇÃO 5 — Stanford / Google (1998)
**Mestre:** Andrew Hunt & David Thomas
**Razão histórica:** O Pragmatic Programmer saiu em 1999, mesmo ano em que o Google
foi incorporado. Os princípios pragmáticos moldaram a geração de devs que construiu
a internet moderna.

**Expansões: 1× (1 livro — 2 autores, 1 obra conjunta)**

| Fase | Conteúdo |
|------|---------|
| INTRO | Hunt e Thomas aparecem juntos: *"Não existem respostas ertas. Existem trade-offs não examinados."* |
| MCQ (10) | DRY vs. "three strikes and you automate", Orthogonality, Tracer Bullets vs Prototypes, Broken Windows, "Programming by Coincidence" vs intencionalidade, contratos (Design by Contract) |
| LIVE CODING | Crawler de URLs com duplicação proposital. Player deve: identificar violação DRY, extrair abstração ortogonal, adicionar contrato (@throws documentado). Final: comparar a versão Tracer Bullet (funciona, simples) vs a versão "certa" (robusta). |
| BOSS Hunt & Thomas | Código com 3 "broken windows" (dead code, magic numbers, copy-paste logic). Player deve reparar todas sem introduzir novos problemas. Testes JUnit validam. |

---

### LOCAÇÃO 6 — PayPal / X.com (2000)
**Mestre:** Martin Fowler
**Razão histórica:** A virada do milênio foi a explosão das enterprise applications.
Fowler formalizou os padrões que sustentam esses sistemas no PoEAA (2002).
Refactoring (1999) chegou logo antes — a segurança de mudar sem quebrar.

**Expansões: 2× (2 livros)**

| Expansão | Livro | Tema Central | Live Coding |
|----------|-------|-------------|-------------|
| 1 | Refactoring (1999) | Catálogo de refactorings nomeados, test harness antes de refatorar | Código com 4 smells nomeados (Feature Envy, Long Method, God Class, Primitive Obsession). Player aplica o refactoring correspondente do catálogo de Fowler por nome. |
| 2 | PoEAA (2002) | Transaction Script vs Domain Model, Repository, Unit of Work, Identity Map, Lazy Load | Implementar Repository Pattern + Unit of Work para um sistema de pagamentos simples. |

**Diálogo de abertura Fowler:**
> *"Musk queria mudar o dinheiro. Você vai aprender a mudar código sem medo.
> Todo refactoring que eu cataloguei tem um nome. Use o nome. Comunique-se com precisão."*

**BOSS Fowler:**
- Sistema PayPal em miniatura: Transaction Script com lógica de negócio no controller
- Player deve migrar para Domain Model usando os padrões do PoEAA
- Constraint: todos os testes existentes devem permanecer verdes durante CADA passo da migração

---

### LOCAÇÃO 7 — Harvard Dorm Room (2004)
**Mestre:** Kent Beck
**Razão histórica:** O Facebook foi construído em ciclos curtos de feedback — a essência
do XP e do TDD. 2004 é o ano perfeito: TDD by Example saiu em 2002, XP Explained em 1999.

**Expansões: 3× (3 livros)**

| Expansão | Livro | Tema Central | Live Coding |
|----------|-------|-------------|-------------|
| 1 | Extreme Programming Explained (1999) | Customer collaboration, pair programming, 10-minute build, simple design | Implementar feature de "adicionar amigo" com regras de negócio simples. O player DEVE escrever o teste antes do código (jogo bloqueia submit se teste não existir antes da implementação). |
| 2 | TDD by Example (2002) | Red-Green-Refactor, fake it till you make it, triangulation | Money example do livro: implementar a classe Money com igualdade, conversão de moeda e operações aritméticas. Sequência rigorosa: RED → GREEN → REFACTOR para cada micro-feature. |
| 3 | Implementation Patterns (2007) | Class, state, behavior, collections — padrões de implementação no nível do código | Código com padrões implícitos. Player deve torná-los explícitos: nomear corretamente, extrair Method Object, aplicar Composed Method. |

**Regra especial do Kent Beck:**
> Em TODO live coding do Kent Beck, a IDE mostra um semáforo:
> - 🔴 RED: existe teste falhando → pode escrever código de produção
> - 🟢 GREEN: testes passando → só pode refatorar
> - 🔵 REFACTOR: refatorando → não pode quebrar verde
>
> Se o player tentar submeter código sem seguir a sequência, o GARAGE AI bloqueia e explica.

**Diálogo de abertura Kent Beck:**
> *"Zuckerberg iterava todo dia. Mas sem testes, iteração rápida é só bagunça rápida.
> Você vai aprender a ter coragem de mudar — porque os testes te protegem."*

**BOSS Kent Beck:**
- Kata completo: FizzBuzz → mas com regras de negócio: múltiplos de 7 = "Garage", múltiplos de 13 = "404"
- Exigência: 100% TDD. O GARAGE AI lê a sequência de commits e verifica se RED veio antes de GREEN em cada passo
- Falhar a sequência = score penalizado (não bloqueado, mas penalizado)

---

### LOCAÇÃO 8 — AWS Re:Invent (2015)
**Mestre:** Gene Kim et al.
**Razão histórica:** DevOps como movimento começou em 2009 (DevOpsDays).
The Phoenix Project chegou em 2013. O Re:Invent de 2015 foi o ápice da cultura DevOps.

**Expansões: 3× (3 livros)**

| Expansão | Livro | Tema Central | Live Coding |
|----------|-------|-------------|-------------|
| 1 | The Phoenix Project (2013) | Three Ways of DevOps (Flow, Feedback, Continual Learning), visualizar o trabalho, eliminar bottlenecks | Simulação: pipeline CI/CD quebrado. Player deve identificar o constraint (Teoria das Restrições aplicada a software), fazer o código passar por todas as gates. |
| 2 | The DevOps Handbook (2016) | Build quality in, telemetria, feature flags, deployment pipeline | Implementar feature flag simples em Java (FeatureToggle) + adicionar log estruturado em JSON com campos: timestamp, user_id, feature, value. Deve passar nos testes de integração. |
| 3 | Accelerate (2018) | DORA metrics: deployment frequency, lead time, MTTR, change failure rate | Dado um histórico de deploys (JSON), player escreve código que calcula as 4 DORA metrics. JUnit valida os valores calculados. |

**Diálogo de abertura Gene Kim:**
> *"Vogels disse que tudo falha. Eu vou te ensinar o que fazer ANTES de falhar.
> O pipeline não é burocracia. É a velocidade que te permite ter coragem de deployar toda hora."*

**BOSS Gene Kim:**
- Código de um sistema de deploy manual (sem testes, sem pipeline, sem feature flags)
- Player deve: adicionar testes, criar FeatureToggle para a nova feature, adicionar logging estruturado
- Meta-validação: o GARAGE AI calcula o "lead time" da solução do player (tempo do primeiro commit ao teste verde)

---

### LOCAÇÃO 9 — MIT 6.824 (2016)
**Mestre:** Martin Kleppmann + Livro Bônus de Live Coding
**Razão histórica:** Designing Data-Intensive Applications (2017) é o livro que
formalizou o que os sistemas distribuídos de 2016 faziam na prática.

**Expansões: 1× Kleppmann + 1× Bônus**

**Kleppmann — Designing Data-Intensive Applications:**

| Fase | Conteúdo |
|------|---------|
| INTRO | Kleppmann: *"Torvalds te ensinou como o kernel funciona. Eu vou te ensinar o que acontece quando o kernel de 100 máquinas precisa concordar em algo."* |
| MCQ (10) | Replication vs Partitioning, eventual consistency, CAP Theorem na prática, Lamport timestamps, write-ahead log, two-phase commit vs Saga, stream processing vs batch |
| LIVE CODING | Implementar um sistema de leaderboard distribuído em Java: (1) aceita writes concorrentes, (2) usa um log append-only como source of truth, (3) Read replica que consome o log. JUnit com testes de concorrência (CountDownLatch). |
| BOSS Kleppmann | Dado um sistema que perde dados sob network partition: player deve identificar a violação do CAP, escolher CP ou AP com justificativa inserida como comentário, e implementar o fix correspondente. |

**Livro Bônus — Programming Pearls (Jon Bentley, 1986) / Cracking the Coding Interview:**
> *(Confirmar o título com o autor do jogo antes de implementar)*
> Campo: `"challenge_type": "coding_pearls"` — reservado no schema.
> Conteúdo: desafio de otimização algorítmica "estilo entrevista" onde o player
> resolve um problema em 3 rounds: brute force → otimizado → perfeito.

---

### LOCAÇÃO 10 — Google SRE HQ (2016)
**Mestre:** Google SRE Team (Beyer, Jones, Petoff, Murphy)
**Razão histórica:** O livro SRE saiu em 2016, escrito pelos próprios engenheiros do Google.
Esta é a locação mais autorreferencial: os Mestres SÃO os engenheiros Google.

**Expansões: 2× (2 livros)**

| Expansão | Livro | Tema Central | Live Coding |
|----------|-------|-------------|-------------|
| 1 | Site Reliability Engineering (2016) | SLI/SLO/SLA, Error Budget, Toil elimination, Postmortem sem culpa | Dado um SLO de 99.9% uptime/mês: player calcula o error budget em minutos, implementa um SLI calculator em Java (minutos de downtime → percentage), escreve o template de postmortem para um incidente fictício. |
| 2 | The Site Reliability Workbook (2018) | SLO alerting, CUJ (Critical User Journeys), reliability roadmap | Dado um sistema sem SLOs: player define 3 CUJs, deriva os SLIs corretos, implementa um alert threshold calculator. JUnit valida os valores com tolerância de ±0.01%. |

**Diálogo de abertura SRE Team:**
> *"Você viu o Google nascer como Intern. Agora veja como o Google não morre.
> Reliability não é acidente. É disciplina matemática. Aprenda a calcular coragem."*

**BOSS SRE:**
- Simulação de incidente: sistema com latência crescendo (dados mock injetados)
- Player deve: (1) identificar o SLO violado, (2) calcular quanto do error budget foi consumido, (3) escrever a ação de mitigação como código (circuit breaker simples), (4) escrever o postmortem em comentário estruturado

---

### LOCAÇÃO 11 — Enterprise Architecture (2020)
**Mestre:** Eric Evans + Michael Feathers
**Razão histórica:** DDD é o culminar do pensamento sobre modelagem de domínio.
Feathers é o guia para quando o DDD encontra o legado que já existe.

**Expansões: 1× Evans + 1× Feathers**

**Eric Evans — Domain-Driven Design (Blue Book):**

| Fase | Conteúdo |
|------|---------|
| INTRO | Evans: *"Você passou por 10 empresas sem saber que cada uma falava uma linguagem diferente. Agora você vai aprender a lingua do domínio."* |
| MCQ (10) | Ubiquitous Language, Bounded Context, Aggregate Root, Domain Event, Anti-Corruption Layer, Context Map, Value Object vs Entity, Repository no sentido DDD |
| LIVE CODING | Modelar o domínio de um sistema bancário: identificar os 3 Bounded Contexts (Conta, Transação, Notificação), implementar o Aggregate Root `Conta` com invariantes, implementar um Domain Event `TransacaoRealizada`. Tudo sem acoplamento a Spring/FastAPI. |
| BOSS Evans | Dado código com anemia de domínio (lógica no service, entidades só com getters/setters): player deve mover a lógica para dentro do domínio, preservando todos os testes. |

**Michael Feathers — Working Effectively with Legacy Code:**

| Fase | Conteúdo |
|------|---------|
| INTRO | Feathers: *"Evans te deu o ideal. Eu vou te dar a realidade. A maioria do código que você vai encontrar não tem testes, não tem domínio, e não vai embora. Você vai aprender a trabalhar COM ele."* |
| MCQ (10) | Definition of legacy code (sem testes), seam, characterization tests, sprout method, wrap method, sensing vs separation, dependency-breaking techniques |
| LIVE CODING | Recebe código legado sem nenhum teste (uma classe de 150 linhas acoplada a banco). Deve: (1) escrever characterization tests sem alterar o comportamento, (2) criar um seam usando Extract Interface, (3) substituir a dependência real por um fake no teste. |
| BOSS Feathers | O BOSS narrativo máximo: o código legado que o player está recebendo **é o código que ele mesmo escreveu no Ato I como estagiário**. O jogo exibe side-by-side a versão antiga e o player deve refatorá-la usando as técnicas de Feathers. |

---

### LOCAÇÃO 12 — The Final Arena (2026)
**Mestre de Estágio:** Edsger Dijkstra + Abelson & Sussman (preâmbulo dos fundamentos)
**BOSS FINAL:** CeziCola

#### Estágio 12a — Dijkstra (A Discipline of Programming)

| Fase | Conteúdo |
|------|---------|
| INTRO | Dijkstra: *"Todos esses anos, você seguiu receitas. Agora eu quero que você PROVE que seu código está correto. Sem testes. Com lógica."* |
| MCQ (10) | Correctness by construction, loop invariants, pre/post conditions, "Testing shows presence of bugs not absence", goto considered harmful, structured programming, formal reasoning sobre código |
| LIVE CODING | Implementar BubbleSort com LOOP INVARIANT documentado como assertion Java (`assert`), pre-condition e post-condition anotadas como JavaDoc `@requires` / `@ensures`. JUnit verifica que as assertions são semanticamente corretas via teste de propriedade. |

#### Estágio 12b — Abelson & Sussman (SICP)

| Fase | Conteúdo |
|------|---------|
| INTRO | Sussman: *"Você aprendeu Java. Mas linguagem de programação é apenas notação. A ideia que você precisa gravar é: computation is about managing complexity through abstraction."* |
| MCQ (10) | Procedural vs data abstraction, higher-order functions, closures como acumuladores de estado, streams lazy, metacircular evaluator, "wishful thinking" como estratégia de design |
| LIVE CODING | Em Java (usando lambdas/streams): implementar map, filter, reduce sem usar a biblioteca padrão. Depois: implementar um interpretador simples de expressões aritméticas (eval de AST). Demonstrar como a MESMA estrutura funciona para inteiros e para strings. |

---

### BOSS FINAL — CeziCola

**Local:** The Final Arena (2026) — palco vazio, iluminação de spotlight, sem empresas.

**Narrativa:**

```
CeziCola aparece como uma silhueta digital com o logo 404 Garage atrás.

"Você foi à Xerox PARC como estagiário. Viu o mouse, a GUI.
Voltou como Junior. Aprendeu com Jobs. Com Gates. Com Bezos.

Depois voltou de novo. Como Senior.
Uncle Bob te deu Clean Code. Kent Beck te deu TDD.
Fowler te deu a linguagem do refactoring. Evans te deu DDD.
Feathers te deu coragem diante do legado.
Dijkstra te deu precisão. Knuth te deu análise.

Agora vamos ver se você aprendeu
ou apenas passou pelos andares sem subir de verdade."
```

**BOSS FINAL — CeziCola — Estrutura:**

O boss tem **5 rounds**. Cada round testa um nível da pirâmide de conhecimento.

| Round | O que testa | Fonte |
|-------|------------|-------|
| 1 — Code Review | Player recebe código com 7 problemas: 3 de Clean Code, 2 de Pragmatic Programmer, 2 de GoF mal aplicados. Identifica todos. | Livros da Jornada 2 |
| 2 — TDD Obrigatório | Feature nova em sistema legado. Player: escreve seam (Feathers), escreve teste RED (Beck), faz GREEN, refatora (Fowler). Sequência verificada pelo GARAGE AI. | Beck + Feathers + Fowler |
| 3 — System Design | Desenhar em texto estruturado (não diagrama, mas código!) a arquitetura de um sistema: Bounded Contexts (Evans), Repository Pattern (Fowler PoEAA), Observability (SRE Team), Feature Flag (Gene Kim). Player escreve os contratos Java (interfaces). | Evans + Fowler + Kim + SRE |
| 4 — Algoritmo com Prova | Implementar Dijkstra's Shortest Path com loop invariant documentado (homenagem ao Dijkstra), análise Big O no JavaDoc (Knuth), refatoração a seguir com Extract Method (Fowler). | Dijkstra + Knuth + Fowler |
| 5 — ADR Final | Escrever um Architecture Decision Record sobre a decisão mais importante que o player tomou durante a Jornada 2. Formato livre. Avaliado pelo GARAGE AI com critérios: problema descrito, alternativas, trade-offs, decisão, consequências. | Brooks + todos |

**Vitória:**
```
CeziCola:
"Você veio como estagiário. Virou Junior. Depois Senior.
Agora você pensa como um engenheiro.

Não porque seguiu um tutorial.
Mas porque enfrentou os Mestres
e sobreviveu com a cabeça cheia de modelos mentais.

Esse é o diferencial.
Você não apenas sabe CRIAR software.
Você sabe PENSAR sobre software.

Bem-vindo. Principal Engineer."

[BADGE]: "PRINCIPAL ENGINEER — OS MESTRES"
[Leaderboard separado]: Jornada 2 — Top Masters Architects
```

---

## 5. ESPECIFICAÇÃO TÉCNICA DE IMPLEMENTAÇÃO

### 5.1 Schema de challenges.json — Jornada 2

Adicionar o campo `journey: 2` em todos os challenges da Jornada 2.
**Nenhum challenge existente (journey: 1) deve ser alterado.**

```json
{
  "id": "j2_xerox_uncle_bob_solid_srp",
  "journey": 2,
  "act": 1,
  "location": "xerox_parc",
  "master": "uncle_bob",
  "book": "clean_code",
  "book_expansion": 2,
  "type": "mcq",
  "question": "Qual dos seguintes métodos viola o Single Responsibility Principle?",
  "options": [
    "A) processPaymentAndSendEmail()",
    "B) processPayment()",
    "C) sendPaymentConfirmationEmail()",
    "D) calculatePaymentTotal()"
  ],
  "correct": 0,
  "explanation": "O método A viola SRP porque tem duas responsabilidades: processar pagamento E enviar email. Fonte: Clean Code, Cap. 10 — Classes.",
  "source_book": "Clean Code — Robert C. Martin — Cap. 10",
  "difficulty": "senior"
}
```

```json
{
  "id": "j2_xerox_uncle_bob_coding_1",
  "journey": 2,
  "act": 1,
  "location": "xerox_parc",
  "master": "uncle_bob",
  "book": "agile_software_dev",
  "book_expansion": 1,
  "type": "coding",
  "title": "Aplicar SRP — Extrair Responsabilidades",
  "description": "A classe abaixo tem 3 responsabilidades. Refatore para 3 classes seguindo SRP.\nFonte: Agile Software Development — Robert C. Martin — Cap. 8",
  "starter_code": "// VIOLA SRP: esta classe faz persistência, validação e envio de email\npublic class UserRegistration {\n    public void register(String name, String email) {\n        // valida\n        if (name == null || name.isBlank()) throw new IllegalArgumentException(\"name required\");\n        if (!email.contains(\"@\")) throw new IllegalArgumentException(\"invalid email\");\n        // persiste\n        Database.save(new User(name, email));\n        // notifica\n        EmailService.send(email, \"Welcome!\");\n    }\n}",
  "test_suite": "j2_uncle_bob_solid_test_1",
  "expected_classes": ["UserValidator", "UserRepository", "UserNotifier"],
  "mentor_comment": "Uncle Bob: 'Uma razão para mudar. Apenas uma. Se você pode imaginar dois motivos diferentes para alterar esta classe, ela tem duas responsabilidades.'",
  "score_xp": 0,
  "difficulty": "senior"
}
```

### 5.2 Perfil do Player — novos campos

```json
{
  "user_id": "uuid",
  "username": "string",
  "journey_1_completed": true,
  "journey_1_completed_at": "2026-03-02T10:00:00Z",
  "journey_2_unlocked": true,
  "journey_2_current_location": "xerox_parc",
  "journey_2_current_master": "uncle_bob",
  "journey_2_current_expansion": 1,
  "journey_2_seniority": "Senior",
  "journey_2_completed": false,
  "journey_2_masters_defeated": ["uncle_bob", "knuth"],
  "journey_2_total_score": 12500,
  "principal_engineer_badge": false
}
```

### 5.3 Estado da Sessão — Jornada 2

```json
{
  "session_id": "uuid",
  "user_id": "uuid",
  "journey": 2,
  "act": 1,
  "location": "xerox_parc",
  "master": "uncle_bob",
  "expansion_index": 2,
  "game_state": "CODING",
  "seniority_locked": true,
  "seniority_value": "Senior"
}
```

### 5.4 Novos endpoints necessários

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/game/journey2/start` | Inicia Jornada 2 (verifica journey_1_completed) |
| `GET` | `/api/game/journey2/status` | Status atual do player na Jornada 2 |
| `POST` | `/api/game/journey2/answer` | Submete MCQ da Jornada 2 |
| `POST` | `/api/game/journey2/code` | Submete live coding da Jornada 2 |
| `POST` | `/api/game/journey2/progress` | Avança estágio/expansão |
| `GET` | `/api/game/leaderboard/masters` | Leaderboard separado da Jornada 2 |

### 5.5 Filtro em game_routes.py

Adicionar `journey` parameter em todas as queries de challenge:

```python
# Existente (não alterar):
challenges = repo.find_by_location(location, journey=1)

# Novo:
challenges_j2 = repo.find_by_location(location, journey=2)
```

### 5.6 HUD — diferenciação visual

Quando `session.journey == 2`:
- Cor do HUD muda de `#fbbf24` (amber) para `#a78bfa` (violeta — cor de "sabedoria")
- Seniority badge mostra: `📚 SENIOR · OS MESTRES` (fixo, não muda)
- Cada expansão adiciona um ícone de livro no HUD: `📖 📖 📖` (quantos livros o mestre tem)
- Nome do NPC atualizado: `"Uncle Bob — Robert C. Martin"`

### 5.7 GARAGE AI — Escopo Completo e Comportamento

#### 5.7.1 Definição do Escopo — SEM LIMITES TÉCNICOS

O GARAGE AI é o assistente técnico principal do jogo. Ele responde **qualquer pergunta
técnica que o player fizer** — do mais básico ao mais avançado e experimental.
Não existe assunto de tecnologia fora do escopo dele.

Exemplos do espectro completo que ele deve responder com excelência:

| Nível | Pergunta exemplo | Resposta esperada |
|-------|-----------------|------------------|
| Básico | O que é uma variável? | Explicação completa com analogia e exemplo Java |
| Intermediário | Como funciona um índice B-Tree? | Explicação estrutural + quando usar + custo |
| Avançado | Como o Raft garante consenso em split brain? | Protocolo completo com casos edge |
| Sênior | Como o Linux gerencia a TLB sob NUMA? | Explicação de kernel memory management |
| Principal | Como a Meta implementa TAO para grafos sociais? | Arquitetura real documentada publicamente |
| Experimental | Como LLMs com MoE (Mixture of Experts) roteiam tokens? | Explicação de sparse activation + exemplos |
| Surreal/cutting-edge | Como funciona o Quantum Error Correction no Google Willow? | Surface codes, logical vs physical qubits |

**Não existe pergunta tecnicamente válida que o GARAGE AI recuse ou simplifique
desnecessariamente.** O player que quiser saber como funciona o scheduler do kernel
Linux enquanto resolve um desafio de TDD no Kent Beck — o AI responde completamente,
e depois retorna ao contexto do desafio.

#### 5.7.2 Modos de Operação

O GARAGE AI opera em dois modos, alternando automaticamente pelo contexto:

**Modo A — Pedagógico (dentro de um desafio ativo):**
Quando o player está dentro de um MCQ ou live coding, o AI adiciona a camada
pedagógica da Jornada 2: cita o livro + capítulo + a citação mais relevante do Mestre.

```json
{
  "mode": "pedagogical",
  "master": "uncle_bob",
  "source_book": "Clean Code",
  "source_chapter": "Cap. 3 — Functions",
  "master_quote": "Functions should do one thing. They should do it well. They should do it only.",
  "ai_response": "Olhe seu método process(): ele está fazendo validação E persistência simultaneamente. Qual responsabilidade você extrairia primeiro como método separado?",
  "follow_up_allowed": true
}
```

**Modo B — Livre (qualquer pergunta técnica fora de desafio ativo, ou pergunta explícita):**
O player pode abrir o GARAGE AI a qualquer momento e perguntar qualquer coisa técnica.
Nenhum tópico é recusado. A resposta é dada na profundidade que o assunto exige.

```json
{
  "mode": "open",
  "topic_detected": "quantum_computing",
  "ai_response": "O Google Willow usa Surface Codes onde...",
  "depth": "advanced",
  "related_challenges": [],
  "source_book": null
}
```

#### 5.7.3 Comportamento quando o player mistura os modos

Exemplo: player está no live coding do Kent Beck (TDD) e pergunta
"Como funciona o GraalVM native image?"

O AI **responde completamente** sobre GraalVM, e depois:
> *"Interessante — aliás, o Kent Beck diria que qualquer otimização prematura
> (incluindo AOT compilation) deve vir DEPOIS do Red-Green-Refactor.
> Quer voltar ao desafio?"*

O AI **nunca bloqueia uma pergunta técnica** para manter o player no trilho.
Ele responde e faz a ponte de volta ao contexto pedagógico.

#### 5.7.4 Tópicos sem limite — lista ilustrativa (não exaustiva)

```
Algoritmos e Estruturas de Dados (qualquer nível)
Sistemas Operacionais: Linux kernel, schedulers, memory management, eBPF
Redes: TCP/IP stack, QUIC, RDMA, BGP, anycast, CDN internals
Banco de dados: B-Tree, LSM-Tree, MVCC, WAL, query planner, vacuum
Sistemas Distribuídos: Paxos, Raft, CRDT, vector clocks, 2PC, Saga
Arquitetura: Clean, Hexagonal, Event-Driven, CQRS, Event Sourcing
Segurança: criptografia assimétrica, TLS 1.3 internals, side-channel attacks
Compiladores: parsing, AST, SSA, LLVM IR, JIT vs AOT, GraalVM
Hardware: CPU pipeline, branch prediction, NUMA, cache coherence, SIMD
Cloud: Kubernetes internals, etcd consensus, service mesh, eBPF networking
AI/ML: transformers, attention mechanism, MoE, LoRA, RAG, embeddings, RLHF
Quantum Computing: qubits, superposition, entanglement, error correction, Shor's algorithm
Blockchain: consensus mechanisms, ZK-proofs, rollups, MEV
Finance Engineering: market microstructure, HFT, order book internals
WebAssembly: WASI, component model, memory model
Programming Languages: type theory, lambda calculus, Hindley-Milner, monads
Formal Methods: TLA+, Alloy, Coq, proof assistants
Design: DDD, Event Storming, C4 model, arc42
Cultura e Processo: Team Topologies, Wardley Maps, OKRs técnicos
... qualquer coisa além disto
```

#### 5.7.5 System Prompt do GARAGE AI (base)

```
Você é o GARAGE AI — o assistente técnico do jogo 404 Garage.
Você é um Principal Engineer com conhecimento irrestrito em toda a pilha de
tecnologia de software e hardware, do básico ao mais experimental e cutting-edge.

Regras:
1. Responda qualquer pergunta técnica com a profundidade que ela merece.
   Nunca simplifique além do necessário. Nunca recuse por "complexidade".
2. Quando o contexto for um desafio da Jornada 2: cite o livro + capítulo +
   quote do Mestre atual ANTES da sua resposta técnica.
3. Quando o player perguntar fora de desafio: responda direto, sem wrapper pedagógico.
4. Se a pergunta tocar em algo coberto pelos 24 livros do jogo: mencione qual
   livro aprofunda o tema (sem ser obrigatório, como bônus de referência).
5. Nunca diga "isso é muito avançado para este nível". O nível do player é SENIOR.
   Trate-o como um colega engenheiro fazendo uma boa pergunta.
6. Use exemplos em Java quando o contexto for código. Use a linguagem mais
   apropriada quando for sobre outro domínio (SQL para BD, Bash para OS, etc.).
7. Respostas longas são bem-vindas quando o assunto exige. Não existe limite
   artificial de tamanho de resposta.
```

Adicionar campo `source_book` na resposta do AI para o frontend exibir a citação
formatada quando `mode == "pedagogical"`.

### 5.8 Mecânica de Expansão — implementação

A expansão não é uma locação nova. É uma **repetição do ciclo** dentro da mesma locação:

```python
# Em progress_stage.py — Jornada 2
def progress_expansion(session: GameSession) -> GameSession:
    master = get_master(session.master)
    if session.expansion_index < master.total_books:
        # continua na mesma locação, próximo livro
        session.expansion_index += 1
        session.game_state = GameState.INTRO  # NPC reaparece citando próximo livro
    else:
        # terminou todos os livros deste Mestre → BOSS da locação
        session.game_state = GameState.BOSS
    return session
```

### 5.9 Verificação TDD para Kent Beck

O GARAGE AI deve ter um validador especial para as sessões do Kent Beck:

```python
# Em ai_validator_routes.py
def validate_tdd_sequence(submissions: list[CodeSubmission]) -> TDDValidationResult:
    """
    Verifica se o player seguiu Red → Green → Refactor.

    Regra:
    1. Primeiro submission deve ter testes que FALHAM (compilam mas falham)
    2. Segundo submission faz os testes PASSAR (mínimo código possível)
    3. Terceiro+ submission refatora sem quebrar os testes verdes

    Retorna: score_penalty se violou a sequência
    """
```

### 5.10 Boss Final CeziCola — validação do ADR

No Round 5 do Boss CeziCola, o GARAGE AI avalia o ADR com os critérios:

```python
ADR_CRITERIA = {
    "problema_descrito": 20,      # Pontos: descreve claramente o problema
    "alternativas_listadas": 20,  # Pontos: pelo menos 2 alternativas consideradas
    "trade_offs_explicitados": 25,# Pontos: pros e contras de cada alternativa
    "decisao_clara": 20,          # Pontos: decisão explícita e justificada
    "consequencias_previstas": 15 # Pontos: o que vai mudar, riscos identificados
}
# Score mínimo para passar: 70/100
```

---

## 6. TRATAMENTO DE CASOS ESPECIAIS

### 6.1 Player que abandona a Jornada 2 no meio

- Sessão salva no PostgreSQL com `journey_2_current_*` campos
- Ao reabrir o jogo, o menu mostra: `▸ CONTINUAR JORNADA 2 — Uncle Bob — Expansão 2`
- Progresso não é perdido
- Pode alternar entre ver o Leaderboard J1 e J2

### 6.2 Score e XP na Jornada 2

**Seniority não muda** (travada em Senior), mas o score acumula separadamente:
- MCQ correto: 50 pontos (vs 100 na J1 — Seniors já deveriam saber)
- Live coding 100%: 500 pontos × índice da expansão (expansão 4 vale 2000 pts)
- BOSS derrotado: 1000 pontos
- Round CeziCola: 500 pts por round (máx 2500 pts)

### 6.3 Leaderboard separado

```
LEADERBOARD — JORNADA 1
  "Os Fundadores" — CEOs e empresas
  Título: "Principal Engineer"

LEADERBOARD — JORNADA 2
  "Os Mestres" — Autores e livros
  Título: "Principal Engineer · Os Mestres"
```

### 6.4 Ordem dos Mestres vs Cronologia dos Livros

Alguns livros são anteriores à empresa onde o Mestre aparece (ex: Knuth 1968 na Apple Garage 1976).
**Isso é intencional e narrado:**

> *"Knuth publicou o Vol. 1 em 1968, antes mesmo do Apple existir.
> Mas foi aqui, neste tipo de problema — eficiência de recursos com memória limitada —
> que a teoria de Knuth encontrou sua aplicação mais visceral."*

A cronologia é usada para **enriquecer o contexto**, não para ser matematicamente perfeita.

---

## 7. CONTEÚDO POR MCQ — BANCO DE PERGUNTAS BASE

### Modelo de 10 perguntas por encontro único / 5 por expansão

Para cada livro, as perguntas seguem a distribuição:
- **2 perguntas**: Conceito fundamental (o QUÊ)
- **2 perguntas**: Aplicação prática (o COMO)
- **1 pergunta**: Trade-off / quando NÃO usar (o QUANDO e POR QUÊ)

### Exemplo — Clean Code, Cap. 1-3 (Expansão 2, Uncle Bob):

```
P1 [Conceito]: Segundo Uncle Bob, qual é o tamanho ideal de uma função?
a) Máximo 20 linhas
b) Deve fazer UMA coisa e apenas uma coisa — o tamanho é consequência ✓
c) Cabe em uma tela sem scroll
d) Máximo 10 linhas

P2 [Conceito]: O que é um "código limpo" segundo Bjarne Stroustrup citado por Martin?
a) Código sem comentários
b) Código que compila sem warnings
c) Código que faz uma coisa bem, elegante, eficiente ✓
d) Código com 100% de cobertura de testes

P3 [Aplicação]: Você tem o método getUserDataAndSendEmail(). Como refatorar?
a) Renomear para processUser()
b) Extrair em getUser() e sendConfirmationEmail() separados ✓
c) Adicionar um comentário explicando o que faz
d) Dividir em dois if/else internos

P4 [Aplicação]: Qual nome de variável segue Clean Code?
a) d (dias)
b) daysSinceCreation ✓
c) days_since_account_creation_in_calendar
d) x

P5 [Trade-off]: Em qual situação um comentário é JUSTIFICÁVEL segundo Clean Code?
a) Para explicar o que o código faz
b) Para lembrar de fazer um TODO depois
c) Para explicar a intenção quando a linguagem não permite expressar claramente ✓
d) Todo método público deve ter JavaDoc
```

---

## 8. CRONOGRAMA DE IMPLEMENTAÇÃO RECOMENDADO

### Sprint 1 — Infraestrutura (sem conteúdo ainda)
- [ ] Adicionar campos `journey_2_*` no schema de users/sessions (migration SQL)
- [ ] Criar endpoint `/api/game/journey2/start` com validação de J1 completa
- [ ] Filtro `journey=2` em `ChallengeRepository.find_by_location()`
- [ ] HUD: detectar `journey=2` e mudar cor + badge
- [ ] Leaderboard separado para J2

### Sprint 2 — Tela de Congratulations + Twist
- [ ] Componente de Congratulations com animação
- [ ] Modal do Twist com efeito máquina de escrever
- [ ] Botão "Iniciar Jornada 2" → chama `/api/game/journey2/start`
- [ ] Transição visual J1→J2 (partícula/fade)

### Sprint 3 — Conteúdo: Uncle Bob (Locação 1, 4 expansões)
- [ ] Criar 20 MCQs no `challenges.json` (journey=2, master=uncle_bob)
- [ ] Criar 4 desafios de live coding com test suites JUnit
- [ ] Diálogo de Uncle Bob para cada expansão
- [ ] BOSS da Locação 1

### Sprint 4 — Kent Beck + Validador TDD
- [ ] Criar 15 MCQs (3 expansões × 5) + 3 live codings
- [ ] Implementar validador de sequência RED→GREEN→REFACTOR no GARAGE AI
- [ ] Semáforo visual na IDE para sessões Beck

### Sprint 5 a 10 — Demais Mestres (um por sprint)
- Sprint 5: Knuth (4 expansões — alto conteúdo)
- Sprint 6: Fowler + Brooks + McConnell
- Sprint 7: GoF + Hunt & Thomas + Feathers
- Sprint 8: Gene Kim (3 expansões) + SRE Team (2 expansões)
- Sprint 9: Eric Evans + Kleppmann
- Sprint 10: Dijkstra + Abelson & Sussman

### Sprint 11 — Boss Final CeziCola
- [ ] 5 rounds implementados
- [ ] Validador de ADR no GARAGE AI
- [ ] Tela de vitória "Principal Engineer · Os Mestres"
- [ ] Badge + Leaderboard J2

---

## 9. REGRAS DE OURO — O QUE NUNCA QUEBRAR

```
1. journey=1 challenges: READONLY — nunca alterar, nunca deletar
2. Seniority J2: sempre "Senior" — nenhum código pode alterar este campo
3. A sequência TDD de Kent Beck NUNCA pode ser bypass ado — é o coração pedagógico
4. Toda citação de livro DEVE ter: título + autor + capítulo/conceito específico
5. O Boss Final CeziCola NUNCA pode ser skippado — não existe flag de "já passou"
6. O código legado do Boss Feathers DEVE ser o mesmo código do Ato I, Jornada 1
   (buscar do histórico do player — campo journey_1_act1_submission)
7. Leaderboards J1 e J2 são SEPARADOS — nunca misturar scores
8. GARAGE AI na J2 cita o livro + capítulo quando em modo pedagógico (desafio ativo).
   Fora de desafio, responde qualquer pergunta técnica sem restrição de escopo ou
   complexidade. Nunca recusa, nunca simplifica artificialmente. O player é Senior.
```

---

## 10. A PROMESSA PEDAGÓGICA

Ao completar as duas jornadas, o player terá:

| Competência | Fonte | Onde praticou |
|------------|-------|--------------|
| História e contexto da computação | Jornada 1 — CEOs | 12 locações |
| SOLID e Clean Code | Uncle Bob | Xerox PARC J2 |
| Análise de algoritmos e complexidade | Knuth | Apple Garage J2 |
| Gestão de complexidade e abstrações | SICP / Abelson | Final Arena J2 |
| Gestão de projetos e expectativas | Brooks + McConnell | Harvard J2 |
| Design Patterns — vocabulário compartilhado | GoF | Amazon J2 |
| Pragmatismo e DRY | Hunt & Thomas | Google J2 |
| Refactoring disciplinado | Fowler | PayPal J2 |
| TDD como disciplina de design | Kent Beck | Harvard Dorm J2 |
| Trabalhar com legado sem medo | Feathers | Enterprise J2 |
| Modelagem de domínio | Eric Evans | Enterprise J2 |
| Sistemas distribuídos na prática | Kleppmann | MIT J2 |
| DevOps e cultura de entrega | Gene Kim | AWS J2 |
| SRE e confiabilidade como ciência | Google SRE Team | Google SRE J2 |
| Correctness e raciocínio formal | Dijkstra | Final Arena J2 |
| Meta-review de tudo | CeziCola | Final Arena J2 |

**Isto não é um curso. É uma formação.**
Um engenheiro que completar as duas jornadas terá passado por mais
modelos mentais de engenharia real do que a maioria dos cursos de graduação.

E vai carregar isso para o resto da vida.

---

*Spec escrita por CeziCola · Bio Code Technology Ltda · 02/03/2026*
*"The only way to go fast is to go well." — Robert C. Martin*
