# Ativação da Equipe Técnica — Guia Rápido

## Opção 1: Ativação Individual (On-Demand)

Mencione o especialista diretamente na conversa com Copilot:

```
@.copilot/team/03-lead-backend.md Como implementar Event Sourcing com Spring Boot?
```

```
@.copilot/team/07-senior-ux-designer.md Preciso de um wireframe para dashboard analytics
```

---

## Opção 2: Ativação de Squad Específico

### Squad Frontend (UI/UX completo)

```json
// Adicionar em .vscode/settings.json
"github.copilot.chat.codeGeneration.instructions": [
  { "file": ".copilot/prompts/cezicola.md" },
  { "file": ".copilot/team/04-lead-frontend.md" },
  { "file": ".copilot/team/07-senior-ux-designer.md" },
  { "file": ".copilot/team/08-design-systems-architect.md" },
  { "file": ".copilot/team/20-accessibility-specialist.md" }
]
```

### Squad Backend (Microservices)

```json
"github.copilot.chat.codeGeneration.instructions": [
  { "file": ".copilot/prompts/cezicola.md" },
  { "file": ".copilot/team/03-lead-backend.md" },
  { "file": ".copilot/team/09-database-architect.md" },
  { "file": ".copilot/team/15-api-architect.md" },
  { "file": ".copilot/team/06-lead-security.md" }
]
```

### Squad DevOps & Cloud

```json
"github.copilot.chat.codeGeneration.instructions": [
  { "file": ".copilot/prompts/cezicola.md" },
  { "file": ".copilot/team/05-lead-devops.md" },
  { "file": ".copilot/team/10-cloud-architect.md" },
  { "file": ".copilot/team/06-lead-security.md" },
  { "file": ".copilot/team/12-performance-engineer.md" }
]
```

### Squad Compliance & Security

```json
"github.copilot.chat.codeGeneration.instructions": [
  { "file": ".copilot/prompts/cezicola.md" },
  { "file": ".copilot/team/06-lead-security.md" },
  { "file": ".copilot/team/11-compliance-officer.md" },
  { "file": ".copilot/team/17-qa-test-automation.md" }
]
```

---

## Opção 3: Ativação de Equipe Completa (20 membros)

**Atenção:** Carregar todos os 20 membros simultaneamente pode consumir muito contexto do Copilot. Recomendado apenas para projetos complexos.

```json
// .vscode/settings.json (Full Team Mode)
"github.copilot.chat.codeGeneration.instructions": [
  { "file": ".github/copilot-instructions.md" },
  { "file": ".copilot/prompts/cezicola.md" },
  { "file": ".copilot/masters/23-masters-council.md" },
  { "file": ".copilot/knowledge/master-library.md" },
  { "file": ".copilot/team/02-strategy-officer.md" },
  { "file": ".copilot/team/03-lead-backend.md" },
  { "file": ".copilot/team/04-lead-frontend.md" },
  { "file": ".copilot/team/05-lead-devops.md" },
  { "file": ".copilot/team/06-lead-security.md" },
  { "file": ".copilot/team/07-senior-ux-designer.md" },
  { "file": ".copilot/team/08-design-systems-architect.md" },
  { "file": ".copilot/team/09-database-architect.md" },
  { "file": ".copilot/team/10-cloud-architect.md" },
  { "file": ".copilot/team/11-compliance-officer.md" },
  { "file": ".copilot/team/12-performance-engineer.md" },
  { "file": ".copilot/team/13-fullstack-developer.md" },
  { "file": ".copilot/team/14-mobile-engineer.md" },
  { "file": ".copilot/team/15-api-architect.md" },
  { "file": ".copilot/team/16-data-engineer.md" },
  { "file": ".copilot/team/17-qa-test-automation.md" },
  { "file": ".copilot/team/18-ai-ml-engineer.md" },
  { "file": ".copilot/team/19-blockchain-engineer.md" },
  { "file": ".copilot/team/20-accessibility-specialist.md" },
  { "file": ".copilot/knowledge/tech-books.md" }
]
```

---

## Opção 4: Chamada Contextual (Recomendado)

Deixe apenas Cezi Cola ativo permanentemente e chame especialistas conforme necessário:

```
Preciso implementar um sistema de autenticação OAuth2 completo.

Consultar:
- @.copilot/team/03-lead-backend.md (Spring Security OAuth2)
- @.copilot/team/06-lead-security.md (Zero Trust, tokens)
- @.copilot/team/11-compliance-officer.md (LGPD compliance)
- @.copilot/team/17-qa-test-automation.md (testes de segurança)

Requisitos:
1. JWT com refresh tokens
2. Rate limiting
3. Audit log mascarado
4. LGPD compliant (consentimento)
```

---

## Exemplo de Uso: Feature Completa

### Tarefa: Implementar Dashboard Analytics

```
Contexto: Preciso de um dashboard analytics com gráficos interativos.

Equipe necessária:
- @.copilot/team/02-strategy-officer.md → Métricas de negócio (KPIs)
- @.copilot/team/07-senior-ux-designer.md → Wireframes e user flows
- @.copilot/team/04-lead-frontend.md → React + Chart.js implementation
- @.copilot/team/08-design-systems-architect.md → Componentes reutilizáveis
- @.copilot/team/16-data-engineer.md → Pipeline de dados (ETL)
- @.copilot/team/12-performance-engineer.md → Otimização de queries
- @.copilot/team/20-accessibility-specialist.md → WCAG compliance

Entregas esperadas:
1. Wireframes (Figma)
2. Component library (Storybook)
3. Data pipeline (Airflow DAG)
4. Frontend (React + TypeScript)
5. Testes E2E (Playwright)
6. Documentação completa
```

---

## Validação de Ativação

Após ativar especialistas, pergunte:

```
Quem está disponível na equipe técnica?
```

O Copilot deve listar os especialistas carregados.

---

## Troubleshooting

### Copilot não reconhece os especialistas

1. Verificar se arquivos `.md` existem em `.copilot/team/`
2. Recarregar VS Code: `Ctrl+Shift+P` → "Developer: Reload Window"
3. Verificar sintaxe do `settings.json` (JSON válido)

### Contexto muito grande (timeout)

- Reduzir número de especialistas carregados
- Usar Opção 4 (chamada contextual on-demand)
- Manter apenas Cezi Cola + 2-3 especialistas por vez

### Respostas genéricas (não usando expertise)

- Mencionar explicitamente o especialista: `@.copilot/team/XX-nome.md`
- Fazer perguntas específicas da área de expertise
- Incluir palavras-chave do domínio (ex: "CQRS", "Event Sourcing", "WCAG AAA")

---

## Recomendação Final

**Setup Ideal:**

- **Permanente:** Cezi Cola (Tech Lead)
- **Cérebro expandido:** 23 mestres + master library
- **On-Demand:** Especialistas conforme necessidade via `@mention`
- **Squad Mode:** Ativar grupo de 4-5 especialistas para features complexas
- **Full Team:** Apenas para projetos enterprise de larga escala

---

## Estrutura de Arquivos

```
.copilot/
├── TEAM-README.md              # Documentação geral da equipe
├── TEAM-ACTIVATION.md          # Este arquivo (guia de ativação)
├── prompts/
│   └── cezicola.md            # Cezi Cola (Tech Lead)
├── team/
│   ├── 00-HIERARCHY.md        # Organograma
│   ├── 02-strategy-officer.md
│   ├── 03-lead-backend.md
│   ├── ... (18 especialistas)
│   └── 20-accessibility-specialist.md
└── knowledge/
    └── tech-books.md          # Base de conhecimento técnico
```

---

**Status:** OK — equipe pronta para ativação
**Data:** 2026-03-04
**Próximo passo:** Escolha um modo de ativação e comece a construir!
