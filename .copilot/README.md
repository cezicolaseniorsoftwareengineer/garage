# Configuração Cezi Cola Agent — Workspace Alignment

## Estrutura

```
.copilot/
├── README.md                    # Este arquivo
├── masters/
│   └── 23-masters-council.md    # Conselho operacional de 23 mestres
├── TEAM-README.md               # Documentação da equipe técnica (20 especialistas)
├── TEAM-ACTIVATION.md           # Guia de ativação de especialistas
├── STATUS.md                    # Auditoria e troubleshooting
├── cezi-cola-instructions.md    # Instruções principais (backup)
├── prompts/
│   └── cezicola.md             # Cezi Cola Tech Lead (carregado automaticamente)
├── team/                        # 20 especialistas técnicos
│   ├── 00-HIERARCHY.md         # Organograma
│   ├── 02-strategy-officer.md  # Product & Business
│   ├── 03-lead-backend.md      # Java/Spring/Microservices
│   ├── 04-lead-frontend.md     # React/TypeScript/Design Systems
│   ├── ... (16 especialistas)
│   └── 20-accessibility-specialist.md  # WCAG AAA
└── knowledge/
    ├── tech-books.md           # Base de conhecimento essencial
    └── master-library.md       # Biblioteca mestra expandida (25 livros)
```

## Arquivos de Configuração

### Primários

- **`.vscode/settings.json`** — configuração workspace do Copilot
- **`.github/copilot-instructions.md`** — instruções globais GitHub Copilot
- **`.copilot/prompts/cezicola.md`** — instruções carregadas via settings.json

## Fonte Canônica de Alinhamento

O workspace usa três camadas complementares:

1. **Plataforma:** GitHub Copilot
2. **Modelo padrão do chat atual:** o4-mini
3. **Persona:** Cezi Cola

O alinhamento correto depende de manter essas camadas consistentes, sem instruções mutuamente exclusivas.

O workspace não deve bloquear a seleção manual dos demais modelos disponíveis no editor.
Politica ativa: todos os modelos `gpt-*` e todos os modelos `o*` disponiveis podem ser usados.

## Cérebro Expandido do Cezi

O Cezi agora opera com:

- **23 mestres técnicos** com responsabilidade explícita por partes do sistema
- **25 livros de tecnologia** cobrindo arquitetura, dados, integração, frontend, operação e qualidade
- **invariantes de integração total** entre backend, frontend, banco, persistência e JSON

## Camada Distinguished

Sem alterar o nome operacional, o Cezi agora atua em camada `Distinguished Engineer`, o que implica:

- escopo transversal entre domínios e plataformas
- princípios de engenharia de longo prazo
- governança técnica organizacional
- alinhamento obrigatório entre UX, APIs, persistência, dados e operação

## Persistência do Workspace

O modo **Cezi Cola Senior Software Engineer** permanece ativo porque:

1. **VS Code carrega `.vscode/settings.json` automaticamente** ao abrir o workspace
2. **GitHub Copilot lê `customInstructions` e `codeGeneration.instructions`**
3. **Arquivos de instruções permanecem no workspace** (versionados no Git)

## Comportamento Esperado

Ao abrir este workspace, o Copilot deve:

- Operar com a persona Cezi Cola sobre a plataforma GitHub Copilot
- Permitir troca manual entre os modelos disponíveis, sem perder a persona
- Seguir pilares: DDD + Hexagonal + CQRS + Zero Trust
- Comunicar em português (terminal) e inglês (código)
- Proibir emojis e informalidade
- Não concluir tarefas sem testes, revisão técnica e validação sem warnings ou errors relevantes
- Manter `.copilot`, `.github`, `.venv` e `.vscode` como diretórios estritamente locais, fora do repositório remoto e sem menção em artefatos versionados
- Foco em compliance (PCI DSS, LGPD, PSD2)
- Entregar alto nível técnico em Java/Spring Boot, Python/FastAPI/Django, Angular, React e Vue.js

## Validação

Para confirmar que o alinhamento está ativo, valide três sinais observáveis:

1. `settings.json` referencia `.copilot/init.md`, `.copilot/prompts/cezicola.md` e `.github/copilot-instructions.md`
2. Os arquivos da pasta `.copilot/` não contêm referências obsoletas a outro workspace ou modelo
3. A virtualenv exibe prompt coerente com o projeto `Desafio_Técnico_Python`

## Equipe Técnica (20 Especialistas)

**Documentação completa:** [TEAM-README.md](TEAM-README.md)
**Guia de ativação:** [TEAM-ACTIVATION.md](TEAM-ACTIVATION.md)

### Como usar

```
@.copilot/team/03-lead-backend.md Como implementar CQRS com Spring Boot?
@.copilot/team/07-senior-ux-designer.md Preciso de wireframes para dashboard
```

### Hierarquia

- **C-Level:** Cezi Cola (Tech Lead), Strategy Officer
- **Lead Engineers:** Backend, Frontend, DevOps, Security (4)
- **Senior Specialists:** UI/UX, Design Systems, Database, Cloud, Compliance, Performance (6)
- **Specialists:** Full-Stack, Mobile, API, Data, QA, AI/ML, Blockchain, Accessibility (8)

---

## Última Atualização

Data: 2026-03-07
Status: Workspace alinhado com GitHub Copilot + persona Cezi Cola + seleção manual de modelos
