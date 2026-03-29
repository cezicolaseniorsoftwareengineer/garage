**Estado do Projeto — Resumo Operacional**

**Resumo Executivo**
- **Serviço:** rodando em modo *JSON-fallback* (sem conexão ao banco). Veja [Garage/garage.py](Garage/garage.py).
- **Idempotência:** middleware implementado e testado. Arquivo: [Garage/app/infrastructure/middleware/idempotency.py](Garage/app/infrastructure/middleware/idempotency.py) — teste: [Garage/tests/test_idempotency.py](Garage/tests/test_idempotency.py).
- **Segurança de segredos:** scanner não-destrutivo executado; relatório: [scripts/secret_audit_tracked.txt](scripts/secret_audit_tracked.txt). Muitos artefatos rastreados contêm strings sensíveis potenciais.
- **Configuração local:** `Garage/.env` foi sanitizado e temporariamente teve `DATABASE_URL` limpo para forçar fallback. Arquivo: [Garage/.env](Garage/.env).

**Fundação Técnica**
- **Backend:** FastAPI — ponto de entrada: [Garage/app/main.py](Garage/app/main.py).
- **Conexão BD:** [Garage/app/infrastructure/database/connection.py](Garage/app/infrastructure/database/connection.py) — validação do `DATABASE_URL` e DDL do idempotency table.
- **Auth / JWT:** [Garage/app/infrastructure/auth/jwt_handler.py](Garage/app/infrastructure/auth/jwt_handler.py) — comportamento *fail-fast* sem `JWT_SECRET_KEY`.
- **Email:** [Garage/app/infrastructure/auth/email_sender.py](Garage/app/infrastructure/auth/email_sender.py) — SMTP primário, fallback Resend.
- **Launcher local:** [Garage/garage.py](Garage/garage.py) — carrega `.env` e inicia `uvicorn` (usado para restaurar serviço em fallback).

**Estado dos Componentes Principais**
- **Idempotency middleware:** Implementado; comportamento DB-backed com fallback em memória; teste unitário presente ([Garage/tests/test_idempotency.py](Garage/tests/test_idempotency.py)).
- **Banco de dados:** Start falhou quando `DATABASE_URL` inválido; atualmente rodando sem BD (fallback). É necessária migração/versionamento para a tabela `idempotency_keys` antes de habilitar BD.
- **Autenticação:** Verificação forte de segredo; se `JWT_SECRET_KEY` ausente, endpoints falham conforme desenho.
- **Email / integrações externas:** Lê chaves de env (ex.: `RESEND_API_KEY`); integrações externas devem ter timeouts/retries.

**Problemas e Riscos Críticos**
- **Segredos rastreados:** o scanner identificou chaves/sugestões em arquivos rastreados. Prioridade: rotacionar chaves expostas antes de qualquer rewrite de histórico. Relatório: [scripts/secret_audit_tracked.txt](scripts/secret_audit_tracked.txt).
- **Configuração inválida do BD:** `DATABASE_URL` malformado causou falha de startup (SQLAlchemy). Foi aplicada alteração reversível em `Garage/.env` para executar em fallback.
- **Assets faltantes:** observada 404 em `/sw.js` na execução atual — efeito na PWA/serviço offline.

**Ações Executadas (até aqui)**
- Executado scanner não-destrutivo para arquivos git-tracked (`scripts/scan_tracked_secrets.py`) e gerado `scripts/secret_audit_tracked.txt`.
- Sanitizado `Garage/.env` localmente e criado `Garage/.env.sample` (valores placeholder).
- Iniciada aplicação em modo fallback via [Garage/garage.py](Garage/garage.py).
- Implementado middleware de idempotência e teste unitário correspondente.
- SDK e demo locais gerados (artefatos mantidos localmente, não versionados).

**Próximos Passos Recomendados (ordem sugerida)**
1. **Rotacionar credenciais expostas** imediatamente nos provedores (não editar histórico primeiro).
2. **Substituir** valores sensíveis em arquivos rastreados por placeholders e commitar mudanças revisadas.
3. **Mover segredos** para Secret Manager (AWS/Azure/GCP/HashiCorp Vault) e usar injeção em runtime; publicar `env.sample` atualizado.
4. **Criar migração** versionada para a tabela `idempotency_keys` e validar com Testcontainers / integração local.
5. **Adicionar pre-commit** (detectores de segredos) + CI scanning em modo audit-only → depois bloquear em CI quando estável.
6. **Testar reprovisionamento**: restaurar `DATABASE_URL` válido em ambiente controlado e validar endpoints e testes automatizados.

**Como reproduzir o estado atual (iniciar localmente)**
```powershell
& ".venv\Scripts\Activate.ps1"
python Garage/garage.py
```

**Links rápidos**
- Relatório scanner: [scripts/secret_audit_tracked.txt](scripts/secret_audit_tracked.txt)
- `.env` atual: [Garage/.env](Garage/.env)
- Idempotency: [Garage/app/infrastructure/middleware/idempotency.py](Garage/app/infrastructure/middleware/idempotency.py)

**Observações finais**
- Este documento reflete o estado observado em 28/03/2026. Algumas ações (rotacionar chaves, mover segredos, aplicar migrações) exigem credenciais externas e decisões de operação; posso ajudar a implementar qualquer passo autorizado.
