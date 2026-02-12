# PLANEJAMENTO MASTER: 404 GARAGE (The Engineering Journey)
## "De Estagiário a Principal Engineer"

**Documento de Design Técnico e Pedagógico v1.0**
**Author:** Cezi Cola -- Senior Software Engineer | Bio Code Technology ltda
**Target**: Transformar o jogo em uma plataforma completa de formação em Engenharia de Software (nível Staff/Principal).

---

## 1. Visão Geral e Arquitetura

O jogo deixará de ser apenas um "platformer" simples para se tornar um RPG de carreira linear, onde a progressão depende da absorção de conceitos complexos de Ciência da Computação e Engenharia de Software Distribuída.

### Stack Tecnológica (Preservada da v2)
- **Engine**: Gráficos Canvas 2D + Física estilo Sonic/Mario.
- **Backend**: Supabase (Auth Anônima + Persistência de Progresso + Leaderboard).
- **Architecture**: Single Page Application (SPA) monolítica (para facilidade de distribuição) ou Modular baseada em ES6 (se escalabilidade for necessária).
- **State Machine**: Controle rígido de estados (INTRO -> LEARNING -> CHALLENGE -> CODING -> BOSS).

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
- **NPC**: O "Mentor" (Cezi Cola Aura).
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

1.  **Cena do Eduardo Saverin**:
    - Deve ser uma *cutscene* obrigatória no nível de Harvard.
    - Foco técnico: Explicar como $N$ usuários geram $N^2$ conexões potenciais e como otimizar isso.

2.  **Mecânica de "Coding Blocks"**:
    - O jogador não apenas "pula" nos inimigos. Ele precisa coletar blocos de código (ex: `if`, `while`, `KafkaProducer`) e montá-los na ordem certa para resolver o puzzle da fase.
    - Ex: Para passar pela "fogueira do tráfego", use um bloco `RateLimiter`.

3.  **Sistema de "Senioridade" (XP)**:
    - Junior -> Mid-Level -> Senior -> Staff -> Principal.
    - O título muda conforme o acerto nos quizzes técnicos.

4.  **Integração Supabase**:
    - Armazenar o "Portfólio" do jogador (quais tecnologias ele dominou).
    - Leaderboard global de "Melhores Arquitetos".

5.  **Estilo Visual v3**:
    - Manter o visual "Steve Jobs" como base, mas permitir skins desbloqueáveis (Moleton do Zuck, Jaqueta de Couro do Jensen Huang, etc.).

---

## 4. Próximos Passos de Desenvolvimento (Action Plan)

1.  **Refatoração de Dados**: Expandir o objeto `CITIES` no `EngenheirodoFuturo.html` para comportar os 12 locais.
2.  **Sistema de Diálogo Avançado**: Criar suporte para cutscenes (diálogo sequencial sem movimento do player) para a cena do Eduardo.
3.  **Motor de Quiz**: Aprimorar o sistema de perguntas para suportar snippets de código reais (Java, Python, Go).
4.  **Implementação da Física**: Ajustar a física para ser mais "plataforma precisa" (Coyote Time, Jump Buffering).

---
*Este plano serve como a "Bíblia" do projeto 404 Garage daqui para frente.*
