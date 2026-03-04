# Configuração Asaas em Render

## Problema

Erro ao tentar gerar pagamento em produção (Render):
```
Erro: Payment gateway error: HTTPStatusError: Asaas 401:
{'errors': [{'code': 'access_token_not_found', 'description': "O cabeçalho de autenticação 'access_token' é obrigatório e não foi encontrado na requisição"}]}
```

**Causa:** A variável de ambiente `ASAAS_API_KEY` não está configurada em Render.

---

## Solução: Configurar em Render

### Passo 1: Acesse o Dashboard do Render
1. Vá para https://dashboard.render.com
2. Faça login com sua conta

### Passo 2: Selecione o Serviço Garage
1. Na lista de serviços, clique em **garage-0lw9** (ou o nome do seu serviço)
2. Você será levado à página do serviço

### Passo 3: Acesse as Variáveis de Ambiente
1. No menu esquerdo, clique em **Environment**
2. Você verá um formulário para adicionar/editar variáveis

### Passo 4: Configure ASAAS_API_KEY
Abra o arquivo `.env` local e copie o valor de `ASAAS_API_KEY`:

```dotenv
# No seu .env local:
ASAAS_API_KEY=$aact_prod_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OjBj...
```

No Render:
1. **Name:** `ASAAS_API_KEY`
2. **Value:** Cole o valor completo do token (começando com `$aact_prod_` ou `$aact_test_`)
3. Clique em **Save Changes**

### Passo 5: Aguarde o Deploy
O Render vai fazer um deploy automático com as novas variáveis. Você verá:
- Status: `Deploying...`
- Pode levar 2-5 minutos

### Passo 6: Teste a Autenticação
Acesse https://garage-0lw9.onrender.com/account e tente gerar um pagamento PIX/Card.

---

## Variáveis Adicionais (se necessário)

Se tiver erros depois de configurar `ASAAS_API_KEY`, verifique também:

| Variável | Valor | Descrição |
|----------|-------|-----------|
| `ASAAS_BASE_URL` | `https://api.asaas.com/v3` | Endpoint de produção do Asaas |
| `PRICE_MONTHLY` | `97.00` | Preço mensal em reais |
| `PRICE_ANNUAL` | `997.00` | Preço anual em reais |

---

## Verificar Variáveis Configuradas

Para ver todas as variáveis já configuradas em Render:
1. Na página do serviço, clique em **Environment** novamente
2. Procure por `ASAAS_*` para confirmar que estão lá

---

## Troubleshooting

### Erro ainda aparece depois de configurar?
- **Verificar token:** O token começa com `$aact_prod_` ou `$aact_test_`?
- **Copiar correto:** Você copiou o TOKEN COMPLETO? Alguns tokens são muito longos.
- **Deploy concluído?** Aguarde o deploy terminar (status: "Healthy")
- **Verificar console:** Vá para **Logs** no Render e procure por "Asaas 401" para ver a mensagem exata

### Sair rapidamente do erro
Se o deploy falhar imediatamente após configurar:
1. Vá em **Render > Logs** e veja a mensagem de erro
2. Se for "ASAAS_API_KEY malformed", remova se estiver vazio e clique Save
3. Se for outro erro, a chave pode estar expirada — gere uma nova no console do Asaas

---

## Validar com Script Remoto (Opcional)

Se tiver SSH acesso ao Render, pode rodar:
```bash
python Garage/scripts/diagnose_asaas.py
```

Isso vai validar se o token está funcionando diretamente lá.
