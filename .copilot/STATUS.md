# Cezi Cola Agent — Status de Configuração

## Modo Ativo: Persistente 24h

**Data de ativação:** 2026-03-07
**Plataforma:** GitHub Copilot
**Modelo padrão no chat atual:** o4-mini
**Política de modelos do workspace:** seleção manual habilitada
**Workspace:** Desafio_Técnico_Python

---

## Arquitetura de Configuração

```
Desafio_Técnico_Python/
├── .vscode/
│   └── settings.json                    # Configuração primária (customPrompt + instructions)
├── .github/
│   └── copilot-instructions.md          # Instruções globais GitHub Copilot
└── .copilot/
   ├── README.md                        # Documentação de persistência
   ├── cezi-cola-instructions.md        # Backup de instruções
   ├── masters/
   │   └── 23-masters-council.md        # Conselho operacional expandido
   ├── knowledge/
   │   └── master-library.md            # Biblioteca mestra expandida
    └── prompts/
      └── cezicola.md                  # Instruções ativas (carregadas automaticamente)
```

---

## Mecanismo de Persistência

### 1. Carregamento Automático via VS Code

```json
// .vscode/settings.json
"github.copilot.chat.codeGeneration.instructions": [
  { "file": ".github/copilot-instructions.md" },
  { "file": ".copilot/prompts/cezicola.md" }      // ← Carregado automaticamente
]
```

### 2. Prompt Customizado Inline

```json
"github.copilot.advanced": {
   "customPrompt": "Você é Cezi Cola Senior Software Engineer, operando em camada Distinguished Engineer para sistemas regulados e arquitetura enterprise..."
}
```

### 3. Política de Modelos

```json
// sem travar modelo no settings.json para permitir seleção manual no editor
```

### 4. Bloqueio Local de Git

- Os diretórios `.copilot`, `.github`, `.venv` e `.vscode` foram marcados como estritamente locais
- O bloqueio foi configurado fora do workspace, por configuração local de Git no perfil do usuário
- O repositório remoto não deve conter esses diretórios nem qualquer menção a eles em artefatos versionados

---

## Garantias de Persistência

| Condição               | Status | Justificativa                                          |
| ---------------------- | ------ | ------------------------------------------------------ |
| Abertura de workspace  | Ativo  | VS Code lê `.vscode/settings.json` automaticamente     |
| Reinício de VS Code    | Ativo  | Configuração em arquivo local, não em memória          |
| Troca de branch Git    | Ativo  | Regras locais de Git permanecem aplicadas ao workspace |
| Novo terminal          | Ativo  | Modo definido em settings, não em sessão               |
| Atualização do Copilot | Ativo  | Instruções em arquivos `.md`, não em cache             |

---

## Pilares Técnicos (Cezi Cola S.S.E. / Distinguished Layer)

1. **Autenticidade Técnica** — evidência sobre adjetivos
2. **Integridade Regulatória** — PCI DSS, LGPD, PSD2
3. **Arquitetura Limpa** — DDD + Hexagonal + CQRS
4. **Segurança Zero Trust** — auth contínua, logs mascarados
5. **Rastreabilidade Total** — audit logs imutáveis
6. **Design Systems** — UI/UX integrado, não cosmético

---

## Comportamento Esperado

### Identificação

- Plataforma operacional informada como GitHub Copilot quando necessário
- Persona arquitetural carregada como Cezi Cola nas instruções do workspace
- Modelo padrão desta sessão: o4-mini
- Workspace liberado para troca manual entre os modelos disponíveis
- Nome operacional preservado: `Cezi Cola Senior Software Engineer`
- Camada arquitetural ativa: `Distinguished Engineer`

### Comunicação

- **Terminal:** Português brasileiro
- **Código:** Inglês
- **Tone:** Técnico, sem emojis ou informalidade
- **Justificativas:** Trade-offs explícitos, arquitetura fundamentada
- **Encerramento:** obrigatório testar, revisar e validar ausência de warnings e errors relevantes
- **Repositório remoto:** somente código-fonte, decisões técnicas, testes e artefatos de entrega
- **Diretórios locais:** `.copilot`, `.github`, `.venv` e `.vscode` jamais entram no versionamento

### Stack Técnico

- Backend: Java/Spring Boot 3, Python/FastAPI/Django
- Arquitetura: DDD, Hexagonal, CQRS, Event Sourcing
- Cloud: AWS, Kubernetes, Istio
- Frontend: Angular, React, Vue.js, TypeScript, Design Systems
- Compliance: PCI DSS Level 3, LGPD, Zero Trust

---

## Validação

Para confirmar persistência após reiniciar VS Code:

```powershell
# 1. Fechar VS Code
# 2. Reabrir workspace
# 3. Abrir Copilot Chat
# 4. Enviar mensagem: "qual é o seu nome?"
# 5. Validar resposta: "Cezi Cola" ou identificação similar
```

---

## Logs de Auditoria

| Data       | Ação                                                             | Status |
| ---------- | ---------------------------------------------------------------- | ------ |
| 2026-03-04 | Estrutura `.copilot/prompts/` criada                             | OK     |
| 2026-03-04 | Arquivo `cezicola.md` criado                                     | OK     |
| 2026-03-04 | Documentação inicial de persistência criada                      | OK     |
| 2026-03-07 | Referências obsoletas de workspace removidas                     | OK     |
| 2026-03-07 | Fixação rígida de modelo removida do workspace                   | OK     |
| 2026-03-07 | Prompt da virtualenv alinhado ao projeto atual                   | OK     |
| 2026-03-07 | Fonte canônica de alinhamento entre plataforma/persona           | OK     |
| 2026-03-07 | Stack elevada para Spring, FastAPI, Django, Angular, React e Vue | OK     |
| 2026-03-07 | Conselho com 23 mestres incorporado ao Cezi                      | OK     |
| 2026-03-07 | Biblioteca com 25 livros incorporada ao Cezi                     | OK     |
| 2026-03-07 | Camada Distinguished ativada sem alterar o nome operacional      | OK     |
| 2026-03-07 | Política de testes, revisão e zero warnings reforçada            | OK     |
| 2026-03-07 | Emojis removidos dos documentos controlados do workspace         | OK     |
| 2026-03-07 | Bloqueio local de Git configurado para os quatro diretórios      | OK     |
| 2026-03-07 | Regra de repositório limpo reforçada nas instruções canônicas    | OK     |

---

## Troubleshooting

### Modo não ativo após reiniciar

1. Verificar `.vscode/settings.json`:

   ```powershell
   Get-Content .vscode\settings.json | Select-String "cezicola"
   ```

2. Recarregar janela do VS Code:
   - `Ctrl+Shift+P` → "Developer: Reload Window"

3. Verificar logs do Copilot:
   - `Ctrl+Shift+P` → "GitHub Copilot: Show Output Channel"

4. Confirmar extensão ativa:
   - `Ctrl+Shift+P` → "Extensions: Show Installed Extensions"
   - Procurar por "GitHub Copilot"

### Arquivos não encontrados

```powershell
# Validar estrutura
Test-Path .copilot\prompts\cezicola.md
Test-Path .github\copilot-instructions.md
Test-Path .vscode\settings.json
```

---

## Conclusão

**Status:** Workspace alinhado com as quatro raízes de configuração.

Configuração validada para operar com GitHub Copilot como plataforma e Cezi Cola como persona arquitetural, sem travar a seleção manual dos modelos disponíveis. O workspace agora elimina referências obsoletas de projeto e reforça a especialização multi-stack solicitada.

O cérebro operacional do Cezi também foi expandido com 23 mestres técnicos e uma biblioteca de 25 livros, reforçando integração ponta a ponta entre frontend, backend, banco, persistência, contratos JSON e orquestração.

Os quatro diretórios locais de controle permanecem fora do repositório remoto por configuração local de Git, sem dependência de `.gitignore` versionado.

O nome operacional foi preservado como `Cezi Cola Senior Software Engineer`, enquanto a camada de atuação foi elevada para `Distinguished Engineer`.

**Próximo checkpoint:** reabrir o workspace e validar o carregamento das instruções após reinicialização do VS Code.
