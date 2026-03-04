# 🔍 Diagnóstico Asaas - Endpoint de Configuração

## 🚨 Problema

Erro `invalid_environment` significa que **a chave API não corresponde ao ambiente da URL**.

Da documentação oficial do Asaas:

> ⚠️ **ATENÇÃO**: Para testar endpoints você precisa de chave de **Sandbox**.
> Caso seja utilizada chave de **produção**, obterá erro **401 Unauthorized**.

---

## ✅ Configurações Corretas (da documentação Asaas)

| Ambiente | URL | Chave | Descrição |
|----------|-----|-------|-----------|
| **Produção** | `https://api.asaas.com/v3` | `$aact_prod_...` | Transações reais, dinheiro real |
| **Sandbox** | `https://api-sandbox.asaas.com/v3` | `$aact_test_...` | Ambiente de testes, sem dinheiro real |

❗ **REGRA**: Chave PRODUCTION só funciona com URL de PRODUCTION
❗ **REGRA**: Chave SANDBOX só funciona com URL de SANDBOX

---

## 🛠️ Novo Endpoint de Diagnóstico

Criamos um endpoint que mostra **exatamente** o que está configurado em Render (produção):

### Local (desenvolvimento)
```bash
curl http://localhost:8000/api/diagnostic/asaas-config
```

### Produção (Render)
```bash
curl https://garage-0lw9.onrender.com/api/diagnostic/asaas-config
```

---

## 📋 Exemplo de Resposta

### ✅ Configuração Correta
```json
{
  "status": "ok",
  "asaas_api_key": {
    "type": "PRODUCTION",
    "preview": "$aact_prod_000MzkwODA2...dhMzFjMTIw",
    "length": 149
  },
  "asaas_base_url": {
    "environment": "PRODUCTION",
    "url": "https://api.asaas.com/v3"
  },
  "validation": {
    "has_mismatch": false,
    "expected": "Key type must match URL environment (both PRODUCTION or both SANDBOX)",
    "recommendation": "Configuration looks correct."
  }
}
```

### ❌ Configuração com Mismatch
```json
{
  "status": "error",
  "asaas_api_key": {
    "type": "PRODUCTION",
    "preview": "$aact_prod_000MzkwODA2...dhMzFjMTIw",
    "length": 149
  },
  "asaas_base_url": {
    "environment": "SANDBOX",
    "url": "https://api-sandbox.asaas.com/v3"
  },
  "validation": {
    "has_mismatch": true,
    "expected": "Key type must match URL environment (both PRODUCTION or both SANDBOX)",
    "recommendation": "MISMATCH DETECTED! Update Render environment variables."
  }
}
```

---

## 🔧 Como Usar para Corrigir

### Passo 1: Verificar configuração em Render

```bash
curl https://garage-0lw9.onrender.com/api/diagnostic/asaas-config
```

### Passo 2: Analisar a resposta

Se `has_mismatch: true`, há problema!

Veja:
- `asaas_api_key.type`: Mostra se a chave é PRODUCTION ou SANDBOX
- `asaas_base_url.environment`: Mostra se a URL é PRODUCTION ou SANDBOX

### Passo 3: Corrigir em Render

Vá para https://dashboard.render.com → garage-0lw9 → Environment

**Para ambiente de PRODUÇÃO:**
```
ASAAS_API_KEY = $aact_prod_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OmY1NGY5NjRiLTJhNmMtNGY0MS1hNjc1LTc5MjM3OGFlNTVkNDo6JGFhY2hfNjE0OTNjM2UtMjg3YS00ZTVmLTkzMmItOGFmNDdhMzFjMTIw
ASAAS_BASE_URL = https://api.asaas.com/v3
```

**OU para ambiente de SANDBOX (testes):**
```
ASAAS_API_KEY = $aact_test_SEU_TOKEN_AQUI
ASAAS_BASE_URL = https://api-sandbox.asaas.com/v3
```

### Passo 4: Salvar e Aguardar Deploy

- Clique **Save Changes**
- Aguarde deploy (2-5 min)
- Teste novamente: `curl https://garage-0lw9.onrender.com/api/diagnostic/asaas-config`
- `has_mismatch` deve ser `false` agora!

---

## 🎯 Checklist Final

- [ ] Executei `curl https://garage-0lw9.onrender.com/api/diagnostic/asaas-config`
- [ ] Vi qual é o `asaas_api_key.type` (PRODUCTION ou SANDBOX)
- [ ] Vi qual é o `asaas_base_url.environment` (PRODUCTION ou SANDBOX)
- [ ] Se há mismatch, corrigi em Render Environment
- [ ] Aguardei deploy completar
- [ ] Testei novamente e `has_mismatch: false`
- [ ] Tentei gerar pagamento em /account
- [ ] **SUCESSO!** ✅

---

## 🔐 Segurança

O endpoint **não expõe** a chave completa, apenas:
- Tipo (PRODUCTION vs SANDBOX)
- Preview redatado (`$aact_prod_000Mzk...dhMzFj`)
- Comprimento da chave (para validar se está completa)

Isso permite diagnosticar sem comprometer segurança.

---

## 📞 Se Ainda Não Funcionar

1. Copie a saída de `/api/diagnostic/asaas-config`
2. Compare com a chave local em `.env`
3. Verifique se o comprimento (`length`) é o mesmo
4. Se for menor, a chave pode estar truncada em Render
5. Se for diferente, pode estar usando chave errada
