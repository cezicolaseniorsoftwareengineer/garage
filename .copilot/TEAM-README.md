# Tech Team — 20 Elite Specialists

## Estrutura Completa

### C-Level (Estratégia)

1. **Cezi Cola** — Tech Lead Architect (baseado em `.copilot/prompts/cezicola.md`)
2. [Strategy Officer](team/02-strategy-officer.md) — Product & Business Architecture

### Lead Engineers (Liderança Técnica)

3. [Lead Backend Engineer](team/03-lead-backend.md) — Java/Spring/Microservices
4. [Lead Frontend Engineer](team/04-lead-frontend.md) — Angular/React/Vue/TypeScript/Design Systems
5. [Lead DevOps/SRE](team/05-lead-devops.md) — K8s/AWS/CI-CD
6. [Lead Security Engineer](team/06-lead-security.md) — Zero Trust/Compliance

### Senior Specialists (Expertise Profunda)

7. [Senior UI/UX Designer](team/07-senior-ux-designer.md) — Figma/Design Thinking
8. [Design Systems Architect](team/08-design-systems-architect.md) — Atomic Design/Tokens
9. [Database Architect](team/09-database-architect.md) — PostgreSQL/MongoDB/Redis
10. [Cloud Architect](team/10-cloud-architect.md) — AWS/Multi-Cloud/Serverless
11. [Compliance Officer](team/11-compliance-officer.md) — PCI DSS/LGPD/PSD2
12. [Performance Engineer](team/12-performance-engineer.md) — Core Web Vitals/Optimization

### Specialists (Implementação)

13. [Full-Stack Developer](team/13-fullstack-developer.md) — End-to-End Implementation
14. [Mobile Engineer](team/14-mobile-engineer.md) — iOS/Android/React Native
15. [API Architect](team/15-api-architect.md) — REST/GraphQL/gRPC
16. [Data Engineer](team/16-data-engineer.md) — ETL/Data Lakes/Analytics
17. [QA/Test Automation](team/17-qa-test-automation.md) — TDD/BDD/E2E
18. [AI/ML Engineer](team/18-ai-ml-engineer.md) — TensorFlow/PyTorch/LLMs
19. [Blockchain Engineer](team/19-blockchain-engineer.md) — Smart Contracts/DeFi
20. [Accessibility Specialist](team/20-accessibility-specialist.md) — WCAG AAA/Inclusive Design

---

## Como Usar a Equipe

### Método 1: Contexto via @-mention

```
@workspace Consulte o Lead Backend Engineer sobre arquitetura de microservices
```

### Método 2: Incluir arquivo específico

```
@.copilot/team/03-lead-backend.md Como implementar CQRS em Spring Boot?
```

### Método 3: Carregar múltiplos especialistas

```
Preciso de ajuda com:
@.copilot/team/04-lead-frontend.md (design system)
@.copilot/team/08-design-systems-architect.md (tokens)
@.copilot/team/20-accessibility-specialist.md (WCAG compliance)

Implementar componente Button acessível e com design tokens.
```

### Método 4: Configuração em settings.json

Adicionar especialistas relevantes no `codeGeneration.instructions`:

```json
{
  "github.copilot.chat.codeGeneration.instructions": [
    { "file": ".github/copilot-instructions.md" },
    { "file": ".copilot/prompts/cezicola.md" },
    { "file": ".copilot/team/03-lead-backend.md" },
    { "file": ".copilot/team/04-lead-frontend.md" }
  ]
}
```

---

## Expertise por Domínio

### Backend Development

- **Lead:** [03-lead-backend.md](team/03-lead-backend.md)
- **Database:** [09-database-architect.md](team/09-database-architect.md)
- **API:** [15-api-architect.md](team/15-api-architect.md)
- **Data:** [16-data-engineer.md](team/16-data-engineer.md)

### Frontend Development

- **Lead:** [04-lead-frontend.md](team/04-lead-frontend.md)
- **UI/UX:** [07-senior-ux-designer.md](team/07-senior-ux-designer.md)
- **Design Systems:** [08-design-systems-architect.md](team/08-design-systems-architect.md)
- **Accessibility:** [20-accessibility-specialist.md](team/20-accessibility-specialist.md)
- **Performance:** [12-performance-engineer.md](team/12-performance-engineer.md)

### Mobile Development

- **Specialist:** [14-mobile-engineer.md](team/14-mobile-engineer.md)
- **API Integration:** [15-api-architect.md](team/15-api-architect.md)
- **UI/UX:** [07-senior-ux-designer.md](team/07-senior-ux-designer.md)

### Infrastructure & DevOps

- **Lead DevOps:** [05-lead-devops.md](team/05-lead-devops.md)
- **Cloud:** [10-cloud-architect.md](team/10-cloud-architect.md)
- **Security:** [06-lead-security.md](team/06-lead-security.md)

### Quality & Testing

- **QA:** [17-qa-test-automation.md](team/17-qa-test-automation.md)
- **Performance:** [12-performance-engineer.md](team/12-performance-engineer.md)
- **Security:** [06-lead-security.md](team/06-lead-security.md)

### Compliance & Governance

- **Compliance:** [11-compliance-officer.md](team/11-compliance-officer.md)
- **Security:** [06-lead-security.md](team/06-lead-security.md)
- **Strategy:** [02-strategy-officer.md](team/02-strategy-officer.md)

### Emerging Tech

- **AI/ML:** [18-ai-ml-engineer.md](team/18-ai-ml-engineer.md)
- **Blockchain:** [19-blockchain-engineer.md](team/19-blockchain-engineer.md)

---

## Base de Conhecimento

Todos os membros têm acesso a:

- [Tech Books](knowledge/tech-books.md) — Livros fundamentais de tecnologia
- [Master Library](knowledge/master-library.md) — 25 livros prioritários para o cérebro expandido
- [23 Masters Council](masters/23-masters-council.md) — conselho operacional do Cezi
- Design Patterns — Gang of Four, Enterprise Patterns
- SOLID, 12-Factor App, CAP Theorem
- WCAG 2.1, OWASP Top 10, PCI DSS

## Integração Total Obrigatória

- Toda feature deve alinhar frontend, backend, persistência, banco de dados e contratos JSON
- Orquestrações e integrações devem prever retries, idempotência, observabilidade e compensação
- O objetivo da equipe não é produzir camadas isoladas, mas um sistema coeso ponta a ponta

---

## Fluxo de Trabalho Típico

### Feature Completa (Login com OAuth2)

1. **Strategy Officer** → Define requisitos de negócio e métricas
2. **UI/UX Designer** → Wireframes e user flows
3. **Design Systems** → Componentes reutilizáveis (Button, Input, Form)
4. **Frontend Lead** → Implementa UI com Angular, React ou Vue + TypeScript
5. **Backend Lead** → API de autenticação com Spring Security + OAuth2
6. **Database Architect** → Schema de usuários, sessões, tokens
7. **Security Engineer** → Audit de segurança (OWASP, Zero Trust)
8. **Compliance Officer** → Validação LGPD (consentimento, dados)
9. **QA Engineer** → Testes automatizados (unit, integration, E2E)
10. **DevOps Lead** → CI/CD pipeline, deployment, monitoring
11. **Performance Engineer** → Otimização (Core Web Vitals, latência)
12. **Accessibility** → WCAG compliance (keyboard, screen readers)

### Resultado

Feature completa, segura, testada, acessível, em produção com monitoramento.

---

## Comunicação

- **Código:** Inglês (variáveis, funções, comentários)
- **Terminal/Docs:** Português brasileiro
- **Tom:** Técnico, direto, sem emojis
- **Justificativas:** Trade-offs explícitos, arquitetura fundamentada

---

## Organograma

```
Cezi Cola (Tech Lead)
├── Strategy Officer (Product & Business)
├── Lead Backend Engineer
│   ├── Database Architect
│   ├── API Architect
│   └── Data Engineer
├── Lead Frontend Engineer
│   ├── UI/UX Designer
│   ├── Design Systems Architect
│   ├── Performance Engineer
│   └── Accessibility Specialist
├── Lead DevOps/SRE
│   └── Cloud Architect
├── Lead Security Engineer
│   └── Compliance Officer
└── Specialists
    ├── Full-Stack Developer
    ├── Mobile Engineer
    ├── QA/Test Automation
    ├── AI/ML Engineer
    └── Blockchain Engineer
```

---

## Última Atualização

**Data:** 2026-03-04
**Status:** OK — 20 membros criados e documentados
**Localização:** `.copilot/team/`
