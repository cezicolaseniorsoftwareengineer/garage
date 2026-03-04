# CORREÇÃO - Domínio garage.onrender.com

## PROBLEMA
O domínio `garage.onrender.com` está apontando para um **serviço Django antigo** (não relacionado ao Garage).

**Serviço correto:** `garage-0lw9.onrender.com` ✅ (FastAPI + Python 3.13 + PostgreSQL)

---

## SOLUÇÃO 1 - Redirecionar domínio (RECOMENDADO)

1. Acesse [render.com](https://render.com) → Dashboard
2. Localize o serviço **`garage-0lw9`** (Python Web Service)
3. Vá em **Settings** → **Custom Domains**
4. Adicione domínio customizado: `garage.onrender.com`
5. Salve e aguarde propagação (1-2 minutos)

---

## SOLUÇÃO 2 - Deletar serviço antigo

1. Identifique qual serviço está usando `garage.onrender.com`
   - Vá em Dashboard → procure por um serviço com Python 3.7 ou Django
2. Entre no serviço antigo
3. Settings → Pause ou Delete

---

## SOLUÇÃO 3 - Atualizar links (temporária)

Enquanto não resolve o domínio, atualize os links:

### No .env (local):
```env
APP_BASE_URL=https://garage-0lw9.onrender.com
```

### No Render (serviço garage-0lw9):
Environment → `APP_BASE_URL` → `https://garage-0lw9.onrender.com`

### Na landing page:
- Todos os botões "JOGAR AGORA" → `https://garage-0lw9.onrender.com/jogo`
- E-mails de boas-vindas vão usar o link correto automaticamente

---

## VERIFICAÇÃO

Após a correção, teste:

```bash
curl -I https://garage.onrender.com/health
```

Deve retornar:
```json
{
  "status": "ok",
  "persistence": "PostgreSQL",
  "database": "Neon Serverless",
  "challenges_loaded": 75
}
```

Se retornar erro 404 do Django = domínio ainda no serviço errado.

---

## Contatos de emergência

- Render Support: https://render.com/docs/support
- Discord Render: https://discord.gg/render

---

**ATENÇÃO:** Enquanto não corrigir, use `garage-0lw9.onrender.com` em todos os links e comunicações.
