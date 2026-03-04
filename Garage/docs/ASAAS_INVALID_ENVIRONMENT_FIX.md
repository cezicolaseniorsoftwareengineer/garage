# Erro: invalid_environment (Asaas 401)

## O que significa?

```
Erro: Payment gateway error: HTTPStatusError: Asaas 401:
{'errors': [{'code': 'invalid_environment', 'description': 'A chave de API informada não pertence a este ambiente'}]}
```

**Tradução:** "A chave de API informada não pertence a este ambiente"

---

## Causa Raiz

Há um **MISMATCH entre a chave API e a URL do ambiente:**

| Situação | Chave | URL | Resultado |
|----------|-------|-----|-----------|
| ✅ Correto | `$aact_prod_...` | `https://api.asaas.com/v3` | Funciona |
| ✅ Correto | `$aact_test_...` | `https://api-sandbox.asaas.com/v3` | Funciona |
| ❌ Erro | `$aact_prod_...` | `https://api-sandbox.asaas.com/v3` | **invalid_environment** |
| ❌ Erro | `$aact_test_...` | `https://api.asaas.com/v3` | **invalid_environment** |

---

## Diagnóstico Rápido

Execute:
```bash
cd Garage
python scripts/diagnose_asaas.py
```

Ele vai mostrar se há mismatch:
```
✗ CRITICAL MISMATCH!
  Key type:  PRODUCTION ($aact_prod_...)
  URL type:  SANDBOX (https://api-sandbox.asaas.com/v3)
```

---

## Como Corrigir

### Opção 1: Usar PRODUCTION (Recomendado para Garage)

**Local (seu PC):** Já está configurado assim no `.env`
```dotenv
ASAAS_API_KEY=$aact_prod_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OjBj...
ASAAS_BASE_URL=https://api.asaas.com/v3
```

**Em Render:** Configure exatamente igual
1. Vá para https://dashboard.render.com
2. Serviço **garage-0lw9** → **Environment**
3. Verifique:
   - `ASAAS_API_KEY`: Comece com `$aact_prod_` (copie do `.env` local)
   - `ASAAS_BASE_URL`: Seja exatamente `https://api.asaas.com/v3`

### Opção 2: Usar SANDBOX (Para Testes)

Se quiser testar com sandbox:

**Local:**
```dotenv
ASAAS_API_KEY=$aact_test_SEU_TOKEN_SANDBOX_HERE
ASAAS_BASE_URL=https://api-sandbox.asaas.com/v3
```

**Em Render:** Configure igual


---

## Passo-a-Passo: Corrigir em Render

### Passo 1: Verificar a chave local
```bash
# No seu terminal local:
grep "^ASAAS_API_KEY" Garage/.env
# Resultado esperado: começa com $aact_prod_ ou $aact_test_
```

### Passo 2: Copiar a chave correta
1. Abra `Garage/.env` no seu editor
2. Copie **COMPLETAMENTE** o valor de `ASAAS_API_KEY`
   - Cuidado: é um token muito longo!
   - Não omita/trunca partes!

### Passo 3: Configurar em Render
1. Acesse https://dashboard.render.com
2. Clique no serviço **garage-0lw9**
3. Menu **Environment** (no lado esquerdo)
4. Procure por `ASAAS_API_KEY`
5. **Substitua o valor completo** pela chave copiada
6. Clique **Save Changes**

### Passo 4: Também configure ASAAS_BASE_URL se não existir
1. Na mesma tela, clique **Add Environment Variable** (se não existir)
2. **Name:** `ASAAS_BASE_URL`
3. **Value:** `https://api.asaas.com/v3` (ou sandbox se aplicável)
4. Clique **Save Changes**

### Passo 5: Aguarde deploy
- Render vai fazer redeploy automático
- Aguarde status: **"Healthy"**
- Leva 2-5 minutos

### Passo 6: Teste
- Acesse https://garage-0lw9.onrender.com/account
- Tente gerar um pagamento PIX/Cartão
- Agora deve funcionar! ✅

---

## Validar Correitura Remotamente

Se tiver SSH acesso a Render, rode:
```bash
cd Garage
python scripts/diagnose_asaas.py
```

Esperado:
```
✓ API key type: PRODUCTION ($aact_prod_)
✓ ASAAS_BASE_URL set to PRODUCTION: https://api.asaas.com/v3
✓ Key and URL environment MATCH (PRODUCTION)
✓ Successfully authenticated with Asaas API
  → Account has 2 customer(s)
✓ Asaas configuration is OK
```

---

## Checklist de Correção

- [ ] Identifiquei se a chave é `$aact_prod_` ou `$aact_test_`
- [ ] Verifiquei se a URL corresponde (production ou sandbox)
- [ ] Copiei a chave **completa** do `.env` local (nada truncado)
- [ ] Configurei em Render com a chave correta
- [ ] Configurei `ASAAS_BASE_URL` se necessário
- [ ] Aguardei deploy completar (status "Healthy")
- [ ] Testei gerar um pagamento em https://garage-0lw9.onrender.com/account
- [ ] Pagamento foi criado com sucesso! ✅

---

## Dúvidas?

Se ainda não funcionar:
1. Execute `python scripts/diagnose_asaas.py` localmente
2. Copie a saída completa
3. Verifique se há `CRITICAL MISMATCH` ou `AUTHENTICATION FAILED`
4. Corrija conforme guidance acima
