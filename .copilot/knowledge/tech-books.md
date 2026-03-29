# Tech Knowledge Base — Essential Books & Principles

## Software Engineering Fundamentals

### "Clean Code" — Robert C. Martin

- **Princípios:**
  - Nomes significativos e intencionais
  - Funções pequenas com responsabilidade única
  - Comentários apenas quando código não é autoexplicativo
  - Tratamento de erros como primeira classe
  - Testes como documentação executável

### "Clean Architecture" — Robert C. Martin

- **Conceitos:**
  - Independência de frameworks
  - Testabilidade isolada
  - Independência de UI e DB
  - Regra de dependência (fluxo para dentro)
  - Entities → Use Cases → Interface Adapters → Frameworks

### "Domain-Driven Design" — Eric Evans

- **Pilares:**
  - Ubiquitous Language (linguagem onipresente)
  - Bounded Contexts (contextos delimitados)
  - Aggregates, Entities, Value Objects
  - Repositories e Domain Services
  - Event Storming e Context Mapping

### "Building Microservices" — Sam Newman

- **Práticas:**
  - Decomposição por domínio de negócio
  - Comunicação via APIs bem definidas
  - Decentralização de dados
  - Resiliência e degradação graciosa
  - Observabilidade distribuída

### "Designing Data-Intensive Applications" — Martin Kleppmann

- **Tópicos:**
  - Confiabilidade, escalabilidade, manutenibilidade
  - Data models: relacional, documento, grafo
  - Replicação e particionamento
  - Transações e consistência
  - Batch processing e stream processing

---

## Design Patterns

### "Design Patterns: Elements of Reusable OO Software" — Gang of Four

- **Criacionais:** Singleton, Factory, Builder, Prototype
- **Estruturais:** Adapter, Facade, Decorator, Proxy
- **Comportamentais:** Strategy, Observer, Command, State

### "Patterns of Enterprise Application Architecture" — Martin Fowler

- **Padrões de Dados:** Repository, Unit of Work, Data Mapper
- **Padrões de Domínio:** Domain Model, Transaction Script
- **Padrões Web:** MVC, Front Controller, Page Controller
- **Padrões de Distribuição:** Remote Facade, DTO

---

## Frontend & UI/UX

### "Don't Make Me Think" — Steve Krug

- **Usabilidade:**
  - Navegação óbvia e autoexplicativa
  - Hierarquia visual clara
  - Redução de carga cognitiva
  - Testes de usabilidade contínuos

### "Refactoring UI" — Adam Wathan & Steve Schoger

- **Princípios:**
  - Hierarquia através de peso, não apenas tamanho
  - Espaçamento consistente via escala
  - Cores com propósito (não apenas decoração)
  - Tipografia responsiva e legível

### "Atomic Design" — Brad Frost

- **Níveis:**
  - Atoms: botões, inputs, labels
  - Molecules: search bar, card header
  - Organisms: header completo, form
  - Templates: página sem conteúdo
  - Pages: instância real com dados

---

## DevOps & Cloud

### "The Phoenix Project" — Gene Kim

- **DevOps Philosophy:**
  - Flow (redução de lead time)
  - Feedback (loops rápidos)
  - Continuous Learning
  - Cultura de colaboração

### "Site Reliability Engineering" — Google

- **SRE Practices:**
  - SLIs, SLOs, SLAs e error budgets
  - Toil reduction (automatização)
  - Incident management e postmortems
  - Capacity planning

### "Kubernetes in Action" — Marko Lukša

- **K8s Core:**
  - Pods, Services, Deployments
  - ConfigMaps e Secrets
  - StatefulSets e DaemonSets
  - Operators e Custom Resources

---

## Security & Compliance

### "OWASP Top 10" — Security Risks

1. Broken Access Control
2. Cryptographic Failures
3. Injection (SQL, XSS, Command)
4. Insecure Design
5. Security Misconfiguration
6. Vulnerable Components
7. Authentication Failures
8. Data Integrity Failures
9. Logging & Monitoring Failures
10. Server-Side Request Forgery

### "Zero Trust Networks" — Evan Gilman & Doug Barth

- **Princípios:**
  - Never trust, always verify
  - Assume breach
  - Verify explicitly
  - Least privilege access

---

## Data & Algorithms

### "Introduction to Algorithms" — CLRS

- **Estruturas de Dados:** Arrays, Listas, Árvores, Grafos, Hash Tables
- **Algoritmos:** Ordenação, Busca, Grafos (Dijkstra, BFS, DFS)
- **Complexidade:** Big O, análise assintótica
- **Paradigmas:** Divisão e conquista, programação dinâmica, greedy

### "Streaming Systems" — Tyler Akidau

- **Stream Processing:**
  - Windowing (tumbling, sliding, session)
  - Watermarks e late data
  - Event time vs processing time
  - Exactly-once semantics

---

## Testing & Quality

### "Test-Driven Development" — Kent Beck

- **TDD Cycle:**
  - Red: escrever teste que falha
  - Green: implementar código mínimo para passar
  - Refactor: melhorar mantendo testes verdes

### "xUnit Test Patterns" — Gerard Meszaros

- **Patterns:**
  - Test Doubles: Stub, Mock, Fake, Spy
  - Fixture Setup: Fresh, Shared, Lazy
  - Result Verification: State, Behavior

---

## Performance & Optimization

### "High Performance Browser Networking" — Ilya Grigorik

- **Web Performance:**
  - Critical rendering path
  - Resource prioritization
  - HTTP/2 e HTTP/3
  - Service Workers e caching

### "Systems Performance" — Brendan Gregg

- **Metodologias:**
  - USE Method (Utilization, Saturation, Errors)
  - RED Method (Rate, Errors, Duration)
  - Profiling e tracing
  - Flamegraphs

---

## Principles Applied Across Team

1. **SOLID** (OOP)
   - Single Responsibility
   - Open/Closed
   - Liskov Substitution
   - Interface Segregation
   - Dependency Inversion

2. **12-Factor App** (Cloud-Native)
   - Codebase versionado
   - Dependências explícitas
   - Configuração em ambiente
   - Backing services anexáveis
   - Build, release, run separados
   - Stateless processes
   - Port binding
   - Concorrência via processos
   - Descartabilidade (fast startup)
   - Dev/prod parity
   - Logs como streams
   - Admin processes

3. **CAP Theorem** (Distributed Systems)
   - Consistency, Availability, Partition Tolerance
   - Choose 2 of 3 under partition
   - Trade-offs explícitos

4. **ACID vs BASE**
   - ACID: Atomicity, Consistency, Isolation, Durability
   - BASE: Basically Available, Soft state, Eventual consistency
