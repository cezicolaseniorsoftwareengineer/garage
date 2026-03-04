# 🔐 SECURITY POLICY — GARAGE PROJECT

## Critical: Never Expose Secrets

This repository contains production code for 404 Garage. **SENSITIVE DATA MUST NEVER BE COMMITTED.**

---

## What Is Sensitive?

### 🚨 NEVER Commit These

| Data Type | Examples | Action |
|-----------|----------|--------|
| **API Keys** | OpenAI, Groq, OpenRouter, Resend, Anthropic | Use `.env`, keep private |
| **Database Credentials** | PostgreSQL passwords, connection URIs | Use `.env`, keep private |
| **Signing Secrets** | JWT_SECRET_KEY, JAVA_RUNNER_SECRET | Use `.env`, rotate regularly |
| **Payment Gateway Keys** | Asaas API keys (`$aact_prod_...`, `$aact_test_...`) | Use `.env`, must be production-only |
| **SMTP/Email Passwords** | Gmail password, SendGrid API keys | Use `.env`, keep private |
| **Admin Credentials** | ADMIN_PASSWORD, ADMIN_USERNAME | Use `.env`, never hardcode |

### ✅ Safe to Commit

- Code (Python, JavaScript, Java, HTML, CSS)
- Configuration templates (`.env.example`)
- Documentation (with placeholder examples)
- Architecture diagrams
- Public API documentation

---

## How to Protect Secrets

### 1. **Use `.env` File (Local Development)**

```bash
# Copy template
cp Garage/.env.example Garage/.env

# Edit with real values
nano Garage/.env
# or
code Garage/.env
```

**NEVER commit `.env`** — it's in `.gitignore` by default.

### 2. **Use Render Environment Variables (Production)**

For production on Render.com:

1. Go to https://dashboard.render.com
2. Select service (garage-0lw9)
3. Menu: **Environment**
4. Add each secret:
   - `ASAAS_API_KEY`
   - `DATABASE_URL`
   - `JWT_SECRET_KEY`
   - `OPENAI_API_KEY`
   - etc.

**NEVER paste secrets in code or commit messages.**

### 3. **Generate Strong Secrets**

```bash
# Generate JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate random password
python -c "import secrets; print(secrets.token_hex(16))"
```

---

## Pre-Commit Checklist

Before `git commit`:

```bash
# 1. Never add .env files
git status  # Check: .env should NOT be listed

# 2. Review all changes
git diff    # Search for: sk-, gsk_, $aact_, password=, key=

# 3. Check staged files
git diff --cached  # Final verification before commit

# 4. Commit message MUST NOT contain secrets
git commit -m "feat: add payment feature"  # ✅ OK
git commit -m "feat: add payment with key sk-xxx"  # ❌ NEVER

# 5. Push safely
git push origin main
```

---

## If You Accidentally Exposed Secrets

### 🚨 Immediate Actions

1. **Revoke the secret immediately**:
   - API keys: Regenerate in provider dashboard (OpenAI, Groq, etc.)
   - Database password: Change in Neon dashboard
   - JWT secret: Regenerate and redeploy

2. **Remove from Git history** (if committed before gitignore):
   ```bash
   # Option 1: If not yet pushed to main
   git reset HEAD~1  # Undo last commit
   git add -A
   git commit -m "fix: remove accidental secrets"
   git push origin main

   # Option 2: If already pushed (use git filter-branch or BFG)
   # Ask CeziCola agent to run security cleanup
   ```

3. **Audit commits**:
   ```bash
   git log --all --oneline -- .env
   git log --oneline | grep -i "key\|secret\|password"
   ```

---

## Verification Checklist

For every production deployment:

- [ ] No `.env` file in git: `git ls-files | grep .env` should be empty
- [ ] `.env.example` exists with placeholders only
- [ ] `.gitignore` includes `.env`, `.env.local`, `*.pem`, `*.key`
- [ ] Last 20 commits have zero API keys: `git log --oneline | head -20` (inspect manually)
- [ ] Render environment variables verified: https://dashboard.render.com → Environment
- [ ] Database password is NOT the default
- [ ] JWT_SECRET_KEY is randomly generated (40+ chars)

---

## Tools for Secret Detection

### Manual Check

```bash
# Find any "sk-" patterns (OpenAI, Anthropic, OpenRouter)
git log -p | grep -i "sk-"

# Find any database URIs with passwords
git log -p | grep -i "postgresql://"

# Find any "$aact" patterns (Asaas)
git log -p | grep "\$aact"
```

### Automated Tools (Optional)

```bash
# Install git-secrets (prevents commits with secrets)
# https://github.com/awslabs/git-secrets

# macOS
brew install git-secrets

# Linux
git clone https://github.com/awslabs/git-secrets.git
cd git-secrets && make install

# Configure for this repo
git secrets --install
git secrets --register-aws  # Or add custom patterns
```

---

## Policy Enforcement

This repository MUST follow these rules:

1. **`.env` must be in `.gitignore`** (verified on every push)
2. **Render environment variables are the source of truth** for production
3. **Any exposed secret** triggers immediate revocation and redeployment
4. **Audit trail** of all secret rotations in wiki/docs (without values)
5. **Code review**: All PRs checked for secret patterns before merge

---

## Contact & Escalation

If you discover exposed secrets:

1. **Do not push further changes**
2. **Notify immediately**: cezicolatecnologia@gmail.com
3. **Revoke secrets** from provider dashboard
4. **Create a private security issue** on GitHub (if available)

---

## References

- [.gitignore rules](../../.gitignore)
- [.env.example template](../.env.example)
- [OWASP Secret Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)

---

**Last Updated**: March 4, 2026
**Status**: ✅ Active & Enforced
